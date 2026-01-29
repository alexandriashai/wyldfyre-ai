"""
Prompt Tier System - Dynamic prompt sizing based on request complexity.

Reduces API costs by using smaller prompts for simple requests while
maintaining full capabilities for complex tasks.

Tiers:
- MINIMAL (~500 tokens): Core instructions only - simple Q&A, basic tasks
- STANDARD (~2K tokens): Core + common scenarios - typical agent tasks
- FULL (~5K+ tokens): Everything including edge cases - complex reasoning

Expected savings: 60-80% on simple requests, 30-40% on average.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .logging import get_logger
from .model_selector import PromptTier

logger = get_logger(__name__)


class TaskCategory(str, Enum):
    """Categories for task classification."""

    CHAT = "chat"              # Simple conversation, Q&A
    SEARCH = "search"          # File/code search
    READ = "read"              # Reading/understanding code
    WRITE = "write"            # Writing/editing code
    PLAN = "plan"              # Planning/architecture
    EXECUTE = "execute"        # Running commands, multi-step
    COMPLEX = "complex"        # Complex reasoning, debugging


# Map task categories to default prompt tiers
CATEGORY_TO_TIER: dict[TaskCategory, PromptTier] = {
    TaskCategory.CHAT: PromptTier.MINIMAL,
    TaskCategory.SEARCH: PromptTier.MINIMAL,
    TaskCategory.READ: PromptTier.STANDARD,
    TaskCategory.WRITE: PromptTier.STANDARD,
    TaskCategory.PLAN: PromptTier.STANDARD,
    TaskCategory.EXECUTE: PromptTier.FULL,
    TaskCategory.COMPLEX: PromptTier.FULL,
}


@dataclass
class PromptSection:
    """A section of a system prompt with tier requirement."""

    name: str
    content: str
    min_tier: PromptTier = PromptTier.MINIMAL
    tokens_estimate: int = 0  # Rough estimate for budgeting

    def __post_init__(self):
        if self.tokens_estimate == 0:
            # Estimate ~4 chars per token
            self.tokens_estimate = len(self.content) // 4 + 1


@dataclass
class TieredPromptConfig:
    """Configuration for tiered prompt building."""

    # Core identity (always included)
    core_identity: str = ""

    # Sections organized by tier
    sections: list[PromptSection] = field(default_factory=list)

    # Tool descriptions (can be subset based on task)
    tool_sections: dict[str, PromptSection] = field(default_factory=dict)

    def get_prompt(self, tier: PromptTier, tools_needed: set[str] | None = None) -> str:
        """Build prompt for the given tier."""
        parts = [self.core_identity]

        # Add sections up to the tier level
        tier_order = [PromptTier.MINIMAL, PromptTier.STANDARD, PromptTier.FULL]
        tier_idx = tier_order.index(tier)

        for section in self.sections:
            section_idx = tier_order.index(section.min_tier)
            if section_idx <= tier_idx:
                parts.append(f"\n## {section.name}\n{section.content}")

        # Add tool sections if specified
        if tools_needed and self.tool_sections:
            tool_parts = []
            for tool_name in tools_needed:
                if tool_name in self.tool_sections:
                    section = self.tool_sections[tool_name]
                    section_idx = tier_order.index(section.min_tier)
                    if section_idx <= tier_idx:
                        tool_parts.append(section.content)
            if tool_parts:
                parts.append("\n## Available Tools\n" + "\n".join(tool_parts))

        return "\n".join(parts)

    def estimate_tokens(self, tier: PromptTier) -> int:
        """Estimate token count for a tier."""
        total = len(self.core_identity) // 4 + 1

        tier_order = [PromptTier.MINIMAL, PromptTier.STANDARD, PromptTier.FULL]
        tier_idx = tier_order.index(tier)

        for section in self.sections:
            section_idx = tier_order.index(section.min_tier)
            if section_idx <= tier_idx:
                total += section.tokens_estimate

        return total


class PromptTierClassifier:
    """
    Classifies requests to determine appropriate prompt tier.

    Uses lightweight heuristics for fast classification:
    - Message length and complexity signals
    - Keyword detection for task type
    - Tool requirements
    """

    # Keywords that suggest simple tasks (-> MINIMAL)
    SIMPLE_KEYWORDS = frozenset([
        "what is", "what's", "explain", "tell me", "how does",
        "where is", "find", "search", "list", "show",
        "hello", "hi", "thanks", "thank you",
    ])

    # Keywords that suggest complex tasks (-> FULL)
    COMPLEX_KEYWORDS = frozenset([
        "implement", "refactor", "debug", "fix bug", "architecture",
        "design", "optimize", "security", "migrate", "integrate",
        "multi-file", "across", "all files", "entire", "comprehensive",
    ])

    # Keywords that suggest code writing (-> STANDARD)
    CODE_KEYWORDS = frozenset([
        "write", "create", "add", "modify", "update", "change",
        "edit", "function", "class", "method", "test",
    ])

    def __init__(self):
        self._cache: dict[str, tuple[PromptTier, TaskCategory]] = {}

    def classify(
        self,
        messages: list[dict[str, Any]],
        tools_count: int = 0,
        has_context: bool = False,
    ) -> tuple[PromptTier, TaskCategory]:
        """
        Classify a request and return (prompt_tier, task_category).

        Args:
            messages: Conversation messages
            tools_count: Number of tools available
            has_context: Whether there's existing conversation context

        Returns:
            Tuple of (PromptTier, TaskCategory)
        """
        # Extract last user message for analysis
        last_user_msg = self._get_last_user_message(messages)
        if not last_user_msg:
            return PromptTier.STANDARD, TaskCategory.CHAT

        # Check cache (simple hash of message start)
        cache_key = last_user_msg[:100].lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Classify
        tier, category = self._do_classify(last_user_msg, tools_count, has_context)

        # Cache result
        if len(self._cache) > 500:
            self._cache.clear()  # Simple eviction
        self._cache[cache_key] = (tier, category)

        logger.debug(
            "Classified request",
            tier=tier.value,
            category=category.value,
            msg_preview=last_user_msg[:50],
        )

        return tier, category

    def _do_classify(
        self,
        message: str,
        tools_count: int,
        has_context: bool,
    ) -> tuple[PromptTier, TaskCategory]:
        """Perform the actual classification."""
        msg_lower = message.lower()
        msg_len = len(message)

        # Very short messages are likely simple
        if msg_len < 50 and tools_count == 0:
            return PromptTier.MINIMAL, TaskCategory.CHAT

        # Check for complex task indicators
        if any(kw in msg_lower for kw in self.COMPLEX_KEYWORDS):
            return PromptTier.FULL, TaskCategory.COMPLEX

        # Check for code writing tasks
        if any(kw in msg_lower for kw in self.CODE_KEYWORDS):
            # Long code requests need more context
            if msg_len > 500 or tools_count > 5:
                return PromptTier.FULL, TaskCategory.WRITE
            return PromptTier.STANDARD, TaskCategory.WRITE

        # Check for simple queries
        if any(kw in msg_lower for kw in self.SIMPLE_KEYWORDS):
            if tools_count == 0:
                return PromptTier.MINIMAL, TaskCategory.CHAT
            return PromptTier.MINIMAL, TaskCategory.SEARCH

        # Many tools suggest complex task
        if tools_count > 10:
            return PromptTier.FULL, TaskCategory.EXECUTE

        # Medium tools count
        if tools_count > 3:
            return PromptTier.STANDARD, TaskCategory.EXECUTE

        # Long messages with context likely need more
        if msg_len > 1000 and has_context:
            return PromptTier.STANDARD, TaskCategory.COMPLEX

        # Default to standard
        return PromptTier.STANDARD, TaskCategory.READ

    def _get_last_user_message(self, messages: list[dict[str, Any]]) -> str:
        """Extract the last user message text."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            return block.get("text", "")
        return ""


# Token savings estimates per tier transition
TIER_TOKEN_ESTIMATES = {
    PromptTier.MINIMAL: 500,
    PromptTier.STANDARD: 2000,
    PromptTier.FULL: 5000,
}


def estimate_savings(from_tier: PromptTier, to_tier: PromptTier) -> int:
    """Estimate token savings from tier transition."""
    from_tokens = TIER_TOKEN_ESTIMATES[from_tier]
    to_tokens = TIER_TOKEN_ESTIMATES[to_tier]
    return from_tokens - to_tokens


# Global classifier instance
_classifier: PromptTierClassifier | None = None


def get_prompt_tier_classifier() -> PromptTierClassifier:
    """Get the global prompt tier classifier."""
    global _classifier
    if _classifier is None:
        _classifier = PromptTierClassifier()
    return _classifier


def classify_prompt_tier(
    messages: list[dict[str, Any]],
    tools_count: int = 0,
    has_context: bool = False,
) -> tuple[PromptTier, TaskCategory]:
    """
    Convenience function to classify a request.

    Args:
        messages: Conversation messages
        tools_count: Number of tools available
        has_context: Whether there's existing conversation context

    Returns:
        Tuple of (PromptTier, TaskCategory)
    """
    classifier = get_prompt_tier_classifier()
    return classifier.classify(messages, tools_count, has_context)
