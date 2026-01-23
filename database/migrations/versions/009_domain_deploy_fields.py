"""Add deploy configuration fields to domains table.

Revision ID: 009_domain_deploy_fields
Revises: 008_project_root_path
Create Date: 2026-01-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_domain_deploy_fields"
down_revision: Union[str, None] = "008_project_root_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deploy configuration
    op.add_column(
        "domains",
        sa.Column("deploy_method", sa.String(50), server_default="local_sync", nullable=False),
    )
    op.add_column(
        "domains",
        sa.Column("deploy_ssh_host", sa.String(255), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("deploy_ssh_path", sa.String(500), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("deploy_ssh_credential_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("deploy_git_remote", sa.String(500), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("deploy_git_branch", sa.String(100), nullable=True, server_default="main"),
    )
    op.add_column(
        "domains",
        sa.Column("deploy_exclude_patterns", sa.Text, nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("deploy_delete_enabled", sa.Boolean, server_default="false", nullable=False),
    )

    # Health monitoring
    op.add_column(
        "domains",
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("health_status", sa.String(20), server_default="unknown", nullable=False),
    )
    op.add_column(
        "domains",
        sa.Column("response_time_ms", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("domains", "response_time_ms")
    op.drop_column("domains", "health_status")
    op.drop_column("domains", "last_health_check_at")
    op.drop_column("domains", "deploy_delete_enabled")
    op.drop_column("domains", "deploy_exclude_patterns")
    op.drop_column("domains", "deploy_git_branch")
    op.drop_column("domains", "deploy_git_remote")
    op.drop_column("domains", "deploy_ssh_credential_id")
    op.drop_column("domains", "deploy_ssh_path")
    op.drop_column("domains", "deploy_ssh_host")
    op.drop_column("domains", "deploy_method")
