"""
Git operation tools for the Code Agent.
"""

import asyncio
import os
from pathlib import Path

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))


def _validate_repo_path(path: str) -> Path:
    """Validate repository path is within workspace."""
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
    """Run a git command and return (returncode, stdout, stderr)."""
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
    name="git_status",
    description="Get the status of the git repository",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
        },
    },
)
async def git_status(path: str = ".") -> ToolResult:
    """Get git status."""
    try:
        repo_path = _validate_repo_path(path)
        code, stdout, stderr = await _run_git_command(
            ["status", "--porcelain", "-b"],
            cwd=repo_path,
        )

        if code != 0:
            return ToolResult.fail(f"Git error: {stderr}")

        # Parse status
        lines = stdout.splitlines()
        branch_line = lines[0] if lines else ""
        changes = lines[1:] if len(lines) > 1 else []

        # Extract branch info
        branch = "unknown"
        if branch_line.startswith("## "):
            branch_info = branch_line[3:]
            branch = branch_info.split("...")[0]

        # Categorize changes
        staged = []
        modified = []
        untracked = []

        for line in changes:
            if len(line) < 2:
                continue
            index_status = line[0]
            worktree_status = line[1]
            filename = line[3:]

            if index_status != " " and index_status != "?":
                staged.append(filename)
            if worktree_status == "M":
                modified.append(filename)
            if index_status == "?":
                untracked.append(filename)

        return ToolResult.ok({
            "branch": branch,
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "clean": len(changes) == 0,
        })

    except Exception as e:
        logger.error("Git status failed", error=str(e))
        return ToolResult.fail(f"Git status failed: {e}")


@tool(
    name="git_diff",
    description="Show changes in the repository",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "file": {
                "type": "string",
                "description": "Specific file to diff",
            },
            "staged": {
                "type": "boolean",
                "description": "Show staged changes",
                "default": False,
            },
        },
    },
)
async def git_diff(
    path: str = ".",
    file: str | None = None,
    staged: bool = False,
) -> ToolResult:
    """Show git diff."""
    try:
        repo_path = _validate_repo_path(path)
        args = ["diff"]

        if staged:
            args.append("--staged")

        if file:
            args.append("--")
            args.append(file)

        code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

        if code != 0:
            return ToolResult.fail(f"Git error: {stderr}")

        return ToolResult.ok(stdout if stdout else "No changes")

    except Exception as e:
        logger.error("Git diff failed", error=str(e))
        return ToolResult.fail(f"Git diff failed: {e}")


@tool(
    name="git_log",
    description="Show commit history",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "count": {
                "type": "integer",
                "description": "Number of commits to show",
                "default": 10,
            },
            "oneline": {
                "type": "boolean",
                "description": "Show one line per commit",
                "default": True,
            },
        },
    },
)
async def git_log(
    path: str = ".",
    count: int = 10,
    oneline: bool = True,
) -> ToolResult:
    """Show git log."""
    try:
        repo_path = _validate_repo_path(path)
        args = ["log", f"-{count}"]

        if oneline:
            args.append("--oneline")
        else:
            args.extend(["--format=%H%n%an%n%ae%n%s%n%b%n---"])

        code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

        if code != 0:
            return ToolResult.fail(f"Git error: {stderr}")

        if oneline:
            commits = []
            for line in stdout.splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    commits.append({"hash": parts[0], "message": parts[1]})
            return ToolResult.ok(commits)

        return ToolResult.ok(stdout)

    except Exception as e:
        logger.error("Git log failed", error=str(e))
        return ToolResult.fail(f"Git log failed: {e}")


@tool(
    name="git_add",
    description="Stage files for commit",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to stage (or ['.'] for all)",
            },
        },
        "required": ["files"],
    },
    permission_level=1,
)
async def git_add(
    files: list[str],
    path: str = ".",
) -> ToolResult:
    """Stage files for commit."""
    try:
        repo_path = _validate_repo_path(path)
        args = ["add"] + files

        code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

        if code != 0:
            return ToolResult.fail(f"Git error: {stderr}")

        return ToolResult.ok(f"Staged {len(files)} file(s)")

    except Exception as e:
        logger.error("Git add failed", error=str(e))
        return ToolResult.fail(f"Git add failed: {e}")


@tool(
    name="git_commit",
    description="Create a commit",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "message": {
                "type": "string",
                "description": "Commit message",
            },
        },
        "required": ["message"],
    },
    permission_level=1,
)
async def git_commit(
    message: str,
    path: str = ".",
) -> ToolResult:
    """Create a commit."""
    try:
        repo_path = _validate_repo_path(path)
        args = ["commit", "-m", message]

        code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

        if code != 0:
            if "nothing to commit" in stderr or "nothing to commit" in stdout:
                return ToolResult.ok("Nothing to commit")
            return ToolResult.fail(f"Git error: {stderr}")

        # Extract commit hash
        for line in stdout.splitlines():
            if line.startswith("["):
                return ToolResult.ok(line)

        return ToolResult.ok(stdout)

    except Exception as e:
        logger.error("Git commit failed", error=str(e))
        return ToolResult.fail(f"Git commit failed: {e}")


@tool(
    name="git_branch",
    description="List or create branches",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "name": {
                "type": "string",
                "description": "Branch name to create (omit to list)",
            },
            "checkout": {
                "type": "boolean",
                "description": "Checkout the branch after creating",
                "default": False,
            },
        },
    },
    permission_level=1,
)
async def git_branch(
    path: str = ".",
    name: str | None = None,
    checkout: bool = False,
) -> ToolResult:
    """List or create branches."""
    try:
        repo_path = _validate_repo_path(path)

        if name:
            # Create branch
            if checkout:
                args = ["checkout", "-b", name]
            else:
                args = ["branch", name]

            code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

            if code != 0:
                return ToolResult.fail(f"Git error: {stderr}")

            return ToolResult.ok(f"Created branch: {name}")

        else:
            # List branches
            args = ["branch", "-a"]
            code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

            if code != 0:
                return ToolResult.fail(f"Git error: {stderr}")

            branches = []
            current = None
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith("* "):
                    current = line[2:]
                    branches.append(current)
                else:
                    branches.append(line)

            return ToolResult.ok({
                "current": current,
                "branches": branches,
            })

    except Exception as e:
        logger.error("Git branch failed", error=str(e))
        return ToolResult.fail(f"Git branch failed: {e}")


@tool(
    name="git_checkout",
    description="Switch branches or restore files",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "target": {
                "type": "string",
                "description": "Branch name or commit hash",
            },
        },
        "required": ["target"],
    },
    permission_level=1,
)
async def git_checkout(
    target: str,
    path: str = ".",
) -> ToolResult:
    """Checkout a branch or commit."""
    try:
        repo_path = _validate_repo_path(path)
        args = ["checkout", target]

        code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

        if code != 0:
            return ToolResult.fail(f"Git error: {stderr}")

        return ToolResult.ok(f"Checked out: {target}")

    except Exception as e:
        logger.error("Git checkout failed", error=str(e))
        return ToolResult.fail(f"Git checkout failed: {e}")


@tool(
    name="git_pull",
    description="Pull changes from remote",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "remote": {
                "type": "string",
                "description": "Remote name",
                "default": "origin",
            },
            "branch": {
                "type": "string",
                "description": "Branch to pull",
            },
        },
    },
    permission_level=1,
)
async def git_pull(
    path: str = ".",
    remote: str = "origin",
    branch: str | None = None,
) -> ToolResult:
    """Pull changes from remote."""
    try:
        repo_path = _validate_repo_path(path)
        args = ["pull", remote]

        if branch:
            args.append(branch)

        code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

        if code != 0:
            return ToolResult.fail(f"Git error: {stderr}")

        return ToolResult.ok(stdout if stdout else "Already up to date")

    except Exception as e:
        logger.error("Git pull failed", error=str(e))
        return ToolResult.fail(f"Git pull failed: {e}")


@tool(
    name="git_push",
    description="Push changes to remote",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to repository",
                "default": ".",
            },
            "remote": {
                "type": "string",
                "description": "Remote name",
                "default": "origin",
            },
            "branch": {
                "type": "string",
                "description": "Branch to push",
            },
            "set_upstream": {
                "type": "boolean",
                "description": "Set upstream tracking",
                "default": False,
            },
        },
    },
    permission_level=2,
)
async def git_push(
    path: str = ".",
    remote: str = "origin",
    branch: str | None = None,
    set_upstream: bool = False,
) -> ToolResult:
    """Push changes to remote."""
    try:
        repo_path = _validate_repo_path(path)
        args = ["push"]

        if set_upstream:
            args.append("-u")

        args.append(remote)

        if branch:
            args.append(branch)

        code, stdout, stderr = await _run_git_command(args, cwd=repo_path)

        if code != 0:
            return ToolResult.fail(f"Git error: {stderr}")

        return ToolResult.ok(stdout if stdout else stderr if stderr else "Pushed successfully")

    except Exception as e:
        logger.error("Git push failed", error=str(e))
        return ToolResult.fail(f"Git push failed: {e}")
