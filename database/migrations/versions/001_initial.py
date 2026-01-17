"""
Initial database schema.

Creates the core tables for the AI Infrastructure system:
- users: User accounts and authentication
- tasks: Agent task tracking
- domains: Managed domains and SSL certificates

Revision ID: 001_initial
Revises: None
Create Date: 2026-01-17
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema."""

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_admin", sa.Boolean(), default=False, nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferences", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for users
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "QUEUED",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="taskstatus",
            ),
            default="PENDING",
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), default=5, nullable=False),
        sa.Column(
            "agent_type",
            sa.Enum(
                "SUPERVISOR",
                "CODE",
                "DATA",
                "INFRA",
                "RESEARCH",
                "QA",
                name="agenttype",
            ),
            nullable=True,
        ),
        sa.Column("correlation_id", sa.String(36), nullable=True, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_data", sa.Text(), nullable=True),
        sa.Column("output_data", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("token_count_input", sa.Integer(), nullable=True),
        sa.Column("token_count_output", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True, index=True
        ),
        sa.Column(
            "parent_task_id",
            sa.String(36),
            sa.ForeignKey("tasks.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for tasks
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_task_type", "tasks", ["task_type"])

    # Create domains table
    op.create_table(
        "domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain_name", sa.String(255), unique=True, nullable=False),
        sa.Column("subdomain", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROVISIONING",
                "ACTIVE",
                "ERROR",
                "SUSPENDED",
                name="domainstatus",
            ),
            default="PENDING",
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), default=False, nullable=False),
        sa.Column("dns_provider", sa.String(50), nullable=True),
        sa.Column("dns_record_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("ssl_enabled", sa.Boolean(), default=False, nullable=False),
        sa.Column("ssl_provider", sa.String(50), nullable=True),
        sa.Column("ssl_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ssl_auto_renew", sa.Boolean(), default=True, nullable=False),
        sa.Column("nginx_config_path", sa.String(500), nullable=True),
        sa.Column("proxy_target", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for domains
    op.create_index("ix_domains_domain_name", "domains", ["domain_name"])
    op.create_index("ix_domains_status", "domains", ["status"])


def downgrade() -> None:
    """Remove initial database schema."""
    op.drop_table("domains")
    op.drop_table("tasks")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS domainstatus")
    op.execute("DROP TYPE IF EXISTS agenttype")
    op.execute("DROP TYPE IF EXISTS taskstatus")
