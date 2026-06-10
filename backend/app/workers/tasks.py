"""
Celery task definitions for background data pipeline.

Tasks handle ETL from external APIs, cache warming, and
incremental data synchronization.
"""

import logging
from datetime import datetime

from app.workers.celery_app import celery_app


def _current_semester() -> str:
    """Return the umd.io semester code (YYYYMM) for the current active semester."""
    now = datetime.now()
    year, month = now.year, now.month
    if month >= 8:
        return f"{year}08"   # Fall starts August
    elif month >= 5:
        return f"{year}05"   # Summer starts May
    else:
        return f"{year}01"   # Spring starts January


def _previous_semester(current: str) -> str:
    """Return the semester code immediately before the given one."""
    year, code = int(current[:4]), current[4:]
    if code == "08":
        return f"{year}01"   # previous = Spring same year
    elif code == "05":
        return f"{year}01"   # previous = Spring same year
    else:
        return f"{year - 1}08"  # previous = Fall last year

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def full_sync(self):
    """Nightly full sync — refresh all course, grade, and professor data."""
    logger.info("Starting full sync from PlanetTerp and umd.io")
    try:
        from app.workers.etl.planetterp_etl import PlanetTerpETL
        from app.workers.etl.umdio_etl import UmdIoETL

        pt_etl = PlanetTerpETL()
        umd_etl = UmdIoETL()

        current = _current_semester()
        previous = _previous_semester(current)

        pt_results = pt_etl.sync_all_courses()
        umd_current = umd_etl.sync_all_sections(current)
        umd_previous = umd_etl.sync_all_sections(previous)

        total_sections = umd_current["sections_synced"] + umd_previous["sections_synced"]
        logger.info(
            f"Full sync complete: {pt_results['courses_synced']} courses, "
            f"{total_sections} sections ({current} + {previous})"
        )
        return {
            "planetterp": pt_results,
            "umdio": {"current": umd_current, "previous": umd_previous},
        }
    except Exception as exc:
        logger.error(f"Full sync failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def delta_sync(self):
    """Hourly incremental sync — only fetch data changed since last sync."""
    logger.info("Starting delta sync")
    try:
        from app.workers.etl.planetterp_etl import PlanetTerpETL
        from app.workers.etl.umdio_etl import UmdIoETL

        pt_etl = PlanetTerpETL()
        umd_etl = UmdIoETL()

        pt_results = pt_etl.sync_incremental()
        umd_results = umd_etl.sync_incremental()

        logger.info(
            f"Delta sync complete: {pt_results['updated']} courses updated, "
            f"{umd_results['updated']} sections updated"
        )
        return {"planetterp": pt_results, "umdio": umd_results}
    except Exception as exc:
        logger.error(f"Delta sync failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task
def warm_cache():
    """Pre-compute and cache recommendation responses for popular queries.

    Runs the same pipeline as POST /api/recommendations and writes results
    into the shared multi-layer cache (Redis + Postgres layers are visible
    to the API process), so cold-start requests for popular majors are
    served from cache. Uses a dedicated NullPool engine because each Celery
    invocation runs in its own event loop.
    """
    import asyncio

    async def _warm() -> dict:
        import redis.asyncio as aioredis
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.api.recommendations import _compute_recommendations
        from app.cache.service import build_cache, cached, make_key
        from app.config import settings
        from app.schemas.schemas import RecommendationRequest

        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        redis_client = aioredis.from_url(settings.redis_url)
        cache = build_cache(redis_client=redis_client, session_factory=session_factory)

        popular_majors = ["Computer Science", "Information Science", "Mathematics"]
        warmed: list[str] = []
        try:
            for major in popular_majors:
                # The cold-start request every new user fires after onboarding.
                body = RecommendationRequest(major=major)
                key = make_key("rec", body.model_dump())
                async with session_factory() as db:
                    await cached(
                        key,
                        lambda: _compute_recommendations(body, db),
                        ttl=900,
                        delta=1.5,
                        cache=cache,
                    )
                warmed.append(major)
        finally:
            await redis_client.aclose()
            await engine.dispose()
        return {"majors_warmed": len(warmed), "majors": warmed}

    logger.info("Starting cache warming")
    result = asyncio.run(_warm())
    logger.info(f"Cache warming complete: {result}")
    return result


@celery_app.task(bind=True, max_retries=2)
def sync_course(self, course_id: str):
    """Sync a single course's data from PlanetTerp. Used for on-demand refresh."""
    try:
        from app.workers.etl.planetterp_etl import PlanetTerpETL
        etl = PlanetTerpETL()
        result = etl.sync_course(course_id)
        logger.info(f"Synced course {course_id}")
        return result
    except Exception as exc:
        logger.error(f"Failed to sync course {course_id}: {exc}")
        raise self.retry(exc=exc)
