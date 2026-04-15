"""Unit tests for the /api/majors router.

Uses a FakeDB mirror of the existing repo pattern (see
``tests/engine/test_requirements_loader.py``). We test the handler function
directly because the project models use Postgres-specific column types
(``JSONB``, ``UUID``) that don't compile against SQLite, and spinning up
testcontainers for a single endpoint is overkill.
"""

import pytest

from app.api.majors import list_majors
from app.schemas.schemas import MajorSummary


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


@pytest.mark.asyncio
async def test_empty_returns_empty_list():
    db = _FakeDB(rows=[])
    result = await list_majors(db)  # type: ignore[arg-type]
    assert result == []


@pytest.mark.asyncio
async def test_groups_tracks_under_major():
    rows = [
        ("Computer Science", "CMSC", "Cybersecurity"),
        ("Computer Science", "CMSC", "General"),
        ("Mathematics", "MATH", "General"),
    ]
    db = _FakeDB(rows=rows)
    result = await list_majors(db)  # type: ignore[arg-type]

    assert len(result) == 2
    cs = next(m for m in result if m.name == "Computer Science")
    assert isinstance(cs, MajorSummary)
    assert cs.code == "CMSC"
    assert set(cs.tracks) == {"General", "Cybersecurity"}

    math = next(m for m in result if m.name == "Mathematics")
    assert math.code == "MATH"
    assert math.tracks == ["General"]


@pytest.mark.asyncio
async def test_preserves_order_from_query():
    # The endpoint relies on ``ORDER BY name, track`` from the DB. The handler
    # must preserve that order — majors appear in the order they're first
    # encountered, tracks in the order they're seen.
    rows = [
        ("Alpha", None, "General"),
        ("Alpha", None, "Honors"),
        ("Beta", None, "General"),
    ]
    db = _FakeDB(rows=rows)
    result = await list_majors(db)  # type: ignore[arg-type]

    assert [m.name for m in result] == ["Alpha", "Beta"]
    assert result[0].tracks == ["General", "Honors"]


@pytest.mark.asyncio
async def test_dedupes_repeated_track():
    # Defensive: if the same (major, track) appears twice (e.g., multiple
    # catalog years), tracks should still be unique per major.
    rows = [
        ("Computer Science", "CMSC", "General"),
        ("Computer Science", "CMSC", "General"),
    ]
    db = _FakeDB(rows=rows)
    result = await list_majors(db)  # type: ignore[arg-type]

    assert len(result) == 1
    assert result[0].tracks == ["General"]


@pytest.mark.asyncio
async def test_handles_null_code():
    rows = [("Unknown Major", None, "General")]
    db = _FakeDB(rows=rows)
    result = await list_majors(db)  # type: ignore[arg-type]

    assert result[0].code is None
    assert result[0].tracks == ["General"]
