"""
Add project_id to domains table.

Links domains to projects for better organization and context.

Revision ID: 005_domain_project
Revises: 004_credentials
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "005_domain_project"
down_revision = "004_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add project_id column to domains table."""

    # Add project_id column with foreign key
    op.add_column(
        "domains",
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
            comment="Optional project this domain is associated with",
        ),
    )

    # Create index for efficient queries
    op.create_index(
        "ix_domains_project_id",
        "domains",
        ["project_id"],
    )


def downgrade() -> None:
    """Remove project_id column from domains table."""

    # Drop index
    op.drop_index("ix_domains_project_id", table_name="domains")

    # Drop column
    op.drop_column("domains", "project_id")
