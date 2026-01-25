"""Add Docker settings to projects.

Revision ID: 014
Revises: 013
Create Date: 2025-01-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "014_project_docker_settings"
down_revision: Union[str, None] = "013_project_terminal_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Docker-related columns to projects table
    op.add_column(
        "projects",
        sa.Column("docker_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "projects",
        sa.Column("docker_project_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("docker_node_version", sa.String(20), nullable=True, server_default="20"),
    )
    op.add_column(
        "projects",
        sa.Column("docker_php_version", sa.String(20), nullable=True, server_default="8.3"),
    )
    op.add_column(
        "projects",
        sa.Column("docker_python_version", sa.String(20), nullable=True, server_default="3.12"),
    )
    op.add_column(
        "projects",
        sa.Column("docker_memory_limit", sa.String(20), nullable=True, server_default="2g"),
    )
    op.add_column(
        "projects",
        sa.Column("docker_cpu_limit", sa.String(20), nullable=True, server_default="2.0"),
    )
    op.add_column(
        "projects",
        sa.Column("docker_expose_ports", sa.Text(), nullable=True),  # JSON array
    )
    op.add_column(
        "projects",
        sa.Column("docker_env_vars", sa.Text(), nullable=True),  # JSON object
    )
    op.add_column(
        "projects",
        sa.Column("docker_container_status", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "docker_container_status")
    op.drop_column("projects", "docker_env_vars")
    op.drop_column("projects", "docker_expose_ports")
    op.drop_column("projects", "docker_cpu_limit")
    op.drop_column("projects", "docker_memory_limit")
    op.drop_column("projects", "docker_python_version")
    op.drop_column("projects", "docker_php_version")
    op.drop_column("projects", "docker_node_version")
    op.drop_column("projects", "docker_project_type")
    op.drop_column("projects", "docker_enabled")
