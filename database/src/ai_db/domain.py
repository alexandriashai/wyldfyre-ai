"""
Domain model for managed domains and SSL certificates.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_core import DomainStatus

from .base import Base, TimestampMixin, UUIDMixin


class Domain(Base, UUIDMixin, TimestampMixin):
    """Managed domain model."""

    __tablename__ = "domains"

    # Domain info
    domain_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    subdomain: Mapped[str | None] = mapped_column(String(100))

    # Status
    status: Mapped[DomainStatus] = mapped_column(
        Enum(DomainStatus),
        default=DomainStatus.PENDING,
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # DNS
    dns_provider: Mapped[str | None] = mapped_column(String(50))  # cloudflare, etc.
    dns_record_id: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(45))

    # SSL
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ssl_provider: Mapped[str | None] = mapped_column(String(50))  # letsencrypt, etc.
    ssl_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ssl_auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)

    # Nginx config
    nginx_config_path: Mapped[str | None] = mapped_column(String(500))
    proxy_target: Mapped[str | None] = mapped_column(String(255))  # localhost:3000

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<Domain {self.domain_name} {self.status.value}>"
