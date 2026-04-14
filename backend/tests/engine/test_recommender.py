"""Tests for the recommendation engine and scorers."""

import pytest

from app.engine.recommender import RecommendationEngine
from app.engine.scorers.base import ScoringContext
from app.engine.scorers.gpa import GPAScorer
from app.engine.scorers.preference_tags import PreferenceTagScorer
from app.engine.scorers.requirement import RequirementScorer


def _make_context(**kwargs) -> ScoringContext:
    defaults = dict(
        user_id="test-user",
        completed_courses={"CMSC131", "CMSC132"},
        in_progress_courses=set(),
        major="Computer Science",
        course_data={},
        professor_data={},
        review_data={},
        grade_data={},
        requirement_impact={},
        selected_sections=[],
        weight_overrides=None,
    )
    defaults.update(kwargs)
    return ScoringContext(**defaults)


class TestGPAScorer:
    @pytest.mark.asyncio
    async def test_high_gpa_scores_high(self):
        scorer = GPAScorer()
        context = _make_context(
            course_data={"CMSC216": {"avg_gpa": 3.8}},
            grade_data={"CMSC216": {"A": 50, "B": 30, "C": 10}},
        )
        result = await scorer.score("CMSC216", context)
        assert result.score > 0.8
        assert "High avg GPA" in result.explanation

    @pytest.mark.asyncio
    async def test_low_gpa_scores_low(self):
        scorer = GPAScorer()
        context = _make_context(
            course_data={"CMSC351": {"avg_gpa": 2.3}},
            grade_data={"CMSC351": {"A": 10, "B": 20, "C": 30, "D": 20, "F": 10}},
        )
        result = await scorer.score("CMSC351", context)
        assert result.score < 0.3
        assert "Low avg GPA" in result.explanation

    @pytest.mark.asyncio
    async def test_no_data_returns_neutral(self):
        scorer = GPAScorer()
        context = _make_context(course_data={"CMSC389": {}})
        result = await scorer.score("CMSC389", context)
        assert result.score == 0.5
        assert result.confidence < 0.5


class TestPreferenceTagScorer:
    @pytest.mark.asyncio
    async def test_online_keywords_match(self):
        scorer = PreferenceTagScorer()
        context = _make_context(
            review_data={
                "HIST200": [
                    {"rating": 4, "text": "This class is fully online and asynchronous, recorded lectures every week."},
                ]
            },
            preference_tags=["online"],
        )
        result = await scorer.score("HIST200", context)
        assert result.score > 0.5
        assert "online" in result.explanation

    @pytest.mark.asyncio
    async def test_no_attendance_and_easy_a_match(self):
        scorer = PreferenceTagScorer()
        context = _make_context(
            review_data={
                "PSYC100": [
                    {"rating": 5, "text": "Easy A and attendance not required, I never went to class."},
                ]
            },
            preference_tags=["easy-a", "no-attendance"],
        )
        result = await scorer.score("PSYC100", context)
        assert result.score >= 0.9

    @pytest.mark.asyncio
    async def test_unmatched_reviews_score_low(self):
        scorer = PreferenceTagScorer()
        context = _make_context(
            review_data={
                "MATH410": [
                    {"rating": 3, "text": "Proof-heavy and in-person with strict attendance."},
                ]
            },
            preference_tags=["online", "easy-a"],
        )
        result = await scorer.score("MATH410", context)
        assert result.score <= 0.35


class TestRequirementScorer:
    @pytest.mark.asyncio
    async def test_high_impact_course(self):
        scorer = RequirementScorer()
        context = _make_context(requirement_impact={"CMSC351": 3})
        result = await scorer.score("CMSC351", context)
        assert result.score > 0.5
        assert "3 unfulfilled degree requirements" in result.explanation

    @pytest.mark.asyncio
    async def test_no_impact_course(self):
        scorer = RequirementScorer()
        context = _make_context(requirement_impact={})
        result = await scorer.score("RANDOM101", context)
        assert result.score == 0.0


class TestRecommendationEngine:
    @pytest.mark.asyncio
    async def test_ranks_by_score(self):
        engine = RecommendationEngine()
        context = _make_context(
            course_data={
                "CMSC330": {"avg_gpa": 3.5},
                "CMSC351": {"avg_gpa": 2.5},
            },
            requirement_impact={"CMSC330": 2, "CMSC351": 2},
            grade_data={
                "CMSC330": {"A": 40, "B": 30},
                "CMSC351": {"A": 10, "B": 20, "C": 30},
            },
        )

        result = await engine.recommend(["CMSC330", "CMSC351"], context, top_n=2)
        assert len(result.recommendations) == 2
        # First recommendation should have higher score
        assert result.recommendations[0].final_score >= result.recommendations[1].final_score

    @pytest.mark.asyncio
    async def test_respects_weight_overrides(self):
        engine = RecommendationEngine()
        context_gpa_heavy = _make_context(
            course_data={
                "EASY101": {"avg_gpa": 3.9},
                "HARD400": {"avg_gpa": 2.1},
            },
            requirement_impact={"HARD400": 3, "EASY101": 0},
            grade_data={
                "EASY101": {"A": 100},
                "HARD400": {"A": 5, "F": 50},
            },
            weight_overrides={"gpa": 0.9, "requirement": 0.1},
        )

        result = await engine.recommend(["EASY101", "HARD400"], context_gpa_heavy, top_n=2)
        # With 90% weight on GPA, the easy course should rank higher
        assert result.recommendations[0].course_id == "EASY101"

    @pytest.mark.asyncio
    async def test_explanations_present(self):
        engine = RecommendationEngine()
        context = _make_context(
            course_data={"CMSC330": {"avg_gpa": 3.2}},
            requirement_impact={"CMSC330": 1},
        )

        result = await engine.recommend(["CMSC330"], context, top_n=1)
        rec = result.recommendations[0]
        assert len(rec.explanations) > 0
        assert rec.top_reason != ""
        # Explanations should be sorted by contribution
        contributions = [e.contribution for e in rec.explanations]
        assert contributions == sorted(contributions, reverse=True)

    @pytest.mark.asyncio
    async def test_easiest_mode_weights_rank_high_gpa_online_course_first(self):
        """Easiest-mode weight overrides should float a high-GPA, 'online'-reviewed course to the top."""
        engine = RecommendationEngine()
        context = _make_context(
            course_data={
                "EASY200": {"avg_gpa": 3.85},
                "TOUGH400": {"avg_gpa": 2.4},
            },
            review_data={
                "EASY200": [
                    {"rating": 5, "text": "Fully online asynchronous course, no final exam, easy A."},
                ],
                "TOUGH400": [
                    {"rating": 2, "text": "Hard proofs and attendance is strictly enforced."},
                ],
            },
            requirement_impact={"TOUGH400": 3, "EASY200": 0},
            preference_tags=["online", "no-attendance", "no-final-exam", "light-workload", "easy-a"],
            weight_overrides={
                "gpa": 0.50,
                "preference_tags": 0.30,
                "sentiment": 0.10,
                "requirement": 0.05,
                "professor": 0.05,
                "collaborative": 0.0,
                "schedule_fit": 0.0,
            },
        )
        result = await engine.recommend(["EASY200", "TOUGH400"], context, top_n=2)
        assert result.recommendations[0].course_id == "EASY200"
        assert result.weights_used["gpa"] >= 0.4

    @pytest.mark.asyncio
    async def test_weights_normalize_to_one(self):
        engine = RecommendationEngine()
        context = _make_context(
            weight_overrides={"gpa": 5.0, "requirement": 5.0},
        )
        result = await engine.recommend(["CMSC330"], context)
        total = sum(result.weights_used.values())
        assert abs(total - 1.0) < 0.01
