"""
Code analysis tools for the Code Agent.

These tools provide code search and analysis capabilities:
- Grep/ripgrep-style code search
- AST-based code analysis
- Dependency extraction
- Symbol/definition search
- Code metrics
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

# Default workspace for code operations
DEFAULT_WORKSPACE = os.environ.get("WORKSPACE_DIR", "/root/AI-Infrastructure")


async def _run_command(
    command: str,
    timeout: int = 60,
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
    name="code_search",
    description="""Search for patterns in code files using ripgrep.
    Supports regex patterns and filtering by file type.""",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Search pattern (regex supported)",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: workspace)",
            },
            "file_type": {
                "type": "string",
                "description": "Filter by file type (py, ts, js, go, etc.)",
            },
            "include_glob": {
                "type": "string",
                "description": "Include files matching glob pattern",
            },
            "exclude_glob": {
                "type": "string",
                "description": "Exclude files matching glob pattern",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case sensitive search",
                "default": False,
            },
            "context_lines": {
                "type": "integer",
                "description": "Lines of context around matches",
                "default": 2,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of matches",
                "default": 50,
            },
        },
        "required": ["pattern"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def code_search(
    pattern: str,
    path: str | None = None,
    file_type: str | None = None,
    include_glob: str | None = None,
    exclude_glob: str | None = None,
    case_sensitive: bool = False,
    context_lines: int = 2,
    max_results: int = 50,
) -> ToolResult:
    """Search for patterns in code files."""
    try:
        search_path = path or DEFAULT_WORKSPACE

        # Build ripgrep command
        cmd_parts = ["rg", "--json"]

        if not case_sensitive:
            cmd_parts.append("-i")

        if file_type:
            cmd_parts.extend(["-t", file_type])

        if include_glob:
            cmd_parts.extend(["-g", include_glob])

        if exclude_glob:
            cmd_parts.extend(["-g", f"!{exclude_glob}"])

        cmd_parts.extend(["-C", str(context_lines)])
        cmd_parts.extend(["-m", str(max_results)])

        # Add pattern and path
        cmd_parts.append(f"'{pattern}'")
        cmd_parts.append(search_path)

        cmd = " ".join(cmd_parts)
        code, stdout, stderr = await _run_command(cmd, timeout=30)

        # Parse JSON output
        matches = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data.get("data", {})
                    matches.append({
                        "file": match_data.get("path", {}).get("text", ""),
                        "line_number": match_data.get("line_number"),
                        "line_text": match_data.get("lines", {}).get("text", "").strip(),
                    })
            except json.JSONDecodeError:
                continue

        return ToolResult.ok({
            "message": f"Found {len(matches)} matches for '{pattern}'",
            "pattern": pattern,
            "path": search_path,
            "matches": matches,
            "count": len(matches),
        })

    except Exception as e:
        logger.error("Code search failed", pattern=pattern, error=str(e))
        return ToolResult.fail(f"Code search failed: {e}")


@tool(
    name="find_definition",
    description="""Find where a symbol (function, class, variable) is defined.
    Searches for common definition patterns.""",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Symbol name to find",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in",
            },
            "language": {
                "type": "string",
                "enum": ["python", "typescript", "javascript", "go", "auto"],
                "description": "Language to search for (auto-detect if not specified)",
                "default": "auto",
            },
        },
        "required": ["symbol"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def find_definition(
    symbol: str,
    path: str | None = None,
    language: str = "auto",
) -> ToolResult:
    """Find where a symbol is defined."""
    try:
        search_path = path or DEFAULT_WORKSPACE

        # Build definition patterns based on language
        patterns = {
            "python": [
                f"^\\s*(def|async def)\\s+{symbol}\\s*\\(",  # Function
                f"^\\s*class\\s+{symbol}\\s*[\\(:]",  # Class
                f"^{symbol}\\s*=",  # Variable
            ],
            "typescript": [
                f"(function|const|let|var|export)\\s+{symbol}\\s*[=(]",
                f"class\\s+{symbol}\\s*",
                f"interface\\s+{symbol}\\s*",
                f"type\\s+{symbol}\\s*=",
            ],
            "javascript": [
                f"(function|const|let|var|export)\\s+{symbol}\\s*[=(]",
                f"class\\s+{symbol}\\s*",
            ],
            "go": [
                f"func\\s+(\\([^)]+\\)\\s+)?{symbol}\\s*\\(",
                f"type\\s+{symbol}\\s+(struct|interface)",
                f"var\\s+{symbol}\\s+",
            ],
        }

        # Determine which patterns to use
        if language == "auto":
            all_patterns = []
            file_types = []
            for lang, pats in patterns.items():
                all_patterns.extend(pats)
                file_types.append(lang)
            search_patterns = all_patterns
        else:
            search_patterns = patterns.get(language, patterns["python"])
            file_types = [language]

        # Search for each pattern
        definitions = []
        for pattern in search_patterns:
            cmd_parts = ["rg", "--json", "-n"]

            # Add file type filters
            if language != "auto":
                if language == "python":
                    cmd_parts.extend(["-t", "py"])
                elif language in ("typescript", "javascript"):
                    cmd_parts.extend(["-t", "ts", "-t", "js"])
                elif language == "go":
                    cmd_parts.extend(["-t", "go"])

            cmd_parts.append(f"'{pattern}'")
            cmd_parts.append(search_path)

            cmd = " ".join(cmd_parts)
            code, stdout, stderr = await _run_command(cmd, timeout=20)

            for line in stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data.get("data", {})
                        definitions.append({
                            "file": match_data.get("path", {}).get("text", ""),
                            "line_number": match_data.get("line_number"),
                            "line_text": match_data.get("lines", {}).get("text", "").strip(),
                        })
                except json.JSONDecodeError:
                    continue

        # Deduplicate
        seen = set()
        unique_definitions = []
        for d in definitions:
            key = (d["file"], d["line_number"])
            if key not in seen:
                seen.add(key)
                unique_definitions.append(d)

        return ToolResult.ok({
            "message": f"Found {len(unique_definitions)} definitions for '{symbol}'",
            "symbol": symbol,
            "definitions": unique_definitions,
            "count": len(unique_definitions),
        })

    except Exception as e:
        logger.error("Find definition failed", symbol=symbol, error=str(e))
        return ToolResult.fail(f"Find definition failed: {e}")


@tool(
    name="find_references",
    description="""Find all references/usages of a symbol in the codebase.""",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Symbol name to find references for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in",
            },
            "file_type": {
                "type": "string",
                "description": "Filter by file type (py, ts, js, etc.)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum references to return",
                "default": 100,
            },
        },
        "required": ["symbol"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def find_references(
    symbol: str,
    path: str | None = None,
    file_type: str | None = None,
    max_results: int = 100,
) -> ToolResult:
    """Find all references to a symbol."""
    try:
        search_path = path or DEFAULT_WORKSPACE

        # Search for word boundary matches
        cmd_parts = ["rg", "--json", "-n", "-w", "-m", str(max_results)]

        if file_type:
            cmd_parts.extend(["-t", file_type])

        cmd_parts.append(f"'{symbol}'")
        cmd_parts.append(search_path)

        cmd = " ".join(cmd_parts)
        code, stdout, stderr = await _run_command(cmd, timeout=30)

        references = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data.get("data", {})
                    references.append({
                        "file": match_data.get("path", {}).get("text", ""),
                        "line_number": match_data.get("line_number"),
                        "line_text": match_data.get("lines", {}).get("text", "").strip(),
                    })
            except json.JSONDecodeError:
                continue

        # Group by file
        by_file = {}
        for ref in references:
            file_path = ref["file"]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append({
                "line": ref["line_number"],
                "text": ref["line_text"],
            })

        return ToolResult.ok({
            "message": f"Found {len(references)} references to '{symbol}' in {len(by_file)} files",
            "symbol": symbol,
            "total_references": len(references),
            "files_with_references": len(by_file),
            "by_file": by_file,
        })

    except Exception as e:
        logger.error("Find references failed", symbol=symbol, error=str(e))
        return ToolResult.fail(f"Find references failed: {e}")


@tool(
    name="get_python_imports",
    description="""Extract all imports from a Python file or directory.
    Useful for understanding dependencies.""",
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
async def get_python_imports(path: str) -> ToolResult:
    """Extract Python imports from a file or directory."""
    try:
        target_path = Path(path)
        if not target_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        imports = {
            "standard_library": set(),
            "third_party": set(),
            "local": set(),
        }

        # Standard library modules (partial list)
        stdlib = {
            "os", "sys", "re", "json", "typing", "datetime", "time",
            "collections", "functools", "itertools", "pathlib", "asyncio",
            "logging", "subprocess", "shutil", "tempfile", "uuid",
            "hashlib", "base64", "urllib", "http", "socket", "ssl",
            "threading", "multiprocessing", "queue", "dataclasses",
            "abc", "enum", "copy", "io", "contextlib", "traceback",
        }

        def extract_imports_from_file(file_path: Path) -> None:
            try:
                content = file_path.read_text()
                # Match import statements
                import_pattern = r"^(?:from\s+(\S+)\s+import|import\s+(\S+))"
                for match in re.finditer(import_pattern, content, re.MULTILINE):
                    module = match.group(1) or match.group(2)
                    # Get top-level module
                    top_module = module.split(".")[0]

                    if top_module in stdlib:
                        imports["standard_library"].add(top_module)
                    elif top_module.startswith(".") or module.startswith("."):
                        imports["local"].add(module)
                    else:
                        imports["third_party"].add(top_module)
            except Exception:
                pass

        if target_path.is_file():
            extract_imports_from_file(target_path)
        else:
            for py_file in target_path.rglob("*.py"):
                extract_imports_from_file(py_file)

        return ToolResult.ok({
            "message": f"Extracted imports from {path}",
            "path": path,
            "imports": {
                "standard_library": sorted(imports["standard_library"]),
                "third_party": sorted(imports["third_party"]),
                "local": sorted(imports["local"]),
            },
            "counts": {
                "standard_library": len(imports["standard_library"]),
                "third_party": len(imports["third_party"]),
                "local": len(imports["local"]),
            },
        })

    except Exception as e:
        logger.error("Get Python imports failed", path=path, error=str(e))
        return ToolResult.fail(f"Get Python imports failed: {e}")


@tool(
    name="get_package_dependencies",
    description="""Get project dependencies from package files (requirements.txt, pyproject.toml, package.json).""",
    parameters={
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Project root directory",
            },
        },
        "required": ["project_path"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def get_package_dependencies(project_path: str) -> ToolResult:
    """Get project dependencies from package files."""
    try:
        path = Path(project_path)
        if not path.exists():
            return ToolResult.fail(f"Path not found: {project_path}")

        dependencies = {
            "python": [],
            "node": [],
            "files_found": [],
        }

        # Check for Python dependencies
        requirements_txt = path / "requirements.txt"
        if requirements_txt.exists():
            dependencies["files_found"].append("requirements.txt")
            content = requirements_txt.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Parse package name (remove version specifiers)
                    pkg = re.split(r"[<>=!~\[]", line)[0].strip()
                    if pkg:
                        dependencies["python"].append({
                            "name": pkg,
                            "spec": line,
                        })

        # Check for pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            dependencies["files_found"].append("pyproject.toml")
            try:
                import tomllib
                content = pyproject.read_text()
                data = tomllib.loads(content)
                # Get dependencies from different locations
                deps = data.get("project", {}).get("dependencies", [])
                deps.extend(data.get("tool", {}).get("poetry", {}).get("dependencies", {}).keys())
                for dep in deps:
                    if isinstance(dep, str):
                        pkg = re.split(r"[<>=!~\[]", dep)[0].strip()
                        if pkg and pkg != "python":
                            dependencies["python"].append({
                                "name": pkg,
                                "spec": dep,
                            })
            except Exception:
                pass

        # Check for package.json
        package_json = path / "package.json"
        if package_json.exists():
            dependencies["files_found"].append("package.json")
            try:
                content = json.loads(package_json.read_text())
                for dep_type in ["dependencies", "devDependencies", "peerDependencies"]:
                    for name, version in content.get(dep_type, {}).items():
                        dependencies["node"].append({
                            "name": name,
                            "version": version,
                            "type": dep_type,
                        })
            except Exception:
                pass

        return ToolResult.ok({
            "message": f"Found dependencies in {len(dependencies['files_found'])} files",
            "project_path": project_path,
            "files_found": dependencies["files_found"],
            "python_dependencies": dependencies["python"],
            "node_dependencies": dependencies["node"],
            "counts": {
                "python": len(dependencies["python"]),
                "node": len(dependencies["node"]),
            },
        })

    except Exception as e:
        logger.error("Get package dependencies failed", path=project_path, error=str(e))
        return ToolResult.fail(f"Get package dependencies failed: {e}")


@tool(
    name="count_lines",
    description="""Count lines of code in files, excluding comments and blank lines.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or directory to analyze",
            },
            "file_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File extensions to include (e.g., ['py', 'ts'])",
            },
        },
        "required": ["path"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def count_lines(
    path: str,
    file_types: list[str] | None = None,
) -> ToolResult:
    """Count lines of code."""
    try:
        target = Path(path)
        if not target.exists():
            return ToolResult.fail(f"Path not found: {path}")

        # Try using cloc if available
        cmd = "which cloc > /dev/null 2>&1"
        code, _, _ = await _run_command(cmd)

        if code == 0:
            # Use cloc
            cmd = f"cloc --json {path}"
            if file_types:
                includes = ",".join(file_types)
                cmd = f"cloc --json --include-ext={includes} {path}"

            code, stdout, stderr = await _run_command(cmd, timeout=60)

            if code == 0 and stdout:
                try:
                    data = json.loads(stdout)
                    # Remove header and SUM entries for language breakdown
                    languages = {}
                    total = data.get("SUM", {})

                    for lang, stats in data.items():
                        if lang not in ("header", "SUM") and isinstance(stats, dict):
                            languages[lang] = {
                                "files": stats.get("nFiles", 0),
                                "blank": stats.get("blank", 0),
                                "comment": stats.get("comment", 0),
                                "code": stats.get("code", 0),
                            }

                    return ToolResult.ok({
                        "message": f"Analyzed {total.get('nFiles', 0)} files with {total.get('code', 0)} lines of code",
                        "path": path,
                        "total": {
                            "files": total.get("nFiles", 0),
                            "blank": total.get("blank", 0),
                            "comment": total.get("comment", 0),
                            "code": total.get("code", 0),
                        },
                        "by_language": languages,
                    })
                except json.JSONDecodeError:
                    pass

        # Fallback: simple line count
        total_lines = 0
        file_count = 0

        def count_file(file_path: Path) -> int:
            try:
                return len(file_path.read_text().splitlines())
            except Exception:
                return 0

        if target.is_file():
            total_lines = count_file(target)
            file_count = 1
        else:
            patterns = [f"*.{ft}" for ft in (file_types or ["py", "ts", "js", "go"])]
            for pattern in patterns:
                for file_path in target.rglob(pattern):
                    total_lines += count_file(file_path)
                    file_count += 1

        return ToolResult.ok({
            "message": f"Counted {total_lines} total lines in {file_count} files",
            "path": path,
            "total_lines": total_lines,
            "file_count": file_count,
            "note": "Includes comments and blank lines (cloc not available)",
        })

    except Exception as e:
        logger.error("Count lines failed", path=path, error=str(e))
        return ToolResult.fail(f"Count lines failed: {e}")
