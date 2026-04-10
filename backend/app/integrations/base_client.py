import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.integrations.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """Abstract resilient API client.

    Subclasses implement ``_get_stale_from_db`` and expose domain-specific
    methods that delegate to ``_request``.

    The request pipeline is:

        1. Acquire a rate-limiter token.
        2. Try the live API call through the circuit breaker.
        3. On failure, attempt a Redis cache lookup.
        4. On cache miss, fall back to stale Postgres data.
        5. Return ``None`` as the last resort.
    """

    base_url: str = ""

    def __init__(
        self,
        circuit_breaker: CircuitBreaker,
        rate_limiter: RateLimiter,
        redis: Redis,
        db: AsyncSession,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._cb = circuit_breaker
        self._rl = rate_limiter
        self._redis = redis
        self._db = db
        self._http = http_client or httpx.AsyncClient(timeout=10.0)

    # -- request pipeline ----------------------------------------------------

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
        cache_ttl: int = 86400,
        stale_key: str | None = None,
    ) -> Any | None:
        """Execute the full resilience pipeline for a single GET request.

        *stale_key* is forwarded to ``_get_stale_from_db`` so subclasses can
        look up the right row when both Redis and the live API are down.
        """
        url = f"{self.base_url}{path}"
        generated_cache_key = cache_key or self._cache_key(url, params)

        # 1. Rate limit
        await self._rl.acquire()

        # 2. Try the live API through the circuit breaker
        try:
            data = await self._cb.call(self._do_get, url, params)
            # Successful call -- cache the response.
            await self._set_cache(generated_cache_key, data, ttl=cache_ttl)
            return data
        except CircuitOpenError:
            logger.warning("Circuit open for %s -- falling back to cache", url)
        except Exception:
            logger.exception("Live request failed for %s", url)

        # 3. Redis cache fallback
        cached = await self._get_from_cache(generated_cache_key)
        if cached is not None:
            logger.info("Serving cached response for %s", generated_cache_key)
            return cached

        # 4. Postgres stale data fallback
        stale = await self._get_stale_from_db(stale_key or generated_cache_key)
        if stale is not None:
            logger.info("Serving stale DB data for %s", stale_key or generated_cache_key)
            return stale

        # 5. Nothing available
        logger.error("All fallbacks exhausted for %s", url)
        return None

    # -- HTTP helper ---------------------------------------------------------

    async def _do_get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._http.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # -- cache helpers -------------------------------------------------------

    @staticmethod
    def _cache_key(url: str, params: dict[str, Any] | None = None) -> str:
        """Deterministic Redis key from URL + sorted query params."""
        raw = url
        if params:
            raw += "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return "api_cache:" + hashlib.sha256(raw.encode()).hexdigest()

    async def _get_from_cache(self, key: str) -> Any | None:
        try:
            raw = await self._redis.get(key)
            if raw is not None:
                return json.loads(raw)
        except Exception:
            logger.warning("Redis read failed for key %s", key, exc_info=True)
        return None

    async def _set_cache(self, key: str, data: Any, *, ttl: int = 86400) -> None:
        try:
            await self._redis.set(key, json.dumps(data), ex=ttl)
        except Exception:
            logger.warning("Redis write failed for key %s", key, exc_info=True)

    # -- abstract fallback ---------------------------------------------------

    @abstractmethod
    async def _get_stale_from_db(self, key: str) -> Any | None:
        """Return stale data from Postgres for the given logical key."""
        ...
