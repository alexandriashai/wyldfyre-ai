"""
OpenAI Provider - Wraps AsyncOpenAI with format conversion to/from Anthropic schema.
"""

import json
from typing import Any

from openai import AsyncOpenAI

from ..llm_provider import (
    BaseLLMProvider,
    LLMProviderType,
    LLMResponse,
    LLMToolCall,
    LLMToolResult,
)


# Model mapping from Anthropic to OpenAI equivalents
MODEL_MAP: dict[str, str] = {
    "claude-opus-4-5-20251101": "gpt-5.2",
    "claude-opus-4-5": "gpt-5.2",
    "claude-sonnet-4-20250514": "gpt-5",
    "claude-sonnet-4": "gpt-5",
    "claude-3-5-haiku-20241022": "gpt-5-mini",
    "claude-3-5-haiku": "gpt-5-mini",
    "claude-haiku-4-20250514": "gpt-5-mini",
    # Legacy
    "claude-3-opus-20240229": "gpt-5.2",
    "claude-3-5-sonnet-20241022": "gpt-5",
}


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider with Anthropic-to-OpenAI format conversion."""

    provider_type = LLMProviderType.OPENAI

    def __init__(self, api_key: str):
        self._client = AsyncOpenAI(api_key=api_key)

    # Native OpenAI models that should pass through without mapping
    _NATIVE_MODELS = {
        "gpt-5.2", "gpt-5", "gpt-5-mini", "gpt-5-nano",
        "gpt-4.1", "gpt-4.1-mini",
        "gpt-4o", "gpt-4o-mini",
        "o4-mini", "o3", "o3-mini", "o1", "o1-mini",
    }

    # Models that use max_completion_tokens instead of max_tokens
    _COMPLETION_TOKEN_MODELS = {"gpt-5.2", "gpt-5", "gpt-5-mini", "gpt-5-nano"}

    # Models that support the reasoning_effort parameter
    _REASONING_EFFORT_MODELS = {"gpt-5.2", "gpt-5"}

    def _map_model(self, model: str) -> str:
        """Map model name to OpenAI equivalent. Native OpenAI names pass through."""
        if model in self._NATIVE_MODELS:
            return model
        return MODEL_MAP.get(model, "gpt-5")

    def _uses_completion_tokens(self, model: str) -> bool:
        """Check if model uses max_completion_tokens instead of max_tokens."""
        return model.startswith("o") or model in self._COMPLETION_TOKEN_MODELS

    async def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Create a message using OpenAI API."""
        openai_model = self._map_model(model)

        # Build OpenAI messages: system prompt as first message
        openai_messages: list[dict[str, Any]] = []
        if system:
            openai_messages.append({"role": "system", "content": system})

        # Convert messages from Anthropic format to OpenAI format
        for msg in messages:
            converted = self._convert_message(msg)
            if isinstance(converted, list):
                openai_messages.extend(converted)
            else:
                openai_messages.append(converted)

        # Build API call kwargs
        # o-series and GPT-5 series use max_completion_tokens instead of max_tokens
        token_param = "max_completion_tokens" if self._uses_completion_tokens(openai_model) else "max_tokens"
        api_kwargs: dict[str, Any] = {
            "model": openai_model,
            token_param: max_tokens,
            "messages": openai_messages,
        }

        if tools:
            api_kwargs["tools"] = self.convert_tools(tools)

        # Pass reasoning_effort for supported models
        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort and openai_model in self._REASONING_EFFORT_MODELS:
            api_kwargs["reasoning_effort"] = reasoning_effort

        response = await self._client.chat.completions.create(**api_kwargs)

        # Normalize response
        choice = response.choices[0]
        message = choice.message

        text_content = message.content or ""
        tool_calls: list[LLMToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                tool_calls.append(
                    LLMToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Map finish reasons
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cached_tokens = 0
        if response.usage and hasattr(response.usage, "prompt_tokens_details"):
            details = response.usage.prompt_tokens_details
            if details and hasattr(details, "cached_tokens"):
                cached_tokens = details.cached_tokens or 0

        return LLMResponse(
            stop_reason=stop_reason,
            text_content=text_content,
            tool_calls=tool_calls,
            raw_content=message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            provider=LLMProviderType.OPENAI,
            model=openai_model,
        )

    def convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Anthropic tool schema to OpenAI function calling format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        return openai_tools

    def build_tool_result_message(self, tool_results: list[LLMToolResult]) -> dict[str, Any]:
        """
        Build tool result messages in OpenAI format.

        OpenAI expects individual tool messages, so we return a list-like structure.
        The LLMClient handles expanding this into multiple messages.
        """
        # Return as a special structure that LLMClient knows to expand
        return {
            "role": "_tool_results",
            "results": [
                {
                    "role": "tool",
                    "tool_call_id": r.tool_call_id,
                    "content": r.content,
                }
                for r in tool_results
            ],
        }

    def build_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """Build assistant message from response for history."""
        msg: dict[str, Any] = {"role": "assistant", "content": response.text_content or None}

        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ]

        return msg

    def _convert_message(self, msg: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Convert a single message from Anthropic format to OpenAI format.

        Handles:
        - Simple text messages
        - Tool use content blocks (assistant)
        - Tool result content blocks (user)
        """
        role = msg.get("role", "user")
        content = msg.get("content")

        # Simple string content
        if isinstance(content, str):
            return {"role": role, "content": content}

        # List of content blocks (Anthropic format)
        if isinstance(content, list):
            # Check if these are tool results
            if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                # Convert to OpenAI tool messages
                tool_messages = []
                for block in content:
                    tool_messages.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": str(block.get("content", "")),
                    })
                return tool_messages

            # Assistant message with tool_use blocks
            if role == "assistant":
                text_parts = []
                tool_calls = []

                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {})),
                                },
                            })
                    else:
                        # Handle Anthropic SDK objects (ContentBlock types)
                        block_type = getattr(block, "type", None)
                        if block_type == "text":
                            text_parts.append(getattr(block, "text", ""))
                        elif block_type == "tool_use":
                            tool_calls.append({
                                "id": getattr(block, "id", ""),
                                "type": "function",
                                "function": {
                                    "name": getattr(block, "name", ""),
                                    "arguments": json.dumps(getattr(block, "input", {})),
                                },
                            })

                result: dict[str, Any] = {
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                }
                if tool_calls:
                    result["tool_calls"] = tool_calls
                return result

            # User message with content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            return {"role": "user", "content": "\n".join(text_parts) if text_parts else ""}

        return {"role": role, "content": str(content) if content else ""}
