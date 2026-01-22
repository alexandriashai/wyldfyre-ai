"""
Code Review Plugin Hooks.

Event handlers for monitoring code operations.
"""

from typing import Any

from .tools import SECURITY_PATTERNS
import re


def on_pre_tool_use(context: dict[str, Any]) -> dict[str, Any]:
    """
    Monitor tool usage for security patterns.

    Intercepts tool calls to check for potentially dangerous operations.
    """
    tool_name = context.get("tool_name", "")
    tool_args = context.get("tool_args", {})

    warnings = []

    # Check file operations
    if tool_name in ("write_file", "edit_file", "create_file"):
        content = tool_args.get("content", "")
        for pattern, message, severity in SECURITY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append({
                    "type": "security_warning",
                    "message": message,
                    "severity": severity.value,
                })

    # Check command execution
    if tool_name in ("run_command", "execute", "bash"):
        command = tool_args.get("command", "")
        dangerous_commands = ["rm -rf", "dd if=", "mkfs", "> /dev/", "chmod 777"]
        for dangerous in dangerous_commands:
            if dangerous in command:
                warnings.append({
                    "type": "dangerous_command",
                    "message": f"Potentially dangerous command: {dangerous}",
                    "severity": "high",
                })

    if warnings:
        context["security_warnings"] = warnings

    return context


def on_task_complete(context: dict[str, Any]) -> dict[str, Any]:
    """
    Generate review summary after code tasks complete.
    """
    task_type = context.get("task_type", "")

    # Only process code-related tasks
    if task_type not in ("code_change", "file_edit", "commit"):
        return context

    changes = context.get("changes", [])

    if changes:
        context["review_summary"] = {
            "files_changed": len(changes),
            "should_review": len(changes) > 3,
            "recommendation": "Consider running /review before committing" if len(changes) > 3 else None,
        }

    return context
