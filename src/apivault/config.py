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

    # CORS
    cors_origins: str = "*"

    # LLM Enrichment
    llm_provider: str = "ollama"  # "ollama", "openai", or "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2"
    openai_api_key: str = ""
    openai_llm_model: str = "gpt-4o-mini"

    # Embeddings
    embedding_provider: str = "ollama"  # "ollama", "openai", or "none"
    ollama_embedding_model: str = "nomic-embed-text"
    openai_embedding_model: str = "text-embedding-3-small"

    # Enrichment worker
    enrichment_batch_size: int = 20
    enrichment_poll_interval: int = 30  # seconds between queue checks
    enrichment_max_retries: int = 3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
