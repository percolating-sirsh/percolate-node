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
    workers: int = Field(default=4, description="Number of background workers")

    # Storage
    storage_path: str = Field(default=".fs/parse-jobs", description="Parse job storage path")
    db_path: str = Field(default=".fs/reader-db", description="RocksDB path for job tracking")

    # Auth (optional)
    auth_enabled: bool = Field(default=False, description="Enable API token auth")
    api_token: str | None = Field(default=None, description="API token for authentication")

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

    # S3/Minio (for cloud gateway mode)
    s3_enabled: bool = Field(default=False, description="Enable S3 storage")
    s3_endpoint: str = Field(
        default="http://localhost:9000", description="S3/Minio endpoint"
    )
    s3_access_key: str | None = Field(default=None, description="S3 access key")
    s3_secret_key: str | None = Field(default=None, description="S3 secret key")
    s3_bucket: str = Field(default="percolate-files", description="S3 bucket name")
    s3_region: str = Field(default="us-east-1", description="S3 region")

    # NATS (for cloud gateway mode)
    nats_enabled: bool = Field(default=False, description="Enable NATS messaging")
    nats_url: str = Field(default="nats://localhost:4222", description="NATS server URL")
    nats_queue_subject: str = Field(
        default="percolate.jobs", description="NATS queue subject"
    )
    nats_queue_group: str = Field(
        default="parse-workers", description="NATS queue group for workers"
    )

    # Deployment mode
    gateway_mode: bool = Field(
        default=False, description="Run as cloud gateway (stage files, export context)"
    )
    worker_mode: bool = Field(
        default=False, description="Run as worker (listen to NATS queue)"
    )


settings = Settings()
