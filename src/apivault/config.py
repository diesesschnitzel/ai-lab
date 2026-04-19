"""APIVault configuration via Pydantic settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://apivault:apivault@localhost:5432/apivault"
    database_pool_min: int = 2
    database_pool_max: int = 20
    database_pool_timeout: int = 30

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2
    admin_key: str = ""
    cors_origins: str = "*"

    # Validation
    validation_concurrency: int = 50
    validation_timeout_connect_seconds: float = 5.0
    validation_timeout_read_seconds: float = 10.0
    validation_dns_timeout_seconds: float = 3.0
    validation_recheck_interval_days: int = 7
    validation_dead_retry_days: int = 3
    validation_dead_max_retries: int = 10
    validation_batch_size: int = 100

    # Monitoring
    log_level: str = "INFO"
    log_format: str = "json"


settings = Settings()
