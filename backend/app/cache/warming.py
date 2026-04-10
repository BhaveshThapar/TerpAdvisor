import logging
from typing import Any

from app.cache.multi_layer import MultiLayerCache

logger = logging.getLogger(__name__)

# Default TTLs (seconds)
COURSE_TTL = 6 * 3600       # 6 hours
REQUIREMENT_TTL = 12 * 3600  # 12 hours
RECOMMENDATION_TTL = 3600    # 1 hour


class CacheWarmer:
    """Pre-populates the multi-layer cache with frequently accessed data.

    Designed to run at application startup or on a periodic schedule so that
    the most common queries are served from upper cache layers.
    """

    def __init__(
        self,
        cache: MultiLayerCache,
        planetterp_client: Any,
        umdio_client: Any,
    ) -> None:
        self._cache = cache
        self._planetterp = planetterp_client
        self._umdio = umdio_client

    # ------------------------------------------------------------------
    # Warming strategies
    # ------------------------------------------------------------------

    async def warm_popular_courses(self, limit: int = 100) -> None:
        """Fetch the top *limit* courses by enrollment and cache them.

        Data is pulled from PlanetTerp (grades / GPA) and umd.io (sections,
        descriptions) then merged into a single dict per course.
        """
        logger.info("Warming cache for top %d popular courses", limit)
        try:
            courses = await self._planetterp.get_courses(limit=limit)
            for course in courses:
                course_id: str = course.get("course_id") or course.get("name", "")
                if not course_id:
                    continue
                cache_key = f"course:{course_id}"

                # Enrich with umd.io data when available.
                try:
                    umd_data = await self._umdio.get_course(course_id)
                    if umd_data:
                        course.update(umd_data)
                except Exception:
                    logger.debug(
                        "umd.io enrichment skipped for %s", course_id, exc_info=True
                    )

                await self._cache.set(cache_key, course, ttl=COURSE_TTL)

            logger.info("Warmed %d courses", len(courses))
        except Exception:
            logger.error("Failed to warm popular courses", exc_info=True)

    async def warm_major_requirements(self, majors: list[str]) -> None:
        """Pre-compute and cache requirement data for the given *majors*."""
        logger.info("Warming requirements for %d majors", len(majors))
        for major in majors:
            try:
                requirements = await self._umdio.get_major_requirements(major)
                if requirements:
                    cache_key = f"requirements:{major}"
                    await self._cache.set(
                        cache_key, requirements, ttl=REQUIREMENT_TTL
                    )
                    logger.debug("Warmed requirements for %s", major)
            except Exception:
                logger.warning(
                    "Failed to warm requirements for %s", major, exc_info=True
                )

    async def warm_recommendations(
        self,
        major: str,
        common_histories: list[list[str]],
    ) -> None:
        """Pre-compute recommendation scores for typical course histories.

        Each entry in *common_histories* is a list of course IDs representing a
        student's completed courses.  The recommendations are cached so that
        students with the same (or similar) history get a near-instant response.
        """
        logger.info(
            "Warming recommendations for major=%s with %d histories",
            major,
            len(common_histories),
        )
        for history in common_histories:
            try:
                # Build a deterministic cache key from the sorted course list.
                history_key = ",".join(sorted(history))
                cache_key = f"recommendations:{major}:{history_key}"

                # Pull requirement data (may already be warm).
                req_key = f"requirements:{major}"
                requirements = await self._cache.get(req_key)
                if requirements is None:
                    try:
                        requirements = await self._umdio.get_major_requirements(major)
                        if requirements:
                            await self._cache.set(
                                req_key, requirements, ttl=REQUIREMENT_TTL
                            )
                    except Exception:
                        logger.debug(
                            "Could not fetch requirements for %s", major, exc_info=True
                        )

                # Compute simple recommendation scores: courses that appear in
                # requirements but are not yet completed get a higher score.
                completed_set = set(history)
                recommendations: list[dict[str, Any]] = []

                if requirements and isinstance(requirements, list):
                    for req in requirements:
                        req_courses: list[str] = (
                            req.get("courses", []) if isinstance(req, dict) else []
                        )
                        for cid in req_courses:
                            if cid not in completed_set:
                                recommendations.append(
                                    {"course_id": cid, "score": 1.0}
                                )

                await self._cache.set(
                    cache_key, recommendations, ttl=RECOMMENDATION_TTL
                )
            except Exception:
                logger.warning(
                    "Failed to warm recommendations for history %s",
                    history,
                    exc_info=True,
                )

    async def warm_all(self) -> None:
        """Run every warming strategy with sensible defaults.

        Intended for application startup.  Override or extend for custom
        behaviour.
        """
        logger.info("Starting full cache warm-up")

        await self.warm_popular_courses(limit=100)

        # Warm the most common UMD CS/engineering majors.
        default_majors = [
            "CMSC",
            "ENEE",
            "MATH",
            "BMGT",
            "BIOL",
            "ECON",
            "PSYC",
            "ENGL",
            "INFO",
            "KNES",
        ]
        await self.warm_major_requirements(default_majors)

        # Warm recommendations for a few representative histories.
        default_histories: list[list[str]] = [
            ["CMSC131", "CMSC132", "CMSC216", "CMSC250"],
            ["CMSC131", "CMSC132"],
            ["MATH140", "MATH141", "CMSC131"],
        ]
        await self.warm_recommendations("CMSC", default_histories)

        logger.info("Full cache warm-up complete")
