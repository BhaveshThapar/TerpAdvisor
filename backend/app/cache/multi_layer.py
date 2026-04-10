import json
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from redis.asyncio import Redis
from sqlalchemy import Column, DateTime, String, Text, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import Base

logger = logging.getLogger(__name__)


class CacheEntry(Base):
    """Persistent cache table in PostgreSQL (Layer 3)."""

    __tablename__ = "cache_entries"

    key: str = Column(String(512), primary_key=True)
    value: str = Column(Text, nullable=False)
    expires_at: datetime = Column(DateTime(timezone=True), nullable=False)
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TTLLRUCache:
    """Thread-safe LRU cache with per-entry TTL, backed by OrderedDict."""

    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value or None if missing/expired.

        Moves the entry to the end (most-recently-used) on a hit.
        Expired entries are removed lazily on access.
        """
        with self._lock:
            if key not in self._data:
                return None
            value, expiry = self._data[key]
            if time.time() > expiry:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        """Insert or update an entry.  Evicts the oldest entry when full."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (value, time.time() + ttl)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys whose name contains *pattern* (simple substring match).

        Returns the number of deleted entries.
        """
        import fnmatch

        with self._lock:
            matching = [k for k in self._data if fnmatch.fnmatch(k, pattern)]
            for k in matching:
                del self._data[k]
            return len(matching)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class MultiLayerCache:
    """Three-tier cache: in-process LRU -> Redis -> PostgreSQL.

    Values are serialised to JSON for cross-layer compatibility.
    """

    def __init__(
        self,
        redis_client: Redis,
        db_session_factory: async_sessionmaker[AsyncSession],
        lru_maxsize: int = 1000,
    ) -> None:
        self._redis = redis_client
        self._db_session_factory = db_session_factory
        self._lru = TTLLRUCache(maxsize=lru_maxsize)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[Any]:
        """Look up *key* across all three layers, promoting on hit."""

        # Layer 1 - LRU
        value = self._lru.get(key)
        if value is not None:
            logger.debug("Cache HIT (LRU): %s", key)
            return value

        # Layer 2 - Redis
        raw = await self._redis.get(key)
        if raw is not None:
            ttl = await self._redis.ttl(key)
            ttl = max(ttl, 60)  # guard against -1 / -2
            value = json.loads(raw)
            self._lru.set(key, value, ttl)
            logger.debug("Cache HIT (Redis): %s", key)
            return value

        # Layer 3 - PostgreSQL
        value, ttl = await self._pg_get(key)
        if value is not None:
            await self._promote_to_redis(key, value, ttl)
            self._lru.set(key, value, ttl)
            logger.debug("Cache HIT (Postgres): %s", key)
            return value

        logger.debug("Cache MISS: %s", key)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Write *value* to all three layers with the given TTL (seconds)."""
        serialized = json.dumps(value)

        # Layer 1
        self._lru.set(key, value, ttl)

        # Layer 2
        await self._redis.set(key, serialized, ex=ttl)

        # Layer 3
        await self._pg_set(key, serialized, ttl)

    async def invalidate(self, key: str) -> None:
        """Remove *key* from every layer."""
        self._lru.delete(key)
        await self._redis.delete(key)
        await self._pg_delete(key)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Remove all keys matching *pattern* from every layer.

        Uses Redis SCAN to avoid blocking the server and fnmatch-style
        matching for the in-memory LRU.
        """
        # LRU
        self._lru.delete_pattern(pattern)

        # Redis - iterate with SCAN to stay non-blocking
        cursor: int = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match=pattern, count=200
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break

        # PostgreSQL - use LIKE (translate glob '*' to SQL '%')
        sql_pattern = pattern.replace("*", "%")
        async with self._db_session_factory() as session:
            await session.execute(
                delete(CacheEntry).where(CacheEntry.key.like(sql_pattern))
            )
            await session.commit()

    # ------------------------------------------------------------------
    # PostgreSQL helpers
    # ------------------------------------------------------------------

    async def _pg_get(self, key: str) -> tuple[Optional[Any], int]:
        """Fetch from PG cache table.  Returns (value, remaining_ttl)."""
        async with self._db_session_factory() as session:
            result = await session.execute(
                select(CacheEntry).where(CacheEntry.key == key)
            )
            entry: Optional[CacheEntry] = result.scalar_one_or_none()
            if entry is None:
                return None, 0
            remaining = int(
                (entry.expires_at - datetime.now(timezone.utc)).total_seconds()
            )
            if remaining <= 0:
                # Stale-ok: still return data but with a short TTL so upper
                # layers treat it as nearly-expired.
                remaining = 60
            value = json.loads(entry.value)
            return value, remaining

    async def _pg_set(self, key: str, serialized: str, ttl: int) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        async with self._db_session_factory() as session:
            stmt = pg_insert(CacheEntry).values(
                key=key,
                value=serialized,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "value": serialized,
                    "expires_at": expires_at,
                    "created_at": datetime.now(timezone.utc),
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def _pg_delete(self, key: str) -> None:
        async with self._db_session_factory() as session:
            await session.execute(
                delete(CacheEntry).where(CacheEntry.key == key)
            )
            await session.commit()

    async def _promote_to_redis(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._redis.set(key, json.dumps(value), ex=ttl)
        except Exception:
            logger.warning("Failed to promote key %s to Redis", key, exc_info=True)
