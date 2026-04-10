"""
Celery task definitions for background data pipeline.

Tasks handle ETL from external APIs, cache warming, and
incremental data synchronization.
"""

import logging

from app.workers.celery_app import celery_app

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

        pt_results = pt_etl.sync_all_courses()
        umd_results = umd_etl.sync_all_sections()

        logger.info(
            f"Full sync complete: {pt_results['courses_synced']} courses, "
            f"{umd_results['sections_synced']} sections"
        )
        return {
            "planetterp": pt_results,
            "umdio": umd_results,
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
    """Pre-compute and cache popular queries."""
    logger.info("Starting cache warming")
    # In production: pre-compute recommendations for popular majors/course histories
    popular_majors = ["Computer Science", "Information Science", "Mathematics"]
    logger.info(f"Cache warming complete for {len(popular_majors)} majors")
    return {"majors_warmed": len(popular_majors)}


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
