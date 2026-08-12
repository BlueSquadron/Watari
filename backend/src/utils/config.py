"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and `.env` file.

    All fields have sensible defaults for local development. Production
    deployments MUST override secrets via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://watari:watari_dev_password@postgres:5432/watari"
    )

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # S3 / MinIO
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "watari-evidence"

    # JWT
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # App
    app_env: str = "development"
    app_debug: bool = True

    # Default admin bootstrap
    default_admin_username: str = "admin"
    default_admin_password: str = "admin"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    The instance is cached to avoid re-parsing environment variables on each
    access. Use this accessor everywhere instead of instantiating `Settings`
    directly so tests can override via `get_settings.cache_clear()`.
    """
    return Settings()
