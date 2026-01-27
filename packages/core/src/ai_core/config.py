"""
Configuration management using Pydantic Settings.

Provides type-safe configuration loading from environment variables
with support for AWS Secrets Manager integration.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    user: str = "ai_infra"
    password: SecretStr = SecretStr("")
    database: str = "ai_infrastructure"
    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30  # Seconds to wait for connection from pool
    pool_recycle: int = 1800  # Recycle connections after 30 minutes
    pool_pre_ping: bool = True  # Verify connections before use

    @property
    def url(self) -> str:
        """Get database URL without password."""
        return f"postgresql+asyncpg://{self.user}@{self.host}:{self.port}/{self.database}"

    @property
    def url_with_password(self) -> str:
        """Get database URL with password."""
        return f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: SecretStr = SecretStr("")
    db: int = 0
    # Connection pool settings
    max_connections: int = 50
    socket_timeout: float = 5.0  # Seconds for socket operations
    socket_connect_timeout: float = 5.0  # Seconds for connection
    retry_on_timeout: bool = True
    health_check_interval: int = 30  # Seconds between health checks

    @property
    def url(self) -> str:
        """Get Redis URL."""
        if self.password.get_secret_value():
            return f"redis://:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    api_key: SecretStr = SecretStr("")
    prefer_grpc: bool = False
    https: bool = False  # Set to True for production with TLS


class APISettings(BaseSettings):
    """External API configuration."""

    model_config = SettingsConfigDict(env_prefix="")

    anthropic_api_key: SecretStr = Field(default=SecretStr(""), alias="ANTHROPIC_API_KEY")
    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")
    # Admin API keys for usage/costs APIs (separate from regular inference keys)
    anthropic_admin_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="ANTHROPIC_ADMIN_API_KEY",
    )
    openai_admin_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="OPENAI_ADMIN_API_KEY",
    )
    github_pat: SecretStr = Field(default=SecretStr(""), alias="GITHUB_PAT")
    cloudflare_api_key: SecretStr = Field(default=SecretStr(""), alias="CLOUDFLARE_API_KEY")
    cloudflare_email: str = Field(default="", alias="CLOUDFLARE_EMAIL")
    cloudflare_account_id: str = Field(default="", alias="CLOUDFLARE_ACCOUNT_ID")


class AWSSettings(BaseSettings):
    """AWS configuration."""

    model_config = SettingsConfigDict(env_prefix="AWS_")

    region: str = "us-east-1"
    access_key_id: SecretStr = SecretStr("")
    secret_access_key: SecretStr = SecretStr("")
    secrets_prefix: str = "ai-infrastructure"


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "console"] = "json"


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    service_name: str = "ai-infrastructure"

    # Security
    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    api: APISettings = Field(default_factory=APISettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings instance (cached after first call)
    """
    return Settings()


def reload_settings() -> Settings:
    """
    Reload settings (clears cache).

    Returns:
        Fresh Settings instance
    """
    get_settings.cache_clear()
    return get_settings()
