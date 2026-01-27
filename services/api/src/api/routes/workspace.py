"""
Workspace routes for file browsing, git operations, and deployment.
"""

import asyncio
import json
import mimetypes
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from database.models import Domain, Project

from ..database import get_db_session
from ..dependencies import CurrentUserDep, GitHubServiceDep
from ..services.github_service import GitHubService
from ..schemas.workspace import (
    DeployHistoryEntry,
    DeployHistoryResponse,
    DeployRequest,
    DeployResponse,
    DeploySettingsUpdate,
    DeployStage,
    FileContentResponse,
    FileCreateRequest,
    FileNode,
    FileNodeType,
    FileRenameRequest,
    FileSearchResponse,
    FileSearchResult,
    FileTreeResponse,
    FileWriteRequest,
    GitCommitRequest,
    GitCommitResponse,
    GitDiffResponse,
    GitFileContentResponse,
    GitFileStatus,
    GitLogEntry,
    GitLogResponse,
    GitStatusResponse,
    HealthCheckResponse,
    RollbackRequest,
    RollbackResponse,
)
from ..schemas.github import (
    Branch,
    BranchListResponse,
    BranchResponse,
    CheckoutRequest,
    ConflictCheckResponse,
    CreateBranchRequest,
    DeleteBranchRequest,
    MergeRequest,
    MergeResponse,
    RebaseRequest,
    RenameBranchRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["Workspace"])

# File extensions considered binary
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff",
    ".mp3", ".mp4", ".wav", ".ogg", ".webm", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".exe", ".dll", ".so", ".dylib",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".sqlite", ".db",
}

# Always hidden directories
ALWAYS_HIDDEN = {".git", "node_modules", "__pycache__", ".next", ".venv", "venv"}

# Max file sizes
MAX_READ_SIZE = 5 * 1024 * 1024  # 5MB
MAX_WRITE_SIZE = 2 * 1024 * 1024  # 2MB

# Language detection from extension
EXTENSION_LANGUAGES = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "typescriptreact", ".jsx": "javascriptreact",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".xml": "xml", ".svg": "xml",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql", ".php": "php", ".rb": "ruby",
    ".go": "go", ".rs": "rust", ".java": "java",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".env": "dotenv", ".gitignore": "plaintext",
    ".dockerfile": "dockerfile", ".tf": "hcl",
}


# --- Helpers ---


async def get_project_with_root(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession,
) -> Project:
    """Fetch project and verify it has a root_path configured."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.sub,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    if not project.root_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_path configured",
        )

    if not os.path.isdir(project.root_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project root_path does not exist on disk",
        )

    return project


def validate_path(root_path: str, relative_path: str) -> str:
    """
    Validate and resolve a relative path within the project root.
    Prevents path traversal attacks.
    Returns the resolved absolute path.
    """
    if not relative_path:
        return root_path

    # Reject absolute paths and obvious traversal
    if relative_path.startswith("/") or ".." in relative_path.split(os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path: absolute paths and '..' are not allowed",
        )

    resolved = os.path.realpath(os.path.join(root_path, relative_path))
    canonical_root = os.path.realpath(root_path)

    if not resolved.startswith(canonical_root + os.sep) and resolved != canonical_root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path resolves outside project root",
        )

    return resolved


def is_binary_file(filepath: str) -> bool:
    """Check if a file is binary based on extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in BINARY_EXTENSIONS


def parse_gitignore(root_path: str) -> list[str]:
    """Parse .gitignore patterns from project root."""
    gitignore_path = os.path.join(root_path, ".gitignore")
    patterns = []
    if os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except (OSError, UnicodeDecodeError):
            pass
    return patterns


def should_hide(name: str, is_dir: bool, gitignore_patterns: list[str], show_hidden: bool) -> bool:
    """Determine if a file/directory should be hidden."""
    if name in ALWAYS_HIDDEN:
        return True

    if not show_hidden:
        # Hide dotfiles
        if name.startswith("."):
            return True

        # Check gitignore patterns (simple matching)
        for pattern in gitignore_patterns:
            pattern_clean = pattern.rstrip("/")
            if pattern.endswith("/") and is_dir and name == pattern_clean:
                return True
            if name == pattern_clean:
                return True

    return False


def get_language(filepath: str) -> str | None:
    """Detect language from file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    # Check for special filenames
    basename = os.path.basename(filepath).lower()
    if basename == "dockerfile":
        return "dockerfile"
    if basename == "makefile":
        return "makefile"
    return EXTENSION_LANGUAGES.get(ext)


def build_file_tree(
    root_path: str,
    base_path: str,
    depth: int,
    max_depth: int,
    gitignore_patterns: list[str],
    show_hidden: bool,
) -> list[FileNode]:
    """Recursively build a file tree."""
    if depth > max_depth:
        return []

    nodes = []
    try:
        entries = sorted(os.scandir(base_path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return []

    for entry in entries:
        if should_hide(entry.name, entry.is_dir(), gitignore_patterns, show_hidden):
            continue

        rel_path = os.path.relpath(entry.path, root_path)

        if entry.is_dir(follow_symlinks=False):
            children = None
            if depth < max_depth:
                children = build_file_tree(
                    root_path, entry.path, depth + 1, max_depth, gitignore_patterns, show_hidden
                )

            nodes.append(FileNode(
                name=entry.name,
                path=rel_path,
                type=FileNodeType.DIRECTORY,
                children=children,
            ))
        elif entry.is_file(follow_symlinks=False):
            try:
                stat = entry.stat()
                nodes.append(FileNode(
                    name=entry.name,
                    path=rel_path,
                    type=FileNodeType.FILE,
                    size=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    is_binary=is_binary_file(entry.name),
                ))
            except OSError:
                continue

    return nodes


async def run_git_command(cwd: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command asynchronously."""
    cmd = ["git"] + list(args)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        result = subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return result
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Git is not installed on this server",
        )


# --- File Endpoints ---


@router.get("/files", response_model=FileTreeResponse)
async def list_files(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    path: str = Query("", description="Subdirectory path to list"),
    depth: int = Query(3, ge=1, le=10, description="Max tree depth"),
    show_hidden: bool = Query(False, description="Show hidden files"),
) -> FileTreeResponse:
    """Get the directory tree for a project."""
    project = await get_project_with_root(project_id, current_user, db)
    base_path = validate_path(project.root_path, path)

    if not os.path.isdir(base_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {path}",
        )

    gitignore_patterns = parse_gitignore(project.root_path)
    nodes = build_file_tree(
        project.root_path, base_path, 1, depth, gitignore_patterns, show_hidden
    )

    return FileTreeResponse(root=path or ".", nodes=nodes)


@router.get("/files/content", response_model=None)
async def read_file_content(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    path: str = Query(..., description="File path relative to project root"),
    raw: bool = Query(False, description="Return raw binary content"),
) -> FileContentResponse | FileResponse:
    """Read file content (text files only, unless raw=true for images)."""
    project = await get_project_with_root(project_id, current_user, db)
    filepath = validate_path(project.root_path, path)

    if not os.path.isfile(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}",
        )

    file_size = os.path.getsize(filepath)

    if file_size > MAX_READ_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({file_size} bytes). Max: {MAX_READ_SIZE} bytes",
        )

    # Binary/image files: return as raw file response
    if is_binary_file(filepath):
        if raw:
            mime_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
            return FileResponse(filepath, media_type=mime_type)
        return FileContentResponse(
            path=path,
            content="",
            size=file_size,
            is_binary=True,
            language=None,
        )

    # Text files
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return FileContentResponse(
            path=path,
            content="",
            size=file_size,
            is_binary=True,
            language=None,
        )

    return FileContentResponse(
        path=path,
        content=content,
        size=file_size,
        language=get_language(filepath),
        is_binary=False,
    )


@router.put("/files/content")
async def write_file_content(
    project_id: str,
    request: FileWriteRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    path: str = Query(..., description="File path relative to project root"),
) -> FileContentResponse:
    """Write/update file content."""
    project = await get_project_with_root(project_id, current_user, db)
    filepath = validate_path(project.root_path, path)

    if is_binary_file(filepath):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot write to binary files via this endpoint",
        )

    content_bytes = request.content.encode("utf-8")
    if len(content_bytes) > MAX_WRITE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Content too large. Max: {MAX_WRITE_SIZE} bytes",
        )

    # Ensure parent directory exists
    parent_dir = os.path.dirname(filepath)
    os.makedirs(parent_dir, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(request.content)

    logger.info("File written", project_id=project_id, path=path, size=len(content_bytes))

    return FileContentResponse(
        path=path,
        content=request.content,
        size=len(content_bytes),
        language=get_language(filepath),
        is_binary=False,
    )


@router.post("/files")
async def create_file(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    path: str = Query(..., description="Path for new file/directory"),
    request: FileCreateRequest | None = None,
) -> FileNode:
    """Create a new file or directory."""
    project = await get_project_with_root(project_id, current_user, db)
    filepath = validate_path(project.root_path, path)

    if os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Path already exists: {path}",
        )

    is_directory = request.is_directory if request else False

    if is_directory:
        os.makedirs(filepath, exist_ok=True)
        return FileNode(
            name=os.path.basename(filepath),
            path=path,
            type=FileNodeType.DIRECTORY,
            children=[],
        )
    else:
        # Create parent dirs
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        content = request.content if request and request.content else ""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        stat = os.stat(filepath)
        return FileNode(
            name=os.path.basename(filepath),
            path=path,
            type=FileNodeType.FILE,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            is_binary=False,
        )


@router.delete("/files")
async def delete_file(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    path: str = Query(..., description="Path to delete"),
) -> dict[str, str]:
    """Delete a file or empty directory."""
    project = await get_project_with_root(project_id, current_user, db)
    filepath = validate_path(project.root_path, path)

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path not found: {path}",
        )

    if os.path.isdir(filepath):
        try:
            os.rmdir(filepath)
        except OSError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Directory is not empty. Delete contents first.",
            )
    else:
        os.remove(filepath)

    logger.info("File deleted", project_id=project_id, path=path)
    return {"message": f"Deleted: {path}"}


@router.post("/files/rename")
async def rename_file(
    project_id: str,
    request: FileRenameRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> FileNode:
    """Rename or move a file."""
    project = await get_project_with_root(project_id, current_user, db)
    old_filepath = validate_path(project.root_path, request.old_path)
    new_filepath = validate_path(project.root_path, request.new_path)

    if not os.path.exists(old_filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source path not found: {request.old_path}",
        )

    if os.path.exists(new_filepath):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Destination already exists: {request.new_path}",
        )

    # Ensure destination parent exists
    os.makedirs(os.path.dirname(new_filepath), exist_ok=True)
    os.rename(old_filepath, new_filepath)

    is_dir = os.path.isdir(new_filepath)
    stat = os.stat(new_filepath)

    return FileNode(
        name=os.path.basename(new_filepath),
        path=request.new_path,
        type=FileNodeType.DIRECTORY if is_dir else FileNodeType.FILE,
        size=None if is_dir else stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        is_binary=is_binary_file(new_filepath) if not is_dir else False,
    )


@router.get("/files/search", response_model=FileSearchResponse)
async def search_files(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    q: str = Query(..., min_length=2, description="Search query"),
    glob_pattern: str = Query("*", alias="glob", description="File glob pattern"),
    max_results: int = Query(100, ge=1, le=500),
) -> FileSearchResponse:
    """Search across project files using grep."""
    project = await get_project_with_root(project_id, current_user, db)

    # Use grep for searching (--null separates filename with NUL byte for safe parsing)
    cmd = [
        "grep", "-rn", "--null", "--include", glob_pattern,
        "-B", "1", "-A", "1",
        "--max-count", "10",  # Max matches per file
        q, project.root_path,
    ]

    # Add exclusions
    for hidden in ALWAYS_HIDDEN:
        cmd.insert(3, f"--exclude-dir={hidden}")

    # Exclude .env files from search
    cmd.insert(3, "--exclude=.env*")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        output = stdout.decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError):
        return FileSearchResponse(query=q, matches=[], total_matches=0, files_searched=0)

    # Parse grep output (--null produces "filename\0linenum:content" for matches
    # and "filename\0linenum-content" for context lines)
    matches: list[FileSearchResult] = []
    files_seen: set[str] = set()
    current_match: dict | None = None

    for line in output.split("\n"):
        if not line or line == "--":
            if current_match:
                matches.append(FileSearchResult(**current_match))
                current_match = None
            continue

        # Split on NUL byte to safely extract filename
        if "\x00" in line:
            filepath, rest = line.split("\x00", 1)
        else:
            # Fallback for lines without NUL (shouldn't happen with --null)
            continue

        # Parse "linenum:content" (match) or "linenum-content" (context)
        # Match lines use ":" separator, context lines use "-"
        match_sep = re.match(r'^(\d+)([:=-])(.*)', rest, re.DOTALL)
        if not match_sep:
            continue

        line_num_str, separator, content = match_sep.group(1), match_sep.group(2), match_sep.group(3)
        line_num = int(line_num_str)
        rel_path = os.path.relpath(filepath, project.root_path)

        if separator == ":":
            # This is a match line
            files_seen.add(rel_path)

            if current_match:
                matches.append(FileSearchResult(**current_match))

            current_match = {
                "path": rel_path,
                "line_number": line_num,
                "line_content": content,
                "context_before": [],
                "context_after": [],
            }

            if len(matches) >= max_results:
                break
        elif separator == "-" and current_match:
            # Context line — determine if before or after current match
            if line_num < current_match["line_number"]:
                current_match["context_before"].append(content)
            else:
                current_match["context_after"].append(content)

    if current_match:
        matches.append(FileSearchResult(**current_match))

    return FileSearchResponse(
        query=q,
        matches=matches[:max_results],
        total_matches=len(matches),
        files_searched=len(files_seen),
    )


# --- Git Endpoints ---


@router.post("/git/init")
async def git_init(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Initialize a git repository in the project root."""
    project = await get_project_with_root(project_id, current_user, db)

    git_dir = os.path.join(project.root_path, ".git")
    if os.path.isdir(git_dir):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Git is already initialized in this project",
        )

    await run_git_command(project.root_path, "init")
    logger.info("Git initialized", project_id=project_id, root_path=project.root_path)
    return {"message": "Git repository initialized"}


@router.get("/git/status", response_model=GitStatusResponse)
async def git_status(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitStatusResponse:
    """Get git status for the project."""
    project = await get_project_with_root(project_id, current_user, db)

    # Check if git is initialized
    if not os.path.isdir(os.path.join(project.root_path, ".git")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Git is not initialized in this project. Run 'git init' first.",
        )

    # Get branch name
    try:
        branch_result = await run_git_command(
            project.root_path, "rev-parse", "--abbrev-ref", "HEAD"
        )
        branch = branch_result.stdout.strip()
    except subprocess.CalledProcessError:
        branch = None

    # Get status
    status_result = await run_git_command(
        project.root_path, "status", "--porcelain", check=False
    )

    modified = []
    untracked = []
    staged = []

    for line in status_result.stdout.strip().split("\n"):
        if not line or len(line) < 4:
            continue
        # Git porcelain format: XY <space> <path>
        # X = index status, Y = worktree status, position 2 = space, position 3+ = path
        index_status = line[0]
        work_status = line[1]
        # Find the path - it starts after "XY " (positions 0, 1, 2)
        # But handle edge cases where there might be extra spaces
        filepath = line[3:].lstrip() if len(line) > 3 else ""

        if not filepath:
            continue

        # Handle renames (format: "old -> new")
        if " -> " in filepath:
            filepath = filepath.split(" -> ")[1]

        if index_status in ("M", "A", "D", "R"):
            staged.append(GitFileStatus(
                path=filepath,
                status={"M": "modified", "A": "added", "D": "deleted", "R": "renamed"}[index_status],
            ))

        if work_status == "M":
            modified.append(GitFileStatus(path=filepath, status="modified"))
        elif work_status == "D":
            modified.append(GitFileStatus(path=filepath, status="deleted"))
        elif index_status == "?" and work_status == "?":
            untracked.append(filepath)

    # Check ahead/behind
    ahead = 0
    behind = 0
    has_remote = False
    try:
        remote_result = await run_git_command(
            project.root_path, "rev-list", "--left-right", "--count", f"HEAD...@{{upstream}}"
        )
        parts = remote_result.stdout.strip().split("\t")
        if len(parts) == 2:
            ahead = int(parts[0])
            behind = int(parts[1])
            has_remote = True
    except (subprocess.CalledProcessError, ValueError):
        pass

    return GitStatusResponse(
        branch=branch,
        is_clean=not modified and not untracked and not staged,
        modified=modified,
        untracked=untracked,
        staged=staged,
        ahead=ahead,
        behind=behind,
        has_remote=has_remote,
    )


@router.post("/git/commit", response_model=GitCommitResponse)
async def git_commit(
    project_id: str,
    request: GitCommitRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitCommitResponse:
    """Stage and commit files."""
    project = await get_project_with_root(project_id, current_user, db)

    if request.files:
        # Stage specific files
        for f in request.files:
            validate_path(project.root_path, f)
            await run_git_command(project.root_path, "add", f)
    else:
        # Stage all changes
        await run_git_command(project.root_path, "add", "-A")

    # Commit
    try:
        await run_git_command(project.root_path, "commit", "-m", request.message)
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in e.stderr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nothing to commit",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git commit failed: {e.stderr}",
        )

    # Get commit info
    log_result = await run_git_command(
        project.root_path, "log", "-1", "--format=%H|%s", "--stat"
    )
    first_line = log_result.stdout.strip().split("\n")[0]
    parts = first_line.split("|", 1)
    commit_hash = parts[0] if parts else "unknown"

    # Count files changed
    diff_result = await run_git_command(
        project.root_path, "diff", "--stat", "HEAD~1..HEAD", check=False
    )
    files_changed = len([l for l in diff_result.stdout.split("\n") if "|" in l])

    return GitCommitResponse(
        commit_hash=commit_hash,
        message=request.message,
        files_changed=files_changed,
    )


class GitRevertRequest(BaseModel):
    """Request to revert file changes."""
    files: list[str] | None = None  # None = revert all


class GitRevertResponse(BaseModel):
    """Response from git revert operation."""
    reverted_files: int
    message: str


@router.post("/git/revert-files", response_model=GitRevertResponse)
async def git_revert_files(
    project_id: str,
    request: GitRevertRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitRevertResponse:
    """Revert modified files to their last committed state (discard changes)."""
    project = await get_project_with_root(project_id, current_user, db)

    reverted_count = 0

    if request.files:
        # Revert specific files
        for f in request.files:
            validate_path(project.root_path, f)
            try:
                await run_git_command(project.root_path, "checkout", "--", f)
                reverted_count += 1
            except subprocess.CalledProcessError:
                # File might be untracked, try to remove it
                file_path = Path(project.root_path) / f
                if file_path.exists():
                    file_path.unlink()
                    reverted_count += 1
    else:
        # Revert all modified files (git checkout .)
        try:
            # First get count of modified files
            status_result = await run_git_command(
                project.root_path, "status", "--porcelain"
            )
            modified_files = [
                line[3:] for line in status_result.stdout.strip().split("\n")
                if line and line[:2].strip() in ("M", "MM", "AM", "A", "D", "")
            ]
            reverted_count = len([f for f in modified_files if f])

            # Revert all tracked changes
            await run_git_command(project.root_path, "checkout", ".")

            # Also clean untracked files if any were selected
            # (only if explicitly requested - for safety we don't auto-clean untracked)
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Git revert failed: {e.stderr}",
            )

    return GitRevertResponse(
        reverted_files=reverted_count,
        message=f"Reverted {reverted_count} file(s) to last committed state",
    )


@router.post("/git/push")
async def git_push(
    project_id: str,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
    branch: str | None = Query(None),
    set_upstream: bool = Query(False),
) -> dict[str, str]:
    """Push commits to remote with PAT authentication."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        # Get current remote URL
        remote_result = await run_git_command(
            project.root_path, "remote", "get-url", "origin", check=False
        )
        remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else None

        # Get PAT and create authenticated URL if available
        pat = await github_service.get_effective_pat(project)
        auth_url = None

        if remote_url and pat:
            auth_url = github_service.get_authenticated_url(remote_url, pat)
            await run_git_command(
                project.root_path, "remote", "set-url", "origin", auth_url
            )

        try:
            # Build push command
            push_args = ["push"]
            if set_upstream:
                push_args.append("-u")
            push_args.append("origin")
            if branch:
                push_args.append(branch)

            await run_git_command(project.root_path, *push_args)
        finally:
            # Restore original URL (PAT never persisted)
            if auth_url and remote_url:
                await run_git_command(
                    project.root_path, "remote", "set-url", "origin", remote_url
                )

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git push failed: {e.stderr}",
        )

    return {"message": "Pushed successfully"}


@router.get("/git/log", response_model=GitLogResponse)
async def git_log(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(20, ge=1, le=100),
) -> GitLogResponse:
    """Get recent commit history."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        result = await run_git_command(
            project.root_path,
            "log",
            f"-{limit}",
            "--format=%H|%h|%s|%an|%aI|%+",
            "--shortstat",
        )
    except subprocess.CalledProcessError:
        return GitLogResponse(entries=[], branch=None)

    entries = []
    lines = result.stdout.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        parts = line.split("|", 4)
        if len(parts) >= 5:
            # Validate date format - parts[4] could be corrupted if message has |
            date_str = parts[4].split("|")[0] if "|" in parts[4] else parts[4]
            # Strip any trailing content from the date
            date_str = date_str.strip()
            entry = GitLogEntry(
                hash=parts[0],
                short_hash=parts[1],
                message=parts[2],
                author=parts[3],
                date=date_str if date_str else "",
            )
            # Check next line for stat
            if i + 1 < len(lines) and "file" in lines[i + 1]:
                stat_match = re.search(r"(\d+) file", lines[i + 1])
                if stat_match:
                    entry.files_changed = int(stat_match.group(1))
                i += 1
            entries.append(entry)
        i += 1

    # Get current branch
    try:
        branch_result = await run_git_command(
            project.root_path, "rev-parse", "--abbrev-ref", "HEAD"
        )
        branch = branch_result.stdout.strip()
    except subprocess.CalledProcessError:
        branch = None

    return GitLogResponse(entries=entries, branch=branch)


@router.get("/git/diff", response_model=GitDiffResponse)
async def git_diff(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitDiffResponse:
    """Get diff of uncommitted changes."""
    project = await get_project_with_root(project_id, current_user, db)

    # Get both staged and unstaged diff
    result = await run_git_command(
        project.root_path, "diff", "HEAD", check=False
    )

    diff_text = result.stdout

    # Parse stats
    stat_result = await run_git_command(
        project.root_path, "diff", "HEAD", "--stat", check=False
    )

    files_changed = 0
    insertions = 0
    deletions = 0

    stat_lines = stat_result.stdout.strip().split("\n")
    if stat_lines:
        last_line = stat_lines[-1]
        files_match = re.search(r"(\d+) file", last_line)
        ins_match = re.search(r"(\d+) insertion", last_line)
        del_match = re.search(r"(\d+) deletion", last_line)
        if files_match:
            files_changed = int(files_match.group(1))
        if ins_match:
            insertions = int(ins_match.group(1))
        if del_match:
            deletions = int(del_match.group(1))

    return GitDiffResponse(
        diff=diff_text,
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
    )


@router.get("/git/file-content", response_model=GitFileContentResponse)
async def git_file_content(
    project_id: str,
    current_user: CurrentUserDep,
    path: str = Query(..., description="File path relative to project root"),
    ref: str = Query("HEAD", description="Git ref (commit, branch, tag)"),
    db: AsyncSession = Depends(get_db_session),
) -> GitFileContentResponse:
    """Get file content at a specific git ref."""
    project = await get_project_with_root(project_id, current_user, db)

    # Validate path doesn't escape project root
    try:
        full_path = Path(project.root_path) / path.lstrip("/")
        full_path.relative_to(project.root_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Use git show to get file content at ref
    try:
        result = await run_git_command(
            project.root_path, "show", f"{ref}:{path.lstrip('/')}", check=True
        )
        content = result.stdout
    except Exception:
        # File might not exist at this ref (new file)
        raise HTTPException(
            status_code=404,
            detail=f"File not found at ref '{ref}'"
        )

    return GitFileContentResponse(
        content=content,
        ref=ref,
        path=path,
    )


# --- Branch Management Endpoints ---


@router.get("/git/branches", response_model=BranchListResponse)
async def list_branches(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    include_remote: bool = Query(True),
) -> BranchListResponse:
    """List all branches (local and optionally remote)."""
    project = await get_project_with_root(project_id, current_user, db)

    # Get current branch
    try:
        current_result = await run_git_command(
            project.root_path, "rev-parse", "--abbrev-ref", "HEAD"
        )
        current = current_result.stdout.strip()
    except subprocess.CalledProcessError:
        current = "main"

    branches: list[Branch] = []

    # Get local branches with tracking info
    args = ["branch", "-v", "--format=%(refname:short)|%(objectname:short)|%(upstream:short)|%(upstream:track)"]
    if include_remote:
        args.insert(1, "-a")

    try:
        result = await run_git_command(project.root_path, *args)
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|")
            name = parts[0].strip()
            commit = parts[1] if len(parts) > 1 else ""
            upstream = parts[2] if len(parts) > 2 else None
            track = parts[3] if len(parts) > 3 else ""

            is_remote = name.startswith("remotes/") or name.startswith("origin/")

            # Parse ahead/behind
            ahead = 0
            behind = 0
            if track:
                ahead_match = re.search(r"ahead (\d+)", track)
                behind_match = re.search(r"behind (\d+)", track)
                if ahead_match:
                    ahead = int(ahead_match.group(1))
                if behind_match:
                    behind = int(behind_match.group(1))

            # Clean up remote branch names
            if name.startswith("remotes/"):
                name = name[8:]  # Remove "remotes/" prefix

            branches.append(Branch(
                name=name,
                commit=commit,
                is_current=name == current,
                is_remote=is_remote,
                upstream=upstream if upstream else None,
                ahead=ahead,
                behind=behind,
            ))
    except subprocess.CalledProcessError:
        pass

    return BranchListResponse(current=current, branches=branches)


@router.post("/git/branches", response_model=BranchResponse)
async def create_branch(
    project_id: str,
    request: CreateBranchRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> BranchResponse:
    """Create a new branch."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        # Create branch
        args = ["checkout", "-b", request.name]
        if request.start_point:
            args.append(request.start_point)

        if request.checkout:
            await run_git_command(project.root_path, *args)
        else:
            # Create without checkout
            branch_args = ["branch", request.name]
            if request.start_point:
                branch_args.append(request.start_point)
            await run_git_command(project.root_path, *branch_args)

        # Get commit hash
        commit_result = await run_git_command(
            project.root_path, "rev-parse", "--short", request.name
        )
        commit = commit_result.stdout.strip()

        logger.info(
            "Branch created",
            project_id=project_id,
            branch=request.name,
        )

        return BranchResponse(
            name=request.name,
            commit=commit,
            is_current=request.checkout,
        )

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create branch: {e.stderr}",
        )


@router.post("/git/branches/checkout", response_model=BranchResponse)
async def checkout_branch(
    project_id: str,
    request: CheckoutRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> BranchResponse:
    """Switch to a branch."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        if request.create:
            await run_git_command(
                project.root_path, "checkout", "-b", request.branch
            )
        else:
            await run_git_command(
                project.root_path, "checkout", request.branch
            )

        # Get commit hash
        commit_result = await run_git_command(
            project.root_path, "rev-parse", "--short", "HEAD"
        )
        commit = commit_result.stdout.strip()

        return BranchResponse(
            name=request.branch,
            commit=commit,
            is_current=True,
        )

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to checkout branch: {e.stderr}",
        )


@router.delete("/git/branches/{branch_name}")
async def delete_branch(
    project_id: str,
    branch_name: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    force: bool = Query(False),
) -> dict[str, str]:
    """Delete a branch."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        flag = "-D" if force else "-d"
        await run_git_command(project.root_path, "branch", flag, branch_name)

        logger.info(
            "Branch deleted",
            project_id=project_id,
            branch=branch_name,
        )

        return {"message": f"Branch '{branch_name}' deleted"}

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete branch: {e.stderr}",
        )


@router.post("/git/branches/rename")
async def rename_branch(
    project_id: str,
    request: RenameBranchRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Rename a branch."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        await run_git_command(
            project.root_path, "branch", "-m", request.old_name, request.new_name
        )

        logger.info(
            "Branch renamed",
            project_id=project_id,
            old_name=request.old_name,
            new_name=request.new_name,
        )

        return {"message": f"Branch renamed from '{request.old_name}' to '{request.new_name}'"}

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to rename branch: {e.stderr}",
        )


@router.post("/git/merge", response_model=MergeResponse)
async def merge_branch(
    project_id: str,
    request: MergeRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> MergeResponse:
    """Merge a source branch into the current branch."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        # Build merge command
        args = ["merge", request.source]
        if request.no_ff:
            args.append("--no-ff")
        if request.squash:
            args.append("--squash")
        if request.message:
            args.extend(["-m", request.message])

        await run_git_command(project.root_path, *args)

        # Get merge commit hash
        commit_result = await run_git_command(
            project.root_path, "rev-parse", "--short", "HEAD"
        )
        merged_commit = commit_result.stdout.strip()

        logger.info(
            "Branch merged",
            project_id=project_id,
            source=request.source,
        )

        return MergeResponse(
            success=True,
            merged_commit=merged_commit,
            message=f"Successfully merged '{request.source}'",
        )

    except subprocess.CalledProcessError as e:
        # Check for merge conflicts
        if "CONFLICT" in e.stderr or "CONFLICT" in e.stdout:
            # Get list of conflicting files
            status_result = await run_git_command(
                project.root_path, "diff", "--name-only", "--diff-filter=U", check=False
            )
            conflicts = [f.strip() for f in status_result.stdout.split("\n") if f.strip()]

            return MergeResponse(
                success=False,
                conflicts=conflicts,
                message="Merge conflicts detected",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Merge failed: {e.stderr}",
        )


@router.post("/git/rebase", response_model=MergeResponse)
async def rebase_branch(
    project_id: str,
    request: RebaseRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> MergeResponse:
    """Rebase current branch onto another branch."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        await run_git_command(project.root_path, "rebase", request.onto)

        # Get current commit hash
        commit_result = await run_git_command(
            project.root_path, "rev-parse", "--short", "HEAD"
        )

        return MergeResponse(
            success=True,
            merged_commit=commit_result.stdout.strip(),
            message=f"Successfully rebased onto '{request.onto}'",
        )

    except subprocess.CalledProcessError as e:
        # Check for rebase conflicts
        if "CONFLICT" in e.stderr or "CONFLICT" in e.stdout:
            status_result = await run_git_command(
                project.root_path, "diff", "--name-only", "--diff-filter=U", check=False
            )
            conflicts = [f.strip() for f in status_result.stdout.split("\n") if f.strip()]

            return MergeResponse(
                success=False,
                conflicts=conflicts,
                message="Rebase conflicts detected",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rebase failed: {e.stderr}",
        )


@router.post("/git/abort")
async def abort_merge_or_rebase(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Abort an in-progress merge or rebase."""
    project = await get_project_with_root(project_id, current_user, db)

    # Try aborting merge first
    merge_result = await run_git_command(
        project.root_path, "merge", "--abort", check=False
    )
    if merge_result.returncode == 0:
        return {"message": "Merge aborted"}

    # Try aborting rebase
    rebase_result = await run_git_command(
        project.root_path, "rebase", "--abort", check=False
    )
    if rebase_result.returncode == 0:
        return {"message": "Rebase aborted"}

    return {"message": "No merge or rebase in progress"}


@router.get("/git/conflicts", response_model=ConflictCheckResponse)
async def check_conflicts(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ConflictCheckResponse:
    """Check for merge/rebase conflicts."""
    project = await get_project_with_root(project_id, current_user, db)

    # Check for conflicting files
    status_result = await run_git_command(
        project.root_path, "diff", "--name-only", "--diff-filter=U", check=False
    )
    conflicts = [f.strip() for f in status_result.stdout.split("\n") if f.strip()]

    # Check if merge is in progress
    merge_head = os.path.join(project.root_path, ".git", "MERGE_HEAD")
    merge_in_progress = os.path.exists(merge_head)

    # Check if rebase is in progress
    rebase_merge = os.path.join(project.root_path, ".git", "rebase-merge")
    rebase_apply = os.path.join(project.root_path, ".git", "rebase-apply")
    rebase_in_progress = os.path.exists(rebase_merge) or os.path.exists(rebase_apply)

    return ConflictCheckResponse(
        has_conflicts=len(conflicts) > 0,
        conflicting_files=conflicts,
        merge_in_progress=merge_in_progress,
        rebase_in_progress=rebase_in_progress,
    )


@router.post("/git/fetch")
async def git_fetch(
    project_id: str,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
    prune: bool = Query(False),
) -> dict[str, str]:
    """Fetch from remote with PAT authentication."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        # Get current remote URL
        remote_result = await run_git_command(
            project.root_path, "remote", "get-url", "origin", check=False
        )
        remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else None

        # Get PAT and create authenticated URL
        pat = await github_service.get_effective_pat(project)
        auth_url = None

        if remote_url and pat:
            auth_url = github_service.get_authenticated_url(remote_url, pat)
            await run_git_command(
                project.root_path, "remote", "set-url", "origin", auth_url
            )

        try:
            args = ["fetch", "origin"]
            if prune:
                args.append("--prune")
            await run_git_command(project.root_path, *args)
        finally:
            # Restore original URL
            if auth_url and remote_url:
                await run_git_command(
                    project.root_path, "remote", "set-url", "origin", remote_url
                )

        return {"message": "Fetched successfully"}

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git fetch failed: {e.stderr}",
        )


@router.post("/git/pull")
async def git_pull(
    project_id: str,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
    branch: str | None = Query(None),
    rebase: bool = Query(False),
) -> dict[str, str]:
    """Pull from remote with PAT authentication."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        # Get current remote URL
        remote_result = await run_git_command(
            project.root_path, "remote", "get-url", "origin", check=False
        )
        remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else None

        # Get PAT and create authenticated URL
        pat = await github_service.get_effective_pat(project)
        auth_url = None

        if remote_url and pat:
            auth_url = github_service.get_authenticated_url(remote_url, pat)
            await run_git_command(
                project.root_path, "remote", "set-url", "origin", auth_url
            )

        try:
            args = ["pull"]
            if rebase:
                args.append("--rebase")
            args.append("origin")
            if branch:
                args.append(branch)
            await run_git_command(project.root_path, *args)
        finally:
            # Restore original URL
            if auth_url and remote_url:
                await run_git_command(
                    project.root_path, "remote", "set-url", "origin", remote_url
                )

        return {"message": "Pulled successfully"}

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git pull failed: {e.stderr}",
        )


# --- Deploy Endpoints ---


@router.post("/deploy", response_model=DeployResponse)
async def deploy_project(
    project_id: str,
    request: DeployRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> DeployResponse:
    """Execute deploy pipeline for the project."""
    project = await get_project_with_root(project_id, current_user, db)

    # Find target domain
    domain_query = select(Domain).where(Domain.project_id == project_id)
    if request.domain_id:
        domain_query = domain_query.where(Domain.id == request.domain_id)
    else:
        domain_query = domain_query.where(Domain.is_primary == True)

    result = await db.execute(domain_query)
    domain = result.scalar_one_or_none()

    if not domain:
        # Try first domain
        result = await db.execute(
            select(Domain).where(Domain.project_id == project_id).limit(1)
        )
        domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No domain configured for this project",
        )

    deploy_id = str(uuid.uuid4())
    stages: list[DeployStage] = []
    commit_hash = None

    try:
        # Stage 1: Git commit (if changes exist)
        stages.append(DeployStage(name="check_changes", status="running"))

        status_result = await run_git_command(
            project.root_path, "status", "--porcelain", check=False
        )

        if status_result.stdout.strip():
            message = request.message or f"Deploy: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            await run_git_command(project.root_path, "add", "-A")
            await run_git_command(project.root_path, "commit", "-m", f"[deploy] {message}")

            hash_result = await run_git_command(
                project.root_path, "rev-parse", "--short", "HEAD"
            )
            commit_hash = hash_result.stdout.strip()

        stages[-1].status = "completed"

        # Stage 2: Deploy based on method
        deploy_method = domain.deploy_method or "local_sync"
        stages.append(DeployStage(name=f"deploy_{deploy_method}", status="running"))

        # Build exclude args
        exclude_args = []
        if domain.deploy_exclude_patterns:
            try:
                patterns = json.loads(domain.deploy_exclude_patterns)
                for p in patterns:
                    exclude_args.extend(["--exclude", p])
            except (json.JSONDecodeError, TypeError):
                pass

        if deploy_method == "local_sync":
            if not domain.web_root:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Domain has no web_root configured for local_sync deploy",
                )

            cmd = ["rsync", "-av", "--mkpath"] + exclude_args
            if domain.deploy_delete_enabled:
                cmd.append("--delete")
            cmd.extend([
                f"{project.root_path}/",
                f"{domain.web_root}/",
            ])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise Exception(f"rsync failed: {stderr.decode()}")

            # Reload nginx if config may have changed (opt-in via domain setting)
            if getattr(domain, 'reload_nginx_on_deploy', False):
                nginx_proc = await asyncio.create_subprocess_exec(
                    "nginx", "-t",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, nginx_err = await nginx_proc.communicate()
                if nginx_proc.returncode == 0:
                    await asyncio.create_subprocess_exec(
                        "nginx", "-s", "reload",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

        elif deploy_method == "ssh_rsync":
            if not domain.deploy_ssh_host or not domain.deploy_ssh_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SSH host and path are required for ssh_rsync deploy",
                )

            # Validate SSH host format
            if not re.match(r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+$', domain.deploy_ssh_host):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid SSH host format. Expected: user@hostname",
                )

            # Validate SSH path - reject shell metacharacters
            if re.search(r'[;&|$`\\]', domain.deploy_ssh_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid characters in SSH path",
                )

            ssh_args = ["ssh"]
            if domain.deploy_ssh_credential_id:
                ssh_args.extend(["-i", f"/etc/wyld/ssh_keys/{domain.deploy_ssh_credential_id}"])
            ssh_cmd = " ".join(ssh_args)

            # Ensure remote directory exists
            mkdir_cmd = ssh_args + [domain.deploy_ssh_host, "mkdir", "-p", domain.deploy_ssh_path]
            mkdir_proc = await asyncio.create_subprocess_exec(
                *mkdir_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await mkdir_proc.communicate()

            cmd = ["rsync", "-avz", "--mkpath", "-e", ssh_cmd] + exclude_args
            if domain.deploy_delete_enabled:
                cmd.append("--delete")
            cmd.extend([
                f"{project.root_path}/",
                f"{domain.deploy_ssh_host}:{domain.deploy_ssh_path}/",
            ])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise Exception(f"SSH rsync failed: {stderr.decode()}")

        elif deploy_method == "git_push":
            remote = domain.deploy_git_remote or "origin"
            branch = domain.deploy_git_branch or "main"

            # Validate remote URL format
            if domain.deploy_git_remote and not re.match(
                r'^(https?://|git@)[\w./:-]+$', domain.deploy_git_remote
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid git remote URL format",
                )

            await run_git_command(project.root_path, "push", remote, branch)

        stages[-1].status = "completed"
        stages[-1].message = f"Deployed via {deploy_method}"

        logger.info(
            "Deploy completed",
            project_id=project_id,
            domain=domain.domain_name,
            method=deploy_method,
            commit=commit_hash,
        )

        return DeployResponse(
            deploy_id=deploy_id,
            status="completed",
            stages=stages,
            commit_hash=commit_hash,
            message=f"Deployed to {domain.domain_name} via {deploy_method}",
        )

    except HTTPException:
        raise
    except Exception as e:
        stages[-1].status = "failed"
        stages[-1].message = str(e)

        logger.error(
            "Deploy failed",
            project_id=project_id,
            error=str(e),
        )

        return DeployResponse(
            deploy_id=deploy_id,
            status="failed",
            stages=stages,
            commit_hash=commit_hash,
            message=f"Deploy failed: {str(e)}",
        )


@router.get("/deploys", response_model=DeployHistoryResponse)
async def deploy_history(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(10, ge=1, le=50),
) -> DeployHistoryResponse:
    """Get recent deploy history from git log."""
    project = await get_project_with_root(project_id, current_user, db)

    try:
        result = await run_git_command(
            project.root_path,
            "log",
            f"-{limit}",
            "--grep=[deploy]",
            "--format=%H|%h|%s|%aI",
        )
    except subprocess.CalledProcessError:
        return DeployHistoryResponse(deploys=[], total=0)

    deploys = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) >= 4:
            message = parts[2].replace("[deploy] ", "")
            deploys.append(DeployHistoryEntry(
                id=parts[0],
                commit_hash=parts[1],
                message=message,
                status="completed",
                started_at=parts[3],
                completed_at=parts[3],
            ))

    return DeployHistoryResponse(deploys=deploys, total=len(deploys))


@router.post("/rollback", response_model=RollbackResponse)
async def rollback_deploy(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    request: RollbackRequest | None = None,
) -> RollbackResponse:
    """Rollback to previous deploy by reverting HEAD commit."""
    project = await get_project_with_root(project_id, current_user, db)

    target = request.commit_hash if request and request.commit_hash else "HEAD"

    # Validate commit hash format to prevent command injection
    if target != "HEAD" and not re.match(r'^[0-9a-f]{7,40}$', target):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid commit hash format",
        )

    try:
        await run_git_command(project.root_path, "revert", "--no-edit", target)
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {e.stderr}",
        )

    # Get new commit hash
    hash_result = await run_git_command(
        project.root_path, "rev-parse", "--short", "HEAD"
    )
    revert_hash = hash_result.stdout.strip()

    return RollbackResponse(
        revert_commit_hash=revert_hash,
        message=f"Reverted {target}",
        deploy_triggered=False,
    )


# --- Health Check Endpoint ---


@router.get("/health", response_model=HealthCheckResponse)
async def check_project_health(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> HealthCheckResponse:
    """Check health of the project's primary domain."""
    project = await get_project_with_root(project_id, current_user, db)

    result = await db.execute(
        select(Domain).where(
            Domain.project_id == project_id,
            Domain.is_primary == True,
        )
    )
    domain = result.scalar_one_or_none()

    if not domain:
        result = await db.execute(
            select(Domain).where(Domain.project_id == project_id).limit(1)
        )
        domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No domain configured for this project",
        )

    return HealthCheckResponse(
        domain=domain.domain_name,
        status=domain.health_status or "unknown",
        response_time_ms=domain.response_time_ms,
        checked_at=domain.last_health_check_at.isoformat() if domain.last_health_check_at else None,
        ssl_valid=domain.ssl_enabled,
        ssl_expires_at=domain.ssl_expires_at.isoformat() if domain.ssl_expires_at else None,
    )
