"""
Project management routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from ai_db import Task
from database.models import Conversation, Domain, Project, ProjectStatus

from ..database import get_db_session
from ..dependencies import CurrentUserDep
from ..schemas.project import (
    ProjectContextResponse,
    ProjectCreate,
    ProjectDomainInfo,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithStatsResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    status_filter: ProjectStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ProjectListResponse:
    """
    List projects for the current user.
    """
    # Build query
    query = select(Project).where(Project.user_id == current_user.sub)

    if status_filter:
        query = query.where(Project.status == status_filter)

    # Get total count
    count_query = select(func.count(Project.id)).where(Project.user_id == current_user.sub)
    if status_filter:
        count_query = count_query.where(Project.status == status_filter)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Apply pagination
    query = (
        query.order_by(Project.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    projects = list(result.scalars().all())

    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """
    Create a new project.
    """
    project = Project(
        name=request.name,
        description=request.description,
        agent_context=request.agent_context,
        color=request.color,
        icon=request.icon,
        user_id=current_user.sub,
    )

    db.add(project)
    await db.flush()
    await db.refresh(project)

    logger.info(
        "Project created",
        project_id=project.id,
        user_id=current_user.sub,
        name=request.name,
    )

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectWithStatsResponse)
async def get_project(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectWithStatsResponse:
    """
    Get project details with statistics.
    """
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

    # Get conversation count
    conv_count_result = await db.execute(
        select(func.count(Conversation.id)).where(Conversation.project_id == project_id)
    )
    conversation_count = conv_count_result.scalar() or 0

    # Get task count
    task_count_result = await db.execute(
        select(func.count(Task.id)).where(Task.project_id == project_id)
    )
    task_count = task_count_result.scalar() or 0

    # Get domain count
    domain_count_result = await db.execute(
        select(func.count(Domain.id)).where(Domain.project_id == project_id)
    )
    domain_count = domain_count_result.scalar() or 0

    return ProjectWithStatsResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        agent_context=project.agent_context,
        status=project.status,
        color=project.color,
        icon=project.icon,
        user_id=project.user_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        conversation_count=conversation_count,
        task_count=task_count,
        domain_count=domain_count,
        total_cost=0.0,  # TODO: Calculate from API usage
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """
    Update a project.
    """
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

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)

    logger.info(
        "Project updated",
        project_id=project_id,
        user_id=current_user.sub,
    )

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    archive: bool = Query(True, description="Archive instead of hard delete"),
) -> dict[str, str]:
    """
    Delete (archive) a project.

    By default, projects are archived (soft delete). Set archive=false for hard delete.
    """
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

    if archive:
        project.status = ProjectStatus.ARCHIVED
        await db.flush()
        logger.info(
            "Project archived",
            project_id=project_id,
            user_id=current_user.sub,
        )
        return {"message": f"Project {project_id} archived"}
    else:
        await db.delete(project)
        await db.flush()
        logger.info(
            "Project deleted",
            project_id=project_id,
            user_id=current_user.sub,
        )
        return {"message": f"Project {project_id} deleted"}


@router.get("/{project_id}/context", response_model=ProjectContextResponse)
async def get_project_context(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectContextResponse:
    """
    Get full project context for agent injection.

    Returns project details with all associated domains, including
    web roots and other context information for AI agents.
    """
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

    # Get all domains associated with this project
    domains_result = await db.execute(
        select(Domain).where(Domain.project_id == project_id)
    )
    domains = list(domains_result.scalars().all())

    domain_infos = [
        ProjectDomainInfo(
            domain_name=d.domain_name,
            web_root=d.web_root,
            proxy_target=d.proxy_target,
            is_primary=d.is_primary,
            status=d.status.value,
        )
        for d in domains
    ]

    return ProjectContextResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        agent_context=project.agent_context,
        domains=domain_infos,
    )
