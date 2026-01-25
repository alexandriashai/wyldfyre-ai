"""
Conversation tags table for categorizing chats.

Revision ID: 012_conversation_tags
Revises: 011_messages_table
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "012_conversation_tags"
down_revision = "011_messages_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create conversation_tags table."""
    op.create_table(
        "conversation_tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("conversation_id", "tag", name="uq_conversation_tag"),
    )

    op.create_index(
        "ix_conversation_tags_conversation_id",
        "conversation_tags",
        ["conversation_id"],
    )

    op.create_index(
        "ix_conversation_tags_tag",
        "conversation_tags",
        ["tag"],
    )


def downgrade() -> None:
    """Drop conversation_tags table."""
    op.drop_index("ix_conversation_tags_tag", table_name="conversation_tags")
    op.drop_index("ix_conversation_tags_conversation_id", table_name="conversation_tags")
    op.drop_table("conversation_tags")
