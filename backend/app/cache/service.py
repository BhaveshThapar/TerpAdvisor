"""Application-level cache service.

Thin entry point that wires :class:`MultiLayerCache` (LRU -> Redis -> Postgres)
and :class:`StampedeProtectedCache` (XFetch early-expiry + distributed lock)
into request handlers.

Design goals:
- **Fail open.** If Redis/Postgres are unreachable, ``cached()`` silently
  falls back to computing the value directly. A cache outage must never take
  down an endpoint.
- **Deterministic keys.** ``make_key()`` hashes a canonical JSON form of the
  request payload so the API process and the Celery cache-warming worker
  produce identical keys.
- **Lazy init.** The singleton is built on first use so importing this module
  never opens connections (keeps unit tests hermetic).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Awaitable, Callable

from app.cache.multi_layer import MultiLayerCache
from app.cache.stampede import StampedeProtectedCache
from app.config import settings

logger = logging.getLogger(__name__)

_cache: StampedeProtectedCache | None = None


def build_cache(redis_client=None, session_factory=None) -> StampedeProtectedCache:
    """Construct a StampedeProtectedCache.

    Pass explicit ``redis_client``/``session_factory`` to build an isolated
    instance (used by Celery workers, which need their own event loop and
    engine). With no arguments, uses the application defaults.
    """
    if redis_client is None and settings.redis_enabled:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url)
    if session_factory is None:
        from app.db.session import async_session

        session_factory = async_session
    return StampedeProtectedCache(MultiLayerCache(redis_client, session_factory))


def get_cache() -> StampedeProtectedCache:
    """Return the process-wide cache singleton, building it lazily."""
    global _cache
    if _cache is None:
        _cache = StampedeProtectedCache(_build_default_multilayer())
    return _cache


def _build_default_multilayer() -> MultiLayerCache:
    from app.db.session import async_session

    redis_client = None
    if settings.redis_enabled:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url)
    return MultiLayerCache(redis_client, async_session)


def reset_cache_for_tests() -> None:
    global _cache
    _cache = None


def make_key(prefix: str, payload: Any) -> str:
    """Build a deterministic cache key from a JSON-serialisable payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    return f"{prefix}:{digest}"


_SENTINEL = object()


async def cached(
    key: str,
    compute_fn: Callable[[], Awaitable[Any]],
    ttl: int = 900,
    delta: float = 1.0,
    cache: StampedeProtectedCache | None = None,
) -> Any:
    """Return the cached value for *key*, computing (and storing) on miss.

    Any exception raised by the cache layers themselves (Redis down, Postgres
    cache table unavailable, serialisation issues) is logged and the value is
    computed directly — the caller never sees cache-infrastructure errors.
    Exceptions raised by *compute_fn* always propagate. *compute_fn* must be
    side-effect-free: on cache-layer failure it may be invoked a second time.
    """
    if cache is None and not settings.cache_enabled:
        # No Redis configured (e.g. free single-service deploy) — skip the cache entirely.
        return await compute_fn()

    backend = cache if cache is not None else get_cache()
    state: dict[str, Any] = {"value": _SENTINEL}

    async def _tracked() -> Any:
        value = await compute_fn()
        state["value"] = value
        return value

    try:
        return await backend.get_or_compute(key, _tracked, ttl=ttl, delta=delta)
    except Exception:
        if state["value"] is not _SENTINEL:
            # Compute succeeded but a cache write failed — serve the value.
            logger.warning("Cache write failed for %s; serving computed value", key, exc_info=True)
            return state["value"]
        logger.warning("Cache unavailable for %s; computing directly", key, exc_info=True)
        return await compute_fn()
