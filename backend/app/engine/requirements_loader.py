"""
Dynamic requirement catalog loader.

Loads DegreeRequirements trees from the `majors` table with an in-process TTL
cache. Falls back to the in-memory `MAJOR_BUILDERS` dict when a major is not
seeded yet, then to Computer Science as a last resort.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.degree_audit import (
    DegreeRequirements,
    MAJOR_BUILDERS,
    Requirement,
    RequirementGroup,
    RequirementType,
    build_cs_requirements,
)
from app.models.major import Major

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600
# Cache stores the *dict* form, never live DegreeRequirements objects.
# Each call to load_requirements_for_major() rebuilds a fresh object so
# callers can mutate their copy (e.g. /audit's minor_prefix injection)
# without leaking state into other requests. See test_requirements_loader.
_cache: dict[tuple[str, str], tuple[dict[str, Any], float]] = {}


def requirements_to_dict(reqs: DegreeRequirements) -> dict[str, Any]:
    return {
        "major": reqs.major,
        "catalog_year": reqs.catalog_year,
        "track": reqs.track,
        "total_credits_required": reqs.total_credits_required,
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "min_requirements_satisfied": g.min_requirements_satisfied,
                "counts_toward_total": g.counts_toward_total,
                "requirements": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "type": r.type.value,
                        "course_options": list(r.course_options),
                        "credits_needed": r.credits_needed,
                        "courses_needed": r.courses_needed,
                        "description": r.description,
                        "prefix_patterns": list(r.prefix_patterns),
                    }
                    for r in g.requirements
                ],
            }
            for g in reqs.groups
        ],
    }


def requirements_from_dict(data: dict[str, Any]) -> DegreeRequirements:
    return DegreeRequirements(
        major=data["major"],
        catalog_year=data["catalog_year"],
        track=data.get("track", "General"),
        total_credits_required=data.get("total_credits_required", 120),
        groups=[
            RequirementGroup(
                id=g["id"],
                name=g["name"],
                description=g.get("description", ""),
                min_requirements_satisfied=g.get("min_requirements_satisfied"),
                counts_toward_total=g.get("counts_toward_total", True),
                requirements=[
                    Requirement(
                        id=r["id"],
                        name=r["name"],
                        type=RequirementType(r["type"]),
                        course_options=list(r.get("course_options", [])),
                        credits_needed=r["credits_needed"],
                        courses_needed=r.get("courses_needed", 1),
                        description=r.get("description", ""),
                        prefix_patterns=list(r.get("prefix_patterns", [])),
                    )
                    for r in g.get("requirements", [])
                ],
            )
            for g in data.get("groups", [])
        ],
    )


def _build_from_memory(major: str, track: str) -> DegreeRequirements:
    builder = MAJOR_BUILDERS.get(major)
    if builder is None:
        logger.warning(
            "No requirements in DB or MAJOR_BUILDERS for major=%r; falling back to Computer Science",
            major,
        )
        return build_cs_requirements(track=track)
    if builder is build_cs_requirements:
        return builder(track=track)
    return builder()


async def load_requirements_for_major(
    db: AsyncSession, major: str, track: str = "General"
) -> DegreeRequirements:
    """Load requirements for a major/track, caching results for an hour.

    Returns a *fresh* DegreeRequirements object on every call (built from a
    cached dict), so endpoint-level mutations can never leak across requests.
    """
    cache_key = (major, track)
    cached = _cache.get(cache_key)
    now = time.time()
    if cached and cached[1] > now:
        return requirements_from_dict(cached[0])

    result = await db.execute(
        select(Major).where(Major.name == major, Major.track == track)
    )
    row = result.scalar_one_or_none()

    if row is None and track != "General":
        result = await db.execute(
            select(Major).where(Major.name == major, Major.track == "General")
        )
        row = result.scalar_one_or_none()

    if row is not None:
        reqs_dict = row.requirements
    else:
        logger.warning(
            "majors table miss for major=%r track=%r; using in-memory builder",
            major,
            track,
        )
        reqs_dict = requirements_to_dict(_build_from_memory(major, track))

    _cache[cache_key] = (reqs_dict, now + _CACHE_TTL_SECONDS)
    return requirements_from_dict(reqs_dict)


def clear_cache() -> None:
    _cache.clear()
