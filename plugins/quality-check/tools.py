"""
Quality check tools.

Provides tools to run linters, formatters, type checkers, and tests.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any


# Common tool detection patterns
TOOL_PATTERNS = {
    "eslint": {
        "config_files": [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc.cjs", "eslint.config.js", "eslint.config.mjs"],
        "package_key": "eslint",
        "default_command": "npx eslint .",
        "fix_command": "npx eslint --fix .",
        "type": "lint",
    },
    "prettier": {
        "config_files": [".prettierrc", ".prettierrc.js", ".prettierrc.json", "prettier.config.js", "prettier.config.cjs"],
        "package_key": "prettier",
        "default_command": "npx prettier --check .",
        "fix_command": "npx prettier --write .",
        "type": "format",
    },
    "ruff": {
        "config_files": ["ruff.toml", "pyproject.toml"],
        "package_key": None,
        "default_command": "ruff check .",
        "fix_command": "ruff check --fix .",
        "type": "lint",
    },
    "black": {
        "config_files": ["pyproject.toml"],
        "package_key": None,
        "default_command": "black --check .",
        "fix_command": "black .",
        "type": "format",
    },
    "mypy": {
        "config_files": ["mypy.ini", "pyproject.toml", ".mypy.ini"],
        "package_key": None,
        "default_command": "mypy .",
        "type": "typecheck",
    },
    "typescript": {
        "config_files": ["tsconfig.json"],
        "package_key": "typescript",
        "default_command": "npx tsc --noEmit",
        "type": "typecheck",
    },
    "stylelint": {
        "config_files": [".stylelintrc", ".stylelintrc.js", ".stylelintrc.json", ".stylelintrc.cjs", "stylelint.config.js"],
        "package_key": "stylelint",
        "default_command": "npx stylelint '**/*.css'",
        "fix_command": "npx stylelint --fix '**/*.css'",
        "type": "lint",
    },
    "phpcs": {
        "config_files": ["phpcs.xml", "phpcs.xml.dist", ".phpcs.xml"],
        "package_key": None,
        "default_command": "vendor/bin/phpcs",
        "fix_command": "vendor/bin/phpcbf",
        "type": "lint",
    },
    "php-cs-fixer": {
        "config_files": [".php-cs-fixer.php", ".php-cs-fixer.dist.php", ".php_cs", ".php_cs.dist"],
        "package_key": None,
        "default_command": "vendor/bin/php-cs-fixer fix --dry-run --diff",
        "fix_command": "vendor/bin/php-cs-fixer fix",
        "type": "format",
    },
    "pytest": {
        "config_files": ["pytest.ini", "pyproject.toml", "setup.cfg"],
        "package_key": None,
        "default_command": "pytest",
        "type": "test",
    },
    "jest": {
        "config_files": ["jest.config.js", "jest.config.ts", "jest.config.json"],
        "package_key": "jest",
        "default_command": "npx jest",
        "type": "test",
    },
    "vitest": {
        "config_files": ["vitest.config.ts", "vitest.config.js", "vite.config.ts"],
        "package_key": "vitest",
        "default_command": "npx vitest run",
        "type": "test",
    },
    "phpunit": {
        "config_files": ["phpunit.xml", "phpunit.xml.dist"],
        "package_key": None,
        "default_command": "vendor/bin/phpunit",
        "type": "test",
    },
}


async def _run_command(
    command: str,
    cwd: str,
    timeout: int = 60,
    max_output_lines: int = 100,
) -> dict[str, Any]:
    """Run a shell command and capture output."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "timed_out": True,
            }

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        # Limit output lines
        stdout_lines = stdout_str.split("\n")
        stderr_lines = stderr_str.split("\n")

        if len(stdout_lines) > max_output_lines:
            stdout_str = "\n".join(stdout_lines[:max_output_lines]) + f"\n... ({len(stdout_lines) - max_output_lines} more lines)"
        if len(stderr_lines) > max_output_lines:
            stderr_str = "\n".join(stderr_lines[:max_output_lines]) + f"\n... ({len(stderr_lines) - max_output_lines} more lines)"

        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "timed_out": False,
        }
    except Exception as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "timed_out": False,
        }


def _detect_tools(root_path: str) -> dict[str, dict[str, Any]]:
    """Detect available quality tools in a project."""
    detected = {}
    root = Path(root_path)

    # Check for package.json
    package_json_path = root / "package.json"
    package_deps = set()
    if package_json_path.exists():
        try:
            with open(package_json_path) as f:
                pkg = json.load(f)
                deps = pkg.get("dependencies", {})
                dev_deps = pkg.get("devDependencies", {})
                package_deps = set(deps.keys()) | set(dev_deps.keys())
        except (json.JSONDecodeError, OSError):
            pass

    for tool_name, config in TOOL_PATTERNS.items():
        # Check for config files
        has_config = False
        for config_file in config.get("config_files", []):
            if (root / config_file).exists():
                has_config = True
                break

        # Check for package dependency
        has_package = False
        if config.get("package_key") and config["package_key"] in package_deps:
            has_package = True

        if has_config or has_package:
            detected[tool_name] = {
                "type": config["type"],
                "command": config["default_command"],
                "fix_command": config.get("fix_command"),
                "has_config": has_config,
                "has_package": has_package,
            }

    return detected


async def detect_quality_tools(context: dict[str, Any]) -> dict[str, Any]:
    """Detect available quality tools in a project."""
    root_path = context.get("root_path")
    if not root_path:
        return {"error": "root_path is required"}

    detected = _detect_tools(root_path)
    return {
        "tools": detected,
        "summary": {
            "lint": [t for t, c in detected.items() if c["type"] == "lint"],
            "format": [t for t, c in detected.items() if c["type"] == "format"],
            "typecheck": [t for t, c in detected.items() if c["type"] == "typecheck"],
            "test": [t for t, c in detected.items() if c["type"] == "test"],
        },
    }


async def run_lint(context: dict[str, Any]) -> dict[str, Any]:
    """Run configured linter."""
    root_path = context.get("root_path")
    if not root_path:
        return {"error": "root_path is required"}

    files = context.get("files", [])
    fix = context.get("fix", False)

    # Try to get lint command from project settings or detect
    quality_settings = context.get("quality_settings", {})
    if isinstance(quality_settings, str):
        try:
            quality_settings = json.loads(quality_settings)
        except json.JSONDecodeError:
            quality_settings = {}

    lint_command = quality_settings.get("lint_command")

    if not lint_command:
        # Auto-detect
        detected = _detect_tools(root_path)
        lint_tools = [t for t, c in detected.items() if c["type"] == "lint"]
        if lint_tools:
            tool = lint_tools[0]
            if fix and detected[tool].get("fix_command"):
                lint_command = detected[tool]["fix_command"]
            else:
                lint_command = detected[tool]["command"]
        else:
            return {"error": "No linter detected or configured"}

    # Append files if specified
    if files:
        lint_command = f"{lint_command} {' '.join(files)}"

    result = await _run_command(lint_command, root_path)
    return {
        "command": lint_command,
        "success": result["success"],
        "output": result["stdout"] or result["stderr"],
        "exit_code": result["exit_code"],
    }


async def run_format(context: dict[str, Any]) -> dict[str, Any]:
    """Run configured formatter."""
    root_path = context.get("root_path")
    if not root_path:
        return {"error": "root_path is required"}

    files = context.get("files", [])
    check_only = context.get("check_only", False)

    quality_settings = context.get("quality_settings", {})
    if isinstance(quality_settings, str):
        try:
            quality_settings = json.loads(quality_settings)
        except json.JSONDecodeError:
            quality_settings = {}

    format_command = quality_settings.get("format_command")

    if not format_command:
        detected = _detect_tools(root_path)
        format_tools = [t for t, c in detected.items() if c["type"] == "format"]
        if format_tools:
            tool = format_tools[0]
            if not check_only and detected[tool].get("fix_command"):
                format_command = detected[tool]["fix_command"]
            else:
                format_command = detected[tool]["command"]
        else:
            return {"error": "No formatter detected or configured"}

    if files:
        format_command = f"{format_command} {' '.join(files)}"

    result = await _run_command(format_command, root_path)
    return {
        "command": format_command,
        "success": result["success"],
        "output": result["stdout"] or result["stderr"],
        "exit_code": result["exit_code"],
    }


async def run_type_check(context: dict[str, Any]) -> dict[str, Any]:
    """Run configured type checker."""
    root_path = context.get("root_path")
    if not root_path:
        return {"error": "root_path is required"}

    quality_settings = context.get("quality_settings", {})
    if isinstance(quality_settings, str):
        try:
            quality_settings = json.loads(quality_settings)
        except json.JSONDecodeError:
            quality_settings = {}

    type_check_command = quality_settings.get("type_check_command")

    if not type_check_command:
        detected = _detect_tools(root_path)
        typecheck_tools = [t for t, c in detected.items() if c["type"] == "typecheck"]
        if typecheck_tools:
            tool = typecheck_tools[0]
            type_check_command = detected[tool]["command"]
        else:
            return {"error": "No type checker detected or configured"}

    result = await _run_command(type_check_command, root_path)
    return {
        "command": type_check_command,
        "success": result["success"],
        "output": result["stdout"] or result["stderr"],
        "exit_code": result["exit_code"],
    }


async def run_tests(context: dict[str, Any]) -> dict[str, Any]:
    """Run configured test command."""
    root_path = context.get("root_path")
    if not root_path:
        return {"error": "root_path is required"}

    test_filter = context.get("test_filter")

    quality_settings = context.get("quality_settings", {})
    if isinstance(quality_settings, str):
        try:
            quality_settings = json.loads(quality_settings)
        except json.JSONDecodeError:
            quality_settings = {}

    test_command = quality_settings.get("test_command")

    if not test_command:
        detected = _detect_tools(root_path)
        test_tools = [t for t, c in detected.items() if c["type"] == "test"]
        if test_tools:
            tool = test_tools[0]
            test_command = detected[tool]["command"]
        else:
            return {"error": "No test runner detected or configured"}

    if test_filter:
        test_command = f"{test_command} {test_filter}"

    result = await _run_command(test_command, root_path, timeout=300)  # Longer timeout for tests
    return {
        "command": test_command,
        "success": result["success"],
        "output": result["stdout"] or result["stderr"],
        "exit_code": result["exit_code"],
        "timed_out": result.get("timed_out", False),
    }


async def run_all_quality_checks(context: dict[str, Any]) -> dict[str, Any]:
    """Run all configured quality checks."""
    root_path = context.get("root_path")
    if not root_path:
        return {"error": "root_path is required"}

    quality_settings = context.get("quality_settings", {})
    files_changed = context.get("files_changed", [])
    fix_issues = context.get("fix_issues", False)

    if isinstance(quality_settings, str):
        try:
            quality_settings = json.loads(quality_settings)
        except json.JSONDecodeError:
            quality_settings = {}

    return await run_all_quality_checks_impl(
        root_path=root_path,
        quality_settings=quality_settings,
        files_changed=files_changed,
        fix_issues=fix_issues,
    )


async def run_all_quality_checks_impl(
    root_path: str,
    quality_settings: dict[str, Any],
    files_changed: list[str] | None = None,
    fix_issues: bool = False,
) -> dict[str, Any]:
    """Implementation for running all quality checks."""
    results = {
        "all_passed": True,
        "checks_run": [],
        "errors": [],
        "warnings": [],
    }

    if not quality_settings.get("enabled", True):
        results["skipped"] = "Quality checks disabled"
        return results

    # Detect available tools
    detected = _detect_tools(root_path)

    # Run lint checks
    lint_enabled = quality_settings.get("lint_on_save", True) or quality_settings.get("lint_on_commit", True)
    if lint_enabled:
        lint_command = quality_settings.get("lint_command")
        if not lint_command:
            lint_tools = [t for t, c in detected.items() if c["type"] == "lint"]
            if lint_tools:
                tool = lint_tools[0]
                if fix_issues and quality_settings.get("auto_fix_lint_errors", True) and detected[tool].get("fix_command"):
                    lint_command = detected[tool]["fix_command"]
                else:
                    lint_command = detected[tool]["command"]

        if lint_command:
            if files_changed:
                # Filter to relevant file types
                lint_files = [f for f in files_changed if any(f.endswith(ext) for ext in [".ts", ".tsx", ".js", ".jsx", ".py", ".php", ".css", ".scss"])]
                if lint_files:
                    lint_command = f"{lint_command} {' '.join(lint_files)}"
                else:
                    lint_command = None  # Skip if no relevant files

            if lint_command:
                result = await _run_command(lint_command, root_path)
                check_result = {
                    "type": "lint",
                    "command": lint_command,
                    "passed": result["success"],
                    "output": result["stdout"] or result["stderr"],
                }
                results["checks_run"].append(check_result)
                if not result["success"]:
                    results["all_passed"] = False
                    results["errors"].append({
                        "type": "lint",
                        "message": result["stderr"] or result["stdout"],
                    })

    # Run format checks
    format_enabled = quality_settings.get("format_on_save", False) or quality_settings.get("format_on_commit", True)
    if format_enabled:
        format_command = quality_settings.get("format_command")
        if not format_command:
            format_tools = [t for t, c in detected.items() if c["type"] == "format"]
            if format_tools:
                tool = format_tools[0]
                if fix_issues:
                    format_command = detected[tool].get("fix_command", detected[tool]["command"])
                else:
                    format_command = detected[tool]["command"]

        if format_command:
            result = await _run_command(format_command, root_path)
            check_result = {
                "type": "format",
                "command": format_command,
                "passed": result["success"],
                "output": result["stdout"] or result["stderr"],
            }
            results["checks_run"].append(check_result)
            if not result["success"]:
                results["all_passed"] = False
                results["errors"].append({
                    "type": "format",
                    "message": result["stderr"] or result["stdout"],
                })

    # Run type checks
    if quality_settings.get("type_check_enabled", True):
        type_command = quality_settings.get("type_check_command")
        if not type_command:
            typecheck_tools = [t for t, c in detected.items() if c["type"] == "typecheck"]
            if typecheck_tools:
                type_command = detected[typecheck_tools[0]]["command"]

        if type_command:
            result = await _run_command(type_command, root_path)
            check_result = {
                "type": "typecheck",
                "command": type_command,
                "passed": result["success"],
                "output": result["stdout"] or result["stderr"],
            }
            results["checks_run"].append(check_result)
            if not result["success"]:
                results["all_passed"] = False
                results["errors"].append({
                    "type": "typecheck",
                    "message": result["stderr"] or result["stdout"],
                })

    # Run tests (only on commit or explicit request)
    if quality_settings.get("run_tests_on_commit", False):
        test_command = quality_settings.get("test_command")
        if not test_command:
            test_tools = [t for t, c in detected.items() if c["type"] == "test"]
            if test_tools:
                test_command = detected[test_tools[0]]["command"]

        if test_command:
            result = await _run_command(test_command, root_path, timeout=300)
            check_result = {
                "type": "test",
                "command": test_command,
                "passed": result["success"],
                "output": result["stdout"] or result["stderr"],
                "timed_out": result.get("timed_out", False),
            }
            results["checks_run"].append(check_result)
            if not result["success"]:
                results["all_passed"] = False
                results["errors"].append({
                    "type": "test",
                    "message": result["stderr"] or result["stdout"],
                })

    # Run custom checks
    custom_checks = quality_settings.get("custom_checks", {})
    for check_name, check_command in custom_checks.items():
        result = await _run_command(check_command, root_path)
        check_result = {
            "type": f"custom:{check_name}",
            "command": check_command,
            "passed": result["success"],
            "output": result["stdout"] or result["stderr"],
        }
        results["checks_run"].append(check_result)
        if not result["success"]:
            results["all_passed"] = False
            results["errors"].append({
                "type": f"custom:{check_name}",
                "message": result["stderr"] or result["stdout"],
            })

    # Determine if blocking
    if quality_settings.get("block_on_errors", False) and not results["all_passed"]:
        results["blocked"] = True

    return results
