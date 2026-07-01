from app.main import app


def _health_route():
    return next(r for r in app.routes if getattr(r, "path", None) == "/api/health")


def test_health_route_allows_get_and_head():
    # HEAD support lets HEAD-only uptime monitors probe /api/health without a 405.
    methods = _health_route().methods
    assert "GET" in methods
    assert "HEAD" in methods
