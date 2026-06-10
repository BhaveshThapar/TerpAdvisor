"""Unit tests for /api/recommendations helper logic.

Pure-function tests for filter application plus a FakeDB test for the batched
completed-credits lookup (mirrors the FakeDB pattern used elsewhere in the
suite — see tests/engine/test_requirements_loader.py).
"""

from collections import namedtuple

import pytest

from app.api.recommendations import _apply_filters, _get_completed_credits
from app.schemas.schemas import RecommendationFilters

_COURSES = ["CMSC131", "CMSC216", "CMSC351", "CMSC416", "MATH410"]


def _meta(credits=3):
    return {
        c: {"department": c[:4], "credits": credits, "avg_gpa": 3.0, "gen_eds": []}
        for c in _COURSES
    }


class TestLevelFilter:
    def test_100_level_only_returns_100_level(self):
        """Regression: old filter matched a level digit ANYWHERE in the ID,
        so a 100-level filter returned CMSC216/351/416 and MATH410 too."""
        f = RecommendationFilters(levels=[100])
        assert _apply_filters(_COURSES, f, _meta()) == ["CMSC131"]

    def test_400_level(self):
        f = RecommendationFilters(levels=[400])
        assert _apply_filters(_COURSES, f, _meta()) == ["CMSC416", "MATH410"]

    def test_multiple_levels(self):
        f = RecommendationFilters(levels=[200, 300])
        assert _apply_filters(_COURSES, f, _meta()) == ["CMSC216", "CMSC351"]

    def test_no_digit_course_id_is_excluded(self):
        f = RecommendationFilters(levels=[100])
        assert _apply_filters(["NODIGITS"], f, {}) == []


class TestCreditFilters:
    def test_none_credits_does_not_crash(self):
        """Courses with NULL credits in the DB must not raise on comparison
        (previously `.get("credits", 3)` returned None when the key existed
        with a None value, making `None >= int` blow up)."""
        meta = _meta(credits=None)
        f = RecommendationFilters(min_credits=3)
        # None credits fall back to the 3-credit assumption and pass min=3.
        assert _apply_filters(_COURSES, f, meta) == _COURSES

    def test_max_credits_excludes(self):
        meta = _meta(credits=4)
        f = RecommendationFilters(max_credits=3)
        assert _apply_filters(_COURSES, f, meta) == []


_Row = namedtuple("_Row", ["course_id", "credits"])


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def execute(self, _stmt):
        self.calls += 1
        return _FakeResult(self._rows)


class TestGetCompletedCredits:
    @pytest.mark.asyncio
    async def test_single_batched_query(self):
        """Regression: previously one DB round-trip per completed course."""
        db = _FakeDB([_Row("CMSC131", 4), _Row("CMSC216", 4)])
        out = await _get_completed_credits(["CMSC131", "CMSC216", "GHOST101"], db)
        assert db.calls == 1
        assert out == {"CMSC131": 4, "CMSC216": 4, "GHOST101": 0}

    @pytest.mark.asyncio
    async def test_overrides_and_transfer_skip_db(self):
        db = _FakeDB([])
        out = await _get_completed_credits(
            ["TR_4_CALC", "CMSC131"],
            db,
            credit_overrides={"CMSC131": 3},
        )
        # Everything resolved without touching the DB.
        assert db.calls == 0
        assert out == {"TR_4_CALC": 4, "CMSC131": 3}
