"""
Context summarization for long conversations.

When conversation history exceeds a threshold, compresses older messages
into a summary while keeping recent messages verbatim. This prevents
context overflow while retaining essential information.
"""

from typing import Any

from ai_core import LLMClient, get_logger

logger = get_logger(__name__)

# Thresholds
SUMMARIZE_THRESHOLD = 24  # Trigger summarization when history exceeds this
KEEP_RECENT = 12  # Number of recent messages to keep verbatim

SUMMARIZATION_PROMPT = """Summarize the following conversation history between a user and an AI assistant.
Focus on:
1. Key decisions made
2. Important context and requirements established
3. Files read/modified and their purposes
4. Tool results that informed later decisions
5. Any errors encountered and how they were resolved

Be concise but preserve essential context that would be needed to continue the conversation.
Output a structured summary in 200-400 words.

Conversation to summarize:
{conversation}"""


class ContextSummarizer:
    """
    Manages context summarization for long conversations.

    When history exceeds SUMMARIZE_THRESHOLD messages, older messages
    are compressed into a summary. The summary is cached until new
    messages push past the threshold again.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self._cached_summary: str | None = None
        self._cached_at_length: int = 0

    def should_summarize(self, history_length: int) -> bool:
        """Check if summarization should be triggered."""
        return history_length > SUMMARIZE_THRESHOLD

    async def summarize_history(
        self,
        history: list[Any],
    ) -> tuple[str, list[Any]]:
        """
        Summarize older messages, keeping recent ones verbatim.

        Args:
            history: Full conversation history (list of ConversationMessage)

        Returns:
            (summary_text, recent_messages) where recent_messages are the
            last KEEP_RECENT messages to include verbatim.
        """
        if len(history) <= SUMMARIZE_THRESHOLD:
            return "", history

        # Split into older (to summarize) and recent (to keep)
        split_point = len(history) - KEEP_RECENT
        older_messages = history[:split_point]
        recent_messages = history[split_point:]

        # Check if we can use cached summary
        if self._cached_summary and self._cached_at_length == split_point:
            return self._cached_summary, recent_messages

        # Build conversation text from older messages
        summary = await self._generate_summary(older_messages)

        # Cache the summary
        self._cached_summary = summary
        self._cached_at_length = split_point

        return summary, recent_messages

    async def _generate_summary(self, messages: list[Any]) -> str:
        """Generate a summary of the given messages using a fast LLM call."""
        # Build conversation text for summarization
        conversation_text = self._format_messages_for_summary(messages)

        try:
            response = await self._llm.create_message(
                model="fast",  # Use FAST tier for cheap summarization
                max_tokens=800,
                system="You are a conversation summarizer. Output only the summary, no preamble.",
                messages=[{
                    "role": "user",
                    "content": SUMMARIZATION_PROMPT.format(conversation=conversation_text),
                }],
            )
            return response.text_content or self._extractive_fallback(messages)

        except Exception as e:
            logger.warning("LLM summarization failed, using extractive fallback", error=str(e))
            return self._extractive_fallback(messages)

    def _format_messages_for_summary(self, messages: list[Any]) -> str:
        """Format messages into readable text for the summarizer."""
        lines = []
        for msg in messages:
            role = msg.role.upper()
            if isinstance(msg.content, str):
                # Truncate very long messages
                content = msg.content[:500]
                lines.append(f"{role}: {content}")
            elif isinstance(msg.content, list):
                # Content blocks (tool use/results)
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            lines.append(f"{role}: {block['text'][:300]}")
                        elif block.get("type") == "tool_use":
                            lines.append(f"{role} [tool_use: {block.get('name', '?')}]")
                        elif block.get("type") == "tool_result":
                            content = str(block.get("content", ""))[:200]
                            is_error = block.get("is_error", False)
                            status = "ERROR" if is_error else "OK"
                            lines.append(f"{role} [tool_result: {status}] {content}")

            # Limit total text to prevent huge summarization prompts
            if len("\n".join(lines)) > 8000:
                lines.append("... (earlier messages truncated)")
                break

        return "\n".join(lines)

    def _extractive_fallback(self, messages: list[Any]) -> str:
        """Fallback: extract key info without LLM call."""
        user_messages = []
        tool_names = set()

        for msg in messages:
            if msg.role == "user" and isinstance(msg.content, str):
                user_messages.append(msg.content[:100])
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_names.add(block.get("name", "unknown"))

        summary_parts = ["[Conversation Summary - Extractive Fallback]"]

        if user_messages:
            summary_parts.append("User requests:")
            for um in user_messages[:10]:
                summary_parts.append(f"  - {um}")

        if tool_names:
            summary_parts.append(f"Tools used: {', '.join(sorted(tool_names))}")

        summary_parts.append(f"Total messages summarized: {len(messages)}")

        return "\n".join(summary_parts)

    def invalidate_cache(self) -> None:
        """Invalidate the cached summary (e.g., when conversation is reset)."""
        self._cached_summary = None
        self._cached_at_length = 0
