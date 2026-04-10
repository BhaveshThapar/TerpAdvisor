import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""


class CircuitOpenError(CircuitBreakerError):
    """Raised when the circuit is open and calls are being fast-failed."""

    def __init__(self, recovery_time: float):
        remaining = max(0.0, recovery_time - time.monotonic())
        super().__init__(
            f"Circuit is OPEN. Retry after {remaining:.1f}s"
        )
        self.recovery_time = recovery_time


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Async circuit breaker that wraps unreliable coroutine calls.

    Tracks failures within a sliding time window. When the failure count
    reaches *failure_threshold*, the circuit opens and all subsequent calls
    are fast-failed with CircuitOpenError until *recovery_timeout* seconds
    have elapsed. After the timeout the circuit enters the half-open state
    and allows up to *half_open_max_calls* probe calls. A successful probe
    closes the circuit; a failing probe reopens it.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        window_size: float = 60.0,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._window_size = window_size

        self._state = CircuitState.CLOSED
        self._failures: deque[float] = deque()
        self._last_failure_time: float | None = None
        self._opened_at: float | None = None
        self._half_open_calls: int = 0
        self._lock = asyncio.Lock()

    # -- public properties ---------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current state, accounting for automatic OPEN -> HALF_OPEN transition."""
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self._recovery_timeout
        ):
            return CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        self._prune_window()
        return len(self._failures)

    @property
    def last_failure_time(self) -> float | None:
        return self._last_failure_time

    # -- core method ---------------------------------------------------------

    async def call(self, coro_fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """Execute *coro_fn* with circuit breaker protection.

        Returns the coroutine's result on success or raises the original
        exception (in CLOSED / HALF_OPEN) or CircuitOpenError (in OPEN).
        """
        async with self._lock:
            current = self.state

            if current == CircuitState.OPEN:
                assert self._opened_at is not None
                raise CircuitOpenError(self._opened_at + self._recovery_timeout)

            if current == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max_calls:
                    # All probe slots used up; treat as still open.
                    raise CircuitOpenError(self._opened_at + self._recovery_timeout)  # type: ignore[operator]
                self._half_open_calls += 1

        # Call runs outside the lock so it doesn't block other callers.
        try:
            result = await coro_fn(*args, **kwargs)
        except Exception:
            await self._record_failure()
            raise

        await self._record_success()
        return result

    # -- internals -----------------------------------------------------------

    async def _record_failure(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._failures.append(now)
            self._last_failure_time = now
            self._prune_window()

            if self._state == CircuitState.HALF_OPEN:
                self._trip()
            elif len(self._failures) >= self._failure_threshold:
                self._trip()

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN or self.state == CircuitState.HALF_OPEN:
                self._reset()

    def _trip(self) -> None:
        """Transition to OPEN."""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._half_open_calls = 0

    def _reset(self) -> None:
        """Transition to CLOSED and clear failure history."""
        self._state = CircuitState.CLOSED
        self._failures.clear()
        self._opened_at = None
        self._half_open_calls = 0

    def _prune_window(self) -> None:
        """Remove failure timestamps that have fallen outside the sliding window."""
        cutoff = time.monotonic() - self._window_size
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
