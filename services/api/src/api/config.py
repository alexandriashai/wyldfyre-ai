"""
API-specific configuration settings.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIConfig(BaseSettings):
    """API service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        extra="ignore",
    )

    # Server
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, description="API port")
    debug: bool = Field(default=False, description="Debug mode")
    reload: bool = Field(default=False, description="Auto-reload on changes")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # JWT Authentication
    jwt_secret_key: str = Field(
        default="change-me-in-production-use-secrets-manager",
        description="JWT signing secret",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token expiration in days"
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://ai_infra:ai_infra@localhost:5432/ai_infra",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(default=10, description="Connection pool size")
    database_max_overflow: int = Field(default=20, description="Max overflow connections")

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(
        default=60, description="Requests per minute per user"
    )
    rate_limit_burst: int = Field(default=10, description="Burst allowance")

    # File Upload
    upload_max_size_mb: int = Field(default=50, description="Max upload size in MB")
    upload_allowed_types: list[str] = Field(
        default=[
            "image/jpeg",
            "image/png",
            "image/gif",
            "application/pdf",
            "text/plain",
            "text/markdown",
            "application/json",
        ],
        description="Allowed upload MIME types",
    )
    upload_directory: str = Field(
        default="/var/lib/ai-infra/uploads",
        description="Upload storage directory",
    )

    # WebSocket
    ws_heartbeat_interval: int = Field(
        default=30, description="WebSocket heartbeat interval in seconds"
    )
    ws_max_connections_per_user: int = Field(
        default=5, description="Max WebSocket connections per user"
    )

    @property
    def upload_max_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.upload_max_size_mb * 1024 * 1024


@lru_cache
def get_api_config() -> APIConfig:
    """Get cached API configuration."""
    return APIConfig()
