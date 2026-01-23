"""
Workspace schemas for file, git, deploy, and search operations.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Enums ---


class DeployMethod(str, Enum):
    LOCAL_SYNC = "local_sync"
    SSH_RSYNC = "ssh_rsync"
    GIT_PUSH = "git_push"


class FileNodeType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


# --- File API Schemas ---


class FileNode(BaseModel):
    """A file or directory node in the tree."""

    name: str
    path: str
    type: FileNodeType
    size: int | None = None
    modified_at: str | None = None
    children: list["FileNode"] | None = None
    is_binary: bool = False


class FileTreeResponse(BaseModel):
    """Response for directory tree listing."""

    root: str
    nodes: list[FileNode]


class FileContentResponse(BaseModel):
    """Response for file content read."""

    path: str
    content: str
    size: int
    language: str | None = None
    is_binary: bool = False


class FileWriteRequest(BaseModel):
    """Request to write file content."""

    content: str = Field(..., max_length=2_097_152)  # 2MB max


class FileCreateRequest(BaseModel):
    """Request to create a new file or directory."""

    is_directory: bool = False
    content: str | None = None


class FileRenameRequest(BaseModel):
    """Request to rename/move a file."""

    old_path: str
    new_path: str


class FileSearchResult(BaseModel):
    """A single search result match."""

    path: str
    line_number: int
    line_content: str
    context_before: list[str] = []
    context_after: list[str] = []


class FileSearchResponse(BaseModel):
    """Response for file search."""

    query: str
    matches: list[FileSearchResult]
    total_matches: int
    files_searched: int


# --- Git API Schemas ---


class GitFileStatus(BaseModel):
    """Status of a single file in git."""

    path: str
    status: str  # modified, added, deleted, untracked, renamed


class GitStatusResponse(BaseModel):
    """Response for git status."""

    branch: str | None = None
    is_clean: bool = True
    modified: list[GitFileStatus] = []
    untracked: list[str] = []
    staged: list[GitFileStatus] = []
    ahead: int = 0
    behind: int = 0
    has_remote: bool = False


class GitCommitRequest(BaseModel):
    """Request to commit files."""

    message: str = Field(..., min_length=1, max_length=500)
    files: list[str] | None = None  # None = commit all staged/modified


class GitCommitResponse(BaseModel):
    """Response after committing."""

    commit_hash: str
    message: str
    files_changed: int


class GitLogEntry(BaseModel):
    """A single git log entry."""

    hash: str
    short_hash: str
    message: str
    author: str
    date: str
    files_changed: int | None = None


class GitLogResponse(BaseModel):
    """Response for git log."""

    entries: list[GitLogEntry]
    branch: str | None = None


class GitDiffResponse(BaseModel):
    """Response for git diff."""

    diff: str
    files_changed: int
    insertions: int
    deletions: int


# --- Deploy API Schemas ---


class DeployRequest(BaseModel):
    """Request to trigger a deploy."""

    message: str | None = None  # Commit message (defaults to timestamp)
    domain_id: str | None = None  # Specific domain (defaults to primary)


class DeployStage(BaseModel):
    """A deploy progress stage."""

    name: str
    status: str  # pending, running, completed, failed
    message: str | None = None


class DeployResponse(BaseModel):
    """Response after triggering a deploy."""

    deploy_id: str
    status: str  # started, completed, failed
    stages: list[DeployStage] = []
    commit_hash: str | None = None
    message: str | None = None


class DeployHistoryEntry(BaseModel):
    """A deploy history entry."""

    id: str
    commit_hash: str | None = None
    message: str | None = None
    domain: str | None = None
    deploy_method: str | None = None
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None


class DeployHistoryResponse(BaseModel):
    """Response for deploy history."""

    deploys: list[DeployHistoryEntry]
    total: int


class DeploySettingsUpdate(BaseModel):
    """Update deploy settings for a domain."""

    deploy_method: DeployMethod | None = None
    deploy_ssh_host: str | None = Field(None, max_length=255)
    deploy_ssh_path: str | None = Field(None, max_length=500)
    deploy_ssh_credential_id: str | None = None
    deploy_git_remote: str | None = Field(None, max_length=500)
    deploy_git_branch: str | None = Field(None, max_length=100)
    deploy_exclude_patterns: list[str] | None = None
    deploy_delete_enabled: bool | None = None


# --- Rollback Schema ---


class RollbackRequest(BaseModel):
    """Request to rollback to previous deploy."""

    commit_hash: str | None = None  # None = revert HEAD


class RollbackResponse(BaseModel):
    """Response after rollback."""

    revert_commit_hash: str
    message: str
    deploy_triggered: bool = False


# --- Health Check Schema ---


class HealthCheckResponse(BaseModel):
    """Response for domain health check."""

    domain: str
    status: str  # up, down, degraded, unknown
    response_time_ms: int | None = None
    checked_at: str | None = None
    ssl_valid: bool | None = None
    ssl_expires_at: str | None = None
