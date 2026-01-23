"""
LLM Client - Facade with automatic provider fallback.

Provides a unified interface for LLM calls with automatic fallback
from Anthropic to OpenAI when credits run out or rate limits are hit.
"""

import os
from typing import Any

from .config import get_settings
from .logging import get_logger
from .llm_provider import (
    BaseLLMProvider,
    LLMProviderType,
    LLMResponse,
    LLMToolCall,
    LLMToolResult,
)
from .model_selector import ModelTier, select_model

logger = get_logger(__name__)

# Error patterns that trigger fallback
FALLBACK_STATUS_CODES = {400, 402, 429, 529}
FALLBACK_ERROR_KEYWORDS = [
    "credit",
    "insufficient_quota",
    "overloaded",
    "rate_limit",
    "billing",
]


def _should_fallback(error: Exception) -> bool:
    """Check if an error should trigger provider fallback."""
    error_str = str(error).lower()

    # Check for known status codes
    status_code = getattr(error, "status_code", None)
    if status_code in FALLBACK_STATUS_CODES:
        return True

    # Check for known error keywords
    for keyword in FALLBACK_ERROR_KEYWORDS:
        if keyword in error_str:
            return True

    return False


class LLMClient:
    """
    LLM Client with automatic provider fallback.

    Reads AI_PROVIDER env var:
    - "anthropic": Only use Anthropic (default behavior)
    - "openai": Only use OpenAI
    - "auto": Try Anthropic first, fall back to OpenAI on credit/rate errors
    """

    def __init__(self):
        settings = get_settings()
        self._provider_mode = os.environ.get("AI_PROVIDER", "auto").lower()
        self._primary: BaseLLMProvider | None = None
        self._fallback: BaseLLMProvider | None = None
        self._using_fallback = False

        anthropic_key = settings.api.anthropic_api_key.get_secret_value()
        openai_key = settings.api.openai_api_key.get_secret_value()

        if self._provider_mode == "openai":
            if openai_key:
                from .providers.openai_provider import OpenAIProvider
                self._primary = OpenAIProvider(api_key=openai_key)
            else:
                logger.warning("AI_PROVIDER=openai but no OPENAI_API_KEY set, falling back to anthropic")
                self._provider_mode = "anthropic"

        if self._provider_mode in ("anthropic", "auto"):
            if anthropic_key:
                from .providers.anthropic_provider import AnthropicProvider
                self._primary = AnthropicProvider(api_key=anthropic_key)

            if self._provider_mode == "auto" and openai_key:
                from .providers.openai_provider import OpenAIProvider
                self._fallback = OpenAIProvider(api_key=openai_key)

    @property
    def active_provider(self) -> LLMProviderType:
        """Get the currently active provider type."""
        if self._using_fallback and self._fallback:
            return self._fallback.provider_type
        if self._primary:
            return self._primary.provider_type
        return LLMProviderType.ANTHROPIC

    async def create_message(
        self,
        model: str = "auto",
        max_tokens: int = 4096,
        system: str = "",
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tier: ModelTier | None = None,
    ) -> LLMResponse:
        """
        Create a message with automatic fallback.

        Args:
            model: Model identifier. Use "auto" for automatic tier-based selection,
                   or a specific model name (e.g., "claude-opus-4-5-20251101") to bypass.
            max_tokens: Maximum tokens in response
            system: System prompt
            messages: Conversation messages (in Anthropic format)
            tools: Tool definitions (in Anthropic schema format)
            tier: Explicit model tier override (FAST/BALANCED/POWERFUL).
                  Only used when model="auto".

        Returns:
            Normalized LLMResponse

        Raises:
            Exception: If all providers fail
        """
        if messages is None:
            messages = []

        # Resolve model when set to "auto"
        if model == "auto":
            model = select_model(
                provider=self.active_provider,
                tier=tier,
                max_tokens=max_tokens,
                tools_count=len(tools) if tools else 0,
                system_prompt_length=len(system),
            )

        # If already using fallback, go directly to fallback provider
        if self._using_fallback and self._fallback:
            return await self._call_provider(self._fallback, model, max_tokens, system, messages, tools)

        if not self._primary:
            raise RuntimeError("No LLM provider configured. Check API keys.")

        # Try primary provider, fall back to secondary on any failure
        try:
            return await self._call_provider(self._primary, model, max_tokens, system, messages, tools)
        except Exception as e:
            if self._fallback:
                logger.warning(
                    "Primary provider failed, falling back",
                    primary=self._primary.provider_type.value,
                    fallback=self._fallback.provider_type.value,
                    error=str(e)[:200],
                )
                self._using_fallback = True
                return await self._call_provider(self._fallback, model, max_tokens, system, messages, tools)
            raise

    async def _call_provider(
        self,
        provider: BaseLLMProvider,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        """Call a specific provider."""
        return await provider.create_message(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )

    def reset_fallback(self) -> None:
        """Reset fallback state to try primary provider again."""
        self._using_fallback = False
        logger.info("Fallback state reset, will try primary provider next")
