"""
Domain management schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from ai_core import DomainStatus


class DomainCreate(BaseModel):
    """Domain creation request."""

    domain_name: str = Field(
        min_length=4,
        max_length=255,
        pattern=r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$",
        description="Fully qualified domain name",
    )
    proxy_target: str | None = Field(
        default=None,
        description="Proxy target (e.g., localhost:3000)",
    )
    ssl_enabled: bool = Field(default=True, description="Enable SSL/TLS")
    dns_provider: str = Field(default="cloudflare", description="DNS provider")


class DomainUpdate(BaseModel):
    """Domain update request."""

    proxy_target: str | None = None
    ssl_enabled: bool | None = None
    ssl_auto_renew: bool | None = None
    notes: str | None = None


class DomainResponse(BaseModel):
    """Domain information response."""

    id: str
    domain_name: str
    subdomain: str | None
    status: DomainStatus
    is_primary: bool

    # DNS
    dns_provider: str | None
    dns_record_id: str | None
    ip_address: str | None

    # SSL
    ssl_enabled: bool
    ssl_provider: str | None
    ssl_expires_at: datetime | None
    ssl_auto_renew: bool

    # Nginx
    nginx_config_path: str | None
    proxy_target: str | None

    # Metadata
    notes: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
