"""Application settings using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reading node configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PERCOLATE_READING_",
        case_sensitive=False,
    )

    # API
    host: str = Field(default="0.0.0.0", description="API server host")
    port: int = Field(default=8001, description="API server port")
    reload: bool = Field(default=False, description="Auto-reload on code changes")

    # Models
    embedding_model: str = Field(
        default="nomic-embed-text-v1.5", description="Embedding model name"
    )
    whisper_model: str = Field(default="base", description="Whisper model size")
    device: str = Field(default="cpu", description="Compute device (cpu/cuda)")

    # Cache
    model_cache_dir: str = Field(
        default="/var/cache/percolate-reading/models", description="Model cache directory"
    )

    # Processing limits
    max_file_size_mb: int = Field(default=100, description="Max upload file size (MB)")
    max_batch_size: int = Field(default=100, description="Max embedding batch size")

    # OpenTelemetry
    otel_enabled: bool = Field(default=False, description="Enable OTEL")
    otel_endpoint: str = Field(
        default="http://localhost:4318", description="OTEL collector endpoint"
    )
    otel_service_name: str = Field(default="percolate-reading", description="Service name")

    # LLM for visual verification (optional)
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")


settings = Settings()
