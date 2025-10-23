"""Application settings using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PERCOLATE_",
        case_sensitive=False,
    )

    # API
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    api_reload: bool = Field(default=False, description="Auto-reload on code changes")

    # Database
    db_path: str = Field(default="./data/percolate.db", description="RocksDB path")
    pg_url: str | None = Field(default=None, description="PostgreSQL URL (optional)")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")

    # Authentication
    auth_enabled: bool = Field(default=True, description="Enable authentication")
    jwt_secret_key: str = Field(default="dev-secret-key", description="JWT signing key")
    jwt_algorithm: str = Field(default="ES256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=60, description="Access token lifetime")
    refresh_token_expire_days: int = Field(default=30, description="Refresh token lifetime")

    # LLM
    default_model: str = Field(
        default="claude-sonnet-4.5", description="Default LLM model"
    )
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")

    # OpenTelemetry
    otel_enabled: bool = Field(default=False, description="Enable OTEL")
    otel_endpoint: str = Field(
        default="http://localhost:4318", description="OTEL collector endpoint"
    )
    otel_service_name: str = Field(default="percolate", description="Service name")

    # Storage
    storage_path: str = Field(default="./data/storage", description="Local storage path")
    s3_bucket: str | None = Field(default=None, description="S3 bucket for cloud storage")
    s3_region: str = Field(default="us-east-1", description="S3 region")

    # MCP
    mcp_enabled: bool = Field(default=True, description="Enable MCP server")


settings = Settings()
