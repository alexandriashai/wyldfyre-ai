"""
Model Selector - Dynamic model selection by task complexity.

Provides automatic model tier selection based on task signals (max_tokens,
tools count, system prompt length) to reduce cost on simple tasks while
maintaining quality for complex reasoning.
"""

from enum import Enum

from .llm_provider import LLMProviderType


class ModelTier(str, Enum):
    """Model complexity tiers."""

    FAST = "fast"          # haiku / gpt-5-mini
    BALANCED = "balanced"  # sonnet / gpt-5
    POWERFUL = "powerful"  # opus / gpt-5.2


# Model names for each provider at each tier
TIER_MODELS: dict[LLMProviderType, dict[ModelTier, str]] = {
    LLMProviderType.ANTHROPIC: {
        ModelTier.FAST: "claude-haiku-4-20250514",
        ModelTier.BALANCED: "claude-sonnet-4-20250514",
        ModelTier.POWERFUL: "claude-opus-4-5-20251101",
    },
    LLMProviderType.OPENAI: {
        ModelTier.FAST: "gpt-5-mini",
        ModelTier.BALANCED: "gpt-5",
        ModelTier.POWERFUL: "gpt-5.2",
    },
}


def select_model(
    provider: LLMProviderType,
    tier: ModelTier | None = None,
    max_tokens: int = 4096,
    tools_count: int = 0,
    system_prompt_length: int = 0,
) -> str:
    """
    Select model for given provider based on tier or auto-detection.

    If tier is explicitly set, returns that tier's model for the active provider.
    Otherwise, auto-detects tier from task signals:
      - FAST: max_tokens <= 200 AND no tools
      - POWERFUL: tools_count > 15 OR system_prompt_length > 3000
      - BALANCED: everything else

    Args:
        provider: Active LLM provider (anthropic or openai)
        tier: Explicit tier override (skips auto-detection)
        max_tokens: Max response tokens requested
        tools_count: Number of tools provided
        system_prompt_length: Length of system prompt in characters

    Returns:
        Model name string for the active provider
    """
    if tier is None:
        tier = _detect_tier(max_tokens, tools_count, system_prompt_length)

    return TIER_MODELS[provider][tier]


def _detect_tier(
    max_tokens: int,
    tools_count: int,
    system_prompt_length: int,
) -> ModelTier:
    """Auto-detect appropriate tier from task signals."""
    # Simple tasks: short output, no tools
    if max_tokens <= 200 and tools_count == 0:
        return ModelTier.FAST

    # Complex tasks: many tools or long system prompts
    if tools_count > 15 or system_prompt_length > 3000:
        return ModelTier.POWERFUL

    # Default: balanced
    return ModelTier.BALANCED
