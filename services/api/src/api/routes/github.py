"""
GitHub integration API routes.

Provides endpoints for:
- Global GitHub settings (admin-only)
- Project-level GitHub settings
- Repository management (create, link, list)
- Pull request operations
- Issue operations
"""

import asyncio
import subprocess
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from database.models import Project

from ..database import get_db_session
from ..dependencies import (
    AdminUserDep,
    CurrentUserDep,
    GitHubServiceDep,
)
from ..schemas.github import (
    CreateIssueRequest,
    CreatePRRequest,
    GitHubGlobalSettings,
    GitHubGlobalSettingsUpdate,
    GitHubIssue,
    GitHubProjectSettings,
    GitHubProjectSettingsUpdate,
    GitHubPullRequest,
    GitHubRepo,
    GitHubRepoCreate,
    GitHubRepoLink,
    GitHubTestRequest,
    GitHubTestResult,
    MergePRRequest,
    MergePRResponse,
)
from ..services.github_service import GitHubService

logger = get_logger(__name__)

router = APIRouter(prefix="/github", tags=["GitHub"])


# === Helper Functions ===


async def get_project_with_auth(
    project_id: str,
    current_user: Any,
    db: AsyncSession,
) -> Project:
    """Get project and verify ownership."""
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
    return project


# === Global Settings (Admin Only) ===


@router.get("/settings", response_model=GitHubGlobalSettings)
async def get_global_settings(
    current_user: AdminUserDep,
    github_service: GitHubServiceDep,
) -> GitHubGlobalSettings:
    """Get global GitHub configuration (admin only)."""
    enabled = await github_service.is_enabled()
    pat_source = await github_service.get_pat_source()
    pat_ts = await github_service.get_global_pat_timestamp()

    return GitHubGlobalSettings(
        enabled=enabled,
        pat_configured=pat_source is not None,
        pat_source=pat_source,  # type: ignore
        pat_last_updated=pat_ts,
    )


@router.put("/settings", response_model=GitHubGlobalSettings)
async def update_global_settings(
    request: GitHubGlobalSettingsUpdate,
    current_user: AdminUserDep,
    github_service: GitHubServiceDep,
) -> GitHubGlobalSettings:
    """Update global GitHub configuration (admin only)."""
    if request.enabled is not None:
        await github_service.set_enabled(request.enabled)

    if request.clear_pat:
        await github_service.clear_global_pat()
    elif request.pat:
        await github_service.set_global_pat(request.pat)

    # Return updated settings
    enabled = await github_service.is_enabled()
    pat_source = await github_service.get_pat_source()
    pat_ts = await github_service.get_global_pat_timestamp()

    logger.info(
        "GitHub global settings updated",
        user_id=current_user.sub,
        enabled=enabled,
        pat_source=pat_source,
    )

    return GitHubGlobalSettings(
        enabled=enabled,
        pat_configured=pat_source is not None,
        pat_source=pat_source,  # type: ignore
        pat_last_updated=pat_ts,
    )


@router.post("/settings/test", response_model=GitHubTestResult)
async def test_global_pat(
    current_user: AdminUserDep,
    github_service: GitHubServiceDep,
) -> GitHubTestResult:
    """Test the currently configured global PAT (admin only)."""
    pat = await github_service.get_effective_pat()
    if not pat:
        return GitHubTestResult(
            success=False,
            error="No PAT configured",
        )

    result = await github_service.test_pat(pat)
    return GitHubTestResult(**result)


@router.post("/test", response_model=GitHubTestResult)
async def test_pat(
    request: GitHubTestRequest,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
) -> GitHubTestResult:
    """Test a provided PAT."""
    result = await github_service.test_pat(request.pat)
    return GitHubTestResult(**result)


# === Repository Management ===


@router.get("/repos", response_model=list[GitHubRepo])
async def list_repos(
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
) -> list[GitHubRepo]:
    """List repositories accessible by the current PAT."""
    pat = await github_service.get_effective_pat()
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    repos = await github_service.list_user_repos(pat, page=page, per_page=per_page)
    return [GitHubRepo(**r) for r in repos]


@router.post("/repos", response_model=GitHubRepo, status_code=status.HTTP_201_CREATED)
async def create_repo(
    request: GitHubRepoCreate,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
) -> GitHubRepo:
    """Create a new GitHub repository."""
    pat = await github_service.get_effective_pat()
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    repo = await github_service.create_repo(
        pat=pat,
        name=request.name,
        description=request.description,
        private=request.private,
    )

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create repository",
        )

    logger.info(
        "GitHub repo created",
        user_id=current_user.sub,
        repo=repo["full_name"],
    )

    return GitHubRepo(**repo)


# === Project Settings ===


@router.get("/projects/{project_id}/settings", response_model=GitHubProjectSettings)
async def get_project_settings(
    project_id: str,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitHubProjectSettings:
    """Get project-level GitHub configuration."""
    project = await get_project_with_auth(project_id, current_user, db)

    has_override = project.github_pat_encrypted is not None
    repo_url = project.github_repo_url
    repo_name = None
    repo_linked = False

    if repo_url:
        parsed = GitHubService.parse_repo_url(repo_url)
        if parsed:
            repo_name = f"{parsed[0]}/{parsed[1]}"
            repo_linked = True

    return GitHubProjectSettings(
        has_override=has_override,
        repo_url=repo_url,
        repo_name=repo_name,
        repo_linked=repo_linked,
    )


@router.put("/projects/{project_id}/settings", response_model=GitHubProjectSettings)
async def update_project_settings(
    project_id: str,
    request: GitHubProjectSettingsUpdate,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitHubProjectSettings:
    """Update project-level GitHub configuration."""
    project = await get_project_with_auth(project_id, current_user, db)

    if request.clear_pat:
        project.github_pat_encrypted = None
    elif request.pat:
        project.github_pat_encrypted = github_service.encrypt_pat(request.pat)

    if request.repo_url is not None:
        project.github_repo_url = request.repo_url or None

    await db.flush()
    await db.refresh(project)

    # Return updated settings
    has_override = project.github_pat_encrypted is not None
    repo_url = project.github_repo_url
    repo_name = None
    repo_linked = False

    if repo_url:
        parsed = GitHubService.parse_repo_url(repo_url)
        if parsed:
            repo_name = f"{parsed[0]}/{parsed[1]}"
            repo_linked = True

    logger.info(
        "GitHub project settings updated",
        user_id=current_user.sub,
        project_id=project_id,
    )

    return GitHubProjectSettings(
        has_override=has_override,
        repo_url=repo_url,
        repo_name=repo_name,
        repo_linked=repo_linked,
    )


@router.delete("/projects/{project_id}/settings")
async def clear_project_settings(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Clear project PAT override (revert to global)."""
    project = await get_project_with_auth(project_id, current_user, db)
    project.github_pat_encrypted = None
    await db.flush()

    logger.info(
        "GitHub project PAT override cleared",
        user_id=current_user.sub,
        project_id=project_id,
    )

    return {"message": "Project PAT override cleared"}


# === Project Repository Operations ===


@router.post("/projects/{project_id}/repo/link")
async def link_repo(
    project_id: str,
    request: GitHubRepoLink,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Link an existing GitHub repository to a project."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.root_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_path configured",
        )

    # Validate the repo URL
    parsed = GitHubService.parse_repo_url(request.repo_url)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub repository URL",
        )

    # Optionally verify the repo exists
    pat = await github_service.get_effective_pat(project)
    if pat:
        repo = await github_service.get_repo(pat, parsed[0], parsed[1])
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {parsed[0]}/{parsed[1]} not found or not accessible",
            )

    # Initialize git if requested
    if request.init_git:
        try:
            # Check if git is already initialized
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--git-dir",
                cwd=project.root_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            if proc.returncode != 0:
                # Initialize git
                proc = await asyncio.create_subprocess_exec(
                    "git", "init",
                    cwd=project.root_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()

            # Set remote origin
            proc = await asyncio.create_subprocess_exec(
                "git", "remote", "remove", "origin",
                cwd=project.root_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()  # Ignore error if origin doesn't exist

            proc = await asyncio.create_subprocess_exec(
                "git", "remote", "add", "origin", request.repo_url,
                cwd=project.root_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise Exception(stderr.decode())

        except Exception as e:
            logger.error("Failed to initialize git", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize git: {e}",
            )

    # Update project
    project.github_repo_url = request.repo_url
    await db.flush()

    logger.info(
        "GitHub repo linked to project",
        user_id=current_user.sub,
        project_id=project_id,
        repo=f"{parsed[0]}/{parsed[1]}",
    )

    return {"message": f"Repository {parsed[0]}/{parsed[1]} linked successfully"}


@router.post("/projects/{project_id}/repo/init")
async def init_repo(
    project_id: str,
    request: GitHubRepoCreate,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitHubRepo:
    """Create a new GitHub repo and link it to the project."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.root_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_path configured",
        )

    pat = await github_service.get_effective_pat(project)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    # Create the repository
    repo = await github_service.create_repo(
        pat=pat,
        name=request.name,
        description=request.description,
        private=request.private,
    )

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create repository",
        )

    # Initialize git and set remote
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "--git-dir",
            cwd=project.root_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        if proc.returncode != 0:
            proc = await asyncio.create_subprocess_exec(
                "git", "init",
                cwd=project.root_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

        # Set remote origin
        proc = await asyncio.create_subprocess_exec(
            "git", "remote", "remove", "origin",
            cwd=project.root_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        proc = await asyncio.create_subprocess_exec(
            "git", "remote", "add", "origin", repo["clone_url"],
            cwd=project.root_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

    except Exception as e:
        logger.error("Failed to initialize git", error=str(e))
        # Don't fail - repo was created successfully

    # Update project
    project.github_repo_url = repo["clone_url"]
    await db.flush()

    logger.info(
        "GitHub repo created and linked",
        user_id=current_user.sub,
        project_id=project_id,
        repo=repo["full_name"],
    )

    return GitHubRepo(**repo)


# === Pull Requests ===


@router.get("/projects/{project_id}/pulls", response_model=list[GitHubPullRequest])
async def list_pull_requests(
    project_id: str,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
    state: str = Query("open", regex="^(open|closed|all)$"),
) -> list[GitHubPullRequest]:
    """List pull requests for the project's repository."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.github_repo_url:
        return []

    parsed = GitHubService.parse_repo_url(project.github_repo_url)
    if not parsed:
        return []

    pat = await github_service.get_effective_pat(project)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    prs = await github_service.list_pull_requests(
        pat=pat,
        owner=parsed[0],
        repo=parsed[1],
        state=state,
    )
    return [GitHubPullRequest(**pr) for pr in prs]


@router.post(
    "/projects/{project_id}/pulls",
    response_model=GitHubPullRequest,
    status_code=status.HTTP_201_CREATED,
)
async def create_pull_request(
    project_id: str,
    request: CreatePRRequest,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitHubPullRequest:
    """Create a pull request."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.github_repo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no linked repository",
        )

    if not project.root_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_path configured",
        )

    parsed = GitHubService.parse_repo_url(project.github_repo_url)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository URL",
        )

    pat = await github_service.get_effective_pat(project)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    # Get current branch if head not specified
    head = request.head
    if not head:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                cwd=project.root_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                head = stdout.decode().strip()
            else:
                head = "main"
        except Exception:
            head = "main"

    pr = await github_service.create_pull_request(
        pat=pat,
        owner=parsed[0],
        repo=parsed[1],
        title=request.title,
        head=head,
        base=request.base,
        body=request.body,
        draft=request.draft,
    )

    if not pr:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create pull request",
        )

    logger.info(
        "Pull request created",
        user_id=current_user.sub,
        project_id=project_id,
        pr_number=pr["number"],
    )

    return GitHubPullRequest(**pr)


@router.get("/projects/{project_id}/pulls/{number}", response_model=GitHubPullRequest)
async def get_pull_request(
    project_id: str,
    number: int,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitHubPullRequest:
    """Get pull request details."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.github_repo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project has no linked repository",
        )

    parsed = GitHubService.parse_repo_url(project.github_repo_url)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository URL",
        )

    pat = await github_service.get_effective_pat(project)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    pr = await github_service.get_pull_request(
        pat=pat,
        owner=parsed[0],
        repo=parsed[1],
        number=number,
    )

    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull request #{number} not found",
        )

    return GitHubPullRequest(**pr)


@router.post("/projects/{project_id}/pulls/{number}/merge", response_model=MergePRResponse)
async def merge_pull_request(
    project_id: str,
    number: int,
    request: MergePRRequest,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> MergePRResponse:
    """Merge a pull request."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.github_repo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no linked repository",
        )

    parsed = GitHubService.parse_repo_url(project.github_repo_url)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository URL",
        )

    pat = await github_service.get_effective_pat(project)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    result = await github_service.merge_pull_request(
        pat=pat,
        owner=parsed[0],
        repo=parsed[1],
        number=number,
        merge_method=request.merge_method,
        commit_message=request.commit_message,
    )

    logger.info(
        "Pull request merge attempted",
        user_id=current_user.sub,
        project_id=project_id,
        pr_number=number,
        success=result["success"],
    )

    return MergePRResponse(**result)


# === Issues ===


@router.get("/projects/{project_id}/issues", response_model=list[GitHubIssue])
async def list_issues(
    project_id: str,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
    state: str = Query("open", regex="^(open|closed|all)$"),
    labels: str | None = Query(None),
) -> list[GitHubIssue]:
    """List issues for the project's repository."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.github_repo_url:
        return []

    parsed = GitHubService.parse_repo_url(project.github_repo_url)
    if not parsed:
        return []

    pat = await github_service.get_effective_pat(project)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    label_list = labels.split(",") if labels else None

    issues = await github_service.list_issues(
        pat=pat,
        owner=parsed[0],
        repo=parsed[1],
        state=state,
        labels=label_list,
    )
    return [GitHubIssue(**issue) for issue in issues]


@router.post(
    "/projects/{project_id}/issues",
    response_model=GitHubIssue,
    status_code=status.HTTP_201_CREATED,
)
async def create_issue(
    project_id: str,
    request: CreateIssueRequest,
    current_user: CurrentUserDep,
    github_service: GitHubServiceDep,
    db: AsyncSession = Depends(get_db_session),
) -> GitHubIssue:
    """Create an issue."""
    project = await get_project_with_auth(project_id, current_user, db)

    if not project.github_repo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no linked repository",
        )

    parsed = GitHubService.parse_repo_url(project.github_repo_url)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository URL",
        )

    pat = await github_service.get_effective_pat(project)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No GitHub PAT configured",
        )

    issue = await github_service.create_issue(
        pat=pat,
        owner=parsed[0],
        repo=parsed[1],
        title=request.title,
        body=request.body,
        labels=request.labels,
    )

    if not issue:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issue",
        )

    logger.info(
        "Issue created",
        user_id=current_user.sub,
        project_id=project_id,
        issue_number=issue["number"],
    )

    return GitHubIssue(**issue)
