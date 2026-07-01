"""The sentiment and preference-tag scorers read precomputed per-course signals
from course_data (backfill_sentiment.py) instead of reprocessing raw review text."""

import pytest

from app.engine.scorers.base import ScoringContext
from app.engine.scorers.preference_tags import PreferenceTagScorer, match_review_tags
from app.engine.scorers.sentiment import SentimentScorer


def _ctx(course_data: dict, preference_tags: list[str] | None = None) -> ScoringContext:
    return ScoringContext(
        user_id="u",
        completed_courses=set(),
        in_progress_courses=set(),
        major="Computer Science",
        course_data=course_data,
        professor_data={},
        review_data={},  # deliberately empty: fast path must not need raw reviews
        grade_data={},
        requirement_impact={},
        selected_sections=[],
        preference_tags=preference_tags,
    )


class TestSentimentFastPath:
    @pytest.mark.asyncio
    async def test_uses_precomputed_polarity(self):
        ctx = _ctx({"C": {"sentiment_polarity": 0.6, "sentiment_confidence": 0.8,
                          "sentiment_summary": "Positive — students praise it"}})
        res = await SentimentScorer().score("C", ctx)
        assert res.score == pytest.approx((0.6 + 1.0) / 2.0)
        assert res.confidence == 0.8
        assert "Positive" in res.explanation

    @pytest.mark.asyncio
    async def test_zero_confidence_reads_as_no_reviews(self):
        ctx = _ctx({"C": {"sentiment_polarity": 0.0, "sentiment_confidence": 0.0}})
        res = await SentimentScorer().score("C", ctx)
        assert res.score == 0.5
        assert res.confidence == 0.1


class TestPreferenceTagsFastPath:
    @pytest.mark.asyncio
    async def test_matches_precomputed_tags(self):
        ctx = _ctx(
            {"C": {"review_tags": ["project-based", "math-heavy"], "review_count": 10}},
            preference_tags=["project-based"],
        )
        res = await PreferenceTagScorer().score("C", ctx)
        assert res.score > 0.5
        assert "project-based" in res.explanation

    @pytest.mark.asyncio
    async def test_no_reviews_precomputed(self):
        ctx = _ctx({"C": {"review_tags": [], "review_count": 0}},
                   preference_tags=["project-based"])
        res = await PreferenceTagScorer().score("C", ctx)
        assert res.score == 0.5
        assert res.confidence == 0.1


class TestMatchReviewTags:
    def test_detects_tags_in_text(self):
        tags = match_review_tags("Great group project, super hands-on and math heavy proofs")
        assert "project-based" in tags
        assert "math-heavy" in tags

    def test_no_tags_in_neutral_text(self):
        assert match_review_tags("The class meets Monday and Wednesday.") == set()
