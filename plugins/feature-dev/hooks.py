"""Feature Development Plugin Hooks."""

from typing import Any


def on_feature_task_start(context: dict[str, Any]) -> dict[str, Any]:
    """Initialize feature development context when a feature task starts."""
    task_description = context.get("description", "").lower()

    # Detect if this is a feature development task
    feature_keywords = ["implement", "add feature", "create", "build", "develop"]
    is_feature_task = any(kw in task_description for kw in feature_keywords)

    if is_feature_task:
        context["feature_dev"] = {
            "enabled": True,
            "phase": "exploration",
            "suggestions": [
                "Use /plan to create a structured implementation plan",
                "Run explore_codebase to understand existing patterns",
            ],
        }

    return context
