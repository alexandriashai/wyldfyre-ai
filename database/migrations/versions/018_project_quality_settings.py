"""
Add quality_settings column to projects table.

Stores JSON configuration for code quality settings per project:
- Linting commands and behavior
- Formatting commands and behavior
- Type checking settings
- Test settings
- Agent auto-fix behavior

Revision ID: 018_project_quality_settings
Revises: 017_provider_usage
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "018_project_quality_settings"
down_revision = "017_provider_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add quality_settings column to projects table."""
    op.add_column(
        "projects",
        sa.Column("quality_settings", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove quality_settings column from projects table."""
    op.drop_column("projects", "quality_settings")
