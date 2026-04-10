import logging
from typing import Any, TypedDict

from sqlalchemy import select

from app.integrations.base_client import BaseAPIClient
from app.models.course import Course

logger = logging.getLogger(__name__)


class GradeDistribution(TypedDict):
    course: str
    semester: str
    section: str
    A_plus: int
    A: int
    A_minus: int
    B_plus: int
    B: int
    B_minus: int
    C_plus: int
    C: int
    C_minus: int
    D_plus: int
    D: int
    D_minus: int
    F: int
    W: int
    other: int


class ProfessorInfo(TypedDict):
    name: str
    slug: str
    type: str
    courses: list[str]
    average_rating: float | None


class CourseInfo(TypedDict):
    name: str
    department: str
    course_id: str
    credits: int
    description: str | None
    average_gpa: float | None


class ReviewInfo(TypedDict):
    professor: str
    course: str
    review: str
    rating: int
    expected_grade: str | None
    created: str


class PlanetTerpClient(BaseAPIClient):
    """Client for the PlanetTerp API with full resilience pipeline."""

    base_url = "https://planetterp.com/api/v1"

    async def get_course(self, course_id: str) -> CourseInfo | None:
        return await self._request(
            "/course",
            params={"name": course_id},
            cache_key=f"pt:course:{course_id}",
            stale_key=course_id,
        )

    async def get_grades(self, course_id: str) -> list[GradeDistribution] | None:
        return await self._request(
            "/grades",
            params={"course": course_id},
            cache_key=f"pt:grades:{course_id}",
            stale_key=f"grades:{course_id}",
        )

    async def get_professor(self, name: str) -> ProfessorInfo | None:
        return await self._request(
            "/professor",
            params={"name": name},
            cache_key=f"pt:prof:{name}",
            stale_key=f"prof:{name}",
        )

    async def get_reviews(self, course_id: str) -> list[ReviewInfo] | None:
        return await self._request(
            "/reviews",
            params={"course": course_id},
            cache_key=f"pt:reviews:{course_id}",
            stale_key=f"reviews:{course_id}",
        )

    async def search(self, query: str) -> list[dict[str, Any]] | None:
        return await self._request(
            "/search",
            params={"query": query},
            cache_key=f"pt:search:{query}",
            stale_key=f"search:{query}",
        )

    # -- stale DB fallback ---------------------------------------------------

    async def _get_stale_from_db(self, key: str) -> Any | None:
        """Look up a course row in Postgres as a last-resort fallback."""
        # Only course lookups have a direct DB mapping.
        if key.startswith(("grades:", "prof:", "reviews:", "search:")):
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
                "name": course.name,
                "department": course.department,
                "course_id": course.course_id,
                "credits": course.credits,
                "description": course.description,
                "average_gpa": course.avg_gpa,
            }
        except Exception:
            logger.exception("Stale DB lookup failed for key=%s", key)
            return None
