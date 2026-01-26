"""
Step scores table for Process Reward Model (Improvement 2).

Tracks individual step execution scores for plan quality analysis
and course correction decisions.

Revision ID: 015_step_scores_table
Revises: 014_project_docker_settings
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# Revision identifiers
revision = "015_step_scores_table"
down_revision = "014_project_docker_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create step_scores table for Process Reward Model."""
    op.create_table(
        "step_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("step_id", sa.String(36), nullable=True),
        sa.Column("step_type", sa.String(50), nullable=True),
        sa.Column("step_title", sa.String(200), nullable=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("completion_score", sa.Float, nullable=True),
        sa.Column("efficiency_score", sa.Float, nullable=True),
        sa.Column("error_free_score", sa.Float, nullable=True),
        sa.Column("file_modification_score", sa.Float, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("files_modified_count", sa.Integer, nullable=True, default=0),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("replanned", sa.Boolean, nullable=True, default=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Index for plan-based queries
    op.create_index(
        "ix_step_scores_plan_id",
        "step_scores",
        ["plan_id"],
    )

    # Index for analyzing step patterns
    op.create_index(
        "ix_step_scores_step_type",
        "step_scores",
        ["step_type"],
    )

    # Index for project-level analysis
    op.create_index(
        "ix_step_scores_project_id",
        "step_scores",
        ["project_id"],
    )

    # Composite index for ordered retrieval
    op.create_index(
        "ix_step_scores_plan_index",
        "step_scores",
        ["plan_id", "step_index"],
    )


def downgrade() -> None:
    """Drop step_scores table."""
    op.drop_index("ix_step_scores_plan_index", table_name="step_scores")
    op.drop_index("ix_step_scores_project_id", table_name="step_scores")
    op.drop_index("ix_step_scores_step_type", table_name="step_scores")
    op.drop_index("ix_step_scores_plan_id", table_name="step_scores")
    op.drop_table("step_scores")
