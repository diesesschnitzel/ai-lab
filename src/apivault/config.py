from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://apivault:apivault@db:5432/apivault"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # App
    app_name: str = "APIVault"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
