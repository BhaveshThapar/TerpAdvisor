"""Tests for the circuit breaker pattern implementation."""

import asyncio
import pytest

from app.integrations.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_passes_through_in_closed_state(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        assert cb.state == CircuitState.CLOSED

        async def success():
            return "success"

        result = await cb.call(success)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        async def failing():
            raise ConnectionError("API down")

        # Fail twice to open the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(failing)

        assert cb.state == CircuitState.OPEN

        # Next call should fast-fail with CircuitOpenError
        with pytest.raises(CircuitOpenError):
            await cb.call(failing)

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        async def failing():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await cb.call(failing)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_on_successful_half_open_call(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        async def failing():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await cb.call(failing)

        await asyncio.sleep(0.15)  # Enter HALF_OPEN

        async def success():
            return "recovered"

        result = await cb.call(success)
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED
