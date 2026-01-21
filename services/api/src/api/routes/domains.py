"""
Domain management routes.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import DomainStatus, get_logger
from ai_messaging import RedisClient

from ..database import get_db_session
from ..dependencies import AdminUserDep, CurrentUserDep, get_redis
from ..schemas import DomainCreate, DomainResponse, DomainUpdate, SuccessResponse
from ..services.domain_service import DomainService

logger = get_logger(__name__)

router = APIRouter(prefix="/domains", tags=["Domains"])


async def get_domain_service(
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
) -> DomainService:
    """Get domain service instance."""
    return DomainService(db, redis)


@router.get("", response_model=list[DomainResponse])
async def list_domains(
    current_user: CurrentUserDep,
    domain_service: DomainService = Depends(get_domain_service),
    status_filter: DomainStatus | None = Query(None, alias="status"),
    project_id: str | None = Query(None, description="Filter by project ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[DomainResponse]:
    """
    List all managed domains.
    """
    domains = await domain_service.list_domains(
        status=status_filter,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    # Build response with project_name
    result = []
    for d in domains:
        response = DomainResponse.model_validate(d)
        if d.project:
            response.project_name = d.project.name
        result.append(response)
    return result


@router.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(
    request: DomainCreate,
    current_user: AdminUserDep,  # Only admins can create domains
    domain_service: DomainService = Depends(get_domain_service),
) -> DomainResponse:
    """
    Create a new domain configuration.

    This creates the database record. Use POST /domains/{name}/provision
    to actually set up the domain on the server.
    """
    try:
        domain = await domain_service.create_domain(
            domain_name=request.domain_name,
            proxy_target=request.proxy_target,
            web_root=request.web_root,
            ssl_enabled=request.ssl_enabled,
            dns_provider=request.dns_provider,
            project_id=request.project_id,
        )
        response = DomainResponse.model_validate(domain)
        if domain.project:
            response.project_name = domain.project.name
        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{domain_name}", response_model=DomainResponse)
async def get_domain(
    domain_name: str,
    current_user: CurrentUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> DomainResponse:
    """
    Get domain details by name.
    """
    domain = await domain_service.get_domain(domain_name)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_name} not found",
        )

    return DomainResponse.model_validate(domain)


@router.put("/{domain_name}", response_model=DomainResponse)
async def update_domain(
    domain_name: str,
    request: DomainUpdate,
    current_user: AdminUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> DomainResponse:
    """
    Update domain configuration.
    """
    try:
        # Only include non-None values
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        domain = await domain_service.update_domain(domain_name, **updates)
        return DomainResponse.model_validate(domain)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/{domain_name}", response_model=SuccessResponse)
async def delete_domain(
    domain_name: str,
    current_user: AdminUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> SuccessResponse:
    """
    Delete a domain configuration.

    This only removes the database record. The actual server cleanup
    should be handled separately via the Infra Agent.
    """
    deleted = await domain_service.delete_domain(domain_name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_name} not found",
        )

    return SuccessResponse(message=f"Domain {domain_name} deleted")


@router.post("/{domain_name}/provision", response_model=dict[str, Any])
async def provision_domain(
    domain_name: str,
    current_user: AdminUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> dict[str, Any]:
    """
    Provision a domain on the server.

    This triggers the Infra Agent to:
    - Create web root directory
    - Configure Nginx virtual host
    - Request SSL certificate
    - Set up DNS (if applicable)
    """
    try:
        result = await domain_service.provision_domain(domain_name)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{domain_name}/verify", response_model=dict[str, Any])
async def verify_domain(
    domain_name: str,
    current_user: CurrentUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> dict[str, Any]:
    """
    Verify domain accessibility and SSL configuration.
    """
    result = await domain_service.verify_domain(domain_name)
    return result


@router.post("/{domain_name}/ssl/renew", response_model=dict[str, Any])
async def renew_ssl(
    domain_name: str,
    current_user: AdminUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> dict[str, Any]:
    """
    Force SSL certificate renewal for a domain.
    """
    result = await domain_service.renew_ssl(domain_name)
    return result


@router.post("/{domain_name}/deploy", response_model=dict[str, Any])
async def deploy_domain(
    domain_name: str,
    current_user: AdminUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> dict[str, Any]:
    """
    Deploy/provision a domain on the server.

    Alias for /provision endpoint for frontend compatibility.
    Triggers the Infra Agent to set up the domain infrastructure.
    """
    try:
        result = await domain_service.provision_domain(domain_name)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{domain_name}/sync", response_model=dict[str, Any])
async def sync_domain_config(
    domain_name: str,
    current_user: AdminUserDep,
    domain_service: DomainService = Depends(get_domain_service),
) -> dict[str, Any]:
    """
    Sync domain configuration from nginx config file.

    Asks the Infra Agent to read the nginx config and update
    the domain record with web_root and other values.
    """
    result = await domain_service.sync_domain_config(domain_name)
    return result
