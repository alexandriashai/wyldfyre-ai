"""
API Usage tracking schema.

Creates tables for tracking API token usage and costs:
- api_usage: Individual API call records with tokens and costs
- budget_alerts: Budget threshold configuration and monitoring

Revision ID: 002_api_usage
Revises: 001_initial
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = "002_api_usage"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create API usage tracking tables."""

    # Create enum types for PostgreSQL
    api_provider_enum = sa.Enum(
        "ANTHROPIC",
        "OPENAI",
        name="apiprovider",
    )
    usage_type_enum = sa.Enum(
        "CHAT",
        "EMBEDDING",
        "TOOL_USE",
        name="usagetype",
    )

    # Create api_usage table
    op.create_table(
        "api_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        # Provider and model
        sa.Column("provider", api_provider_enum, nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("usage_type", usage_type_enum, nullable=False, default="CHAT"),
        # Token counts
        sa.Column("input_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("output_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, default=0),
        # Costs (high precision for micro-transactions)
        sa.Column(
            "cost_input",
            sa.Numeric(precision=12, scale=8),
            nullable=False,
            default=0,
        ),
        sa.Column(
            "cost_output",
            sa.Numeric(precision=12, scale=8),
            nullable=False,
            default=0,
        ),
        sa.Column(
            "cost_cached",
            sa.Numeric(precision=12, scale=8),
            nullable=False,
            default=0,
        ),
        sa.Column(
            "cost_total",
            sa.Numeric(precision=12, scale=8),
            nullable=False,
            default=0,
        ),
        # Agent info (reusing existing agenttype enum from 001_initial)
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
                create_type=False,  # Enum already exists
            ),
            nullable=True,
        ),
        sa.Column("agent_name", sa.String(100), nullable=True),
        # Correlations
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        # Request metadata
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
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

    # Create indexes for api_usage
    op.create_index("ix_api_usage_provider", "api_usage", ["provider"])
    op.create_index("ix_api_usage_model", "api_usage", ["model"])
    op.create_index("ix_api_usage_agent_type", "api_usage", ["agent_type"])
    op.create_index("ix_api_usage_task_id", "api_usage", ["task_id"])
    op.create_index("ix_api_usage_user_id", "api_usage", ["user_id"])
    op.create_index("ix_api_usage_correlation_id", "api_usage", ["correlation_id"])
    op.create_index("ix_api_usage_cost_total", "api_usage", ["cost_total"])

    # Composite indexes for common query patterns
    op.create_index("ix_api_usage_created_date", "api_usage", ["created_at"])
    op.create_index("ix_api_usage_agent_date", "api_usage", ["agent_type", "created_at"])
    op.create_index("ix_api_usage_user_date", "api_usage", ["user_id", "created_at"])
    op.create_index("ix_api_usage_model_date", "api_usage", ["model", "created_at"])

    # Create budget_alerts table
    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        # Alert configuration
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        # Threshold settings
        sa.Column(
            "threshold_amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
        ),
        sa.Column("period", sa.String(20), nullable=False, default="daily"),
        # Current state
        sa.Column(
            "current_spend",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            default=0,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer(), default=0, nullable=False),
        # Alert settings
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("notify_slack", sa.Boolean(), default=True, nullable=False),
        sa.Column("notify_email", sa.Boolean(), default=False, nullable=False),
        # Optional scoping (reusing agenttype enum)
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
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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

    # Create indexes for budget_alerts
    op.create_index("ix_budget_alerts_is_active", "budget_alerts", ["is_active"])
    op.create_index("ix_budget_alerts_period", "budget_alerts", ["period"])

    # Insert default budget alerts
    op.execute("""
        INSERT INTO budget_alerts (id, name, description, threshold_amount, period, is_active, notify_slack)
        VALUES
        (gen_random_uuid()::text, 'Daily Warning', 'Warning when daily spend exceeds $50', 50.00, 'daily', true, true),
        (gen_random_uuid()::text, 'Daily Critical', 'Critical alert when daily spend exceeds $100', 100.00, 'daily', true, true),
        (gen_random_uuid()::text, 'Hourly High Usage', 'Alert when hourly spend exceeds $10', 10.00, 'hourly', true, true)
    """)


def downgrade() -> None:
    """Remove API usage tracking tables."""
    op.drop_table("budget_alerts")
    op.drop_table("api_usage")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS usagetype")
    op.execute("DROP TYPE IF EXISTS apiprovider")
