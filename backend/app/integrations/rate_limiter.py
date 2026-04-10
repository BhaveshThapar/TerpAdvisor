import asyncio
import time


class RateLimiter:
    """Async token-bucket rate limiter.

    Tokens are added at *rate* tokens per second up to a maximum of
    *max_tokens*.  ``acquire()`` waits without blocking the event loop
    until a token is available.
    """

    def __init__(self, rate: float, max_tokens: int | None = None):
        self._rate = rate
        self._max_tokens = float(max_tokens if max_tokens is not None else int(rate))
        self._tokens = self._max_tokens
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Calculate how long until the next token arrives.
                wait = (1.0 - self._tokens) / self._rate

            await asyncio.sleep(wait)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rate)
        self._last_refill = now
