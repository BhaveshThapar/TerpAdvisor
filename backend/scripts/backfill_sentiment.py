"""Backfill precomputed review signals onto the courses table.

The recommendation pipeline used to reprocess every course's raw review text on
each request (sentiment + preference-tag matching), which dominated latency. This
script computes those signals once and stores them on each course:

    review_count, sentiment_polarity, sentiment_confidence, sentiment_summary, review_tags

Idempotent and re-runnable — run it after an ETL refresh whenever reviews change.

Usage (from backend/):  python -m scripts.backfill_sentiment
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select, text

from app.db.session import SyncSession, sync_engine
from app.engine.scorers.preference_tags import match_review_tags
from app.engine.sentiment import analyze_reviews

# Prod runs create_all (not Alembic), which won't add columns to an existing
# table, so add them here idempotently before populating.
_ADD_COLUMNS = (
    "ALTER TABLE courses ADD COLUMN IF NOT EXISTS review_count INTEGER",
    "ALTER TABLE courses ADD COLUMN IF NOT EXISTS sentiment_polarity DOUBLE PRECISION",
    "ALTER TABLE courses ADD COLUMN IF NOT EXISTS sentiment_confidence DOUBLE PRECISION",
    "ALTER TABLE courses ADD COLUMN IF NOT EXISTS sentiment_summary VARCHAR",
    "ALTER TABLE courses ADD COLUMN IF NOT EXISTS review_tags JSON",
)


def _ensure_columns() -> None:
    with sync_engine.begin() as conn:
        for stmt in _ADD_COLUMNS:
            conn.execute(text(stmt))


def backfill() -> tuple[int, int]:
    """Populate review signals for every course. Returns (courses, reviews)."""
    from app.models import Course, Review  # registers mappers

    _ensure_columns()

    reviews_by_course: dict[str, list[dict]] = defaultdict(list)
    updated = 0
    reviews_seen = 0

    with SyncSession() as session:
        for row in session.execute(
            select(Review.course_id, Review.rating, Review.text)
        ).all():
            reviews_by_course[row.course_id].append(
                {"rating": row.rating, "text": row.text or ""}
            )

        for course in session.execute(select(Course)).scalars().all():
            reviews = reviews_by_course.get(course.course_id, [])
            reviews_seen += len(reviews)

            result = analyze_reviews(reviews)
            course.review_count = len(reviews)
            course.sentiment_polarity = result.polarity
            course.sentiment_confidence = result.confidence
            course.sentiment_summary = result.summary
            course.review_tags = sorted(
                match_review_tags(" ".join(r["text"] for r in reviews))
            )
            updated += 1

        session.commit()

    return updated, reviews_seen


if __name__ == "__main__":
    courses, reviews = backfill()
    print(f"Backfilled {courses} courses from {reviews} reviews.")
