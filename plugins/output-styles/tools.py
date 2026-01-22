"""
Output Styles Plugin Tools.

Response formatting and style management.
"""

from typing import Any


OUTPUT_STYLES = {
    "standard": {
        "name": "Standard",
        "description": "Clear, balanced responses",
        "characteristics": [
            "Direct answers",
            "Moderate detail level",
            "Professional tone",
        ],
        "template": "{content}",
        "guidelines": [
            "Be clear and concise",
            "Provide relevant context",
            "Use proper formatting",
        ],
    },
    "explanatory": {
        "name": "Explanatory",
        "description": "Detailed explanations with reasoning",
        "characteristics": [
            "Step-by-step breakdowns",
            "Explains the 'why'",
            "Includes context and background",
            "Uses examples",
        ],
        "template": """## Understanding {topic}

{explanation}

### Why This Matters
{reasoning}

### Example
{example}

### Key Takeaways
{takeaways}""",
        "guidelines": [
            "Always explain reasoning",
            "Provide relevant background",
            "Use concrete examples",
            "Summarize key points",
        ],
    },
    "learning": {
        "name": "Learning",
        "description": "Educational format for teaching concepts",
        "characteristics": [
            "Progressive complexity",
            "Interactive elements",
            "Practice suggestions",
            "Knowledge checks",
        ],
        "template": """## Learning: {topic}

### What You'll Learn
{objectives}

### Core Concepts
{concepts}

### Hands-On Practice
{practice}

### Check Your Understanding
{quiz}

### Next Steps
{next_steps}""",
        "guidelines": [
            "Start with fundamentals",
            "Build complexity gradually",
            "Include practice exercises",
            "Suggest next learning steps",
        ],
    },
    "concise": {
        "name": "Concise",
        "description": "Brief, to-the-point responses",
        "characteristics": [
            "Minimal explanation",
            "Key points only",
            "No filler content",
        ],
        "template": "{content}",
        "guidelines": [
            "Maximum clarity, minimum words",
            "Use bullet points",
            "Skip pleasantries",
            "Focus on actionable info",
        ],
    },
    "detailed": {
        "name": "Detailed",
        "description": "Comprehensive, thorough responses",
        "characteristics": [
            "In-depth coverage",
            "Multiple perspectives",
            "Edge cases addressed",
            "Complete documentation",
        ],
        "template": """## {topic}

### Overview
{overview}

### Details
{details}

### Considerations
{considerations}

### Edge Cases
{edge_cases}

### References
{references}""",
        "guidelines": [
            "Cover all aspects",
            "Address edge cases",
            "Provide alternatives",
            "Include references",
        ],
    },
    "technical": {
        "name": "Technical",
        "description": "Technical documentation style",
        "characteristics": [
            "Precise terminology",
            "Code examples",
            "API references",
            "Implementation details",
        ],
        "template": """## {topic}

### Synopsis
{synopsis}

### Parameters
{parameters}

### Returns
{returns}

### Example
```{language}
{code}
```

### Notes
{notes}""",
        "guidelines": [
            "Use precise technical terms",
            "Include code samples",
            "Document parameters and returns",
            "Note edge cases and gotchas",
        ],
    },
    "beginner-friendly": {
        "name": "Beginner Friendly",
        "description": "Accessible to newcomers",
        "characteristics": [
            "Simple language",
            "Analogies and metaphors",
            "Avoids jargon",
            "Encouraging tone",
        ],
        "template": """## {topic} (Simplified)

### In Plain English
{simple_explanation}

### Think of It Like...
{analogy}

### Try It Yourself
{try_it}

### Common Questions
{faq}""",
        "guidelines": [
            "Use everyday language",
            "Explain jargon when necessary",
            "Use relatable analogies",
            "Be encouraging and patient",
        ],
    },
}

# Current style storage (per-session)
_current_style = "standard"
_custom_styles: dict[str, dict] = {}


def set_output_style(
    style: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Set the output style for responses.

    Args:
        style: Output style to use
        options: Style-specific options

    Returns:
        Style configuration result
    """
    global _current_style

    available_styles = list(OUTPUT_STYLES.keys()) + list(_custom_styles.keys())

    if style not in available_styles:
        return {
            "success": False,
            "error": f"Unknown style: {style}",
            "available_styles": available_styles,
        }

    _current_style = style

    style_info = OUTPUT_STYLES.get(style) or _custom_styles.get(style)

    return {
        "success": True,
        "message": f"Output style set to: {style}",
        "style": style,
        "description": style_info.get("description"),
        "characteristics": style_info.get("characteristics", []),
        "options_applied": options or {},
    }


def get_style_info(
    style: str | None = None,
) -> dict[str, Any]:
    """
    Get information about available output styles.

    Args:
        style: Specific style to get info about

    Returns:
        Style information
    """
    if style:
        style_info = OUTPUT_STYLES.get(style) or _custom_styles.get(style)
        if not style_info:
            return {
                "success": False,
                "error": f"Unknown style: {style}",
            }
        return {
            "success": True,
            "style": style,
            "info": style_info,
        }

    # Return all styles
    all_styles = []
    for name, info in OUTPUT_STYLES.items():
        all_styles.append({
            "name": name,
            "display_name": info["name"],
            "description": info["description"],
            "builtin": True,
        })

    for name, info in _custom_styles.items():
        all_styles.append({
            "name": name,
            "display_name": info.get("name", name),
            "description": info.get("description", "Custom style"),
            "builtin": False,
        })

    return {
        "success": True,
        "styles": all_styles,
        "current_style": _current_style,
        "total": len(all_styles),
    }


def format_response(
    content: str,
    style: str,
) -> dict[str, Any]:
    """
    Format a response according to a style.

    Args:
        content: Content to format
        style: Style to apply

    Returns:
        Formatted content
    """
    style_info = OUTPUT_STYLES.get(style) or _custom_styles.get(style)

    if not style_info:
        return {
            "success": False,
            "error": f"Unknown style: {style}",
        }

    # Apply style guidelines
    guidelines = style_info.get("guidelines", [])

    # For now, return formatting instructions
    # In production, this would actually transform the content
    return {
        "success": True,
        "original_content": content,
        "style": style,
        "formatting_guidelines": guidelines,
        "instruction": (
            f"Format the following content using the '{style}' style:\n\n"
            f"Guidelines:\n" +
            "\n".join(f"- {g}" for g in guidelines) +
            f"\n\nContent to format:\n{content}"
        ),
    }


def create_custom_style(
    name: str,
    template: str,
    rules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a custom output style.

    Args:
        name: Style name
        template: Response template with placeholders
        rules: Formatting rules

    Returns:
        Creation result
    """
    if name in OUTPUT_STYLES:
        return {
            "success": False,
            "error": f"Cannot override built-in style: {name}",
        }

    rules = rules or []

    _custom_styles[name] = {
        "name": name.replace("-", " ").title(),
        "description": f"Custom style: {name}",
        "characteristics": rules[:5],  # Use first 5 rules as characteristics
        "template": template,
        "guidelines": rules,
    }

    return {
        "success": True,
        "message": f"Custom style '{name}' created",
        "style": name,
        "template": template,
        "rules": rules,
    }


def get_current_style() -> dict[str, Any]:
    """
    Get the current output style.

    Returns:
        Current style info
    """
    style_info = OUTPUT_STYLES.get(_current_style) or _custom_styles.get(_current_style)

    return {
        "success": True,
        "current_style": _current_style,
        "info": style_info,
    }


def apply_style_to_prompt(
    system_prompt: str,
    style: str,
) -> dict[str, Any]:
    """
    Apply style modifications to a system prompt.

    Args:
        system_prompt: Original system prompt
        style: Style to apply

    Returns:
        Modified prompt
    """
    style_info = OUTPUT_STYLES.get(style) or _custom_styles.get(style)

    if not style_info:
        return {
            "success": False,
            "error": f"Unknown style: {style}",
        }

    # Build style addition to prompt
    style_addition = f"\n\n## Response Style: {style_info['name']}\n\n"
    style_addition += f"{style_info['description']}\n\n"
    style_addition += "Guidelines:\n"
    for guideline in style_info.get("guidelines", []):
        style_addition += f"- {guideline}\n"

    return {
        "success": True,
        "original_prompt": system_prompt,
        "style_addition": style_addition,
        "modified_prompt": system_prompt + style_addition,
    }
