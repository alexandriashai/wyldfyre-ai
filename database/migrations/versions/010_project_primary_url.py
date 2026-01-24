"""Add primary_url to projects.

Revision ID: 010_project_primary_url
Revises: 009_domain_deploy_fields
Create Date: 2026-01-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_project_primary_url"
down_revision: Union[str, None] = "009_domain_deploy_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("primary_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "primary_url")
