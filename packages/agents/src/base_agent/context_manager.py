"""
Context Manager - Token-aware context management for agents.

Handles:
- Token counting for messages
- Automatic truncation of large tool results
- Context summarization when approaching limits
- Hard limits to prevent API errors

Token limits (Claude):
- Max context: 200K tokens
- Safe operating limit: 150K tokens (leave room for response)
- Summarization trigger: 100K tokens
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from ai_core import get_logger

logger = get_logger(__name__)

# Token limits (Claude has 200K context window)
MAX_CONTEXT_TOKENS = 200_000  # Claude's max
SAFE_CONTEXT_TOKENS = 180_000  # Leave ~20K for response + system prompt
SUMMARIZE_TRIGGER_TOKENS = 100_000  # When to start summarizing (earlier = lower costs)
MIN_TOKENS_AFTER_TRUNCATION = 120_000  # Target after aggressive truncation

# Individual message limits
MAX_TOOL_RESULT_TOKENS = 10_000  # ~40K chars - truncate larger results
MAX_TOOL_RESULT_CHARS = 40_000  # Hard char limit for tool results
MAX_USER_MESSAGE_TOKENS = 20_000  # User messages can be longer

# Screenshot/image limits
MAX_IMAGE_DATA_CHARS = 100_000  # Base64 images get very large
IMAGE_TRUNCATION_MESSAGE = "[Image data truncated - too large to include in context]"


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Uses a simple heuristic: ~4 characters per token for English.
    This is conservative (actual is often ~3.5-4.5).
    """
    if not text:
        return 0
    return len(text) // 4 + 1


def estimate_message_tokens(message: dict[str, Any]) -> int:
    """Estimate tokens for a full message including metadata."""
    tokens = 10  # Base overhead for message structure

    content = message.get("content")
    if isinstance(content, str):
        tokens += estimate_tokens(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    tokens += estimate_tokens(block.get("text", ""))
                elif block_type == "tool_use":
                    tokens += 50  # Tool use overhead
                    tokens += estimate_tokens(json.dumps(block.get("input", {})))
                elif block_type == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, str):
                        tokens += estimate_tokens(result_content)
                    elif isinstance(result_content, list):
                        for item in result_content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                tokens += estimate_tokens(item.get("text", ""))
                elif block_type == "image":
                    # Images are expensive
                    tokens += 1000  # Rough estimate for image processing
            elif isinstance(block, str):
                tokens += estimate_tokens(block)

    return tokens


def truncate_text(text: str, max_chars: int, suffix: str = "\n\n[...truncated...]") -> str:
    """Truncate text to max_chars, adding suffix if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix


def truncate_tool_result(result: Any, max_chars: int = MAX_TOOL_RESULT_CHARS) -> Any:
    """
    Truncate a tool result to fit within limits.

    Handles:
    - String results
    - Dict results (truncates large string values)
    - List results (truncates items)
    - Base64 image data
    """
    if result is None:
        return result

    if isinstance(result, str):
        # Check for base64 image data
        if "base64," in result and len(result) > MAX_IMAGE_DATA_CHARS:
            return IMAGE_TRUNCATION_MESSAGE
        return truncate_text(result, max_chars)

    if isinstance(result, dict):
        truncated = {}
        total_chars = 0
        for key, value in result.items():
            if isinstance(value, str):
                # Special handling for known large fields
                if key in ("data", "data_url", "markdown", "content", "base64"):
                    if len(value) > MAX_IMAGE_DATA_CHARS:
                        if "base64" in value or "data:image" in value:
                            truncated[key] = IMAGE_TRUNCATION_MESSAGE
                        else:
                            truncated[key] = truncate_text(value, max_chars // 4)
                    else:
                        truncated[key] = value
                else:
                    truncated[key] = truncate_text(value, max_chars // 2)
                total_chars += len(truncated[key])
            elif isinstance(value, (dict, list)):
                # Recursively truncate
                truncated[key] = truncate_tool_result(value, max_chars // 2)
            else:
                truncated[key] = value

            # Stop if we've accumulated too much
            if total_chars > max_chars:
                truncated["_truncated"] = True
                break

        return truncated

    if isinstance(result, list):
        if not result:
            return result

        # For lists, truncate each item and limit count
        max_items = min(len(result), 50)  # Max 50 items
        per_item_limit = max_chars // max_items if max_items > 0 else max_chars

        truncated = []
        for item in result[:max_items]:
            truncated.append(truncate_tool_result(item, per_item_limit))

        if len(result) > max_items:
            truncated.append(f"[...{len(result) - max_items} more items truncated...]")

        return truncated

    return result


@dataclass
class ContextStats:
    """Statistics about current context."""
    total_tokens: int
    message_count: int
    user_tokens: int
    assistant_tokens: int
    tool_result_tokens: int
    needs_summarization: bool
    needs_truncation: bool


class ContextManager:
    """
    Manages conversation context to stay within token limits.

    Features:
    - Token counting for all messages
    - Automatic truncation of large tool results
    - Context summarization for long conversations
    - Hard limits to prevent API errors
    """

    def __init__(
        self,
        max_tokens: int = SAFE_CONTEXT_TOKENS,
        summarize_at: int = SUMMARIZE_TRIGGER_TOKENS,
    ):
        self._max_tokens = max_tokens
        self._summarize_at = summarize_at
        self._current_tokens = 0

    def analyze_context(self, messages: list[dict[str, Any]]) -> ContextStats:
        """Analyze the current context and return statistics."""
        total = 0
        user_tokens = 0
        assistant_tokens = 0
        tool_tokens = 0

        for msg in messages:
            msg_tokens = estimate_message_tokens(msg)
            total += msg_tokens

            role = msg.get("role")
            if role == "user":
                user_tokens += msg_tokens
                # Check for tool results in user messages
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_tokens += estimate_tokens(str(block.get("content", "")))
            elif role == "assistant":
                assistant_tokens += msg_tokens

        return ContextStats(
            total_tokens=total,
            message_count=len(messages),
            user_tokens=user_tokens,
            assistant_tokens=assistant_tokens,
            tool_result_tokens=tool_tokens,
            needs_summarization=total > self._summarize_at,
            needs_truncation=total > self._max_tokens,
        )

    def truncate_messages_to_fit(
        self,
        messages: list[dict[str, Any]],
        target_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Truncate messages to fit within token limit.

        Strategy:
        1. Keep system message and most recent messages
        2. Remove older messages from the middle
        3. Ensure tool_use/tool_result pairs stay together
        """
        if target_tokens is None:
            target_tokens = self._max_tokens

        current_tokens = sum(estimate_message_tokens(m) for m in messages)

        if current_tokens <= target_tokens:
            return messages

        # Keep first 2 and last N messages, remove from middle
        if len(messages) <= 4:
            return messages

        # Find how many messages to keep from the end
        keep_recent = 4  # Start with last 4
        recent_tokens = sum(estimate_message_tokens(m) for m in messages[-keep_recent:])

        # Binary search for how many recent messages we can keep
        while keep_recent < len(messages) - 2 and recent_tokens < target_tokens * 0.8:
            keep_recent += 2  # Add 2 at a time to keep pairs together
            recent_tokens = sum(estimate_message_tokens(m) for m in messages[-keep_recent:])

        # Build truncated list
        result = []

        # Add first 2 messages (usually user request + initial response)
        if len(messages) >= 2:
            result.extend(messages[:2])

        # Add truncation notice
        removed_count = len(messages) - 2 - keep_recent
        if removed_count > 0:
            result.append({
                "role": "user",
                "content": f"[Context note: {removed_count} earlier messages removed to fit context limit]"
            })
            result.append({
                "role": "assistant",
                "content": "[Acknowledged - continuing with available context]"
            })

        # Add recent messages
        result.extend(messages[-keep_recent:])

        new_tokens = sum(estimate_message_tokens(m) for m in result)
        logger.info(
            "Truncated context to fit",
            original_messages=len(messages),
            original_tokens=current_tokens,
            new_messages=len(result),
            new_tokens=new_tokens,
            target_tokens=target_tokens,
        )

        return result

    def prepare_tool_result_for_history(
        self,
        tool_name: str,
        result: Any,
        is_error: bool = False,
    ) -> dict[str, Any]:
        """
        Prepare a tool result for storage in conversation history.

        Truncates large results to prevent context overflow.
        """
        # Convert result to string if needed
        if isinstance(result, str):
            result_str = result
        else:
            try:
                result_str = json.dumps(result, indent=2, default=str)
            except Exception:
                result_str = str(result)

        # Check if truncation needed
        original_len = len(result_str)
        if original_len > MAX_TOOL_RESULT_CHARS:
            result_str = truncate_text(result_str, MAX_TOOL_RESULT_CHARS)
            logger.debug(
                "Truncated tool result for history",
                tool=tool_name,
                original_chars=original_len,
                truncated_chars=len(result_str),
            )

        return {
            "type": "tool_result",
            "tool_use_id": "",  # Will be set by caller
            "content": result_str,
            "is_error": is_error,
        }


# Global instance for convenience
_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """Get the global context manager."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


# Utility functions for direct use

def truncate_for_context(text: str, max_chars: int = MAX_TOOL_RESULT_CHARS) -> str:
    """Truncate text to fit in context."""
    return truncate_text(text, max_chars)


def prepare_result_for_context(result: Any) -> Any:
    """Prepare any result for inclusion in context."""
    return truncate_tool_result(result)
