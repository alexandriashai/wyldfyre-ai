"""
Projects and Conversations schema.

Creates tables for project organization and conversation persistence:
- projects: Group related conversations and tasks
- conversations: Persist chat sessions with planning support
- Updates tasks table with project/conversation/domain links

Revision ID: 003_projects_conversations
Revises: 002_api_usage
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "003_projects_conversations"
down_revision = "002_api_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create projects and conversations tables."""

    # Create enum types for PostgreSQL
    project_status_enum = sa.Enum(
        "ACTIVE",
        "ARCHIVED",
        "COMPLETED",
        name="projectstatus",
    )
    conversation_status_enum = sa.Enum(
        "ACTIVE",
        "ARCHIVED",
        "DELETED",
        name="conversationstatus",
    )
    plan_status_enum = sa.Enum(
        "DRAFT",
        "PENDING",
        "APPROVED",
        "REJECTED",
        "COMPLETED",
        name="planstatus",
    )

    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        # Project info
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Status
        sa.Column(
            "status",
            project_status_enum,
            default="ACTIVE",
            nullable=False,
        ),
        # UI customization
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        # Owner
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Timestamps
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

    # Create indexes for projects
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        # Conversation info
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        # Status
        sa.Column(
            "status",
            conversation_status_enum,
            default="ACTIVE",
            nullable=False,
        ),
        # Message tracking
        sa.Column("message_count", sa.Integer(), default=0, nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        # Planning (Claude CLI style)
        sa.Column("plan_content", sa.Text(), nullable=True),
        sa.Column("plan_status", plan_status_enum, nullable=True),
        sa.Column("plan_approved_at", sa.DateTime(timezone=True), nullable=True),
        # Owner
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Project relationship (optional)
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Domain relationship (optional)
        sa.Column(
            "domain_id",
            sa.String(36),
            sa.ForeignKey("domains.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Timestamps
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

    # Create indexes for conversations
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_project_id", "conversations", ["project_id"])
    op.create_index("ix_conversations_domain_id", "conversations", ["domain_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"])
    op.create_index("ix_conversations_plan_status", "conversations", ["plan_status"])

    # Composite indexes for common query patterns
    op.create_index(
        "ix_conversations_user_project",
        "conversations",
        ["user_id", "project_id"],
    )
    op.create_index(
        "ix_conversations_user_status",
        "conversations",
        ["user_id", "status"],
    )

    # Add columns to tasks table for project/conversation/domain links
    op.add_column(
        "tasks",
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "domain_id",
            sa.String(36),
            sa.ForeignKey("domains.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Create indexes for new task columns
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_conversation_id", "tasks", ["conversation_id"])
    op.create_index("ix_tasks_domain_id", "tasks", ["domain_id"])

    # Composite indexes for filtering tasks
    op.create_index(
        "ix_tasks_user_project",
        "tasks",
        ["user_id", "project_id"],
    )
    op.create_index(
        "ix_tasks_user_conversation",
        "tasks",
        ["user_id", "conversation_id"],
    )


def downgrade() -> None:
    """Remove projects and conversations tables."""

    # Drop indexes from tasks
    op.drop_index("ix_tasks_user_conversation", table_name="tasks")
    op.drop_index("ix_tasks_user_project", table_name="tasks")
    op.drop_index("ix_tasks_domain_id", table_name="tasks")
    op.drop_index("ix_tasks_conversation_id", table_name="tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")

    # Remove columns from tasks
    op.drop_column("tasks", "domain_id")
    op.drop_column("tasks", "conversation_id")
    op.drop_column("tasks", "project_id")

    # Drop conversations table
    op.drop_table("conversations")

    # Drop projects table
    op.drop_table("projects")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS planstatus")
    op.execute("DROP TYPE IF EXISTS conversationstatus")
    op.execute("DROP TYPE IF EXISTS projectstatus")
