"""
Exact-match edit tool for surgical file modifications.

Provides Claude Code-style edit_file tool that finds an exact string match
in a file and replaces it, failing if the match is not unique.
"""

import aiofiles

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

from .file_tools import _validate_path

logger = get_logger(__name__)


@tool(
    name="edit_file",
    description="""Perform an exact string replacement in a file.
    Finds old_string in the file and replaces it with new_string.
    Fails if old_string is not found or if it matches multiple locations (ambiguous).
    Use this for surgical edits instead of rewriting entire files.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file (relative to workspace)",
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to find and replace (must be unique in file)",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement text",
            },
        },
        "required": ["path", "old_string", "new_string"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.FILE,
    side_effects=True,
)
async def edit_file(
    path: str,
    old_string: str,
    new_string: str,
) -> ToolResult:
    """Perform exact string replacement in a file."""
    try:
        file_path = _validate_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"File not found: {path}")

        if not file_path.is_file():
            return ToolResult.fail(f"Not a file: {path}")

        # Read current content
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()

        # Count occurrences
        count = content.count(old_string)

        if count == 0:
            # Show first 20 lines as context for debugging
            preview_lines = content.splitlines()[:20]
            preview = "\n".join(preview_lines)
            return ToolResult.fail(
                f"old_string not found in {path}.\n"
                f"File preview (first 20 lines):\n{preview}"
            )

        if count > 1:
            # Find line positions of each match
            lines = content.splitlines()
            positions = []
            search_pos = 0
            for _ in range(count):
                idx = content.index(old_string, search_pos)
                # Calculate line number from character position
                line_num = content[:idx].count("\n") + 1
                positions.append(line_num)
                search_pos = idx + 1

            return ToolResult.fail(
                f"old_string matches {count} locations in {path} (ambiguous). "
                f"Matches at lines: {positions}. "
                f"Provide more surrounding context to make the match unique."
            )

        # Exactly one match — perform replacement
        match_idx = content.index(old_string)
        match_line = content[:match_idx].count("\n") + 1

        new_content = content.replace(old_string, new_string, 1)

        # Write back
        async with aiofiles.open(file_path, "w") as f:
            await f.write(new_content)

        # Calculate diff summary
        old_lines = old_string.count("\n") + 1
        new_lines = new_string.count("\n") + 1

        return ToolResult.ok(
            f"Successfully edited {path} at line {match_line} "
            f"({old_lines} lines removed, {new_lines} lines added)",
            path=str(file_path),
            line=match_line,
            old_lines=old_lines,
            new_lines=new_lines,
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Edit file failed", path=path, error=str(e))
        return ToolResult.fail(f"Failed to edit file: {e}")
