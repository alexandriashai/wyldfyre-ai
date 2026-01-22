"""Plugin Development Toolkit Hooks."""

from typing import Any
from .tools import validate_manifest


def validate_on_load(context: dict[str, Any]) -> dict[str, Any]:
    """
    Validate plugin when loaded.

    Runs validation on newly loaded plugins.
    """
    plugin_name = context.get("plugin_name")
    plugin_dir = context.get("plugin_dir")

    if plugin_name and plugin_dir:
        manifest_path = f"{plugin_dir}/manifest.yaml"
        validation = validate_manifest(manifest_path, strict=False)

        context["plugin_validation"] = {
            "plugin": plugin_name,
            "valid": validation.get("success", False),
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
        }

    return context
