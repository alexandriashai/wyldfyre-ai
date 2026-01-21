"""
Credential storage for E2E testing.

Creates tables for secure credential storage and browser session management:
- stored_credentials: Encrypted credentials for web app authentication
- browser_sessions: Saved browser context states for session reuse

Revision ID: 004_credentials
Revises: 003_projects_conversations
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "004_credentials"
down_revision = "003_projects_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create credential and browser session tables."""

    # Create stored_credentials table
    op.create_table(
        "stored_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        # Application identification
        sa.Column(
            "app_name",
            sa.String(100),
            nullable=False,
            comment="Application name this credential is for",
        ),
        sa.Column(
            "credential_type",
            sa.String(50),
            nullable=False,
            default="basic",
            comment="Type: basic, oauth, api_key, session",
        ),
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            default="user",
            comment="User role: admin, user, guest",
        ),
        # Encrypted sensitive data
        sa.Column(
            "username_encrypted",
            sa.LargeBinary(),
            nullable=False,
            comment="AES-256-GCM encrypted username",
        ),
        sa.Column(
            "password_encrypted",
            sa.LargeBinary(),
            nullable=False,
            comment="AES-256-GCM encrypted password",
        ),
        sa.Column(
            "metadata_encrypted",
            sa.LargeBinary(),
            nullable=True,
            comment="AES-256-GCM encrypted additional metadata (JSON)",
        ),
        # Rotation and expiration
        sa.Column(
            "rotation_days",
            sa.Integer(),
            nullable=False,
            default=30,
            comment="Days between recommended credential rotations",
        ),
        sa.Column(
            "last_rotated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the credential was last rotated",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this credential should be rotated",
        ),
        # Soft delete
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            default=True,
            comment="Whether this credential is active",
        ),
        # Owner
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User who owns this credential",
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

    # Create indexes for stored_credentials
    op.create_index(
        "ix_stored_credentials_app_name",
        "stored_credentials",
        ["app_name"],
    )
    op.create_index(
        "ix_stored_credentials_user_id",
        "stored_credentials",
        ["user_id"],
    )
    op.create_index(
        "ix_stored_credentials_is_active",
        "stored_credentials",
        ["is_active"],
    )
    op.create_index(
        "ix_stored_credentials_expires_at",
        "stored_credentials",
        ["expires_at"],
    )

    # Composite index for common query pattern
    op.create_index(
        "ix_stored_credentials_user_app",
        "stored_credentials",
        ["user_id", "app_name"],
    )
    op.create_index(
        "ix_stored_credentials_user_app_role",
        "stored_credentials",
        ["user_id", "app_name", "role"],
    )

    # Create browser_sessions table
    op.create_table(
        "browser_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        # Session identification
        sa.Column(
            "session_name",
            sa.String(100),
            nullable=False,
            comment="Human-readable session name",
        ),
        sa.Column(
            "app_name",
            sa.String(100),
            nullable=False,
            comment="Application this session is for",
        ),
        # Optional link to context
        sa.Column(
            "context_id",
            sa.String(36),
            nullable=True,
            comment="Browser context ID this session was created from",
        ),
        # Encrypted storage state
        sa.Column(
            "storage_state_encrypted",
            sa.LargeBinary(),
            nullable=False,
            comment="AES-256-GCM encrypted browser storage state",
        ),
        # Expiration
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When this session state expires",
        ),
        sa.Column(
            "is_valid",
            sa.Boolean(),
            nullable=False,
            default=True,
            comment="Whether this session is still valid",
        ),
        # Owner
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User who owns this session",
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

    # Create indexes for browser_sessions
    op.create_index(
        "ix_browser_sessions_app_name",
        "browser_sessions",
        ["app_name"],
    )
    op.create_index(
        "ix_browser_sessions_user_id",
        "browser_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_browser_sessions_is_valid",
        "browser_sessions",
        ["is_valid"],
    )
    op.create_index(
        "ix_browser_sessions_expires_at",
        "browser_sessions",
        ["expires_at"],
    )

    # Composite index for common query pattern
    op.create_index(
        "ix_browser_sessions_user_app",
        "browser_sessions",
        ["user_id", "app_name"],
    )


def downgrade() -> None:
    """Remove credential and browser session tables."""

    # Drop browser_sessions indexes
    op.drop_index("ix_browser_sessions_user_app", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_expires_at", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_is_valid", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_user_id", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_app_name", table_name="browser_sessions")

    # Drop browser_sessions table
    op.drop_table("browser_sessions")

    # Drop stored_credentials indexes
    op.drop_index("ix_stored_credentials_user_app_role", table_name="stored_credentials")
    op.drop_index("ix_stored_credentials_user_app", table_name="stored_credentials")
    op.drop_index("ix_stored_credentials_expires_at", table_name="stored_credentials")
    op.drop_index("ix_stored_credentials_is_active", table_name="stored_credentials")
    op.drop_index("ix_stored_credentials_user_id", table_name="stored_credentials")
    op.drop_index("ix_stored_credentials_app_name", table_name="stored_credentials")

    # Drop stored_credentials table
    op.drop_table("stored_credentials")
