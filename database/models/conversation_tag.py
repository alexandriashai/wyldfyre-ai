"""
Conversation tag model for categorizing chat sessions.
"""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class ConversationTag(Base, UUIDMixin, TimestampMixin):
    """
    Tag associated with a conversation for lifecycle/system categorization.
    """

    __tablename__ = "conversation_tags"
    __table_args__ = (
        UniqueConstraint("conversation_id", "tag", name="uq_conversation_tag"),
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="tags",
    )

    def __repr__(self) -> str:
        return f"<ConversationTag {self.conversation_id[:8]} {self.tag}>"
