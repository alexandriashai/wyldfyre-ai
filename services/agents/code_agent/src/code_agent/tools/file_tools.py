"""
File operation tools for the Code Agent.
"""

import os
from pathlib import Path

import aiofiles

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Safe base directory for file operations
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))


def _validate_path(path: str) -> Path:
    """Validate and resolve a file path within workspace."""
    resolved = (WORKSPACE_DIR / path).resolve()

    # Ensure path is within workspace
    if not str(resolved).startswith(str(WORKSPACE_DIR.resolve())):
        raise ValueError(f"Path escapes workspace: {path}")

    return resolved


@tool(
    name="read_file",
    description="Read the contents of a file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file (relative to workspace)",
            },
            "start_line": {
                "type": "integer",
                "description": "Starting line number (1-indexed, optional)",
            },
            "end_line": {
                "type": "integer",
                "description": "Ending line number (optional)",
            },
        },
        "required": ["path"],
    },
)
async def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> ToolResult:
    """Read file contents."""
    try:
        file_path = _validate_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"File not found: {path}")

        if not file_path.is_file():
            return ToolResult.fail(f"Not a file: {path}")

        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()

        lines = content.splitlines(keepends=True)

        # Apply line filtering
        if start_line is not None or end_line is not None:
            start_idx = (start_line - 1) if start_line else 0
            end_idx = end_line if end_line else len(lines)
            lines = lines[start_idx:end_idx]
            content = "".join(lines)

        return ToolResult.ok(
            content,
            path=str(file_path),
            lines=len(lines),
            size=len(content),
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Failed to read file", path=path, error=str(e))
        return ToolResult.fail(f"Failed to read file: {e}")


@tool(
    name="write_file",
    description="Write content to a file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file (relative to workspace)",
            },
            "content": {
                "type": "string",
                "description": "Content to write",
            },
            "create_dirs": {
                "type": "boolean",
                "description": "Create parent directories if needed",
                "default": True,
            },
        },
        "required": ["path", "content"],
    },
    permission_level=1,
)
async def write_file(
    path: str,
    content: str,
    create_dirs: bool = True,
) -> ToolResult:
    """Write content to a file."""
    try:
        file_path = _validate_path(path)

        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "w") as f:
            await f.write(content)

        return ToolResult.ok(
            f"Successfully wrote {len(content)} bytes to {path}",
            path=str(file_path),
            size=len(content),
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Failed to write file", path=path, error=str(e))
        return ToolResult.fail(f"Failed to write file: {e}")


@tool(
    name="list_directory",
    description="List contents of a directory",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory (relative to workspace)",
                "default": ".",
            },
            "recursive": {
                "type": "boolean",
                "description": "List recursively",
                "default": False,
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern to filter files",
            },
        },
    },
)
async def list_directory(
    path: str = ".",
    recursive: bool = False,
    pattern: str | None = None,
) -> ToolResult:
    """List directory contents."""
    try:
        dir_path = _validate_path(path)

        if not dir_path.exists():
            return ToolResult.fail(f"Directory not found: {path}")

        if not dir_path.is_dir():
            return ToolResult.fail(f"Not a directory: {path}")

        if recursive:
            if pattern:
                items = list(dir_path.rglob(pattern))
            else:
                items = list(dir_path.rglob("*"))
        else:
            if pattern:
                items = list(dir_path.glob(pattern))
            else:
                items = list(dir_path.iterdir())

        # Format output
        entries = []
        for item in sorted(items):
            rel_path = item.relative_to(dir_path)
            entry_type = "dir" if item.is_dir() else "file"
            size = item.stat().st_size if item.is_file() else 0
            entries.append({
                "name": str(rel_path),
                "type": entry_type,
                "size": size,
            })

        return ToolResult.ok(
            entries,
            path=str(dir_path),
            count=len(entries),
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Failed to list directory", path=path, error=str(e))
        return ToolResult.fail(f"Failed to list directory: {e}")


@tool(
    name="search_files",
    description="Search for text in files",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in",
                "default": ".",
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern for files to search",
                "default": "**/*",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results",
                "default": 50,
            },
        },
        "required": ["pattern"],
    },
)
async def search_files(
    pattern: str,
    path: str = ".",
    file_pattern: str = "**/*",
    max_results: int = 50,
) -> ToolResult:
    """Search for text in files."""
    import re

    try:
        dir_path = _validate_path(path)

        if not dir_path.exists():
            return ToolResult.fail(f"Directory not found: {path}")

        regex = re.compile(pattern, re.IGNORECASE)
        results = []

        for file_path in dir_path.rglob(file_pattern):
            if not file_path.is_file():
                continue

            if len(results) >= max_results:
                break

            try:
                async with aiofiles.open(file_path, "r", errors="ignore") as f:
                    content = await f.read()

                for i, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(dir_path)
                        results.append({
                            "file": str(rel_path),
                            "line": i,
                            "content": line.strip()[:200],
                        })

                        if len(results) >= max_results:
                            break

            except (OSError, UnicodeDecodeError):
                continue

        return ToolResult.ok(
            results,
            pattern=pattern,
            count=len(results),
            truncated=len(results) >= max_results,
        )

    except re.error as e:
        return ToolResult.fail(f"Invalid regex pattern: {e}")
    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Search failed", pattern=pattern, error=str(e))
        return ToolResult.fail(f"Search failed: {e}")


@tool(
    name="delete_file",
    description="Delete a file or empty directory",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to delete",
            },
        },
        "required": ["path"],
    },
    permission_level=2,
    requires_confirmation=True,
)
async def delete_file(path: str) -> ToolResult:
    """Delete a file or empty directory."""
    try:
        file_path = _validate_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        if file_path.is_dir():
            file_path.rmdir()  # Only works on empty directories
        else:
            file_path.unlink()

        return ToolResult.ok(f"Successfully deleted: {path}")

    except OSError as e:
        return ToolResult.fail(f"Failed to delete: {e}")
    except ValueError as e:
        return ToolResult.fail(str(e))
