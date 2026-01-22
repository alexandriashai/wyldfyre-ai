"""
Frontend Design Plugin Tools.

UI/UX guidance and component analysis.
"""

import re
from typing import Any


COMPONENT_PATTERNS = {
    "react": {
        "functional": r"(function|const)\s+\w+\s*=?\s*\([^)]*\)\s*[=:>]?\s*{",
        "class": r"class\s+\w+\s+extends\s+(React\.)?Component",
        "hooks": r"use[A-Z]\w+\s*\(",
    },
    "vue": {
        "sfc": r"<template>|<script>|<style>",
        "composition": r"setup\s*\(\)|defineComponent",
    },
}

ACCESSIBILITY_ISSUES = [
    (r"<img[^>]*(?!alt=)[^>]*>", "Image missing alt attribute", "critical"),
    (r"<button[^>]*(?!type=)[^>]*>", "Button missing type attribute", "medium"),
    (r"onClick=.*<div|<span", "Click handler on non-interactive element", "high"),
    (r"<a[^>]*(?!href=)[^>]*>", "Anchor missing href attribute", "high"),
    (r"tabIndex=['\"]?-1['\"]?", "Negative tabIndex removes from tab order", "medium"),
    (r"<input[^>]*(?!id=|aria-label)[^>]*>", "Input missing label association", "high"),
    (r"color:\s*#[0-9a-f]{3,6}", "Check color contrast ratios", "low"),
]

RESPONSIVE_PATTERNS = {
    "mobile_first": r"@media\s*\(\s*min-width",
    "desktop_first": r"@media\s*\(\s*max-width",
    "container_queries": r"@container",
    "clamp": r"clamp\s*\(",
    "viewport_units": r"\d+v[hw]",
}


def analyze_component(
    code: str,
    framework: str | None = None,
) -> dict[str, Any]:
    """
    Analyze a component for best practices and improvements.

    Args:
        code: Component source code
        framework: Frontend framework

    Returns:
        Analysis results with suggestions
    """
    # Detect framework if not provided
    if not framework:
        if re.search(r"import.*from\s+['\"]react['\"]", code):
            framework = "react"
        elif re.search(r"<template>|<script.*>", code):
            framework = "vue"
        elif re.search(r"<script.*context=['\"]module['\"]", code):
            framework = "svelte"
        else:
            framework = "react"  # Default

    findings = []
    suggestions = []

    # React-specific analysis
    if framework == "react":
        # Check for hooks rules violations
        if re.search(r"if\s*\([^)]+\)\s*{[^}]*use[A-Z]", code):
            findings.append({
                "type": "hooks_violation",
                "severity": "high",
                "message": "Hooks called conditionally - violates Rules of Hooks",
            })

        # Check for missing key prop in lists
        if re.search(r"\.map\s*\([^)]+\)\s*=>\s*[^{]*(?!key=)", code):
            findings.append({
                "type": "missing_key",
                "severity": "high",
                "message": "Array map without key prop",
            })

        # Check for inline functions in render
        inline_handlers = len(re.findall(r"onClick={\s*\([^)]*\)\s*=>", code))
        if inline_handlers > 3:
            suggestions.append({
                "type": "performance",
                "message": f"Found {inline_handlers} inline handlers - consider useCallback for optimization",
            })

        # Check for state management
        state_count = len(re.findall(r"useState\s*\(", code))
        if state_count > 5:
            suggestions.append({
                "type": "architecture",
                "message": f"Component has {state_count} state variables - consider useReducer or extracting logic",
            })

    # General checks
    lines = code.split("\n")

    # Component size check
    if len(lines) > 200:
        suggestions.append({
            "type": "maintainability",
            "message": f"Component is {len(lines)} lines - consider splitting into smaller components",
        })

    # Prop drilling check
    props_passed = len(re.findall(r"props\.\w+|{\s*\w+\s*}", code))
    if props_passed > 10:
        suggestions.append({
            "type": "architecture",
            "message": "Many props passed - consider Context API or state management",
        })

    return {
        "success": True,
        "framework": framework,
        "analysis": {
            "lines_of_code": len(lines),
            "findings": findings,
            "suggestions": suggestions,
            "component_type": "functional" if "function" in code or "=>" in code else "class",
        },
        "metrics": {
            "complexity_score": len(findings) * 2 + len(suggestions),
            "issues_found": len(findings),
            "suggestions_count": len(suggestions),
        },
    }


def suggest_component_structure(
    description: str,
    framework: str = "react",
    has_state: bool = True,
    has_props: bool = True,
) -> dict[str, Any]:
    """
    Suggest component structure and organization.

    Args:
        description: Component description and requirements
        framework: Frontend framework
        has_state: Whether component needs state
        has_props: Whether component receives props

    Returns:
        Suggested structure
    """
    structure = {
        "framework": framework,
        "files": [],
        "imports": [],
        "sections": [],
    }

    if framework == "react":
        # Main component file
        structure["files"].append({
            "name": "Component.tsx",
            "purpose": "Main component file",
        })

        # Styles
        structure["files"].append({
            "name": "Component.module.css",
            "purpose": "Component styles (CSS Modules)",
        })

        # Types
        if has_props:
            structure["files"].append({
                "name": "types.ts",
                "purpose": "TypeScript interfaces for props",
            })

        # Hooks
        if has_state:
            structure["files"].append({
                "name": "hooks/useComponentLogic.ts",
                "purpose": "Custom hook for component logic",
            })

        # Component sections
        structure["sections"] = [
            {"name": "imports", "description": "Import statements"},
            {"name": "types", "description": "TypeScript interfaces"},
            {"name": "hooks", "description": "Custom hooks and state"},
            {"name": "handlers", "description": "Event handlers"},
            {"name": "render", "description": "JSX return"},
        ]

        structure["imports"] = [
            "import React from 'react';",
            "import styles from './Component.module.css';",
        ]
        if has_state:
            structure["imports"][0] = "import React, { useState, useCallback } from 'react';"

    elif framework == "vue":
        structure["files"].append({
            "name": "Component.vue",
            "purpose": "Single File Component",
        })
        structure["sections"] = [
            {"name": "template", "description": "HTML template"},
            {"name": "script", "description": "Component logic (Composition API)"},
            {"name": "style", "description": "Scoped styles"},
        ]

    return {
        "success": True,
        "description": description,
        "structure": structure,
        "best_practices": [
            "Keep components focused on a single responsibility",
            "Use semantic HTML elements",
            "Implement proper error boundaries",
            "Add loading and error states",
            "Test with different screen readers",
        ],
    }


def generate_accessibility_fixes(
    code: str,
) -> dict[str, Any]:
    """
    Generate accessibility improvements for a component.

    Args:
        code: Component source code

    Returns:
        Accessibility issues and fixes
    """
    issues = []

    for pattern, message, severity in ACCESSIBILITY_ISSUES:
        matches = re.findall(pattern, code, re.IGNORECASE | re.DOTALL)
        if matches:
            issues.append({
                "pattern": pattern[:50],
                "message": message,
                "severity": severity,
                "occurrences": len(matches),
                "sample": matches[0][:100] if matches else None,
            })

    # Additional checks
    if "<form" in code and "aria-describedby" not in code:
        issues.append({
            "pattern": "form",
            "message": "Form should have aria-describedby for error messages",
            "severity": "medium",
        })

    if "role=" not in code and re.search(r"<div.*onClick|<span.*onClick", code):
        issues.append({
            "pattern": "interactive_div",
            "message": "Add role='button' and tabIndex='0' for interactive divs",
            "severity": "high",
        })

    fixes = []
    for issue in issues:
        fix = {
            "issue": issue["message"],
            "severity": issue["severity"],
        }

        # Generate specific fixes
        if "alt" in issue["message"]:
            fix["fix"] = "Add descriptive alt text: alt='Description of image'"
        elif "button" in issue["message"].lower():
            fix["fix"] = "Add type attribute: type='button' or type='submit'"
        elif "tabIndex" in issue["message"]:
            fix["fix"] = "Remove negative tabIndex or ensure intentional focus management"
        elif "label" in issue["message"]:
            fix["fix"] = "Add id and associate with <label for='id'> or use aria-label"

        fixes.append(fix)

    return {
        "success": True,
        "issues": issues,
        "fixes": fixes,
        "summary": {
            "total_issues": len(issues),
            "critical": sum(1 for i in issues if i["severity"] == "critical"),
            "high": sum(1 for i in issues if i["severity"] == "high"),
            "medium": sum(1 for i in issues if i["severity"] == "medium"),
        },
        "resources": [
            "WCAG 2.1 Guidelines: https://www.w3.org/WAI/WCAG21/quickref/",
            "MDN Accessibility: https://developer.mozilla.org/en-US/docs/Web/Accessibility",
        ],
    }


def review_responsive_design(
    css: str,
    breakpoints: list[str] | None = None,
) -> dict[str, Any]:
    """
    Review responsive design implementation.

    Args:
        css: CSS/styles to review
        breakpoints: Target breakpoints

    Returns:
        Responsive design review
    """
    breakpoints = breakpoints or ["640px", "768px", "1024px", "1280px"]

    findings = []
    approach = "unknown"

    # Detect approach
    if re.search(RESPONSIVE_PATTERNS["mobile_first"], css):
        approach = "mobile_first"
        findings.append({
            "type": "positive",
            "message": "Using mobile-first approach (min-width queries)",
        })
    elif re.search(RESPONSIVE_PATTERNS["desktop_first"], css):
        approach = "desktop_first"
        findings.append({
            "type": "info",
            "message": "Using desktop-first approach (max-width queries)",
        })

    # Check for modern features
    if re.search(RESPONSIVE_PATTERNS["clamp"], css):
        findings.append({
            "type": "positive",
            "message": "Using clamp() for fluid typography/spacing",
        })

    if re.search(RESPONSIVE_PATTERNS["container_queries"], css):
        findings.append({
            "type": "positive",
            "message": "Using container queries for component-level responsiveness",
        })

    # Check for fixed widths
    fixed_widths = re.findall(r"width:\s*(\d+)px", css)
    if fixed_widths:
        large_fixed = [w for w in fixed_widths if int(w) > 400]
        if large_fixed:
            findings.append({
                "type": "warning",
                "message": f"Found {len(large_fixed)} large fixed widths - consider responsive units",
            })

    # Check breakpoint coverage
    media_queries = re.findall(r"@media[^{]+{", css)
    breakpoints_used = set()
    for mq in media_queries:
        for bp in breakpoints:
            if bp in mq:
                breakpoints_used.add(bp)

    missing_breakpoints = set(breakpoints) - breakpoints_used
    if missing_breakpoints:
        findings.append({
            "type": "info",
            "message": f"Missing styles for breakpoints: {', '.join(missing_breakpoints)}",
        })

    return {
        "success": True,
        "approach": approach,
        "findings": findings,
        "breakpoints": {
            "target": breakpoints,
            "covered": list(breakpoints_used),
            "missing": list(missing_breakpoints),
        },
        "recommendations": [
            "Use relative units (rem, em, %) for spacing",
            "Test on actual devices, not just browser resize",
            "Consider touch targets (min 44x44px) for mobile",
            "Use CSS Grid/Flexbox for layout flexibility",
        ],
    }


def suggest_animations(
    component_type: str,
    interaction: str | None = None,
) -> dict[str, Any]:
    """
    Suggest micro-interactions and animations.

    Args:
        component_type: Type of component
        interaction: Type of interaction

    Returns:
        Animation suggestions
    """
    animations = {
        "button": {
            "hover": {
                "css": "transform: scale(1.02); transition: transform 0.15s ease-out;",
                "description": "Subtle scale on hover",
            },
            "click": {
                "css": "transform: scale(0.98); transition: transform 0.1s ease-in;",
                "description": "Press-in effect on click",
            },
            "focus": {
                "css": "outline: 2px solid var(--focus-ring); outline-offset: 2px;",
                "description": "Visible focus ring for accessibility",
            },
        },
        "modal": {
            "enter": {
                "css": "animation: modalIn 0.2s ease-out; @keyframes modalIn { from { opacity: 0; transform: scale(0.95); } }",
                "description": "Fade and scale in",
            },
            "exit": {
                "css": "animation: modalOut 0.15s ease-in; @keyframes modalOut { to { opacity: 0; transform: scale(0.95); } }",
                "description": "Fade and scale out",
            },
        },
        "card": {
            "hover": {
                "css": "transform: translateY(-4px); box-shadow: 0 12px 24px rgba(0,0,0,0.1); transition: all 0.2s ease-out;",
                "description": "Lift effect with shadow",
            },
        },
        "input": {
            "focus": {
                "css": "border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-alpha); transition: all 0.15s ease;",
                "description": "Border highlight with glow",
            },
        },
        "skeleton": {
            "loading": {
                "css": "background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; @keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }",
                "description": "Shimmer loading effect",
            },
        },
    }

    component_animations = animations.get(component_type.lower(), {})

    if interaction:
        specific = component_animations.get(interaction, {})
        return {
            "success": True,
            "component": component_type,
            "interaction": interaction,
            "animation": specific,
            "principles": [
                "Keep animations under 300ms for responsiveness",
                "Use ease-out for enter, ease-in for exit",
                "Respect prefers-reduced-motion",
            ],
        }

    return {
        "success": True,
        "component": component_type,
        "animations": component_animations,
        "principles": [
            "Keep animations under 300ms for responsiveness",
            "Use ease-out for enter, ease-in for exit",
            "Respect prefers-reduced-motion: @media (prefers-reduced-motion: reduce) { animation: none; }",
            "Animate transform and opacity for best performance",
        ],
    }
