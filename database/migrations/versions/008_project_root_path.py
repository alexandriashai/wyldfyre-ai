"""Add root_path to projects for agent file operations.

Revision ID: 008_project_root_path
Revises: 007_api_usage_project
Create Date: 2026-01-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_project_root_path"
down_revision: Union[str, None] = "007_api_usage_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("root_path", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "root_path")
