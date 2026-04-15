"""Majors discovery API."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.major import Major
from app.schemas.schemas import MajorSummary

router = APIRouter(prefix="/api/majors", tags=["majors"])


@router.get("", response_model=list[MajorSummary])
async def list_majors(db: AsyncSession = Depends(get_db)) -> list[MajorSummary]:
    result = await db.execute(
        select(Major.name, Major.code, Major.track).order_by(Major.name, Major.track)
    )
    grouped: dict[str, MajorSummary] = {}
    for name, code, track in result.all():
        entry = grouped.get(name)
        if entry is None:
            grouped[name] = MajorSummary(name=name, code=code, tracks=[track])
        elif track not in entry.tracks:
            entry.tracks.append(track)
    return list(grouped.values())
