"""
Context summarization for long conversations.

Uses a multi-pass approach similar to Claude Code:
1. Extract structured facts (files, tools, decisions)
2. Identify current working state and pending tasks
3. Generate a comprehensive summary that preserves continuity

When conversation history exceeds a threshold, compresses older messages
into a summary while keeping recent messages verbatim.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from ai_core import LLMClient, get_logger

logger = get_logger(__name__)

# Thresholds (message count based - token checks happen separately)
SUMMARIZE_THRESHOLD = 30  # Trigger summarization when history exceeds this
KEEP_RECENT = 15  # Number of recent messages to keep verbatim


@dataclass
class ExtractedContext:
    """Structured information extracted from conversation."""
    primary_objective: str = ""
    current_task: str = ""
    files_read: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    tools_used: set[str] = field(default_factory=set)
    key_decisions: list[str] = field(default_factory=list)
    errors_encountered: list[str] = field(default_factory=list)
    errors_resolved: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    important_values: dict[str, str] = field(default_factory=dict)
    user_preferences: list[str] = field(default_factory=list)


# Patterns for extracting structured information
FILE_PATTERNS = [
    r'(?:read|reading|opened|viewing)\s+[`"]?(/[^\s`"]+)[`"]?',
    r'(?:edit|editing|modified|updated|changed)\s+[`"]?(/[^\s`"]+)[`"]?',
    r'(?:created|wrote|writing)\s+[`"]?(/[^\s`"]+)[`"]?',
    r'file[:\s]+[`"]?(/[^\s`"]+)[`"]?',
]

TASK_PATTERNS = [
    r'(?:working on|implementing|fixing|adding|creating)\s+(.+?)(?:\.|$)',
    r'(?:task|goal|objective)[:\s]+(.+?)(?:\.|$)',
    r'(?:need to|should|will)\s+(.+?)(?:\.|$)',
]


STRUCTURED_SUMMARY_PROMPT = """Analyze this conversation and extract a structured summary.

Output format (use exactly this structure):

## Analysis

### Primary Request
[What the user originally asked for - the main goal]

### Current State
[What task is actively being worked on right now]

### Key Technical Concepts
[Important technical details, APIs, patterns being used]

### Files and Code
| Action | File | Purpose |
|--------|------|---------|
[List files read/modified/created with their purpose]

### Key Decisions Made
- [Decision 1]
- [Decision 2]

### Errors and Resolutions
| Error | Resolution |
|-------|------------|
[List errors and how they were fixed]

### Pending Work
- [Task not yet completed]

### Important Context
[Any values, paths, configurations that need to be remembered]

### Suggested Next Step
[What should happen next to continue the work]

---

Conversation to analyze:
{conversation}"""


class ContextSummarizer:
    """
    Manages context summarization for long conversations.

    Uses a multi-pass approach:
    1. Extract structured facts from messages
    2. Use LLM to generate comprehensive summary
    3. Format for continuity preservation
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self._cached_summary: str | None = None
        self._cached_at_length: int = 0
        self._extracted_context: ExtractedContext | None = None

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

        # Find safe split point that doesn't break tool_use/tool_result pairs
        split_point = self._find_safe_split_point(history, KEEP_RECENT)
        older_messages = history[:split_point]
        recent_messages = history[split_point:]

        # Check if we can use cached summary
        if self._cached_summary and self._cached_at_length == split_point:
            return self._cached_summary, recent_messages

        # Multi-pass summarization
        # Pass 1: Extract structured facts
        extracted = self._extract_structured_facts(older_messages)
        self._extracted_context = extracted

        # Pass 2: Generate LLM summary with structure
        summary = await self._generate_structured_summary(older_messages, extracted)

        # Cache the summary
        self._cached_summary = summary
        self._cached_at_length = split_point

        return summary, recent_messages

    def _extract_structured_facts(self, messages: list[Any]) -> ExtractedContext:
        """
        Pass 1: Extract structured facts from messages without LLM.

        Scans for:
        - File paths (read, modified, created)
        - Tool usage
        - Error patterns
        - Task descriptions
        """
        ctx = ExtractedContext()

        for msg in messages:
            content_text = self._get_message_text(msg)
            role = getattr(msg, 'role', 'unknown')

            # Extract file paths
            for pattern in FILE_PATTERNS:
                matches = re.findall(pattern, content_text, re.IGNORECASE)
                for match in matches:
                    if '/home/' in match or match.startswith('/'):
                        if 'read' in pattern or 'view' in pattern or 'open' in pattern:
                            if match not in ctx.files_read:
                                ctx.files_read.append(match)
                        elif 'edit' in pattern or 'modif' in pattern or 'updat' in pattern:
                            if match not in ctx.files_modified:
                                ctx.files_modified.append(match)
                        elif 'creat' in pattern or 'wro' in pattern:
                            if match not in ctx.files_created:
                                ctx.files_created.append(match)

            # Extract tools used from content blocks
            if hasattr(msg, 'content') and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            tool_name = block.get("name", "unknown")
                            ctx.tools_used.add(tool_name)

                            # Extract file paths from tool inputs
                            tool_input = block.get("input", {})
                            if isinstance(tool_input, dict):
                                for key in ["file_path", "path", "file", "filename"]:
                                    if key in tool_input:
                                        path = tool_input[key]
                                        if path and isinstance(path, str):
                                            if tool_name in ["read_file", "Read"]:
                                                if path not in ctx.files_read:
                                                    ctx.files_read.append(path)
                                            elif tool_name in ["write_file", "Write", "edit_file", "Edit"]:
                                                if path not in ctx.files_modified:
                                                    ctx.files_modified.append(path)

                        elif block.get("type") == "tool_result":
                            if block.get("is_error"):
                                error_content = str(block.get("content", ""))[:200]
                                if error_content and error_content not in ctx.errors_encountered:
                                    ctx.errors_encountered.append(error_content)

            # Extract user's primary request (first user message)
            if role == "user" and isinstance(msg.content, str) and not ctx.primary_objective:
                ctx.primary_objective = msg.content[:300]

        # Limit lists to reasonable sizes
        ctx.files_read = ctx.files_read[:20]
        ctx.files_modified = ctx.files_modified[:20]
        ctx.files_created = ctx.files_created[:10]
        ctx.errors_encountered = ctx.errors_encountered[:10]

        return ctx

    def _get_message_text(self, msg: Any) -> str:
        """Extract text content from a message."""
        if isinstance(msg.content, str):
            return msg.content
        elif isinstance(msg.content, list):
            texts = []
            for block in msg.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            return " ".join(texts)
        return ""

    async def _generate_structured_summary(
        self,
        messages: list[Any],
        extracted: ExtractedContext,
    ) -> str:
        """
        Pass 2: Generate comprehensive structured summary using LLM.
        """
        # Build conversation text for summarization
        conversation_text = self._format_messages_for_summary(messages)

        # Add extracted facts as hints
        facts_hint = self._format_extracted_facts(extracted)

        prompt = STRUCTURED_SUMMARY_PROMPT.format(conversation=conversation_text)
        if facts_hint:
            prompt += f"\n\nPre-extracted facts to incorporate:\n{facts_hint}"

        try:
            response = await self._llm.create_message(
                model="fast",  # Use FAST tier for cheap summarization
                max_tokens=1500,  # Allow longer summaries for structure
                system="You are a conversation summarizer that outputs structured markdown. Preserve technical details and file paths exactly. Focus on actionable information needed to continue the work.",
                messages=[{
                    "role": "user",
                    "content": prompt,
                }],
            )
            summary = response.text_content
            if summary:
                return self._format_final_summary(summary, extracted)
            return self._extractive_fallback(messages, extracted)

        except Exception as e:
            logger.warning("LLM summarization failed, using extractive fallback", error=str(e))
            return self._extractive_fallback(messages, extracted)

    def _format_extracted_facts(self, ctx: ExtractedContext) -> str:
        """Format extracted facts as hints for the LLM."""
        parts = []

        if ctx.files_read:
            parts.append(f"Files read: {', '.join(ctx.files_read[:10])}")
        if ctx.files_modified:
            parts.append(f"Files modified: {', '.join(ctx.files_modified[:10])}")
        if ctx.files_created:
            parts.append(f"Files created: {', '.join(ctx.files_created[:5])}")
        if ctx.tools_used:
            parts.append(f"Tools used: {', '.join(sorted(ctx.tools_used))}")
        if ctx.errors_encountered:
            parts.append(f"Errors seen: {len(ctx.errors_encountered)}")

        return "\n".join(parts)

    def _format_final_summary(self, llm_summary: str, extracted: ExtractedContext) -> str:
        """Format the final summary with header and metadata."""
        header = "# Conversation Summary\n\n"
        header += f"> This summary covers {self._cached_at_length} messages.\n"
        header += f"> Files touched: {len(extracted.files_read)} read, {len(extracted.files_modified)} modified\n"
        header += f"> Tools used: {', '.join(sorted(extracted.tools_used)[:10]) or 'none'}\n\n"
        header += "---\n\n"

        return header + llm_summary

    def _find_safe_split_point(self, history: list[Any], keep_recent: int) -> int:
        """
        Find a split point that doesn't break tool_use/tool_result pairs.

        Tool results must always follow their corresponding tool_use.
        Returns the index where recent messages should start.
        """
        if len(history) <= keep_recent:
            return 0

        # Start from the target split point
        target_split = len(history) - keep_recent

        # Search backward for a safe point (not a tool_result message)
        for i in range(target_split, -1, -1):
            msg = history[i]
            # Check if this message contains tool_result blocks
            if hasattr(msg, 'content') and isinstance(msg.content, list):
                has_tool_result = any(
                    isinstance(block, dict) and block.get("type") == "tool_result"
                    for block in msg.content
                )
                if has_tool_result:
                    continue  # Can't split here, would orphan tool_result

            # Check if this is a user message (not tool_result) or assistant message
            if hasattr(msg, 'role'):
                if msg.role == "assistant":
                    # Safe to split after assistant message
                    return i + 1 if i + 1 < len(history) else i
                elif msg.role == "user":
                    # Check it's not a tool_result user message
                    if isinstance(msg.content, str):
                        return i  # Safe - regular user message

        # Fallback: return target, but ensure we don't start with tool_result
        return target_split

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
                            tool_name = block.get('name', '?')
                            tool_input = block.get('input', {})
                            # Include file path if present
                            file_hint = ""
                            if isinstance(tool_input, dict):
                                for key in ["file_path", "path", "command"]:
                                    if key in tool_input:
                                        file_hint = f" ({tool_input[key][:100]})"
                                        break
                            lines.append(f"{role} [tool: {tool_name}{file_hint}]")
                        elif block.get("type") == "tool_result":
                            content = str(block.get("content", ""))[:200]
                            is_error = block.get("is_error", False)
                            status = "ERROR" if is_error else "OK"
                            lines.append(f"{role} [result: {status}] {content}")

            # Limit total text to prevent huge summarization prompts
            if len("\n".join(lines)) > 12000:
                lines.append("... (earlier messages truncated)")
                break

        return "\n".join(lines)

    def _extractive_fallback(
        self,
        messages: list[Any],
        extracted: ExtractedContext | None = None,
    ) -> str:
        """Fallback: extract key info without LLM call."""
        if extracted is None:
            extracted = self._extract_structured_facts(messages)

        parts = ["# Conversation Summary (Extractive)\n"]

        # Primary request
        if extracted.primary_objective:
            parts.append(f"## Primary Request\n{extracted.primary_objective[:200]}\n")

        # Files
        if extracted.files_read or extracted.files_modified or extracted.files_created:
            parts.append("## Files Touched")
            if extracted.files_read:
                parts.append(f"**Read:** {', '.join(extracted.files_read[:10])}")
            if extracted.files_modified:
                parts.append(f"**Modified:** {', '.join(extracted.files_modified[:10])}")
            if extracted.files_created:
                parts.append(f"**Created:** {', '.join(extracted.files_created[:5])}")
            parts.append("")

        # Tools
        if extracted.tools_used:
            parts.append(f"## Tools Used\n{', '.join(sorted(extracted.tools_used))}\n")

        # Errors
        if extracted.errors_encountered:
            parts.append("## Errors Encountered")
            for err in extracted.errors_encountered[:5]:
                parts.append(f"- {err[:100]}")
            parts.append("")

        # User messages summary
        user_messages = []
        for msg in messages:
            if msg.role == "user" and isinstance(msg.content, str):
                user_messages.append(msg.content[:100])

        if user_messages:
            parts.append("## User Requests")
            for um in user_messages[:10]:
                parts.append(f"- {um}")
            parts.append("")

        parts.append(f"*Total messages summarized: {len(messages)}*")

        return "\n".join(parts)

    def invalidate_cache(self) -> None:
        """Invalidate the cached summary (e.g., when conversation is reset)."""
        self._cached_summary = None
        self._cached_at_length = 0
        self._extracted_context = None

    def get_extracted_context(self) -> ExtractedContext | None:
        """Get the last extracted context for inspection."""
        return self._extracted_context
