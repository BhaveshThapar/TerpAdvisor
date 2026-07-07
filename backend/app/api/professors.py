"""Professor search and detail API endpoints."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Professor, Review
from app.schemas.schemas import ProfessorDetailResponse, ProfessorResponse, ReviewResponse

router = APIRouter(prefix="/api/professors", tags=["professors"])

logger = logging.getLogger("terpadvisor")

PLANETTERP_BASE = "https://planetterp.com/api/v1"


@router.get("/search", response_model=list[ProfessorResponse])
async def search_professors(
    q: str = Query(..., min_length=1),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Professor).where(Professor.name.ilike(f"%{q}%")).limit(10)
    )
    profs = result.scalars().all()
    return [
        ProfessorResponse(
            name=p.name,
            slug=p.slug,
            avg_rating=p.avg_rating,
            review_count=p.review_count,
            courses_taught=p.courses_taught or [],
        )
        for p in profs
    ]


@router.get("/{slug}", response_model=ProfessorDetailResponse)
async def get_professor(
    slug: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    # Try exact slug first, then normalised variants (hyphens ↔ underscores)
    slug_variants = {slug, slug.replace("-", "_"), slug.replace("_", "-")}
    prof = None
    for variant in slug_variants:
        result = await db.execute(select(Professor).where(Professor.slug == variant))
        prof = result.scalar_one_or_none()
        if prof:
            break

    if not prof:
        # Last resort: fuzzy name search (slug → probable name)
        name_guess = slug.replace("-", " ").replace("_", " ")
        result = await db.execute(
            select(Professor).where(Professor.name.ilike(f"%{name_guess}%")).limit(1)
        )
        prof = result.scalar_one_or_none()

    if not prof:
        # Not in our DB — fetch live from PlanetTerp for display only. A GET must be
        # side-effect-free; persist via POST /api/professors/{slug}/sync instead.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{PLANETTERP_BASE}/professor",
                    params={"name": name_guess, "reviews": "true"},
                )
            if resp.status_code == 200:
                data = resp.json()
                live_reviews = data.get("reviews", []) or []
                return ProfessorDetailResponse(
                    name=data.get("name") or name_guess,
                    slug=slug,
                    avg_rating=data.get("average_rating"),
                    review_count=len(live_reviews),
                    courses_taught=data.get("courses", []) or [],
                    reviews=[
                        ReviewResponse(
                            rating=int(r["rating"]) if r.get("rating") is not None else None,
                            text=r.get("review") or "",
                            professor=data.get("name") or name_guess,
                            created_at=r.get("created"),
                        )
                        for r in live_reviews
                        if r.get("rating") is not None or r.get("review")
                    ],
                )
        except Exception:
            logger.warning("Live professor fetch failed for %s", slug, exc_info=True)

    if not prof:
        raise HTTPException(status_code=404, detail=f"Professor '{slug}' not found")

    rev_result = await db.execute(
        select(Review)
        .where(Review.professor_id == prof.id)
        .order_by(Review.created_at.desc())
        .limit(20)
    )
    db_reviews = rev_result.scalars().all()

    # Count actual reviews in DB; fall back to PlanetTerp stored count
    count_result = await db.execute(
        select(func.count()).where(Review.professor_id == prof.id)
    )
    db_review_count = count_result.scalar() or 0

    # If DB has no linked review text, fetch live from PlanetTerp for display only
    # (no persistence — a GET must stay side-effect-free).
    live_reviews: list[dict] = []
    live_review_count: int | None = None
    live_avg_rating: float | None = None
    if not db_reviews:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{PLANETTERP_BASE}/professor",
                    params={"name": prof.name, "reviews": "true"},
                )
            if resp.status_code == 200:
                data = resp.json()
                live_reviews = data.get("reviews", []) or []
                live_review_count = len(live_reviews)
                live_avg_rating = data.get("average_rating")
        except Exception:
            logger.warning("Live professor review fetch failed for %s", prof.slug, exc_info=True)

    review_count = db_review_count if db_review_count > 0 else (live_review_count or prof.review_count)

    # Compute avg_rating: stored value → live value → average of local reviews.
    avg_rating = prof.avg_rating
    if avg_rating is None:
        avg_rating = live_avg_rating
    if avg_rating is None and db_reviews:
        rated = [r.rating for r in db_reviews if r.rating is not None]
        if rated:
            avg_rating = sum(rated) / len(rated)

    # Build unified review list: prefer DB rows, fall back to live PlanetTerp data
    if db_reviews:
        review_list = [
            ReviewResponse(
                rating=r.rating,
                text=r.text or "",
                professor=prof.name,
                created_at=str(r.created_at) if r.created_at else None,
            )
            for r in db_reviews
        ]
    else:
        review_list = [
            ReviewResponse(
                rating=int(r["rating"]) if r.get("rating") is not None else None,
                text=r.get("review") or "",
                professor=prof.name,
                created_at=r.get("created"),
            )
            for r in live_reviews
            if r.get("rating") is not None or r.get("review")
        ]

    return ProfessorDetailResponse(
        name=prof.name,
        slug=prof.slug,
        avg_rating=avg_rating,
        review_count=review_count,
        courses_taught=prof.courses_taught or [],
        reviews=review_list,
    )


@router.post("/{slug}/sync")
async def sync_professor(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-sync a professor's review_count and avg_rating from PlanetTerp."""
    import asyncio
    from app.workers.etl.planetterp_etl import PlanetTerpETL

    # Resolve professor
    slug_variants = {slug, slug.replace("-", "_"), slug.replace("_", "-")}
    prof = None
    for variant in slug_variants:
        result = await db.execute(select(Professor).where(Professor.slug == variant))
        prof = result.scalar_one_or_none()
        if prof:
            break
    if not prof:
        name_guess = slug.replace("-", " ").replace("_", " ")
        result = await db.execute(
            select(Professor).where(Professor.name.ilike(f"%{name_guess}%")).limit(1)
        )
        prof = result.scalar_one_or_none()
    if not prof:
        raise HTTPException(status_code=404, detail=f"Professor '{slug}' not found")

    loop = asyncio.get_event_loop()
    etl = PlanetTerpETL()
    await loop.run_in_executor(None, lambda: _run_prof_sync(etl, prof.name))
    await db.refresh(prof)
    return {"success": True, "name": prof.name, "review_count": prof.review_count, "avg_rating": prof.avg_rating}


def _run_prof_sync(etl, prof_name: str):
    from app.db.session import SyncSession
    with SyncSession() as session:
        etl._sync_professor(session, prof_name)
        session.commit()
