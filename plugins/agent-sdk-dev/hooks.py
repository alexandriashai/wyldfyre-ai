"""Agent SDK Development Toolkit Hooks."""

from typing import Any


def detect_agent_dev_task(context: dict[str, Any]) -> dict[str, Any]:
    """
    Detect agent development tasks.

    Identifies when the task involves creating or modifying agents.
    """
    task = context.get("task", "")
    task_lower = task.lower()

    agent_keywords = [
        "agent", "create agent", "new agent", "agent config",
        "system prompt", "agent sdk", "custom agent", "agent tool",
    ]

    is_agent_dev = any(kw in task_lower for kw in agent_keywords)

    if is_agent_dev:
        context["agent_dev_task"] = {
            "detected": True,
            "suggestions": [
                "Define clear agent role and capabilities",
                "Write comprehensive system prompt",
                "Configure appropriate model parameters",
                "Define necessary tools",
                "Add error handling and validation",
            ],
        }

    return context
