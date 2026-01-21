"""
Type checking tools for the QA Agent.

These tools provide static type analysis capabilities:
- Mypy type checking
- Python AST analysis for type hints
- Type coverage reporting
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

DEFAULT_WORKSPACE = os.environ.get("WORKSPACE_DIR", "/root/AI-Infrastructure")


async def _run_command(
    command: str,
    timeout: int = 120,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
        return (
            process.returncode or 0,
            stdout.decode().strip(),
            stderr.decode().strip(),
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(f"Command timed out after {timeout}s")


@tool(
    name="run_mypy",
    description="""Run mypy type checker on Python files.
    Returns type errors and warnings.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or directory to check",
            },
            "strict": {
                "type": "boolean",
                "description": "Use strict mode",
                "default": False,
            },
            "ignore_missing_imports": {
                "type": "boolean",
                "description": "Ignore missing import errors",
                "default": True,
            },
            "config_file": {
                "type": "string",
                "description": "Path to mypy.ini or pyproject.toml",
            },
        },
        "required": ["path"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def run_mypy(
    path: str,
    strict: bool = False,
    ignore_missing_imports: bool = True,
    config_file: str | None = None,
) -> ToolResult:
    """Run mypy type checker."""
    try:
        # Build mypy command
        cmd_parts = ["mypy", "--show-error-codes", "--no-color-output"]

        if strict:
            cmd_parts.append("--strict")

        if ignore_missing_imports:
            cmd_parts.append("--ignore-missing-imports")

        if config_file:
            cmd_parts.extend(["--config-file", config_file])

        cmd_parts.append(path)
        cmd = " ".join(cmd_parts)

        code, stdout, stderr = await _run_command(cmd)

        # Parse output
        errors = []
        warnings = []
        notes = []

        for line in (stdout + "\n" + stderr).splitlines():
            if not line.strip() or line.startswith("Success:") or line.startswith("Found"):
                continue

            # Parse error format: file:line: severity: message [error-code]
            match = re.match(r"(.+?):(\d+)(?::\d+)?: (error|warning|note): (.+)", line)
            if match:
                file_path = match.group(1)
                line_num = int(match.group(2))
                severity = match.group(3)
                message = match.group(4)

                entry = {
                    "file": file_path,
                    "line": line_num,
                    "message": message,
                }

                if severity == "error":
                    errors.append(entry)
                elif severity == "warning":
                    warnings.append(entry)
                else:
                    notes.append(entry)

        # Extract summary
        summary_match = re.search(r"Found (\d+) errors? in (\d+) files?", stdout + stderr)
        error_count = int(summary_match.group(1)) if summary_match else len(errors)

        success = code == 0 and error_count == 0

        return ToolResult.ok({
            "message": f"Mypy check {'passed' if success else 'found issues'}: {error_count} errors, {len(warnings)} warnings",
            "path": path,
            "success": success,
            "errors": errors[:50],  # Limit output
            "warnings": warnings[:20],
            "notes": notes[:10],
            "summary": {
                "error_count": error_count,
                "warning_count": len(warnings),
                "note_count": len(notes),
            },
        })

    except FileNotFoundError:
        return ToolResult.fail("mypy is not installed. Install with: pip install mypy")
    except Exception as e:
        logger.error("Run mypy failed", path=path, error=str(e))
        return ToolResult.fail(f"Run mypy failed: {e}")


@tool(
    name="check_type_coverage",
    description="""Check type annotation coverage in Python files.
    Reports what percentage of functions have type hints.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or directory to analyze",
            },
        },
        "required": ["path"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def check_type_coverage(path: str) -> ToolResult:
    """Check type annotation coverage."""
    try:
        import ast

        target = Path(path)
        if not target.exists():
            return ToolResult.fail(f"Path not found: {path}")

        stats = {
            "total_functions": 0,
            "typed_functions": 0,
            "partially_typed_functions": 0,
            "untyped_functions": 0,
            "total_parameters": 0,
            "typed_parameters": 0,
            "functions_with_return_type": 0,
        }

        untyped_functions = []

        def analyze_file(file_path: Path) -> None:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Skip private and dunder methods
                        if node.name.startswith("__") and node.name.endswith("__"):
                            continue

                        stats["total_functions"] += 1

                        # Check return type
                        has_return_type = node.returns is not None
                        if has_return_type:
                            stats["functions_with_return_type"] += 1

                        # Check parameters (excluding self, cls)
                        params = node.args.args + node.args.posonlyargs + node.args.kwonlyargs
                        param_count = 0
                        typed_param_count = 0

                        for arg in params:
                            if arg.arg in ("self", "cls"):
                                continue
                            param_count += 1
                            stats["total_parameters"] += 1
                            if arg.annotation is not None:
                                typed_param_count += 1
                                stats["typed_parameters"] += 1

                        # Classify function
                        if has_return_type and (param_count == 0 or typed_param_count == param_count):
                            stats["typed_functions"] += 1
                        elif has_return_type or typed_param_count > 0:
                            stats["partially_typed_functions"] += 1
                        else:
                            stats["untyped_functions"] += 1
                            if len(untyped_functions) < 20:
                                untyped_functions.append({
                                    "file": str(file_path),
                                    "function": node.name,
                                    "line": node.lineno,
                                })

            except SyntaxError:
                pass
            except Exception as e:
                logger.warning("Failed to analyze file", file=str(file_path), error=str(e))

        # Analyze files
        if target.is_file():
            analyze_file(target)
        else:
            for py_file in target.rglob("*.py"):
                # Skip tests and venv
                if "test" in str(py_file) or "venv" in str(py_file) or ".venv" in str(py_file):
                    continue
                analyze_file(py_file)

        # Calculate coverage
        total = stats["total_functions"]
        if total > 0:
            function_coverage = round((stats["typed_functions"] / total) * 100, 1)
            partial_coverage = round(((stats["typed_functions"] + stats["partially_typed_functions"]) / total) * 100, 1)
        else:
            function_coverage = 100.0
            partial_coverage = 100.0

        param_total = stats["total_parameters"]
        if param_total > 0:
            param_coverage = round((stats["typed_parameters"] / param_total) * 100, 1)
        else:
            param_coverage = 100.0

        return_total = stats["total_functions"]
        if return_total > 0:
            return_coverage = round((stats["functions_with_return_type"] / return_total) * 100, 1)
        else:
            return_coverage = 100.0

        return ToolResult.ok({
            "message": f"Type coverage: {function_coverage}% fully typed functions",
            "path": path,
            "coverage": {
                "fully_typed_functions": function_coverage,
                "partially_typed_functions": partial_coverage,
                "parameter_coverage": param_coverage,
                "return_type_coverage": return_coverage,
            },
            "stats": stats,
            "untyped_functions": untyped_functions,
        })

    except Exception as e:
        logger.error("Check type coverage failed", path=path, error=str(e))
        return ToolResult.fail(f"Check type coverage failed: {e}")


@tool(
    name="run_ruff",
    description="""Run Ruff linter for Python code.
    Fast Python linter that can fix issues automatically.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or directory to check",
            },
            "fix": {
                "type": "boolean",
                "description": "Automatically fix issues where possible",
                "default": False,
            },
            "select": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Rule codes to enable (e.g., ['E', 'F', 'W'])",
            },
            "ignore": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Rule codes to ignore",
            },
        },
        "required": ["path"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def run_ruff(
    path: str,
    fix: bool = False,
    select: list[str] | None = None,
    ignore: list[str] | None = None,
) -> ToolResult:
    """Run Ruff linter."""
    try:
        cmd_parts = ["ruff", "check", "--output-format=json"]

        if fix:
            cmd_parts.append("--fix")

        if select:
            cmd_parts.extend(["--select", ",".join(select)])

        if ignore:
            cmd_parts.extend(["--ignore", ",".join(ignore)])

        cmd_parts.append(path)
        cmd = " ".join(cmd_parts)

        code, stdout, stderr = await _run_command(cmd)

        # Parse JSON output
        issues = []
        try:
            if stdout:
                issues = json.loads(stdout)
        except json.JSONDecodeError:
            # Fall back to parsing text output
            for line in stdout.splitlines():
                if ":" in line:
                    issues.append({"message": line})

        # Group by rule code
        by_rule = {}
        for issue in issues:
            rule = issue.get("code", "unknown")
            if rule not in by_rule:
                by_rule[rule] = 0
            by_rule[rule] += 1

        formatted_issues = []
        for issue in issues[:50]:  # Limit output
            formatted_issues.append({
                "file": issue.get("filename", ""),
                "line": issue.get("location", {}).get("row"),
                "column": issue.get("location", {}).get("column"),
                "code": issue.get("code"),
                "message": issue.get("message"),
                "fixable": issue.get("fix") is not None,
            })

        success = len(issues) == 0

        return ToolResult.ok({
            "message": f"Ruff {'passed' if success else f'found {len(issues)} issues'}",
            "path": path,
            "success": success,
            "issues": formatted_issues,
            "summary": {
                "total_issues": len(issues),
                "by_rule": by_rule,
            },
            "fixed": fix and not success,
        })

    except FileNotFoundError:
        return ToolResult.fail("ruff is not installed. Install with: pip install ruff")
    except Exception as e:
        logger.error("Run ruff failed", path=path, error=str(e))
        return ToolResult.fail(f"Run ruff failed: {e}")
