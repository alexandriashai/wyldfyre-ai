"""
Add project_id to api_usage table.

Links API usage to projects for per-project cost tracking.

Revision ID: 007_api_usage_project
Revises: 006_project_agent_context
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "007_api_usage_project"
down_revision = "006_project_agent_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add project_id column to api_usage table."""

    # Add project_id column with foreign key
    op.add_column(
        "api_usage",
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
            comment="Project this API usage is associated with",
        ),
    )

    # Create index for efficient per-project queries
    op.create_index(
        "ix_api_usage_project_id",
        "api_usage",
        ["project_id"],
    )

    # Create composite index for project+date queries
    op.create_index(
        "ix_api_usage_project_date",
        "api_usage",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    """Remove project_id column from api_usage table."""

    # Drop indexes
    op.drop_index("ix_api_usage_project_date", table_name="api_usage")
    op.drop_index("ix_api_usage_project_id", table_name="api_usage")

    # Drop column
    op.drop_column("api_usage", "project_id")
