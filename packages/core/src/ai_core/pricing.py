"""
Model Pricing Module - Cost calculation for AI API usage.

Provides pricing constants and cost calculation utilities for:
- Anthropic Claude models (Opus, Sonnet, Haiku)
- OpenAI embedding models

All prices are per 1 million tokens unless otherwise noted.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import NamedTuple


class Provider(str, Enum):
    """AI model providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class ModelPricing(NamedTuple):
    """Pricing per 1 million tokens for a model."""

    input_cost: Decimal  # Cost per 1M input tokens
    output_cost: Decimal  # Cost per 1M output tokens
    cached_input_cost: Decimal | None = None  # Cost per 1M cached input tokens
    provider: Provider = Provider.ANTHROPIC


# Pricing as of January 2025 (per 1M tokens)
# https://www.anthropic.com/pricing
# https://openai.com/api/pricing/
MODEL_PRICING: dict[str, ModelPricing] = {
    # Anthropic Claude Models
    "claude-opus-4-5-20251101": ModelPricing(
        input_cost=Decimal("15.00"),
        output_cost=Decimal("75.00"),
        cached_input_cost=Decimal("1.875"),  # 87.5% discount
        provider=Provider.ANTHROPIC,
    ),
    "claude-opus-4-5": ModelPricing(
        input_cost=Decimal("15.00"),
        output_cost=Decimal("75.00"),
        cached_input_cost=Decimal("1.875"),
        provider=Provider.ANTHROPIC,
    ),
    "claude-sonnet-4-20250514": ModelPricing(
        input_cost=Decimal("3.00"),
        output_cost=Decimal("15.00"),
        cached_input_cost=Decimal("0.30"),  # 90% discount
        provider=Provider.ANTHROPIC,
    ),
    "claude-sonnet-4": ModelPricing(
        input_cost=Decimal("3.00"),
        output_cost=Decimal("15.00"),
        cached_input_cost=Decimal("0.30"),
        provider=Provider.ANTHROPIC,
    ),
    "claude-3-5-haiku-20241022": ModelPricing(
        input_cost=Decimal("0.80"),
        output_cost=Decimal("4.00"),
        cached_input_cost=Decimal("0.08"),  # 90% discount
        provider=Provider.ANTHROPIC,
    ),
    "claude-3-5-haiku": ModelPricing(
        input_cost=Decimal("0.80"),
        output_cost=Decimal("4.00"),
        cached_input_cost=Decimal("0.08"),
        provider=Provider.ANTHROPIC,
    ),
    # Legacy model aliases
    "claude-3-opus-20240229": ModelPricing(
        input_cost=Decimal("15.00"),
        output_cost=Decimal("75.00"),
        cached_input_cost=Decimal("1.875"),
        provider=Provider.ANTHROPIC,
    ),
    "claude-3-5-sonnet-20241022": ModelPricing(
        input_cost=Decimal("3.00"),
        output_cost=Decimal("15.00"),
        cached_input_cost=Decimal("0.30"),
        provider=Provider.ANTHROPIC,
    ),
    # OpenAI Chat Models
    "gpt-4o": ModelPricing(
        input_cost=Decimal("2.50"),
        output_cost=Decimal("10.00"),
        provider=Provider.OPENAI,
    ),
    "gpt-4o-mini": ModelPricing(
        input_cost=Decimal("0.15"),
        output_cost=Decimal("0.60"),
        provider=Provider.OPENAI,
    ),
    # OpenAI Embedding Models
    "text-embedding-3-small": ModelPricing(
        input_cost=Decimal("0.02"),
        output_cost=Decimal("0.00"),  # Embeddings have no output tokens
        provider=Provider.OPENAI,
    ),
    "text-embedding-3-large": ModelPricing(
        input_cost=Decimal("0.13"),
        output_cost=Decimal("0.00"),
        provider=Provider.OPENAI,
    ),
    "text-embedding-ada-002": ModelPricing(
        input_cost=Decimal("0.10"),
        output_cost=Decimal("0.00"),
        provider=Provider.OPENAI,
    ),
}

# Default model for unknown models (use most expensive to be safe)
DEFAULT_PRICING = ModelPricing(
    input_cost=Decimal("15.00"),
    output_cost=Decimal("75.00"),
    provider=Provider.ANTHROPIC,
)


@dataclass
class UsageCost:
    """Calculated cost breakdown for an API call."""

    input_cost: Decimal
    output_cost: Decimal
    cached_cost: Decimal
    total_cost: Decimal
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    model: str
    provider: Provider


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    cached_tokens: int = 0,
) -> UsageCost:
    """
    Calculate the cost for an API call.

    Args:
        model: The model identifier (e.g., "claude-opus-4-5")
        input_tokens: Number of input tokens (non-cached)
        output_tokens: Number of output tokens
        cached_tokens: Number of cached input tokens

    Returns:
        UsageCost with detailed breakdown
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    # Convert to per-token cost (prices are per 1M tokens)
    per_token_input = pricing.input_cost / Decimal("1000000")
    per_token_output = pricing.output_cost / Decimal("1000000")

    # Calculate costs
    input_cost = per_token_input * Decimal(input_tokens)
    output_cost = per_token_output * Decimal(output_tokens)

    # Handle cached tokens
    cached_cost = Decimal("0")
    if cached_tokens > 0 and pricing.cached_input_cost is not None:
        per_token_cached = pricing.cached_input_cost / Decimal("1000000")
        cached_cost = per_token_cached * Decimal(cached_tokens)

    total_cost = input_cost + output_cost + cached_cost

    return UsageCost(
        input_cost=input_cost,
        output_cost=output_cost,
        cached_cost=cached_cost,
        total_cost=total_cost,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        model=model,
        provider=pricing.provider,
    )


def get_model_provider(model: str) -> Provider:
    """Get the provider for a given model."""
    pricing = MODEL_PRICING.get(model)
    if pricing:
        return pricing.provider
    # Default to Anthropic for unknown models (most of our models are Anthropic)
    return Provider.ANTHROPIC


def get_model_pricing(model: str) -> ModelPricing:
    """Get pricing information for a model."""
    return MODEL_PRICING.get(model, DEFAULT_PRICING)


def estimate_cost(
    model: str,
    estimated_input_tokens: int,
    estimated_output_tokens: int = 0,
) -> Decimal:
    """
    Estimate the cost for a planned API call (no caching).

    Useful for budget planning and pre-flight checks.
    """
    cost = calculate_cost(model, estimated_input_tokens, estimated_output_tokens)
    return cost.total_cost


def format_cost(cost: Decimal) -> str:
    """Format a cost as a USD string."""
    return f"${cost:.6f}"


def format_cost_summary(usage_cost: UsageCost) -> str:
    """Format a complete cost summary for logging."""
    return (
        f"Model: {usage_cost.model} ({usage_cost.provider.value})\n"
        f"Input: {usage_cost.input_tokens:,} tokens = {format_cost(usage_cost.input_cost)}\n"
        f"Output: {usage_cost.output_tokens:,} tokens = {format_cost(usage_cost.output_cost)}\n"
        f"Cached: {usage_cost.cached_tokens:,} tokens = {format_cost(usage_cost.cached_cost)}\n"
        f"Total: {format_cost(usage_cost.total_cost)}"
    )
