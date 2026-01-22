"""
Hookify Plugin Tools.

Custom hook creation and management.
"""

import json
import os
from pathlib import Path
from typing import Any
from datetime import datetime


# In-memory hook storage (would be persisted in production)
_custom_hooks: dict[str, dict] = {}


VALID_EVENTS = [
    "pre_tool_use",
    "post_tool_use",
    "task_start",
    "task_complete",
    "message_received",
    "response_generated",
    "session_start",
    "session_end",
    "error",
]

HOOK_TEMPLATE = '''"""
Custom hook: {name}
Event: {event}
Created: {created}
Description: {description}
"""

from typing import Any


def handler(context: dict[str, Any]) -> dict[str, Any]:
    """
    Hook handler function.

    Args:
        context: Event context with relevant data

    Returns:
        Modified context dictionary
    """
{handler_code}
    return context
'''


def create_hook(
    name: str,
    event: str,
    handler_code: str,
    priority: int = 50,
    description: str | None = None,
) -> dict[str, Any]:
    """
    Create a new custom hook.

    Args:
        name: Hook name
        event: Event that triggers the hook
        handler_code: Python code for the hook handler
        priority: Hook priority (lower runs first)
        description: Hook description

    Returns:
        Creation result
    """
    if event not in VALID_EVENTS:
        return {
            "success": False,
            "error": f"Invalid event '{event}'. Valid events: {', '.join(VALID_EVENTS)}",
        }

    if name in _custom_hooks:
        return {
            "success": False,
            "error": f"Hook '{name}' already exists. Use a different name or delete existing hook.",
        }

    # Validate handler code (basic check)
    if not handler_code.strip():
        return {
            "success": False,
            "error": "Handler code cannot be empty",
        }

    # Ensure proper indentation for template
    indented_code = "\n".join(f"    {line}" for line in handler_code.split("\n"))

    hook_data = {
        "name": name,
        "event": event,
        "handler_code": handler_code,
        "priority": priority,
        "description": description or f"Custom hook for {event}",
        "enabled": True,
        "created_at": datetime.utcnow().isoformat(),
        "full_code": HOOK_TEMPLATE.format(
            name=name,
            event=event,
            created=datetime.utcnow().isoformat(),
            description=description or f"Custom hook for {event}",
            handler_code=indented_code,
        ),
    }

    _custom_hooks[name] = hook_data

    return {
        "success": True,
        "message": f"Hook '{name}' created successfully",
        "hook": {
            "name": name,
            "event": event,
            "priority": priority,
            "enabled": True,
        },
    }


def list_hooks(
    event: str | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    List all registered hooks.

    Args:
        event: Filter by event type
        active_only: Only show enabled hooks

    Returns:
        List of hooks
    """
    hooks = []

    for name, hook_data in _custom_hooks.items():
        if event and hook_data["event"] != event:
            continue
        if active_only and not hook_data["enabled"]:
            continue

        hooks.append({
            "name": name,
            "event": hook_data["event"],
            "priority": hook_data["priority"],
            "enabled": hook_data["enabled"],
            "description": hook_data["description"],
            "created_at": hook_data["created_at"],
        })

    # Sort by event then priority
    hooks.sort(key=lambda h: (h["event"], h["priority"]))

    return {
        "success": True,
        "hooks": hooks,
        "total": len(hooks),
        "events": list(set(h["event"] for h in hooks)),
    }


def toggle_hook(
    name: str,
    enabled: bool,
) -> dict[str, Any]:
    """
    Enable or disable a hook.

    Args:
        name: Hook name
        enabled: Enable or disable

    Returns:
        Toggle result
    """
    if name not in _custom_hooks:
        return {
            "success": False,
            "error": f"Hook '{name}' not found",
        }

    _custom_hooks[name]["enabled"] = enabled

    return {
        "success": True,
        "message": f"Hook '{name}' {'enabled' if enabled else 'disabled'}",
        "hook": {
            "name": name,
            "enabled": enabled,
        },
    }


def delete_hook(
    name: str,
) -> dict[str, Any]:
    """
    Delete a custom hook.

    Args:
        name: Hook name to delete

    Returns:
        Deletion result
    """
    if name not in _custom_hooks:
        return {
            "success": False,
            "error": f"Hook '{name}' not found",
        }

    del _custom_hooks[name]

    return {
        "success": True,
        "message": f"Hook '{name}' deleted successfully",
    }


def test_hook(
    name: str,
    test_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Test a hook with sample context.

    Args:
        name: Hook name to test
        test_context: Test context data

    Returns:
        Test results
    """
    if name not in _custom_hooks:
        return {
            "success": False,
            "error": f"Hook '{name}' not found",
        }

    hook_data = _custom_hooks[name]
    context = test_context or {"test": True, "sample_data": "test_value"}

    try:
        # Create a safe execution environment
        local_vars = {"context": context.copy()}
        exec(hook_data["handler_code"], {"Any": Any}, local_vars)

        return {
            "success": True,
            "message": f"Hook '{name}' executed successfully",
            "input_context": context,
            "output_context": local_vars.get("context", context),
            "execution_info": {
                "event": hook_data["event"],
                "priority": hook_data["priority"],
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Hook execution failed: {str(e)}",
            "hook": name,
            "context": context,
        }


def save_hooks_to_file(
    directory: str = ".wyld/hooks",
) -> dict[str, Any]:
    """
    Save all hooks to files for persistence.

    Args:
        directory: Directory to save hooks

    Returns:
        Save result
    """
    hooks_dir = Path(directory)
    hooks_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for name, hook_data in _custom_hooks.items():
        hook_file = hooks_dir / f"{name}.py"
        hook_file.write_text(hook_data["full_code"])

        meta_file = hooks_dir / f"{name}.json"
        meta_file.write_text(json.dumps({
            "name": name,
            "event": hook_data["event"],
            "priority": hook_data["priority"],
            "enabled": hook_data["enabled"],
            "description": hook_data["description"],
            "created_at": hook_data["created_at"],
        }, indent=2))

        saved.append(name)

    return {
        "success": True,
        "message": f"Saved {len(saved)} hooks to {directory}",
        "hooks": saved,
    }


def load_hooks_from_file(
    directory: str = ".wyld/hooks",
) -> dict[str, Any]:
    """
    Load hooks from files.

    Args:
        directory: Directory containing hook files

    Returns:
        Load result
    """
    hooks_dir = Path(directory)
    if not hooks_dir.exists():
        return {
            "success": True,
            "message": "No hooks directory found",
            "loaded": 0,
        }

    loaded = []
    for meta_file in hooks_dir.glob("*.json"):
        try:
            meta = json.loads(meta_file.read_text())
            hook_file = hooks_dir / f"{meta['name']}.py"

            if hook_file.exists():
                code = hook_file.read_text()
                # Extract handler code from full code
                # This is simplified - real implementation would parse properly
                _custom_hooks[meta["name"]] = {
                    **meta,
                    "handler_code": code,
                    "full_code": code,
                }
                loaded.append(meta["name"])
        except Exception as e:
            continue

    return {
        "success": True,
        "message": f"Loaded {len(loaded)} hooks from {directory}",
        "hooks": loaded,
    }
