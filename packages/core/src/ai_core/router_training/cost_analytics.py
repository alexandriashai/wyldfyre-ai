"""
Cost Analytics for LLMRouter.

Provides utilities for tracking and reporting cost savings from
intelligent model tier routing decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..model_selector import ModelTier


# Cost per 1K tokens by tier (matches pricing.py)
COST_PER_1K_TOKENS = {
    ModelTier.FAST: {"input": 0.00025, "output": 0.00125},      # Haiku
    ModelTier.BALANCED: {"input": 0.003, "output": 0.015},       # Sonnet
    ModelTier.POWERFUL: {"input": 0.015, "output": 0.075},       # Opus
}

# String versions for convenience
COST_PER_1K_TOKENS_STR = {
    "fast": {"input": 0.00025, "output": 0.00125},
    "balanced": {"input": 0.003, "output": 0.015},
    "powerful": {"input": 0.015, "output": 0.075},
}


@dataclass
class RoutingDecision:
    """A single routing decision record."""
    timestamp: datetime
    from_tier: str
    to_tier: str
    estimated_input_tokens: float
    estimated_output_tokens: float = 0.0
    query_hash: str = ""


@dataclass
class CostAnalytics:
    """
    Aggregated cost analytics from routing decisions.
    """

    # Counts
    total_decisions: int = 0
    decisions_to_fast: int = 0
    decisions_to_balanced: int = 0
    decisions_to_powerful: int = 0

    # Token counts
    tokens_to_fast: float = 0.0
    tokens_to_balanced: float = 0.0
    tokens_to_powerful: float = 0.0

    # Cost tracking
    baseline_cost: float = 0.0  # What it would have cost at BALANCED
    actual_cost: float = 0.0    # What it actually cost after routing

    # Time range
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_savings(self) -> float:
        """Total cost savings in dollars."""
        return self.baseline_cost - self.actual_cost

    @property
    def savings_percent(self) -> float:
        """Savings as a percentage of baseline cost."""
        if self.baseline_cost == 0:
            return 0.0
        return (self.total_savings / self.baseline_cost) * 100

    @property
    def efficiency_ratio(self) -> float:
        """Ratio of actual cost to baseline cost (< 1.0 = savings)."""
        if self.baseline_cost == 0:
            return 1.0
        return self.actual_cost / self.baseline_cost

    @property
    def tier_distribution(self) -> dict[str, float]:
        """Distribution of decisions by tier."""
        if self.total_decisions == 0:
            return {"fast": 0.0, "balanced": 0.0, "powerful": 0.0}
        return {
            "fast": self.decisions_to_fast / self.total_decisions,
            "balanced": self.decisions_to_balanced / self.total_decisions,
            "powerful": self.decisions_to_powerful / self.total_decisions,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_decisions": self.total_decisions,
            "tier_distribution": {
                "fast": self.decisions_to_fast,
                "balanced": self.decisions_to_balanced,
                "powerful": self.decisions_to_powerful,
            },
            "tier_distribution_percent": {
                k: f"{v*100:.1f}%" for k, v in self.tier_distribution.items()
            },
            "tokens_redirected": {
                "fast": self.tokens_to_fast,
                "balanced": self.tokens_to_balanced,
                "powerful": self.tokens_to_powerful,
            },
            "cost_analysis": {
                "baseline_cost": f"${self.baseline_cost:.4f}",
                "actual_cost": f"${self.actual_cost:.4f}",
                "total_savings": f"${self.total_savings:.4f}",
                "savings_percent": f"{self.savings_percent:.1f}%",
                "efficiency_ratio": round(self.efficiency_ratio, 3),
            },
            "time_range": {
                "start": self.start_time.isoformat(),
                "end": self.end_time.isoformat(),
            },
        }


class CostAnalyticsTracker:
    """
    Tracks routing decisions and calculates cost analytics.

    Can be used standalone or integrated with Prometheus metrics.
    """

    def __init__(self):
        self._decisions: list[RoutingDecision] = []
        self._analytics = CostAnalytics()

    def record_decision(
        self,
        from_tier: ModelTier | str,
        to_tier: ModelTier | str,
        estimated_input_tokens: float,
        estimated_output_tokens: float = 0.0,
        query_hash: str = "",
    ):
        """
        Record a routing decision.

        Args:
            from_tier: Original tier (typically BALANCED)
            to_tier: Tier after routing decision
            estimated_input_tokens: Estimated input token count
            estimated_output_tokens: Estimated output token count
            query_hash: Optional hash for deduplication
        """
        # Normalize tier to string
        from_str = from_tier.value if isinstance(from_tier, ModelTier) else from_tier
        to_str = to_tier.value if isinstance(to_tier, ModelTier) else to_tier

        decision = RoutingDecision(
            timestamp=datetime.now(timezone.utc),
            from_tier=from_str,
            to_tier=to_str,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            query_hash=query_hash,
        )
        self._decisions.append(decision)

        # Update analytics
        self._update_analytics(decision)

        # Update Prometheus metrics if available
        self._update_prometheus_metrics(decision)

    def _update_analytics(self, decision: RoutingDecision):
        """Update aggregated analytics."""
        a = self._analytics
        a.total_decisions += 1
        a.end_time = decision.timestamp

        # Count by tier
        if decision.to_tier == "fast":
            a.decisions_to_fast += 1
            a.tokens_to_fast += decision.estimated_input_tokens
        elif decision.to_tier == "balanced":
            a.decisions_to_balanced += 1
            a.tokens_to_balanced += decision.estimated_input_tokens
        elif decision.to_tier == "powerful":
            a.decisions_to_powerful += 1
            a.tokens_to_powerful += decision.estimated_input_tokens

        # Calculate costs
        input_tokens = decision.estimated_input_tokens
        output_tokens = decision.estimated_output_tokens

        # Baseline: what it would cost at BALANCED
        baseline_input = COST_PER_1K_TOKENS_STR["balanced"]["input"] * input_tokens / 1000
        baseline_output = COST_PER_1K_TOKENS_STR["balanced"]["output"] * output_tokens / 1000
        a.baseline_cost += baseline_input + baseline_output

        # Actual: what it costs at the routed tier
        if decision.to_tier in COST_PER_1K_TOKENS_STR:
            actual_input = COST_PER_1K_TOKENS_STR[decision.to_tier]["input"] * input_tokens / 1000
            actual_output = COST_PER_1K_TOKENS_STR[decision.to_tier]["output"] * output_tokens / 1000
            a.actual_cost += actual_input + actual_output

    def _update_prometheus_metrics(self, decision: RoutingDecision):
        """Update Prometheus metrics if available."""
        try:
            from ..metrics import (
                routing_cost_savings_dollars,
                routing_tokens_redirected,
                routing_cost_efficiency_ratio,
            )

            # Calculate savings for this decision
            input_tokens = decision.estimated_input_tokens
            baseline = COST_PER_1K_TOKENS_STR["balanced"]["input"] * input_tokens / 1000
            actual = COST_PER_1K_TOKENS_STR.get(decision.to_tier, {}).get("input", 0.003) * input_tokens / 1000
            savings = baseline - actual

            # Counters can only be incremented by non-negative amounts
            # Track savings separately: positive = actual savings, use cost_increase for negative
            if savings >= 0:
                routing_cost_savings_dollars.labels(
                    from_tier=decision.from_tier,
                    to_tier=decision.to_tier,
                ).inc(savings)

            routing_tokens_redirected.labels(
                to_tier=decision.to_tier,
            ).inc(input_tokens)

            # Update efficiency ratio gauge
            if self._analytics.baseline_cost > 0:
                routing_cost_efficiency_ratio.set(self._analytics.efficiency_ratio)

        except (ImportError, Exception):
            pass  # Metrics not critical

    def get_analytics(self) -> CostAnalytics:
        """Get current analytics."""
        return self._analytics

    def get_summary(self) -> dict[str, Any]:
        """Get analytics as a dictionary."""
        return self._analytics.to_dict()

    def reset(self):
        """Reset all tracked data."""
        self._decisions.clear()
        self._analytics = CostAnalytics()


# Global tracker instance
_tracker: CostAnalyticsTracker | None = None


def get_cost_analytics_tracker() -> CostAnalyticsTracker:
    """Get or create the global cost analytics tracker."""
    global _tracker
    if _tracker is None:
        _tracker = CostAnalyticsTracker()
    return _tracker


def calculate_routing_savings(
    tier_distribution: dict[str, float],
    total_input_tokens: float,
    total_output_tokens: float = 0.0,
) -> dict[str, Any]:
    """
    Calculate potential savings from a tier distribution.

    Args:
        tier_distribution: Dict with tier percentages (e.g., {"fast": 0.35, "balanced": 0.40, "powerful": 0.25})
        total_input_tokens: Total input tokens to consider
        total_output_tokens: Total output tokens to consider

    Returns:
        Dictionary with cost analysis
    """
    # Baseline: all at BALANCED
    baseline_input = COST_PER_1K_TOKENS_STR["balanced"]["input"] * total_input_tokens / 1000
    baseline_output = COST_PER_1K_TOKENS_STR["balanced"]["output"] * total_output_tokens / 1000
    baseline_total = baseline_input + baseline_output

    # Routed cost
    routed_input = sum(
        COST_PER_1K_TOKENS_STR[tier]["input"] * total_input_tokens * ratio / 1000
        for tier, ratio in tier_distribution.items()
    )
    routed_output = sum(
        COST_PER_1K_TOKENS_STR[tier]["output"] * total_output_tokens * ratio / 1000
        for tier, ratio in tier_distribution.items()
    )
    routed_total = routed_input + routed_output

    savings = baseline_total - routed_total
    savings_percent = (savings / baseline_total * 100) if baseline_total > 0 else 0

    return {
        "baseline_cost": round(baseline_total, 4),
        "routed_cost": round(routed_total, 4),
        "savings": round(savings, 4),
        "savings_percent": round(savings_percent, 1),
        "tier_distribution": tier_distribution,
        "tokens": {
            "input": total_input_tokens,
            "output": total_output_tokens,
        },
    }


def estimate_monthly_savings(
    requests_per_day: int,
    avg_input_tokens: float = 500,
    avg_output_tokens: float = 200,
    tier_distribution: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Estimate monthly cost savings from routing.

    Args:
        requests_per_day: Average requests per day
        avg_input_tokens: Average input tokens per request
        avg_output_tokens: Average output tokens per request
        tier_distribution: Expected tier distribution after routing

    Returns:
        Dictionary with monthly projections
    """
    if tier_distribution is None:
        # Default estimated distribution from training
        tier_distribution = {"fast": 0.35, "balanced": 0.40, "powerful": 0.25}

    daily_input_tokens = requests_per_day * avg_input_tokens
    daily_output_tokens = requests_per_day * avg_output_tokens

    daily = calculate_routing_savings(
        tier_distribution,
        daily_input_tokens,
        daily_output_tokens,
    )

    return {
        "daily": daily,
        "monthly": {
            "baseline_cost": round(daily["baseline_cost"] * 30, 2),
            "routed_cost": round(daily["routed_cost"] * 30, 2),
            "savings": round(daily["savings"] * 30, 2),
            "savings_percent": daily["savings_percent"],
        },
        "assumptions": {
            "requests_per_day": requests_per_day,
            "avg_input_tokens": avg_input_tokens,
            "avg_output_tokens": avg_output_tokens,
            "tier_distribution": tier_distribution,
        },
    }
