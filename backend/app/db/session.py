from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# SSL is applied via connect_args (not the URL) so the same DSN works for both drivers.
# statement_cache_size=0 keeps asyncpg compatible with Neon's pgbouncer pooler endpoint.
_async_connect_args: dict = {"ssl": "require", "statement_cache_size": 0} if settings.database_ssl else {}
_sync_connect_args: dict = {"sslmode": "require"} if settings.database_ssl else {}

# Async engine — used by FastAPI
engine = create_async_engine(
    settings.database_url, echo=False, pool_size=20, max_overflow=10, connect_args=_async_connect_args
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine — used by Celery workers and Alembic
sync_engine = create_engine(settings.database_url_sync, pool_size=5, connect_args=_sync_connect_args)
SyncSession = sessionmaker(sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
