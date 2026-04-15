#!/usr/bin/env python3
"""
Seed the `majors` table from the in-memory MAJOR_BUILDERS dict.

Usage:
    cd backend
    python scripts/seed_majors.py

Idempotent: re-running upserts each (name, catalog_year, track) row.
Also importable: main.py's lifespan calls seed_majors() on startup when
the majors table is empty.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SyncSession
from app.engine.degree_audit import MAJOR_BUILDERS, build_cs_requirements
from app.engine.requirements_loader import requirements_to_dict
from app.models.major import Major

logger = logging.getLogger(__name__)

CS_TRACKS = ("General", "Cybersecurity", "Data Science", "Machine Learning", "Quantum Information")

DEPT_CODES = {
    "Computer Science": "CMSC",
    "Mathematics": "MATH",
    "Information Science": "INST",
    "Economics": "ECON",
    "Biological Sciences": "BSCI",
    "Mechanical Engineering": "ENME",
}


def _upsert(session: Session, name: str, track: str, reqs_dict: dict) -> bool:
    catalog_year = reqs_dict.get("catalog_year", "2025")
    existing = session.execute(
        select(Major).where(
            Major.name == name, Major.track == track, Major.catalog_year == catalog_year
        )
    ).scalar_one_or_none()

    if existing is None:
        session.add(
            Major(
                name=name,
                code=DEPT_CODES.get(name),
                catalog_year=catalog_year,
                track=track,
                requirements=reqs_dict,
            )
        )
        return True

    existing.requirements = reqs_dict
    existing.code = DEPT_CODES.get(name)
    return False


def seed_majors(session: Session) -> tuple[int, int]:
    """Upsert every known major/track into the majors table.

    Returns (inserted, updated). Caller owns the commit.
    """
    inserted = 0
    updated = 0
    for major_name, builder in MAJOR_BUILDERS.items():
        if builder is build_cs_requirements:
            for track in CS_TRACKS:
                reqs = builder(track=track)
                if _upsert(session, major_name, track, requirements_to_dict(reqs)):
                    inserted += 1
                else:
                    updated += 1
        else:
            reqs = builder()
            track = reqs.track or "General"
            if _upsert(session, major_name, track, requirements_to_dict(reqs)):
                inserted += 1
            else:
                updated += 1
    return inserted, updated


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SyncSession() as session:
        inserted, updated = seed_majors(session)
        session.commit()
    print(f"Done. inserted={inserted} updated={updated}")


if __name__ == "__main__":
    main()
