import json
import logging
import math
import random
import time
from typing import Any, Callable, Coroutine

from app.cache.multi_layer import MultiLayerCache

logger = logging.getLogger(__name__)

# Internal wrapper stored in the cache so we can carry metadata alongside the
# actual value.
_META_PREFIX = "__stampede__"


def should_recompute(expiry: float, delta: float, beta: float = 1.0) -> bool:
    """XFetch probabilistic early-expiration check.

    Returns ``True`` when this request should proactively recompute the value
    *before* the entry actually expires, spreading recomputation load across
    time.

    Formula:  now - (delta * beta * ln(random())) > expiry

    ``delta`` is the wallclock time the computation took last time (seconds).
    ``beta`` >= 1.0 controls how eagerly we recompute (higher = earlier).
    """
    # random.random() is in (0, 1]; we clamp to avoid log(0).
    r = max(random.random(), 1e-12)
    gap = delta * beta * math.log(r)  # negative value
    return time.time() - gap > expiry


class StampedeProtectedCache:
    """Wraps :class:`MultiLayerCache` with XFetch stampede protection.

    Each cached entry is stored as a JSON envelope::

        {"v": <actual_value>, "exp": <unix_expiry>, "delta": <compute_seconds>}

    On reads the XFetch algorithm probabilistically decides whether this
    particular request should recompute the value early.  A Redis ``SETNX``
    distributed lock ensures that at most one worker recomputes at a time.
    """

    LOCK_PREFIX = "stampede:lock:"
    LOCK_TTL = 30  # seconds

    def __init__(self, cache: MultiLayerCache) -> None:
        self._cache = cache

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Coroutine[Any, Any, Any]],
        ttl: int = 3600,
        delta: float = 1.0,
        beta: float = 1.0,
    ) -> Any:
        """Return the cached value for *key*, recomputing if necessary.

        Parameters
        ----------
        key:
            Cache key.
        compute_fn:
            Async callable that produces the value when the cache is cold or
            XFetch decides an early refresh is needed.
        ttl:
            Time-to-live in seconds for the cached entry.
        delta:
            Estimated computation time in seconds (used by XFetch).
        beta:
            XFetch aggressiveness parameter (>= 1.0).
        """
        envelope = await self._cache.get(key)

        if envelope is not None and isinstance(envelope, dict) and _META_PREFIX in envelope:
            value = envelope["v"]
            expiry = envelope["exp"]
            cached_delta = envelope["delta"]

            # If the entry has not hard-expired and XFetch says "don't
            # recompute", return the cached value immediately.
            if not should_recompute(expiry, cached_delta, beta):
                return value

            # XFetch says this request should try to recompute early.
            # Acquire a distributed lock so only one worker does the work.
            lock_key = f"{self.LOCK_PREFIX}{key}"
            acquired = await self._cache._redis.set(
                lock_key, "1", nx=True, ex=self.LOCK_TTL
            )
            if not acquired:
                # Another worker is already recomputing; return stale value.
                return value

            logger.info("XFetch triggered early recompute for %s", key)
        else:
            # Cache miss -- we *must* compute.  Grab the lock to prevent
            # thundering-herd on a cold key.
            lock_key = f"{self.LOCK_PREFIX}{key}"
            acquired = await self._cache._redis.set(
                lock_key, "1", nx=True, ex=self.LOCK_TTL
            )
            if not acquired and envelope is not None:
                # Somebody else is computing; return whatever stale data we had.
                if isinstance(envelope, dict) and "v" in envelope:
                    return envelope["v"]
                return envelope

        # Perform the actual computation.
        try:
            start = time.monotonic()
            value = await compute_fn()
            elapsed = time.monotonic() - start

            new_envelope: dict[str, Any] = {
                _META_PREFIX: True,
                "v": value,
                "exp": time.time() + ttl,
                "delta": elapsed,
            }
            await self._cache.set(key, new_envelope, ttl)
            return value
        finally:
            # Always release the lock.
            lock_key = f"{self.LOCK_PREFIX}{key}"
            try:
                await self._cache._redis.delete(lock_key)
            except Exception:
                logger.warning("Failed to release stampede lock for %s", key, exc_info=True)
