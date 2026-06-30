from pydantic import model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine.url import make_url

# libpq-style SSL params understood by psycopg2 but rejected by asyncpg.
# We strip them from the URLs and re-apply SSL via connect_args instead.
_SSL_QUERY_KEYS = ["sslmode", "channel_binding", "ssl"]


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://terpadvisor:terpadvisor_dev@localhost:5432/terpadvisor"
    database_url_sync: str = ""
    database_ssl: bool = False

    @model_validator(mode="after")
    def _normalize_db_urls(self) -> "Settings":
        # Accept a verbatim provider URL (e.g. Neon's "postgresql://...?sslmode=require")
        # and turn it into driver-correct async/sync URLs with SSL handled in connect_args.
        async_url = make_url(self.database_url)
        ssl_in_url = any(k in async_url.query for k in _SSL_QUERY_KEYS)
        async_url = async_url.difference_update_query(_SSL_QUERY_KEYS)
        if async_url.drivername == "postgresql":
            async_url = async_url.set(drivername="postgresql+asyncpg")
        self.database_url = async_url.render_as_string(hide_password=False)

        if self.database_url_sync:
            sync_url = make_url(self.database_url_sync).difference_update_query(_SSL_QUERY_KEYS)
        else:
            sync_url = async_url.set(drivername=async_url.drivername.replace("+asyncpg", ""))
        self.database_url_sync = sync_url.render_as_string(hide_password=False)

        if ssl_in_url or (async_url.host or "").endswith("neon.tech"):
            self.database_ssl = True
        return self

    # Demo mode — bypass auth for local development (must be explicitly enabled)
    demo_mode: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    # Set false to run without Redis — cache calls compute directly (fail-open by design).
    cache_enabled: bool = True

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"

    # External APIs
    planetterp_base_url: str = "https://planetterp.com/api/v1"
    umdio_base_url: str = "https://api.umd.io/v1"

    # Circuit breaker defaults
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 30
    circuit_breaker_half_open_max_calls: int = 3

    # Rate limiter
    planetterp_rate_limit: int = 10  # requests per second
    umdio_rate_limit: int = 20

    # Cache TTLs (seconds)
    cache_ttl_course: int = 86400  # 24 hours
    cache_ttl_grades: int = 86400
    cache_ttl_professor: int = 86400
    cache_ttl_recommendations: int = 3600  # 1 hour
    lru_cache_maxsize: int = 1000

    # Auth
    secret_key: str = "dev-secret-key-change-in-production"
    google_client_id: str = ""
    google_client_secret: str = ""

    model_config = {"env_prefix": "", "case_sensitive": False, "env_file": ".env"}


settings = Settings()
