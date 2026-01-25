"""
Conversation model for persisting chat sessions.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .conversation_tag import ConversationTag
    from .domain import Domain
    from .project import Project
    from .task import Task
    from .user import User


class ConversationStatus(enum.Enum):
    """Conversation status enum."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class PlanStatus(enum.Enum):
    """Plan approval status enum (Claude CLI style)."""

    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class Conversation(Base, UUIDMixin, TimestampMixin):
    """
    Conversation model for persisting chat sessions.

    Conversations are now persisted to the database (in addition to Redis caching)
    to enable better organization, filtering, and planning visibility.
    """

    __tablename__ = "conversations"

    # Conversation info
    title: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)  # Auto-generated summary

    # Status
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus),
        default=ConversationStatus.ACTIVE,
        nullable=False,
    )

    # Message tracking
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Planning (Claude CLI style)
    plan_content: Mapped[str | None] = mapped_column(Text)  # Markdown plan content
    plan_status: Mapped[PlanStatus | None] = mapped_column(Enum(PlanStatus))
    plan_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Owner relationship
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    user: Mapped["User"] = relationship("User", back_populates="conversations")

    # Project relationship (optional)
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
    )
    project: Mapped["Project | None"] = relationship(
        "Project",
        back_populates="conversations",
    )

    # Domain relationship (optional - for domain-scoped work)
    domain_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("domains.id", ondelete="SET NULL"),
        index=True,
    )
    domain: Mapped["Domain | None"] = relationship("Domain")

    # Child relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="conversation",
    )
    tags: Mapped[list["ConversationTag"]] = relationship(
        "ConversationTag",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id[:8]} {self.status.value}>"
