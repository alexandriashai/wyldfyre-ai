"""
Add terminal_user field to projects for scoped shell access.

Revision ID: 013_project_terminal_user
Revises: 012_conversation_tags
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "013_project_terminal_user"
down_revision = "012_conversation_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add terminal_user column to projects."""
    op.add_column(
        "projects",
        sa.Column("terminal_user", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    """Remove terminal_user column."""
    op.drop_column("projects", "terminal_user")
