"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "terpadvisor",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="US/Eastern",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Celery Beat schedule — automated recurring tasks
celery_app.conf.beat_schedule = {
    # Nightly full sync of popular courses (2 AM ET)
    "nightly-full-sync": {
        "task": "app.workers.tasks.full_sync",
        "schedule": crontab(hour=2, minute=0),
    },
    # Hourly delta sync during registration periods
    "hourly-delta-sync": {
        "task": "app.workers.tasks.delta_sync",
        "schedule": crontab(minute=0),  # Every hour
    },
    # Warm cache for popular queries every 6 hours
    "cache-warming": {
        "task": "app.workers.tasks.warm_cache",
        "schedule": crontab(hour="*/6", minute=15),
    },
}
