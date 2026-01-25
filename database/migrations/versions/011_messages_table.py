"""
Messages table for persistent chat storage.

Provides PostgreSQL fallback for Redis message storage,
ensuring conversation history survives Redis restarts.

Revision ID: 011_messages_table
Revises: 010_project_primary_url
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "011_messages_table"
down_revision = "010_project_primary_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create messages table."""
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("agent", sa.String(50), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("message_index", sa.Integer, nullable=True),
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
    )

    # Index for fast conversation message retrieval
    op.create_index(
        "ix_messages_conversation_id",
        "messages",
        ["conversation_id"],
    )

    # Composite index for ordered retrieval
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    """Drop messages table."""
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
