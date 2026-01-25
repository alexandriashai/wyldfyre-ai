"""
Message model for persistent chat message storage.

Provides a PostgreSQL fallback for messages stored in Redis,
ensuring conversation history survives Redis restarts or key expiry.
"""

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class Message(Base, UUIDMixin, TimestampMixin):
    """Persistent message storage with Redis-first pattern."""

    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    agent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    message_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
