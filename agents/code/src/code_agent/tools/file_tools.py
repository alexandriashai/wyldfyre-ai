"""
File operation tools for the Code Agent.

These tools provide file system operations including reading, writing,
listing, searching, and permission management.
"""

import os
import shutil
import stat
from pathlib import Path

import aiofiles

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Safe base directory for file operations
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))


def _validate_path(path: str) -> Path:
    """Validate and resolve a file path within workspace."""
    # Resolve workspace to absolute path
    workspace_resolved = WORKSPACE_DIR.resolve()

    # Resolve the target path
    resolved = (WORKSPACE_DIR / path).resolve()

    # Use is_relative_to for proper containment check (Python 3.9+)
    # This prevents path traversal attacks like "../workspace-evil/file"
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError:
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
    permission_level=0,
    capability_category=CapabilityCategory.FILE,
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
    capability_category=CapabilityCategory.FILE,
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
    permission_level=0,
    capability_category=CapabilityCategory.FILE,
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
    permission_level=0,
    capability_category=CapabilityCategory.FILE,
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
    capability_category=CapabilityCategory.FILE,
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


@tool(
    name="directory_create",
    description="Create a directory (and parent directories if needed)",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to create (relative to workspace)",
            },
            "parents": {
                "type": "boolean",
                "description": "Create parent directories if they don't exist",
                "default": True,
            },
        },
        "required": ["path"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.FILE,
)
async def directory_create(
    path: str,
    parents: bool = True,
) -> ToolResult:
    """Create a directory."""
    try:
        dir_path = _validate_path(path)

        if dir_path.exists():
            if dir_path.is_dir():
                return ToolResult.ok(
                    f"Directory already exists: {path}",
                    path=str(dir_path),
                    existed=True,
                )
            else:
                return ToolResult.fail(f"Path exists but is not a directory: {path}")

        dir_path.mkdir(parents=parents, exist_ok=True)

        return ToolResult.ok(
            f"Successfully created directory: {path}",
            path=str(dir_path),
            existed=False,
        )

    except OSError as e:
        return ToolResult.fail(f"Failed to create directory: {e}")
    except ValueError as e:
        return ToolResult.fail(str(e))


@tool(
    name="directory_delete",
    description="Delete a directory and all its contents. USE WITH CAUTION.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to delete (relative to workspace)",
            },
            "force": {
                "type": "boolean",
                "description": "Delete even if directory is not empty",
                "default": False,
            },
        },
        "required": ["path"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.FILE,
    requires_confirmation=True,
)
async def directory_delete(
    path: str,
    force: bool = False,
) -> ToolResult:
    """Delete a directory and optionally all its contents."""
    try:
        dir_path = _validate_path(path)

        if not dir_path.exists():
            return ToolResult.fail(f"Directory not found: {path}")

        if not dir_path.is_dir():
            return ToolResult.fail(f"Path is not a directory: {path}")

        # Check if empty
        contents = list(dir_path.iterdir())

        if contents and not force:
            return ToolResult.fail(
                f"Directory not empty ({len(contents)} items). Use force=true to delete anyway."
            )

        if force:
            shutil.rmtree(dir_path)
        else:
            dir_path.rmdir()

        return ToolResult.ok(
            f"Successfully deleted directory: {path}",
            path=str(dir_path),
            force=force,
            items_deleted=len(contents) if force else 0,
        )

    except OSError as e:
        return ToolResult.fail(f"Failed to delete directory: {e}")
    except ValueError as e:
        return ToolResult.fail(str(e))


@tool(
    name="file_chmod",
    description="Change file or directory permissions (Unix-style mode)",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file or directory (relative to workspace)",
            },
            "mode": {
                "type": "string",
                "description": "Permission mode in octal (e.g., '755', '644') or symbolic (e.g., 'u+x')",
            },
            "recursive": {
                "type": "boolean",
                "description": "Apply recursively to directory contents",
                "default": False,
            },
        },
        "required": ["path", "mode"],
    },
    permission_level=3,
    capability_category=CapabilityCategory.FILE,
    requires_confirmation=True,
)
async def file_chmod(
    path: str,
    mode: str,
    recursive: bool = False,
) -> ToolResult:
    """Change file or directory permissions."""
    try:
        file_path = _validate_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        # Parse mode
        if mode.isdigit():
            # Octal mode like "755"
            mode_int = int(mode, 8)
        else:
            # Symbolic mode like "u+x" - simplified handling
            current_mode = file_path.stat().st_mode
            mode_int = current_mode

            # Parse symbolic notation (simplified)
            for part in mode.replace(",", " ").split():
                if "+" in part or "-" in part or "=" in part:
                    # Very basic symbolic mode parsing
                    if "u+x" in part:
                        mode_int |= stat.S_IXUSR
                    elif "u-x" in part:
                        mode_int &= ~stat.S_IXUSR
                    elif "g+x" in part:
                        mode_int |= stat.S_IXGRP
                    elif "g-x" in part:
                        mode_int &= ~stat.S_IXGRP
                    elif "o+x" in part:
                        mode_int |= stat.S_IXOTH
                    elif "o-x" in part:
                        mode_int &= ~stat.S_IXOTH
                    elif "+x" in part:
                        mode_int |= (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    elif "-x" in part:
                        mode_int &= ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    elif "u+r" in part:
                        mode_int |= stat.S_IRUSR
                    elif "u+w" in part:
                        mode_int |= stat.S_IWUSR
                    # Add more as needed

        changed_count = 0

        if recursive and file_path.is_dir():
            for item in file_path.rglob("*"):
                item.chmod(mode_int)
                changed_count += 1
            file_path.chmod(mode_int)
            changed_count += 1
        else:
            file_path.chmod(mode_int)
            changed_count = 1

        return ToolResult.ok(
            f"Successfully changed permissions on {path}",
            path=str(file_path),
            mode=oct(mode_int),
            items_changed=changed_count,
        )

    except PermissionError as e:
        return ToolResult.fail(f"Permission denied: {e}")
    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("File chmod failed", path=path, error=str(e))
        return ToolResult.fail(f"Failed to change permissions: {e}")


@tool(
    name="file_chown",
    description="Change file or directory ownership. Requires SUPERUSER permissions.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file or directory (relative to workspace)",
            },
            "user": {
                "type": "string",
                "description": "New owner username or UID",
            },
            "group": {
                "type": "string",
                "description": "New group name or GID",
            },
            "recursive": {
                "type": "boolean",
                "description": "Apply recursively to directory contents",
                "default": False,
            },
        },
        "required": ["path"],
    },
    permission_level=4,  # SUPERUSER only
    capability_category=CapabilityCategory.FILE,
    requires_confirmation=True,
    allows_elevation=False,  # Cannot be elevated to - must have SUPERUSER
)
async def file_chown(
    path: str,
    user: str | None = None,
    group: str | None = None,
    recursive: bool = False,
) -> ToolResult:
    """Change file or directory ownership."""
    import pwd
    import grp

    try:
        if not user and not group:
            return ToolResult.fail("Must specify user or group (or both)")

        file_path = _validate_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        # Resolve user ID
        uid = -1  # -1 means don't change
        if user:
            try:
                if user.isdigit():
                    uid = int(user)
                else:
                    uid = pwd.getpwnam(user).pw_uid
            except KeyError:
                return ToolResult.fail(f"User not found: {user}")

        # Resolve group ID
        gid = -1  # -1 means don't change
        if group:
            try:
                if group.isdigit():
                    gid = int(group)
                else:
                    gid = grp.getgrnam(group).gr_gid
            except KeyError:
                return ToolResult.fail(f"Group not found: {group}")

        changed_count = 0

        if recursive and file_path.is_dir():
            for item in file_path.rglob("*"):
                os.chown(item, uid, gid)
                changed_count += 1
            os.chown(file_path, uid, gid)
            changed_count += 1
        else:
            os.chown(file_path, uid, gid)
            changed_count = 1

        return ToolResult.ok(
            f"Successfully changed ownership on {path}",
            path=str(file_path),
            user=user,
            group=group,
            items_changed=changed_count,
        )

    except PermissionError as e:
        return ToolResult.fail(f"Permission denied (requires root): {e}")
    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("File chown failed", path=path, error=str(e))
        return ToolResult.fail(f"Failed to change ownership: {e}")
