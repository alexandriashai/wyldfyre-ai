"""
Quality check hook handlers.

Handles post-task quality checks and git hook failures.
"""

import json
from typing import Any


async def on_post_task_quality_check(context: dict[str, Any]) -> dict[str, Any]:
    """
    Hook handler for POST_TASK_QUALITY_CHECK event.

    Runs configured quality checks after task completion.

    Context expected:
        - root_path: str - Project root path
        - files_changed: list[str] | None - Files modified by the task
        - quality_settings: dict | None - Project quality settings
        - auto_fix: bool - Whether to auto-fix issues

    Returns context with:
        - quality_results: dict - Results from quality checks
        - quality_passed: bool - Whether all checks passed
        - quality_errors: list[dict] - List of errors found
    """
    from tools import run_all_quality_checks_impl

    root_path = context.get("root_path")
    if not root_path:
        context["quality_passed"] = True
        context["quality_results"] = {"skipped": "No root_path provided"}
        context["quality_errors"] = []
        return context

    quality_settings = context.get("quality_settings")
    if quality_settings is None:
        context["quality_passed"] = True
        context["quality_results"] = {"skipped": "No quality_settings configured"}
        context["quality_errors"] = []
        return context

    # Parse quality_settings if it's a JSON string
    if isinstance(quality_settings, str):
        try:
            quality_settings = json.loads(quality_settings)
        except json.JSONDecodeError:
            context["quality_passed"] = True
            context["quality_results"] = {"skipped": "Invalid quality_settings JSON"}
            context["quality_errors"] = []
            return context

    # Check if quality checks are enabled
    if not quality_settings.get("enabled", True):
        context["quality_passed"] = True
        context["quality_results"] = {"skipped": "Quality checks disabled"}
        context["quality_errors"] = []
        return context

    files_changed = context.get("files_changed", [])
    auto_fix = context.get("auto_fix", quality_settings.get("auto_fix_lint_errors", False))

    # Run quality checks
    results = await run_all_quality_checks_impl(
        root_path=root_path,
        quality_settings=quality_settings,
        files_changed=files_changed,
        fix_issues=auto_fix,
    )

    context["quality_results"] = results
    context["quality_passed"] = results.get("all_passed", True)
    context["quality_errors"] = results.get("errors", [])

    return context


async def on_git_hook_failed(context: dict[str, Any]) -> dict[str, Any]:
    """
    Hook handler for GIT_HOOK_FAILED event.

    Parses git hook failure output and provides structured error information.

    Context expected:
        - stderr: str - Raw stderr from git command
        - hook_name: str | None - Name of the failed hook
        - root_path: str - Project root path

    Returns context with:
        - hook_failures: list[dict] - Parsed hook failure details
        - affected_files: list[str] - Files that triggered failures
        - suggested_fixes: list[str] - Suggested fix commands
    """
    stderr = context.get("stderr", "")
    root_path = context.get("root_path", "")

    hook_failures = []
    affected_files = set()
    suggested_fixes = []

    # Parse pre-commit style output
    current_hook = None
    current_output = []

    lines = stderr.split("\n")
    for line in lines:
        # Detect hook name from pre-commit output
        if line.startswith("[") and "]" in line:
            # Save previous hook if any
            if current_hook and current_output:
                hook_failures.append({
                    "hook_name": current_hook,
                    "error_output": "\n".join(current_output),
                })

            # Extract hook name: [hook-name] or [hook-name: status]
            bracket_content = line[1:line.index("]")]
            if ":" in bracket_content:
                current_hook = bracket_content.split(":")[0].strip()
            else:
                current_hook = bracket_content.strip()
            current_output = [line]
        elif current_hook:
            current_output.append(line)

            # Extract file paths from common patterns
            # ESLint: /path/to/file.ts:line:col
            if ":" in line and not line.startswith(" "):
                parts = line.split(":")
                if len(parts) >= 2 and parts[0].startswith("/"):
                    affected_files.add(parts[0])
            # Ruff/flake8: path/to/file.py:line:col
            elif ".py:" in line:
                parts = line.split(":")
                if parts:
                    affected_files.add(parts[0])

    # Save last hook
    if current_hook and current_output:
        hook_failures.append({
            "hook_name": current_hook,
            "error_output": "\n".join(current_output),
        })

    # Generate suggested fixes based on detected hooks
    for failure in hook_failures:
        hook_name = failure.get("hook_name", "").lower()

        if "eslint" in hook_name:
            suggested_fixes.append(f"cd {root_path} && npx eslint --fix .")
        elif "prettier" in hook_name:
            suggested_fixes.append(f"cd {root_path} && npx prettier --write .")
        elif "ruff" in hook_name:
            suggested_fixes.append(f"cd {root_path} && ruff check --fix .")
        elif "black" in hook_name:
            suggested_fixes.append(f"cd {root_path} && black .")
        elif "mypy" in hook_name:
            suggested_fixes.append(f"cd {root_path} && mypy --install-types --non-interactive .")
        elif "stylelint" in hook_name:
            suggested_fixes.append(f"cd {root_path} && npx stylelint --fix '**/*.css'")
        elif "php-cs-fixer" in hook_name or "php" in hook_name:
            suggested_fixes.append(f"cd {root_path} && vendor/bin/php-cs-fixer fix")

    context["hook_failures"] = hook_failures
    context["affected_files"] = list(affected_files)
    context["suggested_fixes"] = suggested_fixes

    return context
