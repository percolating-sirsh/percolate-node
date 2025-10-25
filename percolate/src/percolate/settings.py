"""Application settings using Pydantic Settings."""

import os
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Authentication configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AUTH__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(default=False, description="Enable authentication")
    provider: str = Field(
        default="p8fs",
        description="Auth provider: disabled, p8fs, oidc, dev",
    )

    # JWT settings (keypair encryption - ES256 with ECDSA P-256)
    jwt_private_key: str = Field(
        default="""-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgT428/clvyeL1dpKv
WnR6jzjomtZaUs7kLBbx9q0KmzOhRANCAARucrqJRUuDGUMaqzzaMeCcljmGJlfo
Roy5U3K87lqKSGmOjPbdj0x7NjX3FIG8yCiIZtBfWMeHLpBzX1XpO+fW
-----END PRIVATE KEY-----""",
        description="JWT private key (PEM format) - CHANGE IN PRODUCTION",
    )
    jwt_public_key: str = Field(
        default="""-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEbnK6iUVLgxlDGqs82jHgnJY5hiZX
6EaMuVNyvO5aikhpjoz23Y9MezY19xSBvMgoiGbQX1jHhy6Qc19V6Tvn1g==
-----END PUBLIC KEY-----""",
        description="JWT public key (PEM format)",
    )
    jwt_algorithm: str = Field(default="ES256", description="JWT algorithm (ES256)")
    access_token_expire_minutes: int = Field(
        default=60, description="Access token lifetime"
    )
    refresh_token_expire_days: int = Field(default=30, description="Refresh token lifetime")

    # P8FS device key storage
    p8fs_server_stored_keys: bool = Field(
        default=True,
        description="Server generates and stores device keys (true) vs device-generated (false)",
    )
    p8fs_tenant_store: str = Field(
        default="filesystem",
        description="Tenant storage backend: filesystem | rem (percolate-rocks)",
    )
    p8fs_keys_path: str = Field(
        default="~/.p8/tenants",
        description="Path for tenant data (filesystem mode or REM database path)",
    )

    # OIDC external provider (Microsoft, Google, GitHub, etc.)
    oidc_issuer_url: str = Field(
        default="",
        description="OIDC issuer URL",
    )
    oidc_audience: str = Field(default="api", description="Expected audience claim")
    oidc_client_id: str = Field(default="", description="OIDC client ID")
    oidc_client_secret: str = Field(default="", description="OIDC client secret")
    oidc_jwks_cache_ttl: int = Field(
        default=3600, description="JWKS cache TTL in seconds"
    )


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PERCOLATE_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # API
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    api_reload: bool = Field(default=False, description="Auto-reload on code changes")

    # Database
    db_path: str = Field(default="./data/percolate.db", description="RocksDB path")
    pg_url: str | None = Field(default=None, description="PostgreSQL URL (optional)")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")

    # Authentication (nested)
    auth: AuthSettings = Field(default_factory=AuthSettings)

    # LLM
    default_model: str = Field(
        default="anthropic:claude-3-5-sonnet-20241022", description="Default LLM model"
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

    # Percolate-Reading integration
    percolate_reading_url: str = Field(
        default="http://localhost:8001", description="Percolate-Reading API URL"
    )
    percolate_reading_api_token: str | None = Field(
        default=None, description="API token for Percolate-Reading (if auth enabled)"
    )

    @model_validator(mode="after")
    def sync_api_keys_to_env(self) -> "Settings":
        """Sync API keys to environment variables for Pydantic AI providers.

        Pydantic AI providers read directly from environment variables
        (ANTHROPIC_API_KEY, OPENAI_API_KEY) rather than from settings.
        This validator ensures keys are available in the environment.
        """
        if self.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = self.anthropic_api_key
        if self.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        return self


settings = Settings()
