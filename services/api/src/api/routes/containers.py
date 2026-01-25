"""
Container management routes for Dockerized project environments.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from database.models import Project

from ..database import get_db_session
from ..dependencies import CurrentUserDep
from ..services.container_service import (
    ContainerConfig,
    ContainerService,
    ContainerStatus,
    ProjectType,
    container_service,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}/container", tags=["Containers"])


class ContainerActionResponse(BaseModel):
    """Response for container actions."""
    success: bool
    status: str | None = None
    message: str | None = None
    error: str | None = None


class ContainerInfoResponse(BaseModel):
    """Response with container information."""
    exists: bool
    status: str | None = None
    running: bool = False
    image: str | None = None
    memory_limit: int | None = None
    cpu_limit: int | None = None
    error: str | None = None


async def get_project_with_docker(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession,
) -> Project:
    """Get project and verify Docker is enabled."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.sub,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.docker_enabled:
        raise HTTPException(
            status_code=400,
            detail="Docker is not enabled for this project. Enable it in project settings."
        )

    return project


def build_container_config(project: Project) -> ContainerConfig:
    """Build ContainerConfig from project settings."""
    # Parse exposed ports
    expose_ports = None
    if project.docker_expose_ports:
        try:
            ports_str = project.docker_expose_ports
            expose_ports = [int(p.strip()) for p in ports_str.split(",") if p.strip()]
        except (ValueError, json.JSONDecodeError):
            pass

    # Parse environment variables
    env_vars = None
    if project.docker_env_vars:
        try:
            # Parse KEY=value format
            env_vars = {}
            for line in project.docker_env_vars.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        except Exception:
            pass

    # Map project type string to enum
    project_type = ProjectType.CUSTOM
    if project.docker_project_type:
        try:
            project_type = ProjectType(project.docker_project_type)
        except ValueError:
            pass

    return ContainerConfig(
        project_id=project.id,
        project_name=project.name,
        project_type=project_type,
        root_path=project.root_path or "/tmp",
        node_version=project.docker_node_version or "20",
        php_version=project.docker_php_version or "8.3",
        python_version=project.docker_python_version or "3.12",
        memory_limit=project.docker_memory_limit or "2g",
        cpu_limit=project.docker_cpu_limit or "2.0",
        expose_ports=expose_ports,
        env_vars=env_vars,
    )


@router.get("/status", response_model=ContainerInfoResponse)
async def get_container_status(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerInfoResponse:
    """Get the current status of a project's container."""
    project = await get_project_with_docker(project_id, current_user, db)

    info = await container_service.get_container_info(project_id)

    return ContainerInfoResponse(
        exists=info.get("exists", False),
        status=info.get("status"),
        running=info.get("running", False),
        image=info.get("image"),
        memory_limit=info.get("memory_limit"),
        cpu_limit=info.get("cpu_limit"),
        error=info.get("error"),
    )


@router.post("/start", response_model=ContainerActionResponse)
async def start_container(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerActionResponse:
    """Start or create a project's container."""
    project = await get_project_with_docker(project_id, current_user, db)

    # Check current status
    status = await container_service.get_status(project_id)

    if status == ContainerStatus.RUNNING:
        return ContainerActionResponse(
            success=True,
            status="running",
            message="Container is already running",
        )

    if status == ContainerStatus.NOT_FOUND:
        # Create container first
        config = build_container_config(project)
        create_result = await container_service.create_container(config)

        if not create_result.get("success"):
            return ContainerActionResponse(
                success=False,
                error=create_result.get("error", "Failed to create container"),
            )

    # Start container
    start_result = await container_service.start_container(project_id)

    if start_result.get("success"):
        # Update project status
        project.docker_container_status = "running"
        await db.commit()

        return ContainerActionResponse(
            success=True,
            status="running",
            message="Container started successfully",
        )
    else:
        return ContainerActionResponse(
            success=False,
            error=start_result.get("error", "Failed to start container"),
        )


@router.post("/stop", response_model=ContainerActionResponse)
async def stop_container(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerActionResponse:
    """Stop a project's container."""
    project = await get_project_with_docker(project_id, current_user, db)

    result = await container_service.stop_container(project_id)

    if result.get("success"):
        project.docker_container_status = "stopped"
        await db.commit()

        return ContainerActionResponse(
            success=True,
            status="stopped",
            message="Container stopped successfully",
        )
    else:
        return ContainerActionResponse(
            success=False,
            error=result.get("error", "Failed to stop container"),
        )


@router.post("/rebuild", response_model=ContainerActionResponse)
async def rebuild_container(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerActionResponse:
    """Rebuild a project's container with updated settings."""
    project = await get_project_with_docker(project_id, current_user, db)

    # Update status to building
    project.docker_container_status = "building"
    await db.commit()

    # Remove existing container
    await container_service.remove_container(project_id)

    # Build new image and create container
    config = build_container_config(project)

    build_result = await container_service.build_image(config)
    if not build_result.get("success"):
        project.docker_container_status = "error"
        await db.commit()
        return ContainerActionResponse(
            success=False,
            error=build_result.get("error", "Failed to build image"),
        )

    create_result = await container_service.create_container(config)
    if not create_result.get("success"):
        project.docker_container_status = "error"
        await db.commit()
        return ContainerActionResponse(
            success=False,
            error=create_result.get("error", "Failed to create container"),
        )

    # Start the new container
    start_result = await container_service.start_container(project_id)
    if start_result.get("success"):
        project.docker_container_status = "running"
        await db.commit()
        return ContainerActionResponse(
            success=True,
            status="running",
            message="Container rebuilt and started successfully",
        )
    else:
        project.docker_container_status = "stopped"
        await db.commit()
        return ContainerActionResponse(
            success=True,
            status="stopped",
            message="Container rebuilt but not started",
        )


@router.delete("/", response_model=ContainerActionResponse)
async def remove_container(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerActionResponse:
    """Remove a project's container."""
    project = await get_project_with_docker(project_id, current_user, db)

    result = await container_service.remove_container(project_id)

    if result.get("success"):
        project.docker_container_status = None
        await db.commit()

        return ContainerActionResponse(
            success=True,
            message="Container removed successfully",
        )
    else:
        return ContainerActionResponse(
            success=False,
            error=result.get("error", "Failed to remove container"),
        )


@router.get("/logs")
async def get_container_logs(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    tail: int = 100,
) -> dict[str, Any]:
    """Get recent logs from a project's container."""
    await get_project_with_docker(project_id, current_user, db)

    logs = await container_service.get_container_logs(project_id, tail)

    return {"logs": logs}
