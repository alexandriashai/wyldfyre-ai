"""
LLM Provider abstraction - Normalized types for multi-provider support.

Provides a common interface for different LLM providers (Anthropic, OpenAI)
with unified response types and tool call handling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LLMProviderType(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class LLMToolCall:
    """Normalized tool call from any provider."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMToolResult:
    """Normalized tool result to send back to provider."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""

    stop_reason: str  # "end_turn" | "tool_use"
    text_content: str
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    raw_content: Any = None  # Provider-specific content blocks
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    provider: LLMProviderType = LLMProviderType.ANTHROPIC
    model: str = ""


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    provider_type: LLMProviderType

    @abstractmethod
    async def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Create a message/completion.

        Args:
            model: Model identifier
            max_tokens: Maximum tokens in response
            system: System prompt
            messages: Conversation messages
            tools: Tool definitions (in Anthropic schema format)
            **kwargs: Provider-specific parameters (e.g., reasoning_effort)

        Returns:
            Normalized LLMResponse
        """
        ...

    @abstractmethod
    def convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools from Anthropic schema to provider format."""
        ...

    @abstractmethod
    def build_tool_result_message(self, tool_results: list[LLMToolResult]) -> dict[str, Any]:
        """Build a message containing tool results in provider format."""
        ...

    @abstractmethod
    def build_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """Build an assistant message from a response for conversation history."""
        ...
