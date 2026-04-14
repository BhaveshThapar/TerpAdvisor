#!/usr/bin/env python3
"""
Seed TerpAdvisor with the real UMD catalog + PlanetTerp data.

Source of truth:
  - umd.io  -> full course catalog, credits, descriptions, gen_ed tags
  - PlanetTerp -> avg_gpa, professors, review text

Usage:
    cd backend
    python scripts/seed_real_data.py                # upsert-only, idempotent
    python scripts/seed_real_data.py --wipe         # wipe tables first
    python scripts/seed_real_data.py --depts INST CMSC MATH    # limit depts

Writes to whatever DATABASE_URL_SYNC points at. Safe against both
Postgres (prod Neon) and SQLite (preflight).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, SyncSession, sync_engine  # noqa: E402
from app.models import Course, Professor, Review, Section  # noqa: E402

UMD_IO = "https://api.umd.io/v1"
PLANETTERP = "https://planetterp.com/api/v1"

PT_RATE_SECONDS = 0.4
UMD_RATE_SECONDS = 0.15
COMMIT_EVERY = 50


def _norm_course_id(raw: str | None) -> str:
    return (raw or "").upper().replace(" ", "")


def _slug_for(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace(".", "").replace(",", "")


def _flatten_gen_ed(gen_ed: list) -> list[str]:
    if not gen_ed:
        return []
    codes: set[str] = set()
    for group in gen_ed:
        if isinstance(group, list):
            for c in group:
                if isinstance(c, str) and c.strip():
                    codes.add(c.strip().upper())
        elif isinstance(group, str) and group.strip():
            codes.add(group.strip().upper())
    return sorted(codes)


def _coerce_credits(value) -> int:
    try:
        return int(str(value).split("-")[0])
    except (ValueError, TypeError, AttributeError):
        return 3


def fetch_departments(client: httpx.Client) -> list[str]:
    resp = client.get(f"{UMD_IO}/courses/departments")
    resp.raise_for_status()
    return [d["dept_id"] for d in resp.json() if d.get("dept_id")]


def fetch_dept_courses(client: httpx.Client, dept: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        try:
            r = client.get(
                f"{UMD_IO}/courses",
                params={"dept_id": dept, "per_page": 100, "page": page},
            )
        except httpx.HTTPError as e:
            print(f"  [umd.io] {dept} page {page} error: {e}")
            break
        time.sleep(UMD_RATE_SECONDS)
        if r.status_code == 404:
            break
        if r.status_code != 200:
            print(f"  [umd.io] {dept} page {page} HTTP {r.status_code}")
            break
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def fetch_planetterp_course(client: httpx.Client, course_id: str) -> dict | None:
    try:
        r = client.get(
            f"{PLANETTERP}/course",
            params={"name": course_id, "reviews": "true"},
        )
    except httpx.HTTPError as e:
        print(f"  [planetterp] {course_id} error: {e}")
        return None
    time.sleep(PT_RATE_SECONDS)
    if r.status_code != 200:
        return None
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        return None
    return data if isinstance(data, dict) else None


def wipe_all(session) -> None:
    print("Wiping reviews, sections, professors, courses...")
    session.execute(delete(Review))
    session.execute(delete(Section))
    session.execute(delete(Professor))
    session.execute(delete(Course))
    session.commit()


def upsert_course(session, raw: dict) -> str | None:
    cid = _norm_course_id(raw.get("course_id"))
    if not cid:
        return None
    dept = raw.get("dept_id") or "".join(ch for ch in cid if ch.isalpha())
    gen_eds = _flatten_gen_ed(raw.get("gen_ed") or [])
    credits = _coerce_credits(raw.get("credits"))
    description = raw.get("description")
    name = raw.get("name") or cid
    relationships = raw.get("relationships") or {}

    existing = session.execute(
        select(Course).where(Course.course_id == cid)
    ).scalar_one_or_none()
    if existing:
        existing.name = name
        existing.department = dept
        existing.credits = credits
        existing.description = description or existing.description
        if gen_eds:
            existing.gen_eds = gen_eds
        if relationships:
            existing.prerequisites_raw = relationships
    else:
        session.add(
            Course(
                course_id=cid,
                name=name,
                department=dept,
                credits=credits,
                description=description,
                gen_eds=gen_eds or None,
                prerequisites_raw=relationships or None,
            )
        )
    return cid


def upsert_professor(session, prof_cache: dict[str, Professor], name: str) -> Professor | None:
    if not name:
        return None
    slug = _slug_for(name)
    if not slug:
        return None
    if slug in prof_cache:
        return prof_cache[slug]
    existing = session.execute(
        select(Professor).where(Professor.slug == slug)
    ).scalar_one_or_none()
    if existing is None:
        existing = Professor(name=name, slug=slug, review_count=0, courses_taught=[])
        session.add(existing)
        session.flush()
    prof_cache[slug] = existing
    return existing


def apply_planetterp_data(
    session, course: Course, pt: dict, prof_cache: dict[str, Professor]
) -> tuple[int, int]:
    if pt.get("average_gpa") is not None:
        try:
            course.avg_gpa = float(pt["average_gpa"])
        except (TypeError, ValueError):
            pass

    profs_added = 0
    reviews_added = 0

    seen_prof_slugs: set[str] = set()
    for prof_name in (pt.get("professors") or []):
        prof = upsert_professor(session, prof_cache, prof_name)
        if prof is None:
            continue
        seen_prof_slugs.add(prof.slug)
        taught = list(prof.courses_taught or [])
        if course.course_id not in taught:
            taught.append(course.course_id)
            prof.courses_taught = taught
            profs_added += 1

    for rev in (pt.get("reviews") or []):
        rating = rev.get("rating")
        text = rev.get("review")
        if rating is None:
            continue
        try:
            rating_int = int(rating)
        except (ValueError, TypeError):
            continue
        prof_id = None
        prof_name = rev.get("professor")
        if prof_name:
            prof = upsert_professor(session, prof_cache, prof_name)
            if prof is not None:
                prof_id = prof.id
                prof.review_count = (prof.review_count or 0) + 1
        session.add(
            Review(
                course_id=course.course_id,
                professor_id=prof_id,
                rating=rating_int,
                text=text,
                source="planetterp",
            )
        )
        reviews_added += 1

    return profs_added, reviews_added


def recompute_prof_avg_rating(session) -> None:
    profs = session.execute(select(Professor)).scalars().all()
    for prof in profs:
        revs = session.execute(
            select(Review.rating).where(Review.professor_id == prof.id)
        ).scalars().all()
        if revs:
            prof.avg_rating = sum(revs) / len(revs)
            prof.review_count = len(revs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="Wipe tables before ingest")
    parser.add_argument("--depts", nargs="*", help="Limit to specific department codes")
    parser.add_argument("--skip-planetterp", action="store_true", help="Skip PlanetTerp enrichment")
    parser.add_argument("--limit", type=int, default=None, help="Cap total courses processed")
    args = parser.parse_args()

    print("=" * 60)
    print("TerpAdvisor — Real Data Seed")
    print("=" * 60)
    print(f"DB: {sync_engine.url}")

    Base.metadata.create_all(sync_engine)

    client = httpx.Client(timeout=60.0, headers={"User-Agent": "TerpAdvisor-Seed/1.0"})

    with SyncSession() as session:
        if args.wipe:
            wipe_all(session)

    # Step 1 — pull catalog from umd.io
    if args.depts:
        depts = [d.upper() for d in args.depts]
        print(f"\n[1/3] Fetching catalog for depts: {', '.join(depts)}")
    else:
        print("\n[1/3] Fetching department list from umd.io...")
        depts = fetch_departments(client)
        print(f"      {len(depts)} departments")

    raw_courses: list[dict] = []
    for i, dept in enumerate(depts, 1):
        batch = fetch_dept_courses(client, dept)
        if batch:
            raw_courses.extend(batch)
        if i % 20 == 0 or i == len(depts):
            print(f"      {i}/{len(depts)} depts fetched; {len(raw_courses)} courses so far")

    if args.limit:
        raw_courses = raw_courses[: args.limit]

    print(f"      Total courses from umd.io: {len(raw_courses)}")

    # Upsert courses
    print("\n[2/3] Upserting courses...")
    courses_upserted = 0
    with SyncSession() as session:
        for i, raw in enumerate(raw_courses, 1):
            try:
                cid = upsert_course(session, raw)
                if cid:
                    courses_upserted += 1
            except Exception as e:
                print(f"      [upsert] {raw.get('course_id')}: {e}")
                session.rollback()
                continue
            if i % COMMIT_EVERY == 0:
                session.commit()
                print(f"      {i}/{len(raw_courses)} courses upserted")
        session.commit()
    print(f"      {courses_upserted} courses upserted")

    if args.skip_planetterp:
        print("\n[3/3] --skip-planetterp set, done.")
        return 0

    # Step 2 — enrich with PlanetTerp
    print("\n[3/3] Enriching with PlanetTerp (GPA + professors + reviews)...")
    course_ids_to_enrich = [_norm_course_id(c.get("course_id")) for c in raw_courses]
    course_ids_to_enrich = [c for c in course_ids_to_enrich if c]

    total = len(course_ids_to_enrich)
    gpa_set = 0
    reviews_added = 0
    profs_linked = 0
    errors = 0
    prof_cache: dict[str, Professor] = {}

    with SyncSession() as session:
        for i, cid in enumerate(course_ids_to_enrich, 1):
            try:
                pt = fetch_planetterp_course(client, cid)
                if not pt:
                    continue
                with session.no_autoflush:
                    course = session.execute(
                        select(Course).where(Course.course_id == cid)
                    ).scalar_one_or_none()
                    if course is None:
                        continue
                    before_gpa = course.avg_gpa
                    p_added, r_added = apply_planetterp_data(session, course, pt, prof_cache)
                session.flush()
                if course.avg_gpa is not None and before_gpa != course.avg_gpa:
                    gpa_set += 1
                profs_linked += p_added
                reviews_added += r_added
            except Exception as e:
                errors += 1
                print(f"      [planetterp] {cid}: {e}")
                session.rollback()
                prof_cache.clear()
                continue

            if i % COMMIT_EVERY == 0:
                try:
                    session.commit()
                except Exception as e:
                    print(f"      [commit batch] {e}")
                    session.rollback()
                prof_cache.clear()
                print(
                    f"      {i}/{total} enriched | gpa={gpa_set} reviews={reviews_added} prof_links={profs_linked} err={errors}"
                )

        try:
            session.commit()
        except Exception as e:
            print(f"      [final commit] {e}")
            session.rollback()

        print("\n  Recomputing professor avg_rating from reviews...")
        recompute_prof_avg_rating(session)
        session.commit()

    print("\n" + "=" * 60)
    print(f"Done. courses={courses_upserted} gpa_set={gpa_set} "
          f"reviews={reviews_added} prof_links={profs_linked} errors={errors}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
