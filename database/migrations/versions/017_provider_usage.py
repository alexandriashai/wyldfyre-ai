"""
Provider Usage tracking schema.

Creates tables for storing provider-reported usage and costs:
- provider_usage: Usage data fetched from Anthropic/OpenAI Usage APIs
- usage_sync_log: Tracks sync operations with provider APIs

Revision ID: 017_provider_usage
Revises: 016_github_integration
Create Date: 2026-01-26
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "017_provider_usage"
down_revision = "016_github_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create provider usage tracking tables."""

    # Create synctype enum if it doesn't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE synctype AS ENUM ('FULL', 'INCREMENTAL', 'MANUAL');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create provider_usage table using raw SQL to avoid enum creation issues
    op.execute("""
        CREATE TABLE provider_usage (
            id VARCHAR(36) PRIMARY KEY,
            provider apiprovider NOT NULL,
            report_date TIMESTAMP WITH TIME ZONE NOT NULL,
            model VARCHAR(100) NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cached_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd NUMERIC(12, 8) NOT NULL DEFAULT 0,
            workspace_id VARCHAR(100),
            raw_response TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)

    # Create indexes for provider_usage
    op.create_index("ix_provider_usage_provider", "provider_usage", ["provider"])
    op.create_index("ix_provider_usage_report_date", "provider_usage", ["report_date"])
    op.create_index("ix_provider_usage_model", "provider_usage", ["model"])
    op.create_index(
        "ix_provider_usage_provider_date",
        "provider_usage",
        ["provider", "report_date"],
    )
    op.create_index(
        "ix_provider_usage_model_date",
        "provider_usage",
        ["model", "report_date"],
    )
    # Unique constraint to prevent duplicates
    op.create_index(
        "ix_provider_usage_unique",
        "provider_usage",
        ["provider", "report_date", "model", "workspace_id"],
        unique=True,
    )

    # Create usage_sync_log table using raw SQL
    op.execute("""
        CREATE TABLE usage_sync_log (
            id VARCHAR(36) PRIMARY KEY,
            provider apiprovider NOT NULL,
            sync_type synctype NOT NULL DEFAULT 'INCREMENTAL',
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            completed_at TIMESTAMP WITH TIME ZONE,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            records_synced INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            sync_start_date TIMESTAMP WITH TIME ZONE,
            sync_end_date TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)

    # Create indexes for usage_sync_log
    op.create_index("ix_usage_sync_log_provider", "usage_sync_log", ["provider"])
    op.create_index(
        "ix_usage_sync_log_provider_date",
        "usage_sync_log",
        ["provider", "started_at"],
    )


def downgrade() -> None:
    """Remove provider usage tracking tables."""
    op.drop_table("usage_sync_log")
    op.drop_table("provider_usage")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS synctype")
