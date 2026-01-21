"""
User model for authentication and authorization.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .conversation import Conversation
    from .credential import BrowserSession, StoredCredential
    from .project import Project
    from .task import Task


class User(Base, UUIDMixin, TimestampMixin):
    """User account model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Profile
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Preferences (JSON stored as text)
    preferences: Mapped[str | None] = mapped_column(Text)

    # Relationships
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user")
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    stored_credentials: Mapped[list["StoredCredential"]] = relationship(
        "StoredCredential",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    browser_sessions: Mapped[list["BrowserSession"]] = relationship(
        "BrowserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"
