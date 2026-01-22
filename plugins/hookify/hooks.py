"""Hookify Plugin Hooks."""

from typing import Any
from .tools import load_hooks_from_file


def load_custom_hooks(context: dict[str, Any]) -> dict[str, Any]:
    """
    Load custom hooks at session start.

    Loads any saved custom hooks from the hooks directory.
    """
    hooks_dir = context.get("config", {}).get("hooks_directory", ".wyld/hooks")

    result = load_hooks_from_file(hooks_dir)

    context["custom_hooks_loaded"] = {
        "count": len(result.get("hooks", [])),
        "hooks": result.get("hooks", []),
    }

    return context


def handle_hook_error(context: dict[str, Any]) -> dict[str, Any]:
    """
    Handle errors in custom hooks.

    Logs the error and optionally disables the problematic hook.
    """
    error = context.get("hook_error", {})
    hook_name = error.get("hook_name")
    error_message = error.get("error")

    if hook_name and error_message:
        context["hook_error_handled"] = {
            "hook": hook_name,
            "error": error_message,
            "action": "logged",
            "recommendation": f"Consider reviewing hook '{hook_name}' for issues",
        }

    return context
