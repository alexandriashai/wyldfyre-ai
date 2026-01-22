"""Commit Commands Plugin Hooks."""

from typing import Any


def suggest_commit(context: dict[str, Any]) -> dict[str, Any]:
    """Suggest commit after code changes are complete."""
    task_type = context.get("task_type", "")
    changes = context.get("changes", [])

    if task_type in ("code_change", "file_edit", "implementation") and changes:
        context["commit_suggestion"] = {
            "should_commit": True,
            "message": "Consider committing your changes with /commit",
            "files_changed": len(changes),
        }

    return context
