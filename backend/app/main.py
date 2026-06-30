"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlalchemy as sa

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api import courses, majors, professors, recommendations, schedule
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create any missing tables (no Alembic migrations)
    import asyncio
    import logging

    from sqlalchemy import select, func

    from app.db.session import engine, Base, SyncSession
    import app.models  # noqa: F401 — registers all mapped classes with Base
    from app.models.major import Major

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed majors table if empty so /api/majors returns data on a fresh DB.
    def _seed_if_empty() -> tuple[int, int] | None:
        from scripts.seed_majors import seed_majors

        with SyncSession() as session:
            count = session.execute(select(func.count()).select_from(Major)).scalar_one()
            if count > 0:
                return None
            result = seed_majors(session)
            session.commit()
            return result

    try:
        result = await asyncio.to_thread(_seed_if_empty)
        if result is not None:
            inserted, updated = result
            logging.getLogger("terpadvisor").info(
                "Seeded majors table: inserted=%d updated=%d", inserted, updated
            )
    except Exception:
        logging.getLogger("terpadvisor").exception("Failed to auto-seed majors table")

    yield
    # Shutdown: close connections


app = FastAPI(
    title="TerpAdvisor API",
    description=(
        "Intelligent course recommendation engine for UMD students. "
        "Combines DAG-based prerequisite resolution, hybrid recommendation scoring, "
        "and CSP-based schedule optimization."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger("terpadvisor").exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Register route handlers
app.include_router(courses.router)
app.include_router(recommendations.router)
app.include_router(schedule.router)
app.include_router(professors.router)
app.include_router(majors.router)


@app.get("/api/health")
async def health_check():
    from app.db.session import engine
    health = {"status": "healthy", "version": "0.1.0"}
    try:
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        health["database"] = "connected"
    except Exception:
        health["status"] = "degraded"
        health["database"] = "unreachable"
    if not settings.cache_enabled:
        health["redis"] = "disabled"
        return health
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        health["redis"] = "connected"
    except Exception:
        health["status"] = "degraded"
        health["redis"] = "unreachable"
    return health
