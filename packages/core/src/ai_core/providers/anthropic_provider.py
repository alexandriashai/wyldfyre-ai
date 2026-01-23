"""
Anthropic Provider - Wraps AsyncAnthropic with normalized response types.
"""

from typing import Any

from anthropic import AsyncAnthropic

from ..llm_provider import (
    BaseLLMProvider,
    LLMProviderType,
    LLMResponse,
    LLMToolCall,
    LLMToolResult,
)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    provider_type = LLMProviderType.ANTHROPIC

    def __init__(self, api_key: str):
        self._client = AsyncAnthropic(api_key=api_key)

    async def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Create a message using Claude API."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)

        # Normalize response
        text_content = ""
        tool_calls: list[LLMToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    LLMToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        # Map stop reasons
        stop_reason = "end_turn"
        if response.stop_reason == "tool_use":
            stop_reason = "tool_use"

        cached_tokens = getattr(response.usage, "cache_read_input_tokens", 0) or 0

        return LLMResponse(
            stop_reason=stop_reason,
            text_content=text_content,
            tool_calls=tool_calls,
            raw_content=response.content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cached_tokens=cached_tokens,
            provider=LLMProviderType.ANTHROPIC,
            model=model,
        )

    def convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Anthropic tools are already in the correct format."""
        return tools

    def build_tool_result_message(self, tool_results: list[LLMToolResult]) -> dict[str, Any]:
        """Build tool result message in Claude format."""
        content = []
        for result in tool_results:
            content.append({
                "type": "tool_result",
                "tool_use_id": result.tool_call_id,
                "content": result.content,
                "is_error": result.is_error,
            })
        return {"role": "user", "content": content}

    def build_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """Build assistant message from response for history."""
        content = []
        for block in response.raw_content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return {"role": "assistant", "content": content}
