"""
Credential storage model for secure E2E testing credentials.

Stores encrypted credentials for web application authentication
used by the QA Agent's browser automation tools.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class StoredCredential(Base, UUIDMixin, TimestampMixin):
    """
    Encrypted credential storage for E2E testing.

    Credentials are encrypted with AES-256-GCM before storage.
    The encryption key is managed via environment variables or
    a secrets manager.

    Attributes:
        app_name: Application identifier (e.g., "wyld-web", "admin-portal")
        credential_type: Type of credential ("basic", "oauth", "api_key", "session")
        role: User role for this credential ("admin", "user", "guest")
        username_encrypted: Encrypted username/email
        password_encrypted: Encrypted password/secret
        metadata_encrypted: Encrypted additional data (client_id, tokens, etc.)
        rotation_days: Days between recommended rotations
        last_rotated_at: When the credential was last rotated
        expires_at: When the credential should be considered stale
        is_active: Soft delete flag
        user_id: Owner of this credential
    """

    __tablename__ = "stored_credentials"

    # Application identification
    app_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Application name this credential is for",
    )

    # Credential type
    credential_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="basic",
        comment="Type: basic, oauth, api_key, session",
    )

    # Role
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user",
        comment="User role: admin, user, guest",
    )

    # Encrypted sensitive data
    username_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-256-GCM encrypted username",
    )

    password_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-256-GCM encrypted password",
    )

    metadata_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="AES-256-GCM encrypted additional metadata (JSON)",
    )

    # Rotation and expiration
    rotation_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Days between recommended credential rotations",
    )

    last_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the credential was last rotated",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When this credential should be rotated",
    )

    # Soft delete
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this credential is active",
    )

    # Owner relationship
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this credential",
    )

    # Relationship
    user = relationship("User", back_populates="stored_credentials")

    def __repr__(self) -> str:
        return (
            f"StoredCredential(id={self.id!r}, "
            f"app_name={self.app_name!r}, "
            f"credential_type={self.credential_type!r}, "
            f"role={self.role!r})"
        )


class BrowserSession(Base, UUIDMixin, TimestampMixin):
    """
    Saved browser session state for E2E testing.

    Stores serialized browser context state (cookies, localStorage)
    for reuse across test runs.

    Attributes:
        session_name: Human-readable session identifier
        app_name: Application this session is for
        context_id: Browser context this session was created from
        storage_state_encrypted: Encrypted serialized storage state
        expires_at: When this session state expires
        is_valid: Whether this session is still valid
        user_id: Owner of this session
    """

    __tablename__ = "browser_sessions"

    # Session identification
    session_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable session name",
    )

    app_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Application this session is for",
    )

    # Optional link to context
    context_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="Browser context ID this session was created from",
    )

    # Encrypted storage state
    storage_state_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-256-GCM encrypted browser storage state",
    )

    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When this session state expires",
    )

    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this session is still valid",
    )

    # Owner relationship
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this session",
    )

    # Relationship
    user = relationship("User", back_populates="browser_sessions")

    def __repr__(self) -> str:
        return (
            f"BrowserSession(id={self.id!r}, "
            f"session_name={self.session_name!r}, "
            f"app_name={self.app_name!r})"
        )
