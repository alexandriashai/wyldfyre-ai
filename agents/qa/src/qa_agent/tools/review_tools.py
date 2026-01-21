"""
Code review tools for the QA Agent.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import aiofiles

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


async def _run_git_command(
    args: list[str],
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    """Run a git command."""
    cwd = cwd or WORKSPACE_DIR

    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    return (
        process.returncode or 0,
        stdout.decode().strip(),
        stderr.decode().strip(),
    )


@tool(
    name="review_changes",
    description="Review git changes for potential issues",
    parameters={
        "type": "object",
        "properties": {
            "base": {
                "type": "string",
                "description": "Base branch or commit to compare against",
                "default": "main",
            },
            "path": {
                "type": "string",
                "description": "Repository path",
                "default": ".",
            },
        },
    },
)
async def review_changes(
    base: str = "main",
    path: str = ".",
) -> ToolResult:
    """Review git changes for issues."""
    try:
        repo_path = _validate_workspace_path(path)

        # Get diff
        code, diff_output, stderr = await _run_git_command(
            ["diff", base, "--unified=3"],
            cwd=repo_path,
        )

        if code != 0:
            return ToolResult.fail(f"Git diff failed: {stderr}")

        if not diff_output:
            return ToolResult.ok(
                {"message": "No changes to review", "issues": []},
                files_changed=0,
            )

        # Analyze changes
        issues: list[dict[str, Any]] = []
        current_file = ""
        current_line = 0

        for line in diff_output.splitlines():
            # Track current file
            if line.startswith("+++ b/"):
                current_file = line[6:]
                current_line = 0
            elif line.startswith("@@"):
                # Parse line number
                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line = int(match.group(1))
            elif line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                current_line += 1

                # Check for common issues
                checks = [
                    (
                        r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]",
                        "Potential hardcoded credential",
                        "security",
                    ),
                    (
                        r"print\s*\(",
                        "Debug print statement",
                        "cleanup",
                    ),
                    (
                        r"console\.log\s*\(",
                        "Debug console.log statement",
                        "cleanup",
                    ),
                    (
                        r"TODO|FIXME|HACK|XXX",
                        "TODO/FIXME comment found",
                        "todo",
                    ),
                    (
                        r"^\s*import\s+\*",
                        "Wildcard import",
                        "style",
                    ),
                    (
                        r"except\s*:",
                        "Bare except clause",
                        "error-handling",
                    ),
                    (
                        r"eval\s*\(|exec\s*\(",
                        "Potentially dangerous eval/exec",
                        "security",
                    ),
                    (
                        r"sleep\s*\(\s*\d+\s*\)",
                        "Hardcoded sleep value",
                        "performance",
                    ),
                ]

                for pattern, message, category in checks:
                    if re.search(pattern, content, re.IGNORECASE):
                        issues.append({
                            "file": current_file,
                            "line": current_line,
                            "category": category,
                            "message": message,
                            "content": content.strip()[:100],
                        })

        # Get file stats
        code, stat_output, _ = await _run_git_command(
            ["diff", base, "--stat"],
            cwd=repo_path,
        )

        # Parse stats
        files_changed = 0
        insertions = 0
        deletions = 0

        for line in stat_output.splitlines():
            if "file" in line and "changed" in line:
                match = re.search(
                    r"(\d+) files? changed(?:, (\d+) insertions?)?(?:, (\d+) deletions?)?",
                    line,
                )
                if match:
                    files_changed = int(match.group(1))
                    insertions = int(match.group(2) or 0)
                    deletions = int(match.group(3) or 0)

        result = {
            "base": base,
            "files_changed": files_changed,
            "insertions": insertions,
            "deletions": deletions,
            "issues": issues,
            "issue_count": len(issues),
            "issues_by_category": {},
        }

        # Group issues by category
        for issue in issues:
            cat = issue["category"]
            if cat not in result["issues_by_category"]:
                result["issues_by_category"][cat] = 0
            result["issues_by_category"][cat] += 1

        return ToolResult.ok(result)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Review changes failed", error=str(e))
        return ToolResult.fail(f"Review changes failed: {e}")


@tool(
    name="analyze_code_quality",
    description="Analyze code quality metrics for a file or directory",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to analyze",
            },
            "pattern": {
                "type": "string",
                "description": "File pattern to match",
                "default": "**/*.py",
            },
        },
        "required": ["path"],
    },
)
async def analyze_code_quality(
    path: str,
    pattern: str = "**/*.py",
) -> ToolResult:
    """Analyze code quality metrics."""
    try:
        target_path = _validate_workspace_path(path)

        if not target_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        # Collect files
        if target_path.is_file():
            files = [target_path]
        else:
            files = list(target_path.glob(pattern))

        metrics: dict[str, Any] = {
            "files_analyzed": 0,
            "total_lines": 0,
            "code_lines": 0,
            "comment_lines": 0,
            "blank_lines": 0,
            "functions": 0,
            "classes": 0,
            "complexity_issues": [],
            "file_details": [],
        }

        for file_path in files[:100]:  # Limit to 100 files
            if not file_path.is_file():
                continue

            try:
                async with aiofiles.open(file_path, "r", errors="ignore") as f:
                    content = await f.read()

                lines = content.splitlines()
                file_metrics = {
                    "path": str(file_path.relative_to(WORKSPACE_DIR)),
                    "lines": len(lines),
                    "code_lines": 0,
                    "comment_lines": 0,
                    "blank_lines": 0,
                    "functions": 0,
                    "classes": 0,
                    "max_line_length": 0,
                    "long_functions": [],
                }

                in_multiline_string = False
                function_lines = 0
                current_function = ""

                for i, line in enumerate(lines, 1):
                    stripped = line.strip()

                    # Track line length
                    if len(line) > file_metrics["max_line_length"]:
                        file_metrics["max_line_length"] = len(line)

                    # Check for long lines
                    if len(line) > 120:
                        metrics["complexity_issues"].append({
                            "file": file_metrics["path"],
                            "line": i,
                            "issue": f"Line too long ({len(line)} chars)",
                        })

                    # Classify line
                    if not stripped:
                        file_metrics["blank_lines"] += 1
                    elif stripped.startswith("#"):
                        file_metrics["comment_lines"] += 1
                    elif '"""' in stripped or "'''" in stripped:
                        in_multiline_string = not in_multiline_string
                        file_metrics["comment_lines"] += 1
                    elif in_multiline_string:
                        file_metrics["comment_lines"] += 1
                    else:
                        file_metrics["code_lines"] += 1

                    # Count definitions
                    if re.match(r"^\s*def\s+(\w+)", line):
                        file_metrics["functions"] += 1
                        match = re.match(r"^\s*def\s+(\w+)", line)
                        if current_function and function_lines > 50:
                            file_metrics["long_functions"].append({
                                "name": current_function,
                                "lines": function_lines,
                            })
                        current_function = match.group(1) if match else ""
                        function_lines = 0
                    elif re.match(r"^\s*class\s+\w+", line):
                        file_metrics["classes"] += 1
                    elif current_function:
                        function_lines += 1

                # Check last function
                if current_function and function_lines > 50:
                    file_metrics["long_functions"].append({
                        "name": current_function,
                        "lines": function_lines,
                    })

                # Update totals
                metrics["files_analyzed"] += 1
                metrics["total_lines"] += file_metrics["lines"]
                metrics["code_lines"] += file_metrics["code_lines"]
                metrics["comment_lines"] += file_metrics["comment_lines"]
                metrics["blank_lines"] += file_metrics["blank_lines"]
                metrics["functions"] += file_metrics["functions"]
                metrics["classes"] += file_metrics["classes"]

                # Add long functions to complexity issues
                for func in file_metrics["long_functions"]:
                    metrics["complexity_issues"].append({
                        "file": file_metrics["path"],
                        "issue": f"Long function: {func['name']} ({func['lines']} lines)",
                    })

                metrics["file_details"].append(file_metrics)

            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")

        # Calculate ratios
        if metrics["total_lines"] > 0:
            metrics["comment_ratio"] = round(
                metrics["comment_lines"] / metrics["total_lines"] * 100, 1
            )
        else:
            metrics["comment_ratio"] = 0

        # Limit complexity issues in output
        metrics["complexity_issues"] = metrics["complexity_issues"][:20]
        metrics["file_details"] = metrics["file_details"][:20]

        return ToolResult.ok(metrics)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Analyze code quality failed", path=path, error=str(e))
        return ToolResult.fail(f"Analyze code quality failed: {e}")


@tool(
    name="check_dependencies",
    description="Check for dependency issues in requirements or pyproject.toml",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to requirements.txt or pyproject.toml",
            },
        },
        "required": ["path"],
    },
)
async def check_dependencies(path: str) -> ToolResult:
    """Check dependency configuration."""
    try:
        file_path = _validate_workspace_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"File not found: {path}")

        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()

        issues: list[dict[str, str]] = []
        dependencies: list[dict[str, Any]] = []

        if path.endswith(".toml"):
            # Parse pyproject.toml dependencies
            in_deps = False
            for line in content.splitlines():
                if "dependencies" in line and "=" in line:
                    in_deps = True
                elif in_deps:
                    if line.strip().startswith("]"):
                        in_deps = False
                    elif line.strip().startswith('"'):
                        dep = line.strip().strip('",')
                        # Parse dependency
                        match = re.match(r"([a-zA-Z0-9_-]+)([<>=!]+.*)?", dep)
                        if match:
                            name = match.group(1)
                            version = match.group(2) or "any"
                            dependencies.append({
                                "name": name,
                                "version_spec": version,
                            })

                            # Check for issues
                            if version == "any":
                                issues.append({
                                    "dependency": name,
                                    "issue": "No version constraint specified",
                                    "severity": "warning",
                                })
                            elif "==" in version and not re.search(r"\d+\.\d+\.\d+", version):
                                issues.append({
                                    "dependency": name,
                                    "issue": "Incomplete version pinning",
                                    "severity": "info",
                                })

        else:
            # Parse requirements.txt
            for line_num, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse requirement
                match = re.match(r"([a-zA-Z0-9_-]+)([<>=!]+.*)?", line)
                if match:
                    name = match.group(1)
                    version = match.group(2) or "any"
                    dependencies.append({
                        "name": name,
                        "version_spec": version,
                        "line": line_num,
                    })

                    # Check for issues
                    if version == "any":
                        issues.append({
                            "dependency": name,
                            "line": line_num,
                            "issue": "No version constraint",
                            "severity": "warning",
                        })

        result = {
            "file": path,
            "dependencies": dependencies,
            "dependency_count": len(dependencies),
            "issues": issues,
            "issue_count": len(issues),
        }

        return ToolResult.ok(result)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Check dependencies failed", path=path, error=str(e))
        return ToolResult.fail(f"Check dependencies failed: {e}")
