"""
Agent SDK Development Toolkit Tools.

Tools for building and configuring custom agents.
"""

import re
from typing import Any


AGENT_CONFIG_TEMPLATE = '''name: {name}
description: {description}
version: 1.0.0

model:
  name: {model}
  temperature: 0.7
  max_tokens: 4096

capabilities:
{capabilities}

system_prompt: |
{system_prompt}

tools:
{tools}

settings:
  max_turns: 50
  timeout: 300
  retry_on_error: true
'''

AGENT_PY_TEMPLATE = '''"""
{name} Agent.

{description}
"""

import asyncio
from typing import Any
from ai_core import BaseAgent, AgentConfig


class {class_name}(BaseAgent):
    """
    {description}
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.name = "{name}"

    async def process(self, message: str, context: dict[str, Any] | None = None) -> str:
        """
        Process a message and generate a response.

        Args:
            message: User message
            context: Additional context

        Returns:
            Agent response
        """
        context = context or {{}}

        # Add any preprocessing here
        processed_message = self._preprocess(message)

        # Generate response using the model
        response = await self._generate_response(processed_message, context)

        # Add any postprocessing here
        return self._postprocess(response)

    def _preprocess(self, message: str) -> str:
        """Preprocess the input message."""
        return message.strip()

    def _postprocess(self, response: str) -> str:
        """Postprocess the response."""
        return response

    async def _generate_response(
        self,
        message: str,
        context: dict[str, Any],
    ) -> str:
        """Generate response using the model."""
        messages = [
            {{"role": "user", "content": message}}
        ]

        result = await self.client.messages.create(
            model=self.config.model.name,
            max_tokens=self.config.model.max_tokens,
            system=self.config.system_prompt,
            messages=messages,
        )

        return result.content[0].text


async def main():
    """Run the agent."""
    config = AgentConfig.from_yaml("config.yaml")
    agent = {class_name}(config)

    print(f"{{agent.name}} ready.")

    # Example interaction
    response = await agent.process("Hello!")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
'''


def create_agent_scaffold(
    name: str,
    description: str | None = None,
    capabilities: list[str] | None = None,
    model: str = "claude-sonnet",
) -> dict[str, Any]:
    """
    Create a new agent with standard structure.

    Args:
        name: Agent name (kebab-case)
        description: Agent description
        capabilities: Agent capabilities/tools
        model: Model to use

    Returns:
        Scaffold creation result
    """
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        return {
            "success": False,
            "error": "Agent name must be kebab-case",
        }

    description = description or f"Agent for {name.replace('-', ' ')}"
    capabilities = capabilities or ["file_read", "file_write", "bash"]

    # Generate class name
    class_name = "".join(word.title() for word in name.split("-")) + "Agent"

    # Format capabilities
    caps_yaml = "\n".join(f"  - {cap}" for cap in capabilities)

    # Generate system prompt
    system_prompt = f"""  You are {name.replace('-', ' ')}, an AI assistant.

  Your capabilities include:
{chr(10).join(f'  - {cap}' for cap in capabilities)}

  Guidelines:
  - Be helpful and accurate
  - Ask for clarification when needed
  - Explain your reasoning"""

    # Generate tools section
    tools_yaml = "\n".join(f"  - {cap}" for cap in capabilities)

    files = {
        "config.yaml": AGENT_CONFIG_TEMPLATE.format(
            name=name,
            description=description,
            model=model,
            capabilities=caps_yaml,
            system_prompt=system_prompt,
            tools=tools_yaml,
        ),
        "agent.py": AGENT_PY_TEMPLATE.format(
            name=name,
            description=description,
            class_name=class_name,
        ),
        "__init__.py": f'"""{name} agent."""\nfrom .agent import {class_name}\n',
        "requirements.txt": "anthropic>=0.18.0\nai-core>=0.1.0\npyyaml>=6.0\n",
    }

    return {
        "success": True,
        "agent_name": name,
        "class_name": class_name,
        "directory": f"agents/{name}",
        "files": files,
        "instructions": [
            f"Create directory: mkdir -p agents/{name}",
            f"Create files in agents/{name}/",
            "Install dependencies: pip install -r requirements.txt",
            "Configure agent in config.yaml",
            "Run: python -m agents.{name.replace('-', '_')}.agent",
        ],
    }


def define_agent_tools(
    agent_name: str,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Define tools available to an agent.

    Args:
        agent_name: Agent name
        tools: Tool definitions

    Returns:
        Tool definitions result
    """
    formatted_tools = []

    for tool in tools:
        formatted = {
            "name": tool.get("name", "unnamed_tool"),
            "description": tool.get("description", "No description"),
            "input_schema": {
                "type": "object",
                "properties": tool.get("parameters", {}),
                "required": tool.get("required", []),
            },
        }
        formatted_tools.append(formatted)

    # Generate YAML
    tools_yaml = []
    for tool in formatted_tools:
        tool_yaml = f"""  - name: {tool['name']}
    description: {tool['description']}
    parameters:
      type: object
      properties:"""
        for prop, spec in tool["input_schema"]["properties"].items():
            tool_yaml += f"""
        {prop}:
          type: {spec.get('type', 'string')}
          description: {spec.get('description', '')}"""
        if tool["input_schema"]["required"]:
            tool_yaml += f"""
      required:
        - {chr(10) + '        - '.join(tool['input_schema']['required'])}"""
        tools_yaml.append(tool_yaml)

    return {
        "success": True,
        "agent": agent_name,
        "tools": formatted_tools,
        "yaml": "\n".join(tools_yaml),
        "claude_format": formatted_tools,  # Ready for Anthropic API
    }


def generate_system_prompt(
    agent_name: str,
    role: str,
    capabilities: list[str] | None = None,
    guidelines: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate a system prompt for an agent.

    Args:
        agent_name: Agent name
        role: Agent role description
        capabilities: List of capabilities
        guidelines: Behavior guidelines

    Returns:
        Generated system prompt
    """
    capabilities = capabilities or []
    guidelines = guidelines or [
        "Be helpful and accurate",
        "Ask for clarification when needed",
        "Explain your reasoning",
    ]

    prompt_parts = [
        f"You are {agent_name}, {role}.",
        "",
    ]

    if capabilities:
        prompt_parts.append("## Capabilities")
        prompt_parts.append("")
        for cap in capabilities:
            prompt_parts.append(f"- {cap}")
        prompt_parts.append("")

    prompt_parts.append("## Guidelines")
    prompt_parts.append("")
    for guideline in guidelines:
        prompt_parts.append(f"- {guideline}")

    prompt = "\n".join(prompt_parts)

    return {
        "success": True,
        "agent": agent_name,
        "role": role,
        "system_prompt": prompt,
        "token_estimate": len(prompt.split()) * 1.3,  # Rough estimate
    }


def test_agent_response(
    agent_name: str,
    test_input: str,
    expected_behavior: str | None = None,
) -> dict[str, Any]:
    """
    Test agent response to a sample input.

    Args:
        agent_name: Agent name
        test_input: Test message to send
        expected_behavior: Expected behavior description

    Returns:
        Test configuration
    """
    return {
        "success": True,
        "agent": agent_name,
        "test_input": test_input,
        "expected_behavior": expected_behavior,
        "instruction": (
            f"To test {agent_name}:\n"
            f"1. Load agent config from agents/{agent_name}/config.yaml\n"
            f"2. Initialize agent with config\n"
            f"3. Send test message: {test_input[:100]}...\n"
            f"4. Verify response matches expected behavior"
        ),
        "test_template": {
            "message": test_input,
            "expected": expected_behavior,
            "validate": [
                "Response is not empty",
                "Response is relevant to input",
                "No error messages in response",
            ],
        },
    }


def analyze_agent_config(
    config_path: str,
) -> dict[str, Any]:
    """
    Analyze agent configuration for issues.

    Args:
        config_path: Path to agent config

    Returns:
        Analysis result
    """
    import yaml

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Config not found: {config_path}",
        }
    except yaml.YAMLError as e:
        return {
            "success": False,
            "error": f"Invalid YAML: {str(e)}",
        }

    issues = []
    warnings = []
    suggestions = []

    # Check required fields
    required = ["name", "model", "system_prompt"]
    for field in required:
        if field not in config:
            issues.append(f"Missing required field: {field}")

    # Check model configuration
    if "model" in config:
        model = config["model"]
        if isinstance(model, dict):
            if model.get("temperature", 0) > 1.0:
                warnings.append("Temperature > 1.0 may produce inconsistent results")
            if model.get("max_tokens", 0) < 1000:
                warnings.append("max_tokens < 1000 may truncate responses")
        else:
            suggestions.append("Consider using detailed model config with temperature and max_tokens")

    # Check system prompt
    if "system_prompt" in config:
        prompt = config["system_prompt"]
        if len(prompt) < 50:
            warnings.append("System prompt is very short - consider adding more context")
        if len(prompt) > 10000:
            warnings.append("System prompt is very long - may impact performance")

    # Check tools
    if "tools" in config:
        tools = config["tools"]
        if len(tools) > 20:
            warnings.append("Many tools defined - may impact model selection accuracy")

    return {
        "success": len(issues) == 0,
        "config_path": config_path,
        "agent_name": config.get("name"),
        "issues": issues,
        "warnings": warnings,
        "suggestions": suggestions,
        "stats": {
            "tools_count": len(config.get("tools", [])),
            "capabilities_count": len(config.get("capabilities", [])),
            "prompt_length": len(config.get("system_prompt", "")),
        },
    }
