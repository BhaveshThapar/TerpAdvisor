from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://terpadvisor:terpadvisor_dev@localhost:5432/terpadvisor"
    database_url_sync: str = ""

    @model_validator(mode="after")
    def _derive_sync_url(self) -> "Settings":
        if not self.database_url_sync:
            self.database_url_sync = self.database_url.replace("+asyncpg", "")
        return self

    # Demo mode — bypass auth for local development (must be explicitly enabled)
    demo_mode: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Redis
    redis_url: str = "redis://localhost:6379/0"

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
