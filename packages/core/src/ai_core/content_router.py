"""
Content-based model routing using LLMRouter (MFRouter).

Analyzes prompt content to refine tier selection beyond structural heuristics.
Only invoked for BALANCED-tier requests (the uncertain middle ground).
Uses MFRouter's matrix factorization model to predict the optimal tier
based on learned query complexity patterns.

Also provides prompt tier classification for dynamic prompt sizing.
"""

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
from .logging import get_logger
from .model_selector import ModelTier, PromptTier

logger = get_logger(__name__)

# Configuration via environment variables with sensible defaults
ROUTER_ENABLED_KEY = "llm:router_enabled"  # Redis key to enable/disable
# Default 2000ms (2s) timeout - Longformer embedding takes ~1-2s on CPU
# For production, consider pre-computing embeddings or using GPU
LATENCY_BUDGET_MS = int(os.environ.get("CONTENT_ROUTER_LATENCY_BUDGET_MS", "2000"))
ROUTER_CONFIG_PATH = os.environ.get(
    "CONTENT_ROUTER_CONFIG_PATH",
    "/home/wyld-core/config/router/router_config.yaml"
)
CACHE_TTL = 300  # Cache routing decisions for 5 min (same prompt pattern)


@dataclass
class RoutingResult:
    """Result of content routing including both model and prompt tiers."""

    model_tier: ModelTier
    prompt_tier: PromptTier
    from_cache: bool = False

    def __iter__(self):
        """Allow tuple unpacking: model_tier, prompt_tier = result"""
        return iter((self.model_tier, self.prompt_tier))


# Cost tracking constants (per 1K tokens)
COST_PER_1K_TOKENS = {
    ModelTier.FAST: {"input": 0.00025, "output": 0.00125},      # Haiku
    ModelTier.BALANCED: {"input": 0.003, "output": 0.015},       # Sonnet
    ModelTier.POWERFUL: {"input": 0.015, "output": 0.075},       # Opus
}


class ContentRouter:
    """
    Content-based LLM routing using MFRouter (LLMRouter library).

    Uses a trained matrix factorization model to analyze prompt complexity
    and decide if a BALANCED request should be upgraded to POWERFUL
    or downgraded to FAST. Includes cost tracking for analytics.
    """

    def __init__(self, redis: Any = None):
        self._router = None  # Lazy-loaded MFRouter instance
        self._redis = redis
        self._enabled = os.environ.get("CONTENT_ROUTER_ENABLED", "true").lower() == "true"
        self._latency_budget_ms = LATENCY_BUDGET_MS
        self._cache: dict[str, tuple[ModelTier, float]] = {}  # hash -> (tier, timestamp)
        self._circuit_breaker = get_circuit_breaker(
            "content-router",
            CircuitBreakerConfig(failure_threshold=5, timeout=30.0),
        )
        self._cost_tracking_enabled = True

    def _get_router(self):
        """Lazy-load the MFRouter model."""
        if self._router is None:
            # Check if config path is set and exists
            if not ROUTER_CONFIG_PATH:
                logger.info("CONTENT_ROUTER_CONFIG_PATH not set, disabling content routing")
                self._enabled = False
                return None

            import os.path
            if not os.path.exists(ROUTER_CONFIG_PATH):
                logger.info(f"Router config not found at {ROUTER_CONFIG_PATH}, disabling content routing")
                self._enabled = False
                return None

            try:
                from llmrouter.models.mfrouter.router import MFRouter
                self._router = MFRouter(yaml_path=ROUTER_CONFIG_PATH)
                logger.info(f"Loaded MFRouter from {ROUTER_CONFIG_PATH}")
            except ImportError:
                logger.warning("llmrouter package not installed, disabling content routing")
                self._enabled = False
                return None
            except Exception as e:
                logger.warning(f"Failed to load MFRouter, disabling content routing: {e}")
                self._enabled = False
                return None
        return self._router

    async def route(
        self,
        messages: list[dict],
        system: str = "",
        current_tier: ModelTier = ModelTier.BALANCED,
    ) -> ModelTier:
        """
        Analyze content and return recommended tier.

        Only refines BALANCED tier decisions. Returns current_tier unchanged
        if router is disabled, circuit is open, or decision is uncertain.
        """
        from .metrics import routing_decisions_total

        # Only route BALANCED tier (FAST/POWERFUL already decided by structure)
        if current_tier != ModelTier.BALANCED:
            return current_tier

        # Check if enabled
        if not self._enabled:
            return current_tier

        # Check cache (hash of last user message)
        cache_key = self._compute_cache_key(messages, system)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Route with circuit breaker + latency budget
        try:
            tier = await self._circuit_breaker.call(
                self._do_route, messages, system
            )
            self._cache_result(cache_key, tier)
            routing_decisions_total.labels(
                from_tier="balanced", to_tier=tier.value
            ).inc()
            return tier
        except Exception:
            # Fallback: keep BALANCED on any failure
            routing_decisions_total.labels(
                from_tier="balanced", to_tier="fallback"
            ).inc()
            return current_tier

    async def route_with_prompt_tier(
        self,
        messages: list[dict],
        system: str = "",
        current_tier: ModelTier = ModelTier.BALANCED,
        tools_count: int = 0,
    ) -> RoutingResult:
        """
        Route request and determine both model tier and prompt tier.

        This method combines model routing with prompt tier classification
        for maximum cost optimization.

        Args:
            messages: Conversation messages
            system: System prompt text
            current_tier: Initial model tier from structural analysis
            tools_count: Number of tools available

        Returns:
            RoutingResult with model_tier and prompt_tier
        """
        from .prompt_tier import classify_prompt_tier

        # Get model tier (using existing routing)
        model_tier = await self.route(messages, system, current_tier)

        # Classify prompt tier based on request complexity
        has_context = len(messages) > 2
        prompt_tier, _category = classify_prompt_tier(
            messages, tools_count, has_context
        )

        # Align prompt tier with model tier for consistency
        # FAST model should use MINIMAL prompt, POWERFUL should allow FULL
        if model_tier == ModelTier.FAST and prompt_tier != PromptTier.MINIMAL:
            prompt_tier = PromptTier.MINIMAL
        elif model_tier == ModelTier.POWERFUL and prompt_tier == PromptTier.MINIMAL:
            prompt_tier = PromptTier.STANDARD  # Don't use minimal with powerful model

        logger.debug(
            "Routed request with prompt tier",
            model_tier=model_tier.value,
            prompt_tier=prompt_tier.value,
            tools_count=tools_count,
        )

        return RoutingResult(
            model_tier=model_tier,
            prompt_tier=prompt_tier,
            from_cache=False,
        )

    async def _do_route(self, messages: list[dict], system: str) -> ModelTier:
        """Execute routing and track cost impact."""
        from .metrics import routing_latency_seconds

        start = time.monotonic()
        router = self._get_router()

        # If router failed to load, return BALANCED
        if router is None:
            return ModelTier.BALANCED

        # Build the prompt text for the router
        prompt_text = self._extract_prompt_text(messages, system)

        # Use MFRouter's route_single() method for tier prediction
        result = await asyncio.wait_for(
            asyncio.to_thread(router.route_single, {"query": prompt_text}),
            timeout=self._latency_budget_ms / 1000,
        )

        elapsed_ms = (time.monotonic() - start) * 1000
        routing_latency_seconds.observe(elapsed_ms / 1000)

        # Map model_name to ModelTier
        model_name = result.get("model_name", "balanced")
        selected_tier = self._tier_from_model_name(model_name)

        # Track cost analytics
        if self._cost_tracking_enabled:
            # Rough token estimate: words * 1.3
            estimated_tokens = len(prompt_text.split()) * 1.3
            self._record_routing_cost_impact(
                from_tier=ModelTier.BALANCED,
                to_tier=selected_tier,
                estimated_tokens=estimated_tokens,
            )

        return selected_tier

    def _tier_from_model_name(self, model_name: str) -> ModelTier:
        """Map MFRouter model name to ModelTier."""
        mapping = {
            "fast": ModelTier.FAST,
            "balanced": ModelTier.BALANCED,
            "powerful": ModelTier.POWERFUL,
        }
        return mapping.get(model_name.lower(), ModelTier.BALANCED)

    def _record_routing_cost_impact(
        self,
        from_tier: ModelTier,
        to_tier: ModelTier,
        estimated_tokens: float,
    ):
        """Record cost savings/increase from routing decision."""
        # Update Prometheus metrics
        try:
            from .metrics import (
                routing_cost_savings_dollars,
                routing_tokens_redirected,
            )

            baseline_cost = COST_PER_1K_TOKENS[from_tier]["input"] * estimated_tokens / 1000
            actual_cost = COST_PER_1K_TOKENS[to_tier]["input"] * estimated_tokens / 1000
            savings = baseline_cost - actual_cost

            # Counters can only be incremented by non-negative amounts
            if savings >= 0:
                routing_cost_savings_dollars.labels(
                    from_tier=from_tier.value,
                    to_tier=to_tier.value,
                ).inc(savings)

            routing_tokens_redirected.labels(
                to_tier=to_tier.value,
            ).inc(estimated_tokens)
        except Exception:
            pass  # Metrics not critical

        # Update cost analytics tracker (handles both savings and costs)
        try:
            from .router_training.cost_analytics import get_cost_analytics_tracker
            tracker = get_cost_analytics_tracker()
            tracker.record_decision(
                from_tier=from_tier,
                to_tier=to_tier,
                estimated_input_tokens=estimated_tokens,
            )
        except Exception:
            pass  # Analytics not critical

    def _extract_prompt_text(self, messages: list[dict], system: str) -> str:
        """Extract text from messages for router input."""
        parts = []
        if system:
            parts.append(system[:500])  # Limit system prompt contribution
        # Use last 2 user messages for context
        user_msgs = [m for m in messages if m.get("role") == "user"]
        for msg in user_msgs[-2:]:
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content[:1000])
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", "")[:1000])
        return "\n".join(parts)

    def _compute_cache_key(self, messages: list[dict], system: str) -> str:
        """Compute cache key from message content."""
        text = self._extract_prompt_text(messages, system)
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _get_cached(self, key: str) -> ModelTier | None:
        """Get cached routing decision if still valid."""
        if key in self._cache:
            tier, ts = self._cache[key]
            if time.time() - ts < CACHE_TTL:
                return tier
            del self._cache[key]
        return None

    def _cache_result(self, key: str, tier: ModelTier):
        """Cache a routing decision."""
        # Evict old entries if cache too large
        if len(self._cache) > 1000:
            cutoff = time.time() - CACHE_TTL
            self._cache = {k: v for k, v in self._cache.items() if v[1] > cutoff}
        self._cache[key] = (tier, time.time())

    async def set_enabled(self, enabled: bool):
        """Enable/disable the router (persists to Redis if available)."""
        self._enabled = enabled
        if self._redis:
            await self._redis.client.set(ROUTER_ENABLED_KEY, "1" if enabled else "0")

    async def load_state(self):
        """Load all config from Redis."""
        if self._redis:
            try:
                val = await self._redis.client.get(ROUTER_ENABLED_KEY)
                if val is not None:
                    self._enabled = val == "1"

                val = await self._redis.client.get("llm:router_latency_budget_ms")
                if val is not None:
                    self._latency_budget_ms = int(val)

                val = await self._redis.client.get("llm:router_cost_tracking")
                if val is not None:
                    self._cost_tracking_enabled = val == "1"
            except Exception:
                pass

    def update_config(
        self,
        enabled: bool | None = None,
        latency_budget_ms: int | None = None,
        cost_tracking_enabled: bool | None = None,
    ):
        """Update in-memory config (called by API after Redis write)."""
        if enabled is not None:
            self._enabled = enabled
        if latency_budget_ms is not None:
            self._latency_budget_ms = latency_budget_ms
        if cost_tracking_enabled is not None:
            self._cost_tracking_enabled = cost_tracking_enabled

    def reload_router(self):
        """Force reload of the MFRouter model."""
        self._router = None
        logger.info("MFRouter marked for reload on next request")


# Global singleton
_content_router: ContentRouter | None = None


def get_content_router(redis: Any = None) -> ContentRouter:
    """Get or create the global ContentRouter instance."""
    global _content_router
    if _content_router is None:
        _content_router = ContentRouter(redis=redis)
    return _content_router
