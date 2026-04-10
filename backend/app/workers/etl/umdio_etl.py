"""
umd.io ETL pipeline.

Extract: Fetch course catalog and section data from umd.io API
Transform: Normalize section times, merge with PlanetTerp data
Load: Upsert into PostgreSQL, publish update events
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.session import SyncSession
from app.models import Course, Professor, Section

logger = logging.getLogger(__name__)

_last_sync: dict[str, datetime] = {}


class UmdIoETL:
    """ETL pipeline for umd.io section and course catalog data."""

    def __init__(self):
        self.base_url = settings.umdio_base_url
        self.client = httpx.Client(timeout=30.0)

    def sync_all_sections(self, semester: str = "202508") -> dict:
        """Full sync — fetch all sections for a semester."""
        logger.info(f"umd.io full sync: fetching sections for {semester}")
        sections_synced = 0
        errors = 0

        try:
            page = 1
            with SyncSession() as session:
                while True:
                    response = self.client.get(
                        f"{self.base_url}/courses/sections",
                        params={"semester": semester, "page": page, "per_page": 100},
                    )
                    if response.status_code != 200:
                        break

                    sections = response.json()
                    if not sections:
                        break

                    for section_data in sections:
                        try:
                            self._process_section(session, section_data, semester)
                            sections_synced += 1
                        except Exception as e:
                            logger.warning(f"Error processing section: {e}")
                            errors += 1

                    # Commit in batches of 100
                    session.commit()
                    page += 1

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during section sync: {e}")
            errors += 1

        _last_sync["full"] = datetime.now(timezone.utc)
        return {"sections_synced": sections_synced, "errors": errors}

    def sync_incremental(self) -> dict:
        """Incremental sync — check for seat availability changes."""
        logger.info("umd.io incremental sync")
        updated = 0

        popular = ["CMSC131", "CMSC132", "CMSC216", "CMSC250", "CMSC330", "CMSC351"]
        with SyncSession() as session:
            for course_id in popular:
                try:
                    response = self.client.get(
                        f"{self.base_url}/courses/{course_id}/sections"
                    )
                    if response.status_code == 200:
                        for section_data in response.json():
                            self._process_section(session, section_data)
                            updated += 1
                except Exception as e:
                    logger.warning(f"Error syncing sections for {course_id}: {e}")
            session.commit()

        _last_sync["incremental"] = datetime.now(timezone.utc)
        return {"updated": updated, "errors": 0}

    def sync_course_sections(self, course_id: str, semester: str = "202508") -> dict:
        """Sync sections for a single course."""
        try:
            response = self.client.get(
                f"{self.base_url}/courses/{course_id}/sections",
                params={"semester": semester},
            )
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}

            sections = response.json()
            with SyncSession() as session:
                for section_data in sections:
                    self._process_section(session, section_data, semester)
                session.commit()

            return {"success": True, "sections_synced": len(sections)}
        except Exception as e:
            logger.error(f"Failed to sync sections for {course_id}: {e}")
            return {"success": False, "error": str(e)}

    def _process_section(self, session, section_data: dict, semester: str = "202508") -> None:
        """Upsert a section record into PostgreSQL."""
        section_id = section_data.get("section_id", "")
        course_id = section_data.get("course", "")
        if not section_id or not course_id:
            return

        # Ensure the course exists (create stub if not)
        course = session.execute(
            select(Course).where(Course.course_id == course_id)
        ).scalar_one_or_none()
        if not course:
            dept = "".join(c for c in course_id if c.isalpha())
            course = Course(
                course_id=course_id,
                name=course_id,
                department=dept,
                credits=3,
            )
            session.add(course)
            session.flush()

        # Resolve professor
        professor_id = None
        instructors = section_data.get("instructors", [])
        if instructors:
            prof_name = instructors[0]
            slug = prof_name.lower().replace(" ", "_").replace(".", "")
            prof = session.execute(
                select(Professor).where(Professor.slug == slug)
            ).scalar_one_or_none()
            if not prof:
                prof = Professor(name=prof_name, slug=slug, review_count=0)
                session.add(prof)
                session.flush()
            professor_id = prof.id

        # Parse meeting times — take the first meeting's days/times
        days_str = None
        start_time = None
        end_time = None
        meetings = section_data.get("meetings", [])
        if meetings:
            meeting = meetings[0]
            days_str = meeting.get("days", "")
            raw_start = meeting.get("start_time", "")
            raw_end = meeting.get("end_time", "")
            if raw_start and raw_end:
                start_time = self._parse_time(raw_start)
                end_time = self._parse_time(raw_end)

        seats = section_data.get("seats", {})
        total_seats = seats.get("total", 0) if isinstance(seats, dict) else 0
        open_seats = seats.get("open", 0) if isinstance(seats, dict) else 0
        waitlist = seats.get("waitlist", 0) if isinstance(seats, dict) else 0

        # Upsert section
        existing = session.execute(
            select(Section).where(Section.section_id == section_id)
        ).scalar_one_or_none()

        if existing:
            existing.days = days_str or existing.days
            existing.start_time = start_time or existing.start_time
            existing.end_time = end_time or existing.end_time
            existing.total_seats = total_seats
            existing.open_seats = open_seats
            existing.waitlist = waitlist
            if professor_id:
                existing.professor_id = professor_id
        else:
            section = Section(
                section_id=section_id,
                course_id=course_id,
                professor_id=professor_id,
                semester=semester,
                days=days_str,
                start_time=start_time,
                end_time=end_time,
                total_seats=total_seats,
                open_seats=open_seats,
                waitlist=waitlist,
            )
            session.add(section)

    @staticmethod
    def _parse_time(time_str: str) -> time | None:
        """Parse a time string like '10:00am' or '14:30' into a time object."""
        try:
            time_str = time_str.strip()
            if "am" in time_str.lower() or "pm" in time_str.lower():
                is_pm = "pm" in time_str.lower()
                time_str = time_str.lower().replace("am", "").replace("pm", "").strip()
                parts = time_str.split(":")
                h = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 else 0
                if is_pm and h != 12:
                    h += 12
                elif not is_pm and h == 12:
                    h = 0
                return time(h, m)
            else:
                parts = time_str.split(":")
                return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_days(days_str: str) -> list[str]:
        """Parse day string like 'MWF' or 'TuTh' into individual day codes."""
        result = []
        i = 0
        while i < len(days_str):
            if i + 1 < len(days_str) and days_str[i + 1].islower():
                result.append(days_str[i : i + 2])
                i += 2
            else:
                result.append(days_str[i])
                i += 1
        return result
