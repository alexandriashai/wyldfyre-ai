"""Tests for Template Agent."""

import pytest
from template_agent import TemplateAgent


@pytest.fixture
def agent():
    """Create a template agent for testing."""
    return TemplateAgent()


class TestTemplateAgent:
    """Tests for the TemplateAgent class."""

    def test_get_system_prompt(self, agent):
        """Test that system prompt is defined."""
        prompt = agent.get_system_prompt()
        assert prompt
        assert isinstance(prompt, str)

    def test_get_tools(self, agent):
        """Test that tools are defined."""
        tools = agent.get_tools()
        assert tools
        assert len(tools) > 0

    def test_example_tool_exists(self, agent):
        """Test that example_tool is available."""
        tools = agent.get_tools()
        tool_names = [t.name for t in tools]
        assert "example_tool" in tool_names


@pytest.mark.asyncio
class TestTemplateAgentTools:
    """Tests for template agent tools."""

    async def test_example_tool_success(self, agent):
        """Test example_tool with valid input."""
        result = await agent._example_tool_handler(
            input="test input"
        )
        assert result.success
        assert "result" in result.data
        assert "Processed: test input" in result.data["result"]

    async def test_example_tool_with_options(self, agent):
        """Test example_tool with verbose option."""
        result = await agent._example_tool_handler(
            input="test",
            options={"verbose": True}
        )
        assert result.success
        assert "verbose" in result.data["result"]
