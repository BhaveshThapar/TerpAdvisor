import logging
from typing import Any, TypedDict

from sqlalchemy import select

from app.integrations.base_client import BaseAPIClient
from app.models.course import Course

logger = logging.getLogger(__name__)


class UmdCourseInfo(TypedDict):
    course_id: str
    name: str
    dept_id: str
    credits: int
    description: str | None
    gen_ed: list[list[str]]
    relationships: dict[str, Any]


class SectionInfo(TypedDict):
    section_id: str
    course: str
    semester: str
    number: str
    seats: int
    open_seats: int
    waitlist: int
    instructors: list[str]
    meetings: list[dict[str, Any]]


class DepartmentInfo(TypedDict):
    dept_id: str
    name: str


class UmdIOClient(BaseAPIClient):
    """Client for the umd.io API with full resilience pipeline."""

    base_url = "https://api.umd.io/v1"

    async def get_course(self, course_id: str) -> UmdCourseInfo | None:
        data = await self._request(
            f"/courses/{course_id}",
            cache_key=f"umd:course:{course_id}",
            stale_key=course_id,
        )
        # umd.io returns a list with a single element for individual lookups.
        if isinstance(data, list) and len(data) == 1:
            return data[0]
        return data

    async def get_sections(
        self, course_id: str, semester: str
    ) -> list[SectionInfo] | None:
        return await self._request(
            f"/courses/{course_id}/sections",
            params={"semester": semester},
            cache_key=f"umd:sections:{course_id}:{semester}",
            stale_key=f"sections:{course_id}:{semester}",
        )

    async def get_departments(self) -> list[DepartmentInfo] | None:
        return await self._request(
            "/courses/departments",
            cache_key="umd:departments",
            stale_key="departments",
        )

    # -- stale DB fallback ---------------------------------------------------

    async def _get_stale_from_db(self, key: str) -> Any | None:
        """Look up a course row in Postgres as a last-resort fallback."""
        if key.startswith(("sections:", "departments")):
            return None

        course_id = key
        try:
            result = await self._db.execute(
                select(Course).where(Course.course_id == course_id)
            )
            course = result.scalar_one_or_none()
            if course is None:
                return None
            return {
                "course_id": course.course_id,
                "name": course.name,
                "dept_id": course.department,
                "credits": course.credits,
                "description": course.description,
                "gen_ed": course.gen_eds or [],
                "relationships": course.prerequisites_raw or {},
            }
        except Exception:
            logger.exception("Stale DB lookup failed for key=%s", key)
            return None
