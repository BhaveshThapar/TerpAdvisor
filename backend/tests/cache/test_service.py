"""Tests for app.cache.service — the fail-open cache entry point.

Uses in-memory stubs for MultiLayerCache and the Redis lock so no external
services are required (consistent with the rest of the suite).
"""

import pytest

from app.cache.service import cached, make_key
from app.cache.stampede import StampedeProtectedCache


class _StubRedis:
    """Just enough of redis.asyncio for the stampede lock."""

    def __init__(self):
        self._data = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    async def delete(self, key):
        self._data.pop(key, None)


class _StubMultiLayer:
    """Dict-backed stand-in for MultiLayerCache (get/set + ._redis)."""

    def __init__(self, fail_on_get=False, fail_on_set=False):
        self._store = {}
        self._redis = _StubRedis()
        self.fail_on_get = fail_on_get
        self.fail_on_set = fail_on_set

    async def get(self, key):
        if self.fail_on_get:
            raise ConnectionError("redis down")
        return self._store.get(key)

    async def set(self, key, value, ttl=3600):
        if self.fail_on_set:
            raise ConnectionError("redis down")
        self._store[key] = value


def _counting_compute(value="result"):
    calls = {"n": 0}

    async def compute():
        calls["n"] += 1
        return value

    return compute, calls


class TestCachedHelper:
    @pytest.mark.asyncio
    async def test_miss_computes_then_hit_skips_compute(self):
        cache = StampedeProtectedCache(_StubMultiLayer())
        compute, calls = _counting_compute({"recs": [1, 2, 3]})

        first = await cached("k1", compute, ttl=60, cache=cache)
        second = await cached("k1", compute, ttl=60, cache=cache)

        assert first == {"recs": [1, 2, 3]}
        assert second == {"recs": [1, 2, 3]}
        assert calls["n"] == 1  # second call served from cache

    @pytest.mark.asyncio
    async def test_fail_open_when_cache_layers_down(self):
        """A cache outage must never break the endpoint."""
        cache = StampedeProtectedCache(_StubMultiLayer(fail_on_get=True))
        compute, calls = _counting_compute("computed")

        assert await cached("k2", compute, ttl=60, cache=cache) == "computed"
        assert calls["n"] >= 1

    @pytest.mark.asyncio
    async def test_write_failure_after_compute_serves_value_without_recompute(self):
        cache = StampedeProtectedCache(_StubMultiLayer(fail_on_set=True))
        compute, calls = _counting_compute("expensive")

        assert await cached("k3", compute, ttl=60, cache=cache) == "expensive"
        assert calls["n"] == 1  # value stashed; not recomputed on write failure

    @pytest.mark.asyncio
    async def test_compute_errors_propagate(self):
        cache = StampedeProtectedCache(_StubMultiLayer())

        async def boom():
            raise ValueError("bad input")

        with pytest.raises(ValueError):
            await cached("k4", boom, ttl=60, cache=cache)


class TestMakeKey:
    def test_deterministic_and_order_insensitive(self):
        a = make_key("rec", {"major": "CS", "top_n": 20, "completed": ["A", "B"]})
        b = make_key("rec", {"top_n": 20, "completed": ["A", "B"], "major": "CS"})
        assert a == b
        assert a.startswith("rec:")

    def test_different_payloads_differ(self):
        a = make_key("rec", {"major": "CS", "top_n": 20})
        b = make_key("rec", {"major": "CS", "top_n": 10})
        assert a != b
