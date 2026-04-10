#!/usr/bin/env python3
"""
Seed the database with real UMD course data from PlanetTerp API.

Usage:
    cd backend
    python scripts/seed_data.py

Fetches ~50 CS/MATH/STAT courses, their professors, reviews, and
creates demo section data so the app has real content without running
the full Celery ETL pipeline.
"""

import sys
import time as time_module
from datetime import time
from pathlib import Path

import httpx
from sqlalchemy import select

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SyncSession, sync_engine, Base
from app.models import Course, Professor, Review, Section

API_BASE = "https://planetterp.com/api/v1"
client = httpx.Client(timeout=30.0)

# Rate limit: ~2 requests/sec to be polite
def _rate_limit():
    time_module.sleep(0.5)


def fetch_courses(departments: list[str]) -> list[dict]:
    """Fetch courses for given departments from PlanetTerp."""
    all_courses = []
    for dept in departments:
        print(f"  Fetching {dept} courses...")
        try:
            resp = client.get(f"{API_BASE}/courses", params={"department": dept})
            _rate_limit()
            if resp.status_code == 200:
                courses = resp.json()
                all_courses.extend(courses)
                print(f"    Found {len(courses)} courses")
            else:
                print(f"    Failed: HTTP {resp.status_code}")
        except Exception as e:
            print(f"    Error: {e}")
    return all_courses


def fetch_professor(name: str) -> dict | None:
    """Fetch professor details from PlanetTerp."""
    try:
        resp = client.get(f"{API_BASE}/professor", params={"name": name})
        _rate_limit()
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def fetch_reviews(course_name: str, limit: int = 20) -> list[dict]:
    """Fetch reviews for a course from PlanetTerp."""
    try:
        resp = client.get(
            f"{API_BASE}/course",
            params={"name": course_name, "reviews": "true"},
        )
        _rate_limit()
        if resp.status_code == 200:
            data = resp.json()
            return (data.get("reviews") or [])[:limit]
    except Exception:
        pass
    return []


def seed_courses(session, raw_courses: list[dict]) -> int:
    """Insert courses into DB. Returns count of courses added."""
    count = 0
    for c in raw_courses:
        course_id = (c.get("name") or "").upper().replace(" ", "")
        if not course_id:
            continue

        existing = session.execute(
            select(Course).where(Course.course_id == course_id)
        ).scalar_one_or_none()
        if existing:
            existing.avg_gpa = c.get("average_gpa") or existing.avg_gpa
            continue

        dept = c.get("department", "")
        if not dept:
            dept = "".join(ch for ch in course_id if ch.isalpha())

        course = Course(
            course_id=course_id,
            name=c.get("title") or course_id,
            department=dept,
            credits=c.get("credits") or 3,
            avg_gpa=c.get("average_gpa"),
        )
        session.add(course)
        count += 1
    return count


def seed_professors(session, raw_courses: list[dict]) -> int:
    """Fetch and insert professors mentioned in courses."""
    seen_slugs = set()
    count = 0

    # Collect unique professor names from courses
    prof_names = set()
    for c in raw_courses:
        for name in c.get("professors") or []:
            prof_names.add(name)

    # Limit to most relevant (first 40)
    for name in list(prof_names)[:40]:
        slug = name.lower().replace(" ", "_").replace(".", "")
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        existing = session.execute(
            select(Professor).where(Professor.slug == slug)
        ).scalar_one_or_none()
        if existing:
            continue

        data = fetch_professor(name)
        if data:
            prof = Professor(
                name=name,
                slug=slug,
                avg_rating=data.get("average_rating"),
                review_count=len(data.get("reviews") or []),
                courses_taught=data.get("courses", []),
            )
        else:
            prof = Professor(name=name, slug=slug, review_count=0)

        session.add(prof)
        count += 1

        # Commit periodically
        if count % 10 == 0:
            session.commit()
            print(f"    {count} professors so far...")

    return count


def seed_reviews(session, course_ids: list[str]) -> int:
    """Fetch and insert reviews for key courses."""
    count = 0
    # Only fetch reviews for a subset of important courses
    key_courses = [c for c in course_ids if any(
        c.startswith(p) for p in ["CMSC1", "CMSC2", "CMSC3", "CMSC4", "MATH1", "MATH2", "STAT4"]
    )][:25]

    for course_id in key_courses:
        reviews = fetch_reviews(course_id)
        for rev in reviews:
            rating = rev.get("rating")
            if rating is None:
                continue

            # Link to professor if exists
            prof_id = None
            prof_name = rev.get("professor")
            if prof_name:
                slug = prof_name.lower().replace(" ", "_").replace(".", "")
                prof = session.execute(
                    select(Professor).where(Professor.slug == slug)
                ).scalar_one_or_none()
                if prof:
                    prof_id = prof.id

            review = Review(
                course_id=course_id,
                professor_id=prof_id,
                rating=int(rating),
                text=rev.get("review"),
                source="planetterp",
            )
            session.add(review)
            count += 1

        if reviews:
            session.commit()

    return count


def seed_fallback_courses(session) -> int:
    """Insert hardcoded courses that are universally required but may be absent
    from the PlanetTerp API response (e.g. writing-intensive GenEds, INST/BSCI intros)."""
    fallback = [
        # ENGL
        {"course_id": "ENGL101", "name": "Academic Writing", "department": "ENGL", "credits": 3, "avg_gpa": 3.3},
        {"course_id": "ENGL393", "name": "Technical Writing", "department": "ENGL", "credits": 3, "avg_gpa": 3.4},
        # AASP / General GenEd
        {"course_id": "AASP100", "name": "Introduction to African American Studies", "department": "AASP", "credits": 3, "avg_gpa": 3.2},
        # INST
        {"course_id": "INST126", "name": "Introduction to Information Science", "department": "INST", "credits": 3, "avg_gpa": 3.1},
        {"course_id": "INST201", "name": "Object-Oriented Programming for Information Science", "department": "INST", "credits": 3, "avg_gpa": 3.0},
        {"course_id": "INST311", "name": "Information Organization", "department": "INST", "credits": 3, "avg_gpa": 3.2},
        {"course_id": "INST314", "name": "Data Science for Information Science", "department": "INST", "credits": 3, "avg_gpa": 3.1},
        {"course_id": "INST327", "name": "Information Privacy", "department": "INST", "credits": 3, "avg_gpa": 3.3},
        {"course_id": "INST335", "name": "Information Policy", "department": "INST", "credits": 3, "avg_gpa": 3.2},
        {"course_id": "INST346", "name": "Technologies for Information Services", "department": "INST", "credits": 3, "avg_gpa": 3.1},
        {"course_id": "INST352", "name": "Human-Computer Interaction", "department": "INST", "credits": 3, "avg_gpa": 3.2},
        {"course_id": "INST354", "name": "Decision-Making for Information Science", "department": "INST", "credits": 3, "avg_gpa": 3.0},
        {"course_id": "INST362", "name": "Information Architecture", "department": "INST", "credits": 3, "avg_gpa": 3.1},
        {"course_id": "INST377", "name": "Dynamic Web Applications", "department": "INST", "credits": 3, "avg_gpa": 3.0},
        {"course_id": "INST408", "name": "Special Topics in Information Science", "department": "INST", "credits": 3, "avg_gpa": 3.2},
        {"course_id": "INST414", "name": "Data Science Techniques", "department": "INST", "credits": 3, "avg_gpa": 3.0},
        {"course_id": "INST447", "name": "Data Analytics", "department": "INST", "credits": 3, "avg_gpa": 3.1},
        {"course_id": "INST462", "name": "User Experience Research", "department": "INST", "credits": 3, "avg_gpa": 3.2},
        {"course_id": "INST466", "name": "Information Systems Design", "department": "INST", "credits": 3, "avg_gpa": 3.1},
        {"course_id": "INST490", "name": "Capstone in Information Science", "department": "INST", "credits": 3, "avg_gpa": 3.3},
        # BSCI
        {"course_id": "BSCI105", "name": "Principles of Biology I", "department": "BSCI", "credits": 3, "avg_gpa": 2.8},
        {"course_id": "BSCI106", "name": "Principles of Biology II", "department": "BSCI", "credits": 3, "avg_gpa": 2.7},
        {"course_id": "BSCI207", "name": "Principles of Biology III", "department": "BSCI", "credits": 3, "avg_gpa": 2.9},
        {"course_id": "BSCI222", "name": "Principles of Genetics", "department": "BSCI", "credits": 3, "avg_gpa": 2.8},
        {"course_id": "BSCI330", "name": "Cell Biology and Physiology", "department": "BSCI", "credits": 3, "avg_gpa": 2.9},
        # CHEM
        {"course_id": "CHEM131", "name": "General Chemistry I", "department": "CHEM", "credits": 3, "avg_gpa": 2.5},
        {"course_id": "CHEM132", "name": "General Chemistry II", "department": "CHEM", "credits": 3, "avg_gpa": 2.4},
        {"course_id": "CHEM241", "name": "Organic Chemistry I", "department": "CHEM", "credits": 3, "avg_gpa": 2.6},
        {"course_id": "CHEM242", "name": "Organic Chemistry II", "department": "CHEM", "credits": 3, "avg_gpa": 2.5},
        # PHYS
        {"course_id": "PHYS141", "name": "General Physics: Mechanics and Particle Dynamics", "department": "PHYS", "credits": 3, "avg_gpa": 2.7},
        {"course_id": "PHYS142", "name": "General Physics: Vibrations, Waves, Heat, Electricity, and Magnetism", "department": "PHYS", "credits": 3, "avg_gpa": 2.6},
        # STAT
        {"course_id": "STAT100", "name": "Elementary Statistics and Probability", "department": "STAT", "credits": 3, "avg_gpa": 3.1},
        {"course_id": "STAT401", "name": "Applied Probability and Statistics II", "department": "STAT", "credits": 3, "avg_gpa": 3.0},
        # ECON
        {"course_id": "ECON200", "name": "Principles of Micro-Economics", "department": "ECON", "credits": 3, "avg_gpa": 2.9},
        {"course_id": "ECON201", "name": "Principles of Macro-Economics", "department": "ECON", "credits": 3, "avg_gpa": 3.0},
        # MATH extras
        {"course_id": "MATH115", "name": "Precalculus", "department": "MATH", "credits": 3, "avg_gpa": 2.9},
        {"course_id": "MATH246", "name": "Differential Equations for Scientists and Engineers", "department": "MATH", "credits": 3, "avg_gpa": 3.0},
        {"course_id": "MATH310", "name": "Introduction to Mathematical Proof", "department": "MATH", "credits": 3, "avg_gpa": 3.1},
    ]

    count = 0
    for entry in fallback:
        existing = session.execute(
            select(Course).where(Course.course_id == entry["course_id"])
        ).scalar_one_or_none()
        if existing:
            # Update avg_gpa only if it's missing
            if existing.avg_gpa is None and entry.get("avg_gpa") is not None:
                existing.avg_gpa = entry["avg_gpa"]
            continue
        course = Course(
            course_id=entry["course_id"],
            name=entry["name"],
            department=entry["department"],
            credits=entry["credits"],
            avg_gpa=entry.get("avg_gpa"),
        )
        session.add(course)
        count += 1

    return count


def seed_demo_sections(session, course_ids: list[str]) -> int:
    """Create realistic section data for key courses.

    Since umd.io may be unavailable, we generate plausible sections
    so the schedule solver has data to work with.
    """
    count = 0
    time_slots = [
        ("MWF", time(9, 0), time(9, 50)),
        ("MWF", time(10, 0), time(10, 50)),
        ("MWF", time(11, 0), time(11, 50)),
        ("MWF", time(13, 0), time(13, 50)),
        ("MWF", time(14, 0), time(14, 50)),
        ("TuTh", time(9, 30), time(10, 45)),
        ("TuTh", time(11, 0), time(12, 15)),
        ("TuTh", time(14, 0), time(15, 15)),
        ("TuTh", time(15, 30), time(16, 45)),
    ]

    _SECTION_DEPTS = {"CMSC", "MATH", "STAT", "INST", "BSCI", "CHEM", "PHYS", "ECON", "ENGL"}
    key_courses = [c for c in course_ids if any(c.startswith(d) for d in _SECTION_DEPTS)]

    for course_id in key_courses:
        # Each course gets 2-3 sections
        num_sections = 2 if course_id > "CMSC400" else 3
        for i in range(num_sections):
            slot_idx = (hash(course_id) + i) % len(time_slots)
            days, start, end = time_slots[slot_idx]
            section_id = f"{course_id}-{i+1:04d}"

            existing = session.execute(
                select(Section).where(Section.section_id == section_id)
            ).scalar_one_or_none()
            if existing:
                continue

            section = Section(
                section_id=section_id,
                course_id=course_id,
                semester="202508",
                days=days,
                start_time=start,
                end_time=end,
                total_seats=40,
                open_seats=max(5, 40 - (hash(course_id + str(i)) % 35)),
                waitlist=0,
            )
            session.add(section)
            count += 1

    return count


def main():
    print("=" * 60)
    print("TerpAdvisor — Seed Data Script")
    print("=" * 60)

    # Create tables if they don't exist
    print("\n1. Ensuring database tables exist...")
    Base.metadata.create_all(sync_engine)
    print("   Done.")

    departments = ["CMSC", "MATH", "STAT", "ENGL", "INST", "BSCI", "CHEM", "ECON"]

    print(f"\n2. Fetching courses from PlanetTerp ({', '.join(departments)})...")
    raw_courses = fetch_courses(departments)
    print(f"   Total: {len(raw_courses)} courses fetched")

    with SyncSession() as session:
        print("\n3. Inserting courses...")
        n = seed_courses(session, raw_courses)
        session.commit()
        print(f"   {n} new courses added")

        print("\n3b. Inserting fallback courses (GenEd, INST, BSCI, CHEM, etc.)...")
        n = seed_fallback_courses(session)
        session.commit()
        print(f"   {n} fallback courses added")

        # Collect all course IDs now in DB
        all_ids = [
            row[0] for row in session.execute(select(Course.course_id)).all()
        ]

        print(f"\n4. Fetching and inserting professors...")
        n = seed_professors(session, raw_courses)
        session.commit()
        print(f"   {n} new professors added")

        print(f"\n5. Fetching and inserting reviews...")
        n = seed_reviews(session, all_ids)
        session.commit()
        print(f"   {n} reviews added")

        print(f"\n6. Creating demo sections...")
        n = seed_demo_sections(session, all_ids)
        session.commit()
        print(f"   {n} sections created")

    print("\n" + "=" * 60)
    print("Seed complete! The database is ready.")
    print("=" * 60)


if __name__ == "__main__":
    main()
