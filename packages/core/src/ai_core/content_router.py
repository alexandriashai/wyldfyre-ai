"""
Content-based model routing using LLMRouter.

Analyzes prompt content to refine tier selection beyond structural heuristics.
Only invoked for BALANCED-tier requests (the uncertain middle ground).
Uses a two-threshold approach: score > UP_THRESHOLD -> POWERFUL,
score < DOWN_THRESHOLD -> FAST, otherwise keep BALANCED.
"""

import asyncio
import hashlib
import os
import time
from typing import Any

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
from .logging import get_logger
from .model_selector import ModelTier

logger = get_logger(__name__)

# Configuration via environment variables with sensible defaults
ROUTER_ENABLED_KEY = "llm:router_enabled"  # Redis key to enable/disable
UP_THRESHOLD = float(os.environ.get("CONTENT_ROUTER_UP_THRESHOLD", "0.75"))
DOWN_THRESHOLD = float(os.environ.get("CONTENT_ROUTER_DOWN_THRESHOLD", "0.30"))
LATENCY_BUDGET_MS = int(os.environ.get("CONTENT_ROUTER_LATENCY_BUDGET_MS", "50"))
ROUTER_TYPE = os.environ.get("CONTENT_ROUTER_TYPE", "mf")
CACHE_TTL = 300  # Cache routing decisions for 5 min (same prompt pattern)


class ContentRouter:
    """
    Content-based LLM routing using LLMRouter library.

    Uses a trained router model to analyze prompt complexity and
    decide if a BALANCED request should be upgraded to POWERFUL
    or downgraded to FAST.
    """

    def __init__(self, redis: Any = None):
        self._router = None  # Lazy-loaded LLMRouter instance
        self._redis = redis
        self._enabled = os.environ.get("CONTENT_ROUTER_ENABLED", "true").lower() == "true"
        self._up_threshold = UP_THRESHOLD
        self._down_threshold = DOWN_THRESHOLD
        self._latency_budget_ms = LATENCY_BUDGET_MS
        self._router_type = ROUTER_TYPE
        self._cache: dict[str, tuple[ModelTier, float]] = {}  # hash -> (tier, timestamp)
        self._circuit_breaker = get_circuit_breaker(
            "content-router",
            CircuitBreakerConfig(failure_threshold=5, timeout=30.0),
        )

    def _get_router(self):
        """Lazy-load the LLMRouter model."""
        if self._router is None:
            from llmrouter import Router

            # Use the configured router type (default: mf - matrix factorization)
            self._router = Router(router_type=self._router_type)
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

    async def _do_route(self, messages: list[dict], system: str) -> ModelTier:
        """Execute the actual routing logic."""
        from .metrics import routing_latency_seconds

        start = time.monotonic()
        router = self._get_router()

        # Build the prompt text for the router
        prompt_text = self._extract_prompt_text(messages, system)

        # Get routing score (0.0 = simple/FAST, 1.0 = complex/POWERFUL)
        score = await asyncio.wait_for(
            asyncio.to_thread(router.route, prompt_text),
            timeout=self._latency_budget_ms / 1000,
        )

        elapsed_ms = (time.monotonic() - start) * 1000
        routing_latency_seconds.observe(elapsed_ms / 1000)

        # Two-threshold decision
        if score >= self._up_threshold:
            return ModelTier.POWERFUL
        elif score <= self._down_threshold:
            return ModelTier.FAST
        else:
            return ModelTier.BALANCED  # Uncertain -> keep default

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

                val = await self._redis.client.get("llm:router_up_threshold")
                if val is not None:
                    self._up_threshold = float(val)

                val = await self._redis.client.get("llm:router_down_threshold")
                if val is not None:
                    self._down_threshold = float(val)

                val = await self._redis.client.get("llm:router_latency_budget_ms")
                if val is not None:
                    self._latency_budget_ms = int(val)

                val = await self._redis.client.get("llm:router_type")
                if val is not None and val != self._router_type:
                    self._router_type = val
                    self._router = None  # Force re-init with new type
            except Exception:
                pass

    def update_config(
        self,
        enabled: bool | None = None,
        up_threshold: float | None = None,
        down_threshold: float | None = None,
        latency_budget_ms: int | None = None,
        router_type: str | None = None,
    ):
        """Update in-memory config (called by API after Redis write)."""
        if enabled is not None:
            self._enabled = enabled
        if up_threshold is not None:
            self._up_threshold = up_threshold
        if down_threshold is not None:
            self._down_threshold = down_threshold
        if latency_budget_ms is not None:
            self._latency_budget_ms = latency_budget_ms
        if router_type is not None and router_type != self._router_type:
            self._router_type = router_type
            self._router = None  # Force re-init with new type


# Global singleton
_content_router: ContentRouter | None = None


def get_content_router(redis: Any = None) -> ContentRouter:
    """Get or create the global ContentRouter instance."""
    global _content_router
    if _content_router is None:
        _content_router = ContentRouter(redis=redis)
    return _content_router
