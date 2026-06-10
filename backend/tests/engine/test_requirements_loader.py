"""Tests for the dynamic requirements loader."""

import pytest

from app.engine import requirements_loader
from app.engine.degree_audit import (
    Requirement,
    RequirementGroup,
    RequirementType,
    build_cs_requirements,
    build_requirements_for_major,
)
from app.engine.requirements_loader import (
    clear_cache,
    load_requirements_for_major,
    requirements_from_dict,
    requirements_to_dict,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeDB:
    def __init__(self, rows: list):
        self._rows = list(rows)
        self.calls = 0

    async def execute(self, _stmt):
        self.calls += 1
        return _FakeResult(self._rows.pop(0) if self._rows else None)


class _FakeMajorRow:
    def __init__(self, requirements: dict):
        self.requirements = requirements


class TestSerialization:
    def test_round_trip_cs(self):
        original = build_cs_requirements()
        round_tripped = requirements_from_dict(requirements_to_dict(original))
        assert round_tripped.major == original.major
        assert round_tripped.catalog_year == original.catalog_year
        assert round_tripped.track == original.track
        assert len(round_tripped.groups) == len(original.groups)
        for og, rg in zip(original.groups, round_tripped.groups):
            assert og.id == rg.id
            assert len(og.requirements) == len(rg.requirements)
            for orq, rrq in zip(og.requirements, rg.requirements):
                assert orq.id == rrq.id
                assert orq.type == rrq.type
                assert orq.course_options == rrq.course_options
                assert orq.prefix_patterns == rrq.prefix_patterns

    def test_round_trip_all_seeded_majors(self):
        for major in ("Computer Science", "Mathematics", "Information Science",
                      "Economics", "Biological Sciences", "Mechanical Engineering"):
            reqs = build_requirements_for_major(major)
            assert requirements_from_dict(requirements_to_dict(reqs)).major == reqs.major


class TestLoader:
    @pytest.mark.asyncio
    async def test_db_hit(self):
        cs = build_cs_requirements()
        db = _FakeDB([_FakeMajorRow(requirements_to_dict(cs))])
        loaded = await load_requirements_for_major(db, "Computer Science", "General")
        assert loaded.major == cs.major
        assert len(loaded.groups) == len(cs.groups)
        assert db.calls == 1

    @pytest.mark.asyncio
    async def test_db_miss_falls_back_to_in_memory(self, caplog):
        db = _FakeDB([None, None])  # also no fallback to General row
        with caplog.at_level("WARNING"):
            loaded = await load_requirements_for_major(db, "Mathematics", "General")
        assert loaded.major == "Mathematics"
        assert any("majors table miss" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_unknown_major_falls_back_to_cs(self, caplog):
        db = _FakeDB([None, None])
        with caplog.at_level("WARNING"):
            loaded = await load_requirements_for_major(db, "Underwater Basket Weaving", "General")
        assert loaded.major == "Computer Science"
        assert any("falling back to Computer Science" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_cache_avoids_second_db_call(self):
        cs = build_cs_requirements()
        db = _FakeDB([_FakeMajorRow(requirements_to_dict(cs))])
        await load_requirements_for_major(db, "Computer Science", "General")
        await load_requirements_for_major(db, "Computer Science", "General")
        assert db.calls == 1

    @pytest.mark.asyncio
    async def test_cached_objects_are_isolated_between_calls(self):
        """Regression: /audit mutates ulc prefix_patterns for minor injection.

        The loader used to cache and return the *same* DegreeRequirements
        object, so one user's minor prefixes leaked into every other user's
        audit for the cache TTL. Each call must now return a fresh object.
        """
        cs = build_cs_requirements()
        db = _FakeDB([_FakeMajorRow(requirements_to_dict(cs))])

        # Request 1: simulate /audit injecting a MATH minor into the ULC req.
        first = await load_requirements_for_major(db, "Computer Science", "General")
        ulc_group = next(g for g in first.groups if g.id == "ulc")
        ulc_group.requirements[0].prefix_patterns.extend(["MATH3", "MATH4"])
        first.groups[0].requirements[0].course_options.append("FAKE999")

        # Request 2: a different user with no minor must see pristine data.
        second = await load_requirements_for_major(db, "Computer Science", "General")
        assert second is not first
        ulc_second = next(g for g in second.groups if g.id == "ulc")
        assert "MATH3" not in ulc_second.requirements[0].prefix_patterns
        assert "MATH4" not in ulc_second.requirements[0].prefix_patterns
        assert "FAKE999" not in second.groups[0].requirements[0].course_options
        # Still served from cache — no extra DB round-trip.
        assert db.calls == 1
