"""
Plugin Bridge for Plan Step Execution.

Wraps plugin tool functions so they can be called directly
from the step execution loop without going through the full
plugin/hook infrastructure.
"""

import sys
from pathlib import Path
from typing import Any

# Add plugins directory to path so we can import plugin modules
_plugins_dir = Path("/home/wyld-core/plugins")
if str(_plugins_dir) not in sys.path:
    sys.path.insert(0, str(_plugins_dir))


def run_accessibility_check(code: str) -> dict[str, Any]:
    """
    Run accessibility analysis on HTML/CSS code.

    Wraps the frontend-design plugin's generate_accessibility_fixes tool.
    """
    try:
        from importlib import import_module
        # Import the plugin's tools module directly
        spec_path = _plugins_dir / "frontend-design" / "tools.py"
        if spec_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "frontend_design_tools", str(spec_path)
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.generate_accessibility_fixes(code)
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Frontend design plugin not found"}


def run_responsive_review(css: str, breakpoints: list[str] | None = None) -> dict[str, Any]:
    """
    Review CSS for responsive design quality.

    Wraps the frontend-design plugin's review_responsive_design tool.
    """
    try:
        spec_path = _plugins_dir / "frontend-design" / "tools.py"
        if spec_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "frontend_design_tools", str(spec_path)
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.review_responsive_design(css, breakpoints)
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Frontend design plugin not found"}


def run_animation_suggestions(
    component_type: str, interaction: str | None = None
) -> dict[str, Any]:
    """
    Get CSS animation/transition suggestions.

    Wraps the frontend-design plugin's suggest_animations tool.
    """
    try:
        spec_path = _plugins_dir / "frontend-design" / "tools.py"
        if spec_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "frontend_design_tools", str(spec_path)
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.suggest_animations(component_type, interaction)
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Frontend design plugin not found"}


def run_component_analysis(code: str, framework: str | None = None) -> dict[str, Any]:
    """
    Analyze a component for best practices.

    Wraps the frontend-design plugin's analyze_component tool.
    """
    try:
        spec_path = _plugins_dir / "frontend-design" / "tools.py"
        if spec_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "frontend_design_tools", str(spec_path)
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.analyze_component(code, framework)
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Frontend design plugin not found"}
