"""Add GitHub integration columns to projects.

Revision ID: 016
Revises: 015
Create Date: 2026-01-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "016_github_integration"
down_revision: Union[str, None] = "015_step_scores_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add GitHub integration columns to projects table
    op.add_column(
        "projects",
        sa.Column("github_pat_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("github_repo_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "github_repo_url")
    op.drop_column("projects", "github_pat_encrypted")
