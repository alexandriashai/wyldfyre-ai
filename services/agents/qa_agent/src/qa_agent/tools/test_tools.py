"""
Test execution tools for the QA Agent.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Workspace configuration
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))


def _validate_workspace_path(path: str) -> Path:
    """Validate and resolve a path within workspace."""
    workspace_resolved = WORKSPACE_DIR.resolve()
    resolved = (WORKSPACE_DIR / path).resolve()

    try:
        resolved.relative_to(workspace_resolved)
    except ValueError:
        raise ValueError(f"Path escapes workspace: {path}")

    return resolved


async def _run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: float = 300.0,
) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    cwd = cwd or WORKSPACE_DIR

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
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
        return (-1, "", "Command timed out")


def _parse_pytest_output(output: str) -> dict[str, Any]:
    """Parse pytest output for structured results."""
    results: dict[str, Any] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "warnings": 0,
        "failures": [],
    }

    # Parse summary line
    summary_match = re.search(
        r"(\d+) passed|(\d+) failed|(\d+) skipped|(\d+) error|(\d+) warning",
        output,
    )
    if summary_match:
        for match in re.finditer(r"(\d+) (passed|failed|skipped|error|warning)", output):
            count = int(match.group(1))
            status = match.group(2)
            if status == "error":
                results["errors"] = count
            elif status == "warning":
                results["warnings"] = count
            else:
                results[status] = count

    # Extract failure details
    failure_sections = re.split(r"={10,} FAILURES ={10,}", output)
    if len(failure_sections) > 1:
        failures_text = failure_sections[1].split("=" * 20)[0]
        # Parse individual failures
        failure_blocks = re.split(r"_{10,} ", failures_text)
        for block in failure_blocks[1:]:
            lines = block.strip().splitlines()
            if lines:
                test_name = lines[0].split()[0] if lines[0] else "unknown"
                results["failures"].append({
                    "test": test_name,
                    "details": "\n".join(lines[:20]),
                })

    return results


@tool(
    name="run_tests",
    description="Run tests using pytest",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to test file or directory",
                "default": ".",
            },
            "pattern": {
                "type": "string",
                "description": "Test name pattern to match (-k flag)",
            },
            "markers": {
                "type": "string",
                "description": "Marker expression (-m flag)",
            },
            "verbose": {
                "type": "boolean",
                "description": "Verbose output",
                "default": False,
            },
            "failfast": {
                "type": "boolean",
                "description": "Stop on first failure",
                "default": False,
            },
        },
    },
    permission_level=1,
)
async def run_tests(
    path: str = ".",
    pattern: str | None = None,
    markers: str | None = None,
    verbose: bool = False,
    failfast: bool = False,
) -> ToolResult:
    """Run pytest tests."""
    try:
        test_path = _validate_workspace_path(path)

        cmd = ["python", "-m", "pytest", str(test_path)]

        if pattern:
            cmd.extend(["-k", pattern])

        if markers:
            cmd.extend(["-m", markers])

        if verbose:
            cmd.append("-v")

        if failfast:
            cmd.append("-x")

        # Add color output
        cmd.append("--color=no")

        code, stdout, stderr = await _run_command(cmd, cwd=WORKSPACE_DIR)

        output = stdout if stdout else stderr
        parsed = _parse_pytest_output(output)

        result = {
            "exit_code": code,
            "passed": parsed["passed"],
            "failed": parsed["failed"],
            "skipped": parsed["skipped"],
            "errors": parsed["errors"],
            "success": code == 0,
        }

        if parsed["failures"]:
            result["failures"] = parsed["failures"]

        # Include truncated output
        result["output"] = output[:5000] if len(output) > 5000 else output

        return ToolResult.ok(result)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Run tests failed", path=path, error=str(e))
        return ToolResult.fail(f"Run tests failed: {e}")


@tool(
    name="list_tests",
    description="List available tests without running them",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to test file or directory",
                "default": ".",
            },
            "pattern": {
                "type": "string",
                "description": "Test name pattern to filter",
            },
        },
    },
)
async def list_tests(
    path: str = ".",
    pattern: str | None = None,
) -> ToolResult:
    """List available tests."""
    try:
        test_path = _validate_workspace_path(path)

        cmd = ["python", "-m", "pytest", str(test_path), "--collect-only", "-q"]

        if pattern:
            cmd.extend(["-k", pattern])

        code, stdout, stderr = await _run_command(cmd, cwd=WORKSPACE_DIR)

        if code != 0 and "no tests ran" not in stderr.lower():
            return ToolResult.fail(f"Failed to list tests: {stderr}")

        # Parse test list
        tests = []
        for line in stdout.splitlines():
            line = line.strip()
            if line and "::" in line and not line.startswith(("=", "-", "<")):
                tests.append(line)

        return ToolResult.ok(
            tests,
            count=len(tests),
            path=path,
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("List tests failed", path=path, error=str(e))
        return ToolResult.fail(f"List tests failed: {e}")


@tool(
    name="run_coverage",
    description="Run tests with coverage reporting",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to test file or directory",
                "default": ".",
            },
            "source": {
                "type": "string",
                "description": "Source directory to measure coverage for",
            },
            "min_coverage": {
                "type": "number",
                "description": "Minimum coverage percentage required",
                "default": 0,
            },
        },
    },
    permission_level=1,
)
async def run_coverage(
    path: str = ".",
    source: str | None = None,
    min_coverage: float = 0,
) -> ToolResult:
    """Run tests with coverage."""
    try:
        test_path = _validate_workspace_path(path)

        cmd = [
            "python",
            "-m",
            "pytest",
            str(test_path),
            "--cov-report=term-missing",
            "--color=no",
        ]

        if source:
            source_path = _validate_workspace_path(source)
            cmd.append(f"--cov={source_path}")
        else:
            cmd.append("--cov=.")

        if min_coverage > 0:
            cmd.append(f"--cov-fail-under={min_coverage}")

        code, stdout, stderr = await _run_command(cmd, cwd=WORKSPACE_DIR, timeout=600)

        output = stdout if stdout else stderr

        # Parse coverage results
        coverage_data: dict[str, Any] = {
            "files": [],
            "total": 0,
        }

        # Look for coverage table
        in_coverage = False
        for line in output.splitlines():
            if "TOTAL" in line:
                parts = line.split()
                for part in parts:
                    if part.endswith("%"):
                        try:
                            coverage_data["total"] = float(part.rstrip("%"))
                        except ValueError:
                            pass
                break
            elif "Name" in line and "Stmts" in line:
                in_coverage = True
            elif in_coverage and line.strip() and not line.startswith("-"):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        coverage_data["files"].append({
                            "name": parts[0],
                            "statements": int(parts[1]),
                            "missing": int(parts[2]),
                            "coverage": float(parts[3].rstrip("%")),
                        })
                    except (ValueError, IndexError):
                        pass

        result = {
            "exit_code": code,
            "success": code == 0,
            "total_coverage": coverage_data["total"],
            "files": coverage_data["files"][:20],  # Limit files
            "meets_threshold": coverage_data["total"] >= min_coverage,
            "output": output[:3000],
        }

        return ToolResult.ok(result)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Run coverage failed", path=path, error=str(e))
        return ToolResult.fail(f"Run coverage failed: {e}")


@tool(
    name="run_lint",
    description="Run linting tools (ruff, mypy)",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to lint",
                "default": ".",
            },
            "tool": {
                "type": "string",
                "enum": ["ruff", "mypy", "all"],
                "description": "Linting tool to run",
                "default": "all",
            },
            "fix": {
                "type": "boolean",
                "description": "Auto-fix issues (ruff only)",
                "default": False,
            },
        },
    },
    permission_level=1,
)
async def run_lint(
    path: str = ".",
    tool: str = "all",
    fix: bool = False,
) -> ToolResult:
    """Run linting tools."""
    try:
        lint_path = _validate_workspace_path(path)

        results: dict[str, Any] = {}

        # Run ruff
        if tool in ("ruff", "all"):
            ruff_cmd = ["python", "-m", "ruff", "check", str(lint_path)]
            if fix:
                ruff_cmd.append("--fix")

            code, stdout, stderr = await _run_command(ruff_cmd, cwd=WORKSPACE_DIR)
            output = stdout if stdout else stderr

            # Parse ruff output
            issues = []
            for line in output.splitlines():
                if re.match(r"^[^:]+:\d+:\d+:", line):
                    issues.append(line)

            results["ruff"] = {
                "exit_code": code,
                "success": code == 0,
                "issues": issues[:50],
                "issue_count": len(issues),
            }

        # Run mypy
        if tool in ("mypy", "all"):
            mypy_cmd = ["python", "-m", "mypy", str(lint_path), "--no-color-output"]

            code, stdout, stderr = await _run_command(
                mypy_cmd, cwd=WORKSPACE_DIR, timeout=300
            )
            output = stdout if stdout else stderr

            # Parse mypy output
            errors = []
            for line in output.splitlines():
                if ": error:" in line:
                    errors.append(line)

            # Look for summary
            summary_match = re.search(r"Found (\d+) error", output)
            error_count = int(summary_match.group(1)) if summary_match else len(errors)

            results["mypy"] = {
                "exit_code": code,
                "success": code == 0,
                "errors": errors[:50],
                "error_count": error_count,
            }

        # Overall success
        overall_success = all(r.get("success", False) for r in results.values())

        return ToolResult.ok(
            results,
            path=path,
            success=overall_success,
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Run lint failed", path=path, error=str(e))
        return ToolResult.fail(f"Run lint failed: {e}")
