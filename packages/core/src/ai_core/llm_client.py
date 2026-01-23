"""
LLM Client - Facade with automatic provider fallback.

Provides a unified interface for LLM calls with automatic fallback
from Anthropic to OpenAI when credits run out or rate limits are hit.
Includes retry with backoff for transient errors and periodic primary
provider recovery.
"""

import asyncio
import os
import time
from typing import Any

from .config import get_settings
from .logging import get_logger
from .llm_provider import (
    BaseLLMProvider,
    LLMProviderType,
    LLMResponse,
)
from .model_selector import ModelTier, TIER_MODELS, select_model

logger = get_logger(__name__)

# Status codes that indicate credit/billing issues (permanent until resolved)
CREDIT_STATUS_CODES = {402}  # Payment Required

# Status codes that are transient and should be retried
RETRY_STATUS_CODES = {429, 529}  # Rate limited, Overloaded

# All codes that can trigger fallback after retries exhausted
FALLBACK_STATUS_CODES = {402, 429, 529}

# Error keywords indicating credit/billing exhaustion
CREDIT_ERROR_KEYWORDS = [
    "credit",
    "insufficient_quota",
    "billing",
    "payment",
    "balance",
]

# Error keywords indicating transient overload
RETRY_ERROR_KEYWORDS = [
    "overloaded",
    "rate_limit",
    "too_many_requests",
    "capacity",
]

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds
RETRY_MAX_DELAY = 30.0  # seconds

# How long to stay on fallback before trying primary again (5 minutes)
FALLBACK_RECOVERY_INTERVAL = 300

# Redis key that disables primary provider until manually deleted
FALLBACK_DISABLED_KEY = "llm:primary_disabled"


def _is_credit_error(error: Exception) -> bool:
    """Check if error is a credit/billing issue (non-transient)."""
    error_str = str(error).lower()
    status_code = getattr(error, "status_code", None)

    if status_code in CREDIT_STATUS_CODES:
        return True

    for keyword in CREDIT_ERROR_KEYWORDS:
        if keyword in error_str:
            return True

    return False


def _is_retryable_error(error: Exception) -> bool:
    """Check if error is transient and worth retrying."""
    error_str = str(error).lower()
    status_code = getattr(error, "status_code", None)

    if status_code in RETRY_STATUS_CODES:
        return True

    for keyword in RETRY_ERROR_KEYWORDS:
        if keyword in error_str:
            return True

    return False


def _should_fallback(error: Exception) -> bool:
    """Check if an error should trigger provider fallback."""
    return _is_credit_error(error) or _is_retryable_error(error)


class LLMClient:
    """
    LLM Client with automatic provider fallback.

    Reads AI_PROVIDER env var:
    - "anthropic": Only use Anthropic (default behavior)
    - "openai": Only use OpenAI
    - "auto": Try Anthropic first, fall back to OpenAI on credit/rate errors

    Features:
    - Retry with exponential backoff for transient errors (429, 529)
    - Immediate fallback for credit/billing errors (402)
    - Periodic primary provider recovery (tries primary again after interval)
    - Model re-resolution for fallback provider
    """

    def __init__(self, redis=None):
        settings = get_settings()
        self._provider_mode = os.environ.get("AI_PROVIDER", "auto").lower()
        self._primary: BaseLLMProvider | None = None
        self._fallback: BaseLLMProvider | None = None
        self._using_fallback = False
        self._fallback_since: float = 0  # timestamp when fallback started
        self._fallback_reason: str = ""  # why we fell back
        self._redis = redis  # Optional RedisClient for persistent fallback state

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

    async def _check_fallback_recovery(self) -> None:
        """Check if primary provider should be recovered from fallback."""
        if not self._using_fallback:
            return

        # Credit exhaustion: only recover if manually re-enabled (Redis key deleted)
        if self._fallback_reason == "credit_exhausted":
            if self._redis:
                try:
                    disabled = await self._redis.client.exists(FALLBACK_DISABLED_KEY)
                    if not disabled:
                        logger.info("Primary provider manually re-enabled")
                        self._using_fallback = False
                        self._fallback_reason = ""
                except Exception as e:
                    logger.debug("Redis check for fallback recovery failed", error=str(e))
            return

        # Rate limits: keep existing 300s auto-recovery
        elapsed = time.time() - self._fallback_since
        if elapsed >= FALLBACK_RECOVERY_INTERVAL:
            logger.info(
                "Fallback recovery: trying primary provider again",
                elapsed_seconds=int(elapsed),
                fallback_reason=self._fallback_reason,
            )
            self._using_fallback = False
            self._fallback_reason = ""

    # Map tier shorthand strings to ModelTier enum
    _TIER_SHORTCUTS = {
        "fast": ModelTier.FAST,
        "balanced": ModelTier.BALANCED,
        "powerful": ModelTier.POWERFUL,
    }

    def _resolve_model(self, model: str, provider: LLMProviderType, tier: ModelTier | None,
                       max_tokens: int, tools: list[dict[str, Any]] | None, system: str) -> str:
        """
        Resolve model name for a specific provider.

        Handles:
        - "auto": auto-detect tier from task complexity
        - "fast"/"balanced"/"powerful": explicit tier shorthand
        - Specific model names (e.g. "claude-sonnet-4-20250514"): pass through
        """
        # Check for tier shorthand strings (used by subagents)
        if model in self._TIER_SHORTCUTS:
            return select_model(
                provider=provider,
                tier=self._TIER_SHORTCUTS[model],
            )

        # Auto mode: detect tier from task signals
        if model == "auto":
            return select_model(
                provider=provider,
                tier=tier,
                max_tokens=max_tokens,
                tools_count=len(tools) if tools else 0,
                system_prompt_length=len(system),
            )

        # Specific model name: pass through
        return model

    async def create_message(
        self,
        model: str = "auto",
        max_tokens: int = 4096,
        system: str = "",
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tier: ModelTier | None = None,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """
        Create a message with retry and automatic fallback.

        Behavior:
        1. For transient errors (429/529): retry with exponential backoff
        2. For credit errors (402): immediately fall back to secondary provider
        3. For other errors: raise without fallback
        4. Periodically tries to recover primary provider after fallback

        Args:
            model: Model identifier. Use "auto" for automatic tier-based selection,
                   or a specific model name (e.g., "claude-opus-4-5-20251101") to bypass.
            max_tokens: Maximum tokens in response
            system: System prompt
            messages: Conversation messages (in Anthropic format)
            tools: Tool definitions (in Anthropic schema format)
            tier: Explicit model tier override (FAST/BALANCED/POWERFUL).
                  Only used when model="auto".
            reasoning_effort: Reasoning effort level for supported models
                  (none/minimal/low/medium/high). Auto-set to "high" for
                  POWERFUL tier on OpenAI if not specified.

        Returns:
            Normalized LLMResponse

        Raises:
            Exception: If all providers fail or error is not fallback-eligible
        """
        if messages is None:
            messages = []

        # Check if we should try recovering from fallback
        await self._check_fallback_recovery()

        # If already using fallback, resolve model for fallback provider and call it
        if self._using_fallback and self._fallback:
            fallback_model = self._resolve_model(
                model, self._fallback.provider_type, tier, max_tokens, tools, system
            )
            # Auto-set reasoning_effort for POWERFUL tier on OpenAI
            effective_effort = reasoning_effort
            if (effective_effort is None
                    and self._fallback.provider_type == LLMProviderType.OPENAI
                    and fallback_model == TIER_MODELS[LLMProviderType.OPENAI][ModelTier.POWERFUL]):
                effective_effort = "high"
            return await self._call_with_retry(
                self._fallback, fallback_model, max_tokens, system, messages, tools,
                reasoning_effort=effective_effort,
            )

        if not self._primary:
            raise RuntimeError("No LLM provider configured. Check API keys.")

        # Resolve model for primary provider
        primary_model = self._resolve_model(
            model, self._primary.provider_type, tier, max_tokens, tools, system
        )

        # Auto-set reasoning_effort for POWERFUL tier on OpenAI (when primary is OpenAI)
        effective_effort = reasoning_effort
        if (effective_effort is None
                and self._primary.provider_type == LLMProviderType.OPENAI
                and primary_model == TIER_MODELS[LLMProviderType.OPENAI][ModelTier.POWERFUL]):
            effective_effort = "high"

        # Try primary provider with retry
        try:
            return await self._call_with_retry(
                self._primary, primary_model, max_tokens, system, messages, tools,
                reasoning_effort=effective_effort,
            )
        except Exception as e:
            # Only fall back for credit/rate errors, not arbitrary failures
            if self._fallback and _should_fallback(e):
                reason = "credit_exhausted" if _is_credit_error(e) else "rate_limited"
                logger.warning(
                    "Primary provider failed, falling back",
                    primary=self._primary.provider_type.value,
                    fallback=self._fallback.provider_type.value,
                    reason=reason,
                    error=str(e)[:200],
                )
                self._using_fallback = True
                self._fallback_since = time.time()
                self._fallback_reason = reason

                # Persist disabled state for credit exhaustion
                if reason == "credit_exhausted" and self._redis:
                    try:
                        await self._redis.client.set(FALLBACK_DISABLED_KEY, "1")
                        logger.info("Primary provider disabled until manual re-enable (DEL llm:primary_disabled)")
                    except Exception as redis_err:
                        logger.debug("Failed to set fallback disabled key", error=str(redis_err))

                # Resolve model for fallback provider
                fallback_model = self._resolve_model(
                    model, self._fallback.provider_type, tier, max_tokens, tools, system
                )
                # Auto-set reasoning_effort for POWERFUL tier on OpenAI
                fallback_effort = reasoning_effort
                if (fallback_effort is None
                        and self._fallback.provider_type == LLMProviderType.OPENAI
                        and fallback_model == TIER_MODELS[LLMProviderType.OPENAI][ModelTier.POWERFUL]):
                    fallback_effort = "high"
                return await self._call_with_retry(
                    self._fallback, fallback_model, max_tokens, system, messages, tools,
                    reasoning_effort=fallback_effort,
                )
            raise

    async def _call_with_retry(
        self,
        provider: BaseLLMProvider,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """
        Call a provider with retry for transient errors.

        Retries with exponential backoff for rate limits (429) and
        overloaded (529). Immediately raises for credit errors (402)
        and non-retryable failures.
        """
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                kwargs: dict[str, Any] = {}
                if reasoning_effort:
                    kwargs["reasoning_effort"] = reasoning_effort
                return await provider.create_message(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    tools=tools,
                    **kwargs,
                )
            except Exception as e:
                last_error = e

                # Credit errors: don't retry, fail immediately (caller handles fallback)
                if _is_credit_error(e):
                    raise

                # Retryable errors: wait and try again
                if _is_retryable_error(e) and attempt < MAX_RETRIES:
                    delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                    logger.warning(
                        "Retryable error, backing off",
                        provider=provider.provider_type.value,
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        delay=delay,
                        error=str(e)[:100],
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-retryable, non-credit error: raise immediately
                raise

        # Exhausted retries
        raise last_error  # type: ignore[misc]

    def reset_fallback(self) -> None:
        """Reset fallback state to try primary provider again."""
        self._using_fallback = False
        self._fallback_since = 0
        self._fallback_reason = ""
        logger.info("Fallback state reset, will try primary provider next")
