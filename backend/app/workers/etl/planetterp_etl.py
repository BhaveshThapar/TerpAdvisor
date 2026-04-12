"""
PlanetTerp ETL pipeline.

Extract: Fetch course, grade, and professor data from PlanetTerp API
Transform: Normalize course IDs, compute aggregate stats, merge duplicates
Load: Upsert into PostgreSQL, invalidate affected cache keys
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.session import SyncSession
from app.models import Course, Professor, Review

logger = logging.getLogger(__name__)

_last_sync: dict[str, datetime] = {}


class PlanetTerpETL:
    """ETL pipeline for PlanetTerp data."""

    def __init__(self):
        self.base_url = settings.planetterp_base_url
        self.client = httpx.Client(timeout=30.0)

    def sync_all_courses(self) -> dict:
        """Full sync — fetch all courses from PlanetTerp by department to get full catalog."""
        logger.info("PlanetTerp full sync: fetching courses by department")
        courses_synced = 0
        errors = 0

        # All UMD department prefixes — same list used in courses.py
        all_depts = [
            "AASP", "AAST", "AGNR", "AMSC", "AMST", "ANSC", "ANTH", "AOSC", "ARAB",
            "ARCH", "AREC", "ARHU", "ARMY", "ARSC", "ARTH", "ARTT", "ASTR", "BCHM",
            "BIOE", "BIOL", "BIOM", "BIPH", "BMGT", "BSCI", "BSCV", "BSOS", "BSST",
            "BUAC", "BUDT", "BUFN", "BULM", "BUMK", "BUMO", "BUSI", "BUSM", "CCJS",
            "CHBE", "CHEM", "CHIN", "CHPH", "CINE", "CLAS", "CLFS", "CMLT", "CMSC",
            "COMM", "CPMS", "CPSD", "CPSP", "DANC", "ECON", "EDCI", "EDCP", "EDHD",
            "EDHI", "EDMS", "EDPS", "EDSP", "EDUC", "ENAE", "ENCE", "ENCH", "ENCO",
            "ENEE", "ENES", "ENFP", "ENGL", "ENMA", "ENME", "ENPM", "ENPP", "ENRE",
            "ENSE", "ENSP", "ENST", "ENTM", "EPIB", "FGSM", "FILM", "FIRE", "FMSC",
            "FOLA", "FREN", "GEMS", "GEOG", "GEOL", "GERM", "GREK", "GVPT", "HACS",
            "HDCC", "HEBR", "HEIP", "HESP", "HHUM", "HISP", "HIST", "HLSA", "HLSC",
            "HLTH", "HONR", "IDEA", "IMDM", "IMMR", "INAG", "INFM", "INST", "ISRL",
            "ITAL", "JAPN", "JOUR", "JWST", "KINE", "KNES", "KORA", "LACS", "LARC",
            "LATN", "LBSC", "LING", "MATH", "MEES", "MIEH", "MITH", "MLSC", "MSML",
            "MUSC", "NACS", "NAVY", "NFSC", "PERS", "PHIL", "PHPE", "PHSC", "PHYS",
            "PLCY", "PLSC", "PORT", "PSYC", "PUAF", "RDEV", "RELS", "RUSS", "SLAA",
            "SLLC", "SOCY", "SPAN", "SPHL", "STAT", "SURV", "TDPS", "THET", "TLPL",
            "TLTC", "UMEI", "UNIV", "URSP", "USLT", "VMSC", "WMST",
        ]

        for dept in all_depts:
            try:
                response = self.client.get(
                    f"{self.base_url}/courses", params={"department": dept}
                )
                if response.status_code != 200:
                    continue
                for course in response.json():
                    try:
                        with SyncSession() as session:
                            self._process_course(session, course)
                            session.commit()
                        courses_synced += 1
                    except Exception as e:
                        logger.warning(f"Error processing course {course.get('name', '?')}: {e}")
                        errors += 1
            except httpx.HTTPError as e:
                logger.warning(f"HTTP error fetching dept {dept}: {e}")
                errors += 1

        _last_sync["full"] = datetime.now(timezone.utc)
        return {"courses_synced": courses_synced, "errors": errors}

    def sync_incremental(self) -> dict:
        """Incremental sync — only fetch courses updated since last sync."""
        last = _last_sync.get("incremental") or _last_sync.get("full")
        if last is None:
            logger.info("No previous sync found, running full sync instead")
            result = self.sync_all_courses()
            return {"updated": result["courses_synced"], "errors": result["errors"]}

        logger.info(f"PlanetTerp incremental sync since {last.isoformat()}")
        updated = 0
        popular_depts = ["CMSC", "MATH", "STAT", "PHYS", "ECON"]
        with SyncSession() as session:
            for dept in popular_depts:
                try:
                    response = self.client.get(
                        f"{self.base_url}/courses", params={"department": dept}
                    )
                    if response.status_code == 200:
                        for course in response.json():
                            self._process_course(session, course)
                            updated += 1
                except Exception as e:
                    logger.warning(f"Error syncing department {dept}: {e}")
            session.commit()

        _last_sync["incremental"] = datetime.now(timezone.utc)
        return {"updated": updated, "errors": 0}

    def sync_course(self, course_id: str) -> dict:
        """Sync a single course on-demand."""
        try:
            response = self.client.get(
                f"{self.base_url}/course", params={"name": course_id}
            )
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}

            course_data = response.json()
            with SyncSession() as session:
                self._process_course(session, course_data)

                # Also sync professors listed for this course
                for prof_name in course_data.get("professors", []):
                    self._sync_professor(session, prof_name)

                # Fetch and persist reviews
                reviews_resp = self.client.get(
                    f"{self.base_url}/course", params={"name": course_id, "reviews": "true"}
                )
                if reviews_resp.status_code == 200:
                    review_data = reviews_resp.json()
                    for rev in review_data.get("reviews", []):
                        self._process_review(session, course_id, rev)

                session.commit()

            return {
                "success": True,
                "course_id": course_id,
                "avg_gpa": course_data.get("average_gpa"),
            }
        except Exception as e:
            logger.error(f"Failed to sync course {course_id}: {e}")
            return {"success": False, "error": str(e)}

    def _process_course(self, session, course_data: dict) -> None:
        """Upsert a course record into PostgreSQL."""
        course_id = course_data.get("name", "").upper().replace(" ", "")
        if not course_id:
            return

        dept = course_data.get("department", "")
        if not dept:
            # Derive department from course_id (e.g., "CMSC131" -> "CMSC")
            dept = "".join(c for c in course_id if c.isalpha())

        existing = session.execute(
            select(Course).where(Course.course_id == course_id)
        ).scalar_one_or_none()

        if existing:
            existing.name = course_data.get("title") or existing.name
            existing.department = dept or existing.department
            existing.avg_gpa = course_data.get("average_gpa") or existing.avg_gpa
        else:
            course = Course(
                course_id=course_id,
                name=course_data.get("title") or course_id,
                department=dept,
                credits=course_data.get("credits") or 3,
                avg_gpa=course_data.get("average_gpa"),
            )
            session.add(course)

    def _sync_professor(self, session, prof_name: str) -> Professor:
        """Upsert a professor by name, always refreshing review_count, avg_rating, and review text."""
        slug = prof_name.lower().replace(" ", "_").replace(".", "")
        existing = session.execute(
            select(Professor).where(Professor.slug == slug)
        ).scalar_one_or_none()

        # Always fetch from PlanetTerp so review_count stays accurate
        reviews_data: list[dict] = []
        try:
            resp = self.client.get(
                f"{self.base_url}/professor", params={"name": prof_name, "reviews": "true"}
            )
            if resp.status_code == 200:
                data = resp.json()
                avg_rating = data.get("average_rating")
                reviews_data = data.get("reviews") or []
                review_count = len(reviews_data)
                courses_taught = data.get("courses", [])
            else:
                avg_rating = None
                review_count = 0
                courses_taught = []
        except Exception:
            avg_rating = None
            review_count = 0
            courses_taught = []

        if existing:
            existing.avg_rating = avg_rating or existing.avg_rating
            existing.review_count = review_count if review_count > 0 else existing.review_count
            existing.courses_taught = courses_taught or existing.courses_taught
            prof = existing
        else:
            prof = Professor(
                name=prof_name,
                slug=slug,
                avg_rating=avg_rating,
                review_count=review_count,
                courses_taught=courses_taught,
            )
            session.add(prof)
            session.flush()

        # Persist review text rows if not already in DB
        if reviews_data and prof.id:
            # Build set of valid course_ids already in the DB to avoid FK violations
            from app.models import Course as _Course
            valid_courses = {
                r[0] for r in session.execute(select(_Course.course_id)).all()
            }
            existing_texts = {
                r.text for r in session.execute(
                    select(Review).where(Review.professor_id == prof.id)
                ).scalars().all()
                if r.text
            }
            for rev in reviews_data:
                text = rev.get("review")
                rating = rev.get("rating")
                if rating is None:
                    continue
                if text and text in existing_texts:
                    continue  # already persisted
                course_id = (rev.get("course") or "").upper().replace(" ", "")
                if not course_id or course_id not in valid_courses:
                    continue  # skip reviews for courses not in DB
                review = Review(
                    course_id=course_id,
                    professor_id=prof.id,
                    rating=int(rating),
                    text=text,
                    source="planetterp",
                )
                session.add(review)

        return prof

    def sync_all_professors(self) -> dict:
        """Sync all professors in the DB — refresh review_count, avg_rating, and review text."""
        logger.info("PlanetTerp: syncing all professors")
        synced = 0
        errors = 0
        with SyncSession() as session:
            prof_names = [r[0] for r in session.execute(select(Professor.name)).all()]

        for name in prof_names:
            try:
                with SyncSession() as session:
                    self._sync_professor(session, name)
                    session.commit()
                synced += 1
            except Exception as e:
                logger.warning(f"Error syncing professor {name}: {e}")
                errors += 1

        return {"synced": synced, "errors": errors}

    def _process_review(self, session, course_id: str, review_data: dict) -> None:
        """Upsert a review into PostgreSQL."""
        rating = review_data.get("rating")
        if rating is None:
            return

        # Find professor if mentioned
        prof_id = None
        prof_name = review_data.get("professor")
        if prof_name:
            prof = self._sync_professor(session, prof_name)
            prof_id = prof.id

        review = Review(
            course_id=course_id.upper().replace(" ", ""),
            professor_id=prof_id,
            rating=int(rating),
            text=review_data.get("review"),
            source="planetterp",
        )
        session.add(review)
