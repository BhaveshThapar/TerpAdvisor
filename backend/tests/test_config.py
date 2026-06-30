from app.config import Settings


def make_settings(**kwargs) -> Settings:
    # _env_file=None keeps tests hermetic against the local .env (which points at Neon).
    return Settings(_env_file=None, **kwargs)


def test_local_url_unchanged_and_no_ssl():
    s = make_settings(database_url="postgresql+asyncpg://u:p@localhost:5432/db")
    assert s.database_url == "postgresql+asyncpg://u:p@localhost:5432/db"
    assert s.database_url_sync == "postgresql://u:p@localhost:5432/db"
    assert s.database_ssl is False


def test_neon_libpq_url_is_normalized():
    # The string a user pastes straight from the Neon console.
    s = make_settings(
        database_url=(
            "postgresql://neondb_owner:pw@ep-x-pooler.c-6.us-east-1.aws.neon.tech"
            "/neondb?sslmode=require&channel_binding=require"
        )
    )
    # asyncpg driver added, SSL params stripped from the URL.
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in s.database_url
    assert "channel_binding" not in s.database_url
    # Sync URL derived without the async driver and without SSL params.
    assert s.database_url_sync.startswith("postgresql://")
    assert "asyncpg" not in s.database_url_sync
    assert "sslmode" not in s.database_url_sync
    # SSL auto-enabled (params present + neon.tech host).
    assert s.database_ssl is True


def test_explicit_sync_url_keeps_async_url_async():
    s = make_settings(
        database_url="postgresql+asyncpg://u:p@host/db",
        database_url_sync="postgresql://u:p@host/db?sslmode=require",
    )
    assert s.database_url == "postgresql+asyncpg://u:p@host/db"
    assert "sslmode" not in s.database_url_sync


def test_ssl_enabled_for_neon_host_without_params():
    s = make_settings(database_url="postgresql+asyncpg://u:p@ep-x.c-6.us-east-1.aws.neon.tech/neondb")
    assert s.database_ssl is True
