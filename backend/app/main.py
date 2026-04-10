"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlalchemy as sa

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api import courses, professors, recommendations, schedule
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create any missing tables (no Alembic migrations)
    from app.db.session import engine, Base
    import app.models  # noqa: F401 — registers all mapped classes with Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
