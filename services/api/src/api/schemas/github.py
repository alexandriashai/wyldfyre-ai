"""
GitHub integration schemas.

Request/response models for GitHub settings, repository management,
branch operations, and pull request workflows.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# === Global Settings ===


class GitHubGlobalSettings(BaseModel):
    """Global GitHub configuration."""

    enabled: bool = True
    pat_configured: bool = False
    pat_source: Literal["env", "admin", None] = None
    pat_last_updated: str | None = None


class GitHubGlobalSettingsUpdate(BaseModel):
    """Update global GitHub settings."""

    enabled: bool | None = None
    pat: str | None = Field(None, min_length=1, description="Personal access token")
    clear_pat: bool = False


class GitHubTestResult(BaseModel):
    """Result of PAT test."""

    success: bool
    username: str | None = None
    scopes: list[str] | None = None
    error: str | None = None


class GitHubTestRequest(BaseModel):
    """Request to test a PAT."""

    pat: str = Field(..., min_length=1)


# === Project Settings ===


class GitHubProjectSettings(BaseModel):
    """Project-level GitHub configuration."""

    has_override: bool = False
    repo_url: str | None = None
    repo_name: str | None = None
    repo_linked: bool = False


class GitHubProjectSettingsUpdate(BaseModel):
    """Update project GitHub settings."""

    pat: str | None = Field(None, min_length=1)
    repo_url: str | None = Field(None, max_length=500)
    clear_pat: bool = False


# === Repository Management ===


class GitHubRepo(BaseModel):
    """GitHub repository information."""

    id: int
    name: str
    full_name: str
    html_url: str
    clone_url: str
    private: bool
    description: str | None = None
    default_branch: str | None = None


class GitHubRepoCreate(BaseModel):
    """Create a new GitHub repository."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    private: bool = True


class GitHubRepoLink(BaseModel):
    """Link an existing repository to a project."""

    repo_url: str = Field(..., min_length=1, max_length=500)
    init_git: bool = True


# === Branch Management ===


class Branch(BaseModel):
    """Git branch information."""

    name: str
    commit: str
    is_current: bool = False
    is_remote: bool = False
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0


class BranchListResponse(BaseModel):
    """Response for branch listing."""

    current: str
    branches: list[Branch]


class CreateBranchRequest(BaseModel):
    """Request to create a new branch."""

    name: str = Field(..., min_length=1, max_length=100)
    start_point: str | None = None
    checkout: bool = True


class CheckoutRequest(BaseModel):
    """Request to checkout a branch."""

    branch: str = Field(..., min_length=1)
    create: bool = False


class DeleteBranchRequest(BaseModel):
    """Request to delete a branch."""

    name: str = Field(..., min_length=1)
    force: bool = False


class RenameBranchRequest(BaseModel):
    """Request to rename a branch."""

    old_name: str = Field(..., min_length=1)
    new_name: str = Field(..., min_length=1, max_length=100)


class MergeRequest(BaseModel):
    """Request to merge branches."""

    source: str = Field(..., min_length=1)
    no_ff: bool = False
    squash: bool = False
    message: str | None = None


class MergeResponse(BaseModel):
    """Response from merge operation."""

    success: bool
    merged_commit: str | None = None
    conflicts: list[str] | None = None
    message: str | None = None


class RebaseRequest(BaseModel):
    """Request to rebase current branch."""

    onto: str = Field(..., min_length=1)


# === Pull Request ===


class GitHubPullRequest(BaseModel):
    """GitHub pull request information."""

    number: int
    title: str
    body: str | None = None
    state: str
    head: str
    base: str
    html_url: str
    created_at: str
    user: str
    mergeable: bool | None = None
    draft: bool = False
    merged: bool = False
    merge_commit_sha: str | None = None
    comments: int = 0
    review_comments: int = 0
    commits: int = 0
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class CreatePRRequest(BaseModel):
    """Request to create a pull request."""

    title: str = Field(..., min_length=1, max_length=256)
    body: str | None = None
    head: str | None = None  # Defaults to current branch
    base: str = "main"
    draft: bool = False


class MergePRRequest(BaseModel):
    """Request to merge a pull request."""

    merge_method: Literal["merge", "squash", "rebase"] = "merge"
    commit_message: str | None = None


class MergePRResponse(BaseModel):
    """Response from PR merge."""

    success: bool
    sha: str | None = None
    message: str


# === Issues ===


class GitHubIssue(BaseModel):
    """GitHub issue information."""

    number: int
    title: str
    body: str | None = None
    state: str
    html_url: str
    created_at: str
    user: str
    labels: list[str] = []
    comments: int = 0


class CreateIssueRequest(BaseModel):
    """Request to create an issue."""

    title: str = Field(..., min_length=1, max_length=256)
    body: str | None = None
    labels: list[str] | None = None


# === Workspace Branch Schemas (for workspace.py) ===


class BranchResponse(BaseModel):
    """Single branch response."""

    name: str
    commit: str
    is_current: bool


class ConflictCheckResponse(BaseModel):
    """Response for conflict check."""

    has_conflicts: bool
    conflicting_files: list[str] = []
    merge_in_progress: bool = False
    rebase_in_progress: bool = False
