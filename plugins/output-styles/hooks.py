"""Output Styles Plugin Hooks."""

from typing import Any
from .tools import get_current_style, OUTPUT_STYLES


def apply_output_style(context: dict[str, Any]) -> dict[str, Any]:
    """
    Apply output style to generated responses.

    Modifies the response format based on current style.
    """
    response = context.get("response", "")
    current = get_current_style()
    style_name = current.get("current_style", "standard")

    if style_name != "standard":
        style_info = current.get("info", {})
        context["output_style_applied"] = {
            "style": style_name,
            "guidelines": style_info.get("guidelines", []),
            "hint": f"Response should follow '{style_name}' style guidelines",
        }

    return context


def load_user_style_preference(context: dict[str, Any]) -> dict[str, Any]:
    """
    Load user's preferred output style.

    Checks for user preference settings at session start.
    """
    user_prefs = context.get("user_preferences", {})
    preferred_style = user_prefs.get("output_style", "standard")

    if preferred_style in OUTPUT_STYLES:
        context["loaded_output_style"] = {
            "style": preferred_style,
            "source": "user_preference",
        }
    else:
        context["loaded_output_style"] = {
            "style": "standard",
            "source": "default",
        }

    return context
