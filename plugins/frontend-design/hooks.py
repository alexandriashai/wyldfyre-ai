"""Frontend Design Plugin Hooks."""

from typing import Any


def detect_frontend_task(context: dict[str, Any]) -> dict[str, Any]:
    """
    Detect frontend-related tasks.

    Identifies when the task involves frontend development.
    """
    task = context.get("task", "")
    task_lower = task.lower()

    frontend_keywords = [
        "component", "ui", "ux", "frontend", "react", "vue", "svelte",
        "css", "style", "layout", "responsive", "animation", "form",
        "button", "modal", "dropdown", "navigation", "tailwind",
    ]

    is_frontend = any(kw in task_lower for kw in frontend_keywords)

    if is_frontend:
        context["frontend_task"] = {
            "detected": True,
            "suggestions": [
                "Consider accessibility requirements",
                "Plan responsive breakpoints",
                "Define component states (loading, error, empty)",
            ],
        }

    return context


def suggest_ui_improvements(context: dict[str, Any]) -> dict[str, Any]:
    """
    Suggest UI improvements after file creation.

    Triggered after files are created or modified.
    """
    tool_name = context.get("tool_name", "")
    file_path = context.get("file_path", "")

    # Check if a frontend file was created
    frontend_extensions = [".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss"]

    if tool_name in ("write_file", "create_file", "edit_file"):
        if any(file_path.endswith(ext) for ext in frontend_extensions):
            context["ui_suggestions"] = {
                "enabled": True,
                "file": file_path,
                "suggestions": [
                    "Test with keyboard navigation",
                    "Verify color contrast ratios",
                    "Check responsive behavior",
                    "Add loading states if async",
                ],
            }

    return context
