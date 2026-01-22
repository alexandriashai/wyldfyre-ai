"""
Plugin Development Toolkit Tools.

Tools for creating, validating, and testing plugins.
"""

import os
import re
from pathlib import Path
from typing import Any


MANIFEST_TEMPLATE = '''name: {name}
version: 1.0.0
description: {description}
author: Wyld Fyre AI

agents:
  - "*"

requires:
  - ai_core >= 0.1.0

permissions:
  - files:read

config:
  enabled:
    type: boolean
    default: true

tools:
{tools_section}

hooks:
{hooks_section}
'''

TOOL_TEMPLATE = '''  - name: {name}
    description: {description}
    handler: tools:{name}
    parameters:
      type: object
      properties:
        input:
          type: string
          description: Input parameter
      required:
        - input
'''

HOOK_TEMPLATE = '''  - event: {event}
    handler: hooks:{handler_name}
    priority: 50
    description: Handle {event} event
'''

TOOLS_PY_TEMPLATE = '''"""
{plugin_name} Plugin Tools.

{description}
"""

from typing import Any

{tool_functions}
'''

TOOL_FUNCTION_TEMPLATE = '''
def {name}(
    input: str,
    **kwargs,
) -> dict[str, Any]:
    """
    {description}

    Args:
        input: Input parameter

    Returns:
        Tool result
    """
    # TODO: Implement tool logic
    return {{
        "success": True,
        "result": f"Processed: {{input}}",
    }}
'''

HOOKS_PY_TEMPLATE = '''"""
{plugin_name} Plugin Hooks.

Event handlers for {plugin_name}.
"""

from typing import Any

{hook_functions}
'''

HOOK_FUNCTION_TEMPLATE = '''
def {handler_name}(context: dict[str, Any]) -> dict[str, Any]:
    """
    Handle {event} event.

    Args:
        context: Event context

    Returns:
        Modified context
    """
    # TODO: Implement hook logic
    return context
'''

VALID_EVENTS = [
    "session_start",
    "session_end",
    "task_start",
    "task_complete",
    "pre_tool_use",
    "post_tool_use",
    "message_received",
    "response_generated",
    "plugin_loaded",
    "error",
]


def create_plugin_scaffold(
    name: str,
    description: str | None = None,
    tools: list[str] | None = None,
    hooks: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a new plugin with standard structure.

    Args:
        name: Plugin name (kebab-case)
        description: Plugin description
        tools: List of tool names to include
        hooks: List of hook events to handle

    Returns:
        Scaffold creation result
    """
    # Validate name
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        return {
            "success": False,
            "error": "Plugin name must be kebab-case (lowercase letters, numbers, hyphens)",
        }

    description = description or f"Plugin for {name.replace('-', ' ')}"
    tools = tools or ["example_tool"]
    hooks = hooks or []

    # Generate tools section
    tools_section = ""
    tool_functions = ""
    for tool_name in tools:
        tools_section += TOOL_TEMPLATE.format(
            name=tool_name,
            description=f"Tool: {tool_name.replace('_', ' ')}",
        )
        tool_functions += TOOL_FUNCTION_TEMPLATE.format(
            name=tool_name,
            description=f"Tool: {tool_name.replace('_', ' ')}",
        )

    # Generate hooks section
    hooks_section = ""
    hook_functions = ""
    for event in hooks:
        if event not in VALID_EVENTS:
            continue
        handler_name = f"handle_{event}"
        hooks_section += HOOK_TEMPLATE.format(
            event=event,
            handler_name=handler_name,
        )
        hook_functions += HOOK_FUNCTION_TEMPLATE.format(
            event=event,
            handler_name=handler_name,
        )

    if not hooks_section:
        hooks_section = "  []  # No hooks defined"

    # Generate files
    files = {
        "manifest.yaml": MANIFEST_TEMPLATE.format(
            name=name,
            description=description,
            tools_section=tools_section,
            hooks_section=hooks_section,
        ),
        "tools.py": TOOLS_PY_TEMPLATE.format(
            plugin_name=name.replace("-", " ").title(),
            description=description,
            tool_functions=tool_functions,
        ),
        "hooks.py": HOOKS_PY_TEMPLATE.format(
            plugin_name=name.replace("-", " ").title(),
            hook_functions=hook_functions if hook_functions else "# No hooks defined\npass",
        ),
        "__init__.py": f'"""{name} plugin."""\n',
    }

    return {
        "success": True,
        "plugin_name": name,
        "directory": f"plugins/{name}",
        "files": files,
        "instructions": [
            f"Create directory: mkdir -p plugins/{name}",
            f"Create files in plugins/{name}/",
            "Implement tool logic in tools.py",
            "Implement hook logic in hooks.py if needed",
            "Test with: python -m ai_core.plugins validate {name}",
        ],
    }


def validate_manifest(
    manifest_path: str,
    strict: bool = True,
) -> dict[str, Any]:
    """
    Validate a plugin manifest file.

    Args:
        manifest_path: Path to manifest.yaml
        strict: Enable strict validation

    Returns:
        Validation result
    """
    import yaml

    errors = []
    warnings = []

    try:
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Manifest not found: {manifest_path}",
        }
    except yaml.YAMLError as e:
        return {
            "success": False,
            "error": f"Invalid YAML: {str(e)}",
        }

    # Required fields
    required_fields = ["name", "version", "description"]
    for field in required_fields:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")

    # Validate name format
    if "name" in manifest:
        if not re.match(r"^[a-z][a-z0-9-]*$", manifest["name"]):
            errors.append("Plugin name must be kebab-case")

    # Validate version format
    if "version" in manifest:
        if not re.match(r"^\d+\.\d+\.\d+$", manifest["version"]):
            warnings.append("Version should follow semver (x.y.z)")

    # Validate tools
    if "tools" in manifest:
        for i, tool in enumerate(manifest["tools"]):
            if "name" not in tool:
                errors.append(f"Tool {i} missing 'name'")
            if "handler" not in tool:
                errors.append(f"Tool {i} missing 'handler'")
            if "parameters" not in tool and strict:
                warnings.append(f"Tool '{tool.get('name', i)}' has no parameters schema")

    # Validate hooks
    if "hooks" in manifest and manifest["hooks"]:
        for i, hook in enumerate(manifest["hooks"]):
            if "event" not in hook:
                errors.append(f"Hook {i} missing 'event'")
            elif hook["event"] not in VALID_EVENTS:
                warnings.append(f"Hook {i} uses non-standard event: {hook['event']}")
            if "handler" not in hook:
                errors.append(f"Hook {i} missing 'handler'")

    # Check for handler files
    plugin_dir = Path(manifest_path).parent
    if "tools" in manifest and manifest["tools"]:
        tools_file = plugin_dir / "tools.py"
        if not tools_file.exists():
            errors.append("tools.py not found but tools are defined")

    if "hooks" in manifest and manifest["hooks"]:
        hooks_file = plugin_dir / "hooks.py"
        if not hooks_file.exists():
            errors.append("hooks.py not found but hooks are defined")

    is_valid = len(errors) == 0

    return {
        "success": is_valid,
        "manifest_path": manifest_path,
        "plugin_name": manifest.get("name"),
        "errors": errors,
        "warnings": warnings,
        "validation": {
            "strict": strict,
            "fields_checked": len(required_fields),
            "tools_count": len(manifest.get("tools", [])),
            "hooks_count": len(manifest.get("hooks", [])),
        },
    }


def test_plugin_tool(
    plugin_name: str,
    tool_name: str,
    test_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Test a plugin tool with sample inputs.

    Args:
        plugin_name: Plugin name
        tool_name: Tool name to test
        test_input: Test input parameters

    Returns:
        Test result
    """
    test_input = test_input or {}

    # This would import and test the tool in production
    return {
        "success": True,
        "plugin": plugin_name,
        "tool": tool_name,
        "input": test_input,
        "instruction": (
            f"To test this tool:\n"
            f"1. Import: from plugins.{plugin_name.replace('-', '_')}.tools import {tool_name}\n"
            f"2. Call: result = {tool_name}(**{test_input})\n"
            f"3. Verify result structure and values"
        ),
    }


def generate_plugin_docs(
    plugin_name: str,
    format: str = "markdown",
) -> dict[str, Any]:
    """
    Generate documentation for a plugin.

    Args:
        plugin_name: Plugin name
        format: Output format (markdown, json, yaml)

    Returns:
        Generated documentation
    """
    import yaml

    manifest_path = f"plugins/{plugin_name}/manifest.yaml"

    try:
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Plugin not found: {plugin_name}",
        }

    if format == "markdown":
        doc = f"# {manifest['name']}\n\n"
        doc += f"{manifest.get('description', 'No description')}\n\n"
        doc += f"**Version:** {manifest.get('version', 'unknown')}\n\n"

        if manifest.get("tools"):
            doc += "## Tools\n\n"
            for tool in manifest["tools"]:
                doc += f"### {tool['name']}\n\n"
                doc += f"{tool.get('description', 'No description')}\n\n"
                if tool.get("parameters", {}).get("properties"):
                    doc += "**Parameters:**\n\n"
                    for param, spec in tool["parameters"]["properties"].items():
                        required = param in tool["parameters"].get("required", [])
                        doc += f"- `{param}` ({spec.get('type', 'any')})"
                        if required:
                            doc += " *required*"
                        doc += f": {spec.get('description', '')}\n"
                doc += "\n"

        if manifest.get("hooks"):
            doc += "## Hooks\n\n"
            for hook in manifest["hooks"]:
                doc += f"- **{hook['event']}**: {hook.get('description', 'No description')}\n"

        return {
            "success": True,
            "plugin": plugin_name,
            "format": format,
            "documentation": doc,
        }

    elif format == "json":
        import json
        return {
            "success": True,
            "plugin": plugin_name,
            "format": format,
            "documentation": json.dumps(manifest, indent=2),
        }

    else:  # yaml
        return {
            "success": True,
            "plugin": plugin_name,
            "format": format,
            "documentation": yaml.dump(manifest, default_flow_style=False),
        }


def list_plugin_events() -> dict[str, Any]:
    """
    List all available plugin events and hooks.

    Returns:
        Available events
    """
    events = {
        "session_start": {
            "description": "Fired when a new session begins",
            "context": ["session_id", "user_id", "config"],
        },
        "session_end": {
            "description": "Fired when a session ends",
            "context": ["session_id", "duration", "stats"],
        },
        "task_start": {
            "description": "Fired when a task begins",
            "context": ["task", "task_type", "conversation_id"],
        },
        "task_complete": {
            "description": "Fired when a task completes",
            "context": ["task", "result", "changes"],
        },
        "pre_tool_use": {
            "description": "Fired before a tool is executed",
            "context": ["tool_name", "tool_args", "can_block"],
        },
        "post_tool_use": {
            "description": "Fired after a tool completes",
            "context": ["tool_name", "tool_args", "result"],
        },
        "message_received": {
            "description": "Fired when user message is received",
            "context": ["message", "conversation_id", "user_id"],
        },
        "response_generated": {
            "description": "Fired when response is generated",
            "context": ["response", "tokens_used", "model"],
        },
        "plugin_loaded": {
            "description": "Fired when a plugin is loaded",
            "context": ["plugin_name", "version", "tools"],
        },
        "error": {
            "description": "Fired when an error occurs",
            "context": ["error", "stack_trace", "context"],
        },
    }

    return {
        "success": True,
        "events": events,
        "total": len(events),
    }
