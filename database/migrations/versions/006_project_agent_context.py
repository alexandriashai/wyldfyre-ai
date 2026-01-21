"""Add agent_context to projects and web_root to domains.

Revision ID: 006_project_agent_context
Revises: 005_domain_project
Create Date: 2026-01-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_project_agent_context"
down_revision: Union[str, None] = "005_domain_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add agent_context to projects
    op.add_column(
        "projects",
        sa.Column("agent_context", sa.Text(), nullable=True),
    )

    # Add web_root to domains
    op.add_column(
        "domains",
        sa.Column("web_root", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("domains", "web_root")
    op.drop_column("projects", "agent_context")
