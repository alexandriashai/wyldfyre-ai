"""
Domain model for managed domains and SSL certificates.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_core import DomainStatus

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .project import Project


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
    web_root: Mapped[str | None] = mapped_column(String(500))  # /var/www/example.com

    # Deploy configuration
    deploy_method: Mapped[str] = mapped_column(String(50), default="local_sync")
    deploy_ssh_host: Mapped[str | None] = mapped_column(String(255))
    deploy_ssh_path: Mapped[str | None] = mapped_column(String(500))
    deploy_ssh_credential_id: Mapped[str | None] = mapped_column(String(36))
    deploy_git_remote: Mapped[str | None] = mapped_column(String(500))
    deploy_git_branch: Mapped[str | None] = mapped_column(String(100), default="main")
    deploy_exclude_patterns: Mapped[str | None] = mapped_column(Text)  # JSON array
    deploy_delete_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Health monitoring
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")
    response_time_ms: Mapped[int | None] = mapped_column(Integer)

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Project association
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
    )
    project: Mapped["Project | None"] = relationship("Project", back_populates="domains")

    def __repr__(self) -> str:
        return f"<Domain {self.domain_name} {self.status.value}>"
