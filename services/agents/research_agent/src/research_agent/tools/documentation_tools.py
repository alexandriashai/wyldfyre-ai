"""
Documentation tools for the Research Agent.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Documentation directory
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))
DOCS_DIR = WORKSPACE_DIR / "docs"


def _validate_docs_path(path: str) -> Path:
    """Validate and resolve a path within docs directory."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    docs_resolved = DOCS_DIR.resolve()
    resolved = (DOCS_DIR / path).resolve()

    try:
        resolved.relative_to(docs_resolved)
    except ValueError:
        raise ValueError(f"Path escapes docs directory: {path}")

    return resolved


def _extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from markdown content."""
    frontmatter: dict[str, Any] = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()

            # Simple YAML parsing
            for line in fm_text.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()

    return frontmatter, body


def _extract_sections(content: str) -> list[dict[str, Any]]:
    """Extract sections from markdown content."""
    sections = []
    current_section: dict[str, Any] | None = None

    for line in content.splitlines():
        # Check for headers
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            if current_section:
                sections.append(current_section)
            current_section = {
                "level": len(header_match.group(1)),
                "title": header_match.group(2).strip(),
                "content": "",
            }
        elif current_section:
            current_section["content"] += line + "\n"

    if current_section:
        sections.append(current_section)

    return sections


@tool(
    name="search_documentation",
    description="Search through documentation files",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "path": {
                "type": "string",
                "description": "Subdirectory to search in",
                "default": ".",
            },
            "file_pattern": {
                "type": "string",
                "description": "File pattern to match (e.g., '*.md')",
                "default": "*.md",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return",
                "default": 20,
            },
        },
        "required": ["query"],
    },
)
async def search_documentation(
    query: str,
    path: str = ".",
    file_pattern: str = "*.md",
    max_results: int = 20,
) -> ToolResult:
    """Search documentation files."""
    try:
        search_path = _validate_docs_path(path)

        if not search_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        query_lower = query.lower()
        query_words = query_lower.split()
        results = []

        # Search through files
        for file_path in search_path.rglob(file_pattern):
            if not file_path.is_file():
                continue

            try:
                async with aiofiles.open(file_path, "r", errors="ignore") as f:
                    content = await f.read()

                content_lower = content.lower()

                # Check if query matches
                if not all(word in content_lower for word in query_words):
                    continue

                # Extract relevant context
                rel_path = file_path.relative_to(DOCS_DIR)
                frontmatter, body = _extract_frontmatter(content)

                # Find matching lines
                matches = []
                for i, line in enumerate(content.splitlines(), 1):
                    if any(word in line.lower() for word in query_words):
                        matches.append({
                            "line": i,
                            "text": line.strip()[:200],
                        })
                        if len(matches) >= 3:
                            break

                results.append({
                    "file": str(rel_path),
                    "title": frontmatter.get("title", file_path.stem),
                    "matches": matches,
                    "score": sum(
                        content_lower.count(word) for word in query_words
                    ),
                })

                if len(results) >= max_results:
                    break

            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")
                continue

        # Sort by relevance score
        results.sort(key=lambda x: x["score"], reverse=True)

        return ToolResult.ok(
            results,
            query=query,
            count=len(results),
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Search documentation failed", error=str(e))
        return ToolResult.fail(f"Search documentation failed: {e}")


@tool(
    name="read_documentation",
    description="Read a documentation file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the documentation file",
            },
            "section": {
                "type": "string",
                "description": "Specific section to extract (by heading)",
            },
        },
        "required": ["path"],
    },
)
async def read_documentation(
    path: str,
    section: str | None = None,
) -> ToolResult:
    """Read a documentation file."""
    try:
        file_path = _validate_docs_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"File not found: {path}")

        if not file_path.is_file():
            return ToolResult.fail(f"Not a file: {path}")

        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()

        frontmatter, body = _extract_frontmatter(content)
        sections = _extract_sections(body)

        result: dict[str, Any] = {
            "path": path,
            "frontmatter": frontmatter,
        }

        if section:
            # Find specific section
            section_lower = section.lower()
            for sec in sections:
                if section_lower in sec["title"].lower():
                    result["section"] = sec
                    result["content"] = sec["content"].strip()
                    return ToolResult.ok(result)

            return ToolResult.fail(f"Section not found: {section}")

        # Return full document
        result["content"] = body
        result["sections"] = [
            {"level": s["level"], "title": s["title"]} for s in sections
        ]
        result["word_count"] = len(body.split())

        return ToolResult.ok(result)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Read documentation failed", path=path, error=str(e))
        return ToolResult.fail(f"Read documentation failed: {e}")


@tool(
    name="create_documentation",
    description="Create a new documentation file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path for the new file",
            },
            "title": {
                "type": "string",
                "description": "Document title",
            },
            "content": {
                "type": "string",
                "description": "Document content (markdown)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for the document",
            },
        },
        "required": ["path", "title", "content"],
    },
    permission_level=1,
)
async def create_documentation(
    path: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
) -> ToolResult:
    """Create a new documentation file."""
    try:
        file_path = _validate_docs_path(path)

        if file_path.exists():
            return ToolResult.fail(f"File already exists: {path}")

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Build document with frontmatter
        now = datetime.now().isoformat()
        frontmatter_lines = [
            "---",
            f"title: {title}",
            f"created: {now}",
            f"updated: {now}",
        ]
        if tags:
            frontmatter_lines.append(f"tags: [{', '.join(tags)}]")
        frontmatter_lines.append("---")
        frontmatter_lines.append("")

        # Combine frontmatter and content
        full_content = "\n".join(frontmatter_lines) + content

        async with aiofiles.open(file_path, "w") as f:
            await f.write(full_content)

        return ToolResult.ok(
            f"Created documentation: {path}",
            path=str(file_path),
            title=title,
            size=len(full_content),
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Create documentation failed", path=path, error=str(e))
        return ToolResult.fail(f"Create documentation failed: {e}")


@tool(
    name="update_documentation",
    description="Update an existing documentation file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the documentation file",
            },
            "content": {
                "type": "string",
                "description": "New content (replaces existing)",
            },
            "append": {
                "type": "boolean",
                "description": "Append instead of replace",
                "default": False,
            },
            "section": {
                "type": "string",
                "description": "Specific section to update (by heading)",
            },
        },
        "required": ["path", "content"],
    },
    permission_level=1,
)
async def update_documentation(
    path: str,
    content: str,
    append: bool = False,
    section: str | None = None,
) -> ToolResult:
    """Update an existing documentation file."""
    try:
        file_path = _validate_docs_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"File not found: {path}")

        # Read existing content
        async with aiofiles.open(file_path, "r") as f:
            existing = await f.read()

        frontmatter, body = _extract_frontmatter(existing)

        # Update timestamp
        frontmatter["updated"] = datetime.now().isoformat()

        if append:
            # Append to end
            new_body = body + "\n\n" + content
        elif section:
            # Update specific section
            sections = _extract_sections(body)
            section_lower = section.lower()
            found = False

            new_lines = []
            in_target_section = False
            target_level = 0

            for line in body.splitlines():
                header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
                if header_match:
                    level = len(header_match.group(1))
                    title = header_match.group(2).strip()

                    if section_lower in title.lower():
                        # Start of target section
                        in_target_section = True
                        target_level = level
                        new_lines.append(line)
                        new_lines.append(content)
                        found = True
                        continue
                    elif in_target_section and level <= target_level:
                        # End of target section
                        in_target_section = False

                if not in_target_section:
                    new_lines.append(line)

            if not found:
                return ToolResult.fail(f"Section not found: {section}")

            new_body = "\n".join(new_lines)
        else:
            # Replace entire body
            new_body = content

        # Rebuild document
        fm_lines = ["---"]
        for key, value in frontmatter.items():
            fm_lines.append(f"{key}: {value}")
        fm_lines.append("---")
        fm_lines.append("")

        full_content = "\n".join(fm_lines) + new_body

        async with aiofiles.open(file_path, "w") as f:
            await f.write(full_content)

        return ToolResult.ok(
            f"Updated documentation: {path}",
            path=str(file_path),
            size=len(full_content),
            append=append,
            section=section,
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Update documentation failed", path=path, error=str(e))
        return ToolResult.fail(f"Update documentation failed: {e}")
