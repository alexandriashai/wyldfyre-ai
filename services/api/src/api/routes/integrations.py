"""
Integration routes for visual builders: GrapesJS templates, NocoBase, Webstudio, Mobirise.
"""

import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from database.models import Project

from ..database import get_db_session
from ..dependencies import CurrentUserDep
from ..schemas.integrations import (
    GrapesJSBlock,
    GrapesJSBlocksResponse,
    IntegrationStatus,
    IntegrationsStatusResponse,
    MobiriseImportRequest,
    MobiriseImportResponse,
    NocoBaseAppCreate,
    NocoBaseAppResponse,
    NocoBaseCollectionCreate,
    NocoBaseCollectionResponse,
    NocoBaseProxyRequest,
    NocoBaseProxyResponse,
    TemplateCategory,
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
    WebstudioBuildRequest,
    WebstudioBuildResponse,
    WebstudioExportRequest,
    WebstudioExportResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations"])

# Configuration
NOCOBASE_URL = os.getenv("NOCOBASE_URL", "http://nocobase:13000")
NOCOBASE_API_TOKEN = os.getenv("NOCOBASE_API_TOKEN", "")
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", "/home/wyld-data/templates")
WEBSTUDIO_CLI = os.getenv("WEBSTUDIO_CLI", "npx webstudio")


# --- Helpers ---


def get_templates_path() -> str:
    """Get or create the templates directory."""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    return TEMPLATES_DIR


def load_template(template_id: str) -> dict | None:
    """Load a template from disk."""
    path = os.path.join(get_templates_path(), f"{template_id}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_template(template_id: str, data: dict) -> None:
    """Save a template to disk."""
    path = os.path.join(get_templates_path(), f"{template_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def delete_template_file(template_id: str) -> bool:
    """Delete a template file."""
    path = os.path.join(get_templates_path(), f"{template_id}.json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


async def get_project_root(
    project_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession,
) -> str:
    """Get project root path."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.sub,
        )
    )
    project = result.scalar_one_or_none()
    if not project or not project.root_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or has no root_path",
        )
    return project.root_path


# --- Template Library Endpoints ---


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    request: TemplateCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> TemplateResponse:
    """Create a new reusable template/block."""
    template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    template_data = {
        "id": template_id,
        "name": request.name,
        "category": request.category.value,
        "description": request.description,
        "html": request.html,
        "css": request.css,
        "js": request.js,
        "thumbnail_url": request.thumbnail_url,
        "tags": request.tags,
        "is_public": request.is_public,
        "created_by": current_user.sub,
        "created_at": now,
        "updated_at": now,
    }

    save_template(template_id, template_data)
    logger.info("Template created", template_id=template_id, name=request.name)

    return TemplateResponse(**template_data)


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    category: TemplateCategory | None = None,
    search: str | None = Query(None, min_length=2),
    tag: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> TemplateListResponse:
    """List available templates with optional filtering."""
    templates_path = get_templates_path()
    all_templates: list[dict] = []

    for filename in os.listdir(templates_path):
        if not filename.endswith(".json"):
            continue
        template_id = filename[:-5]
        template = load_template(template_id)
        if template:
            # Filter: only show public templates or own templates
            if template.get("is_public") or template.get("created_by") == current_user.sub:
                all_templates.append(template)

    # Apply filters
    if category:
        all_templates = [t for t in all_templates if t.get("category") == category.value]

    if search:
        search_lower = search.lower()
        all_templates = [
            t for t in all_templates
            if search_lower in t.get("name", "").lower()
            or search_lower in (t.get("description") or "").lower()
        ]

    if tag:
        all_templates = [t for t in all_templates if tag in t.get("tags", [])]

    # Sort by updated_at descending
    all_templates.sort(key=lambda t: t.get("updated_at", ""), reverse=True)

    # Paginate
    total = len(all_templates)
    start = (page - 1) * per_page
    end = start + per_page
    page_templates = all_templates[start:end]

    return TemplateListResponse(
        templates=[TemplateResponse(**t) for t in page_templates],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/templates/blocks/grapesjs", response_model=GrapesJSBlocksResponse)
async def get_grapesjs_blocks(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    category: TemplateCategory | None = None,
) -> GrapesJSBlocksResponse:
    """Get templates formatted as GrapesJS blocks for the Block Manager."""
    templates_path = get_templates_path()
    blocks: list[GrapesJSBlock] = []

    for filename in os.listdir(templates_path):
        if not filename.endswith(".json"):
            continue
        template = load_template(filename[:-5])
        if not template or not template.get("is_public"):
            continue

        if category and template.get("category") != category.value:
            continue

        # Build content with CSS embedded
        content = template["html"]
        if template.get("css"):
            content = f'<style>{template["css"]}</style>{content}'

        blocks.append(GrapesJSBlock(
            id=f'tpl-{template["id"][:8]}',
            label=template["name"],
            category=template.get("category", "custom").title(),
            content=content,
        ))

    return GrapesJSBlocksResponse(blocks=blocks)


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> TemplateResponse:
    """Get a specific template."""
    template = load_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if not template.get("is_public") and template.get("created_by") != current_user.sub:
        raise HTTPException(status_code=403, detail="Access denied")

    return TemplateResponse(**template)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: TemplateUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> TemplateResponse:
    """Update an existing template."""
    template = load_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.get("created_by") != current_user.sub:
        raise HTTPException(status_code=403, detail="Can only update own templates")

    # Apply updates
    update_data = request.model_dump(exclude_unset=True)
    if "category" in update_data and update_data["category"]:
        update_data["category"] = update_data["category"].value

    template.update(update_data)
    template["updated_at"] = datetime.now(timezone.utc).isoformat()

    save_template(template_id, template)
    logger.info("Template updated", template_id=template_id)

    return TemplateResponse(**template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete a template."""
    template = load_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.get("created_by") != current_user.sub:
        raise HTTPException(status_code=403, detail="Can only delete own templates")

    delete_template_file(template_id)
    logger.info("Template deleted", template_id=template_id)

    return {"message": f"Template {template_id} deleted"}


# --- NocoBase Integration Endpoints ---


@router.post("/nocobase/apps", response_model=NocoBaseAppResponse)
async def create_nocobase_app(
    request: NocoBaseAppCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> NocoBaseAppResponse:
    """Create a new NocoBase app instance for a project."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{NOCOBASE_URL}/api/applications:create",
                headers={"Authorization": f"Bearer {NOCOBASE_API_TOKEN}"},
                json={"name": request.app_name},
            )

            if response.status_code >= 400:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"NocoBase error: {response.text}",
                )

            data = response.json()

    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NocoBase service is not available. Ensure it is running.",
        )

    return NocoBaseAppResponse(
        app_name=request.app_name,
        url=f"{NOCOBASE_URL}/apps/{request.app_name}",
        api_base=f"{NOCOBASE_URL}/api/{request.app_name}",
        status="running",
    )


@router.post("/nocobase/collections", response_model=NocoBaseCollectionResponse)
async def create_nocobase_collection(
    request: NocoBaseCollectionCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> NocoBaseCollectionResponse:
    """Create a new collection (data model) in NocoBase."""
    fields_payload = []
    for field in request.fields:
        field_def: dict = {
            "name": field.name,
            "type": field.type,
            "interface": _map_field_type_to_interface(field.type),
        }
        if field.title:
            field_def["uiSchema"] = {"title": field.title}
        if field.required:
            field_def["required"] = True
        if field.unique:
            field_def["unique"] = True
        fields_payload.append(field_def)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{NOCOBASE_URL}/api/collections:create",
                headers={"Authorization": f"Bearer {NOCOBASE_API_TOKEN}"},
                json={
                    "name": request.name,
                    "title": request.title or request.name,
                    "fields": fields_payload,
                },
            )

            if response.status_code >= 400:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"NocoBase error: {response.text}",
                )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NocoBase service is not available",
        )

    return NocoBaseCollectionResponse(
        name=request.name,
        title=request.title,
        fields=request.fields,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/nocobase/proxy", response_model=NocoBaseProxyResponse)
async def nocobase_proxy(
    request: NocoBaseProxyRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> NocoBaseProxyResponse:
    """Proxy requests to the NocoBase REST API."""
    # Validate method
    allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
    if request.method.upper() not in allowed_methods:
        raise HTTPException(status_code=400, detail="Invalid HTTP method")

    # Prevent path traversal
    if ".." in request.path or request.path.startswith("/"):
        clean_path = request.path.lstrip("/")
    else:
        clean_path = request.path

    url = f"{NOCOBASE_URL}/api/{clean_path}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method.upper(),
                url=url,
                headers={"Authorization": f"Bearer {NOCOBASE_API_TOKEN}"},
                json=request.body if request.body else None,
                params=request.params if request.params else None,
            )

            try:
                data = response.json()
            except Exception:
                data = None

            return NocoBaseProxyResponse(
                status_code=response.status_code,
                data=data if isinstance(data, (dict, list)) else None,
                error=str(data) if response.status_code >= 400 else None,
            )

    except httpx.ConnectError:
        return NocoBaseProxyResponse(
            status_code=503,
            error="NocoBase service is not available",
        )


# --- Webstudio Integration Endpoints ---


@router.post(
    "/projects/{project_id}/webstudio/export",
    response_model=WebstudioExportResponse,
)
async def webstudio_export(
    project_id: str,
    request: WebstudioExportRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> WebstudioExportResponse:
    """Export a Webstudio project via CLI."""
    root_path = await get_project_root(project_id, current_user, db)

    output_path = request.output_path or ""
    if output_path:
        # Validate path
        resolved = os.path.realpath(os.path.join(root_path, output_path))
        if not resolved.startswith(os.path.realpath(root_path)):
            raise HTTPException(status_code=400, detail="Invalid output path")
        target_dir = resolved
    else:
        target_dir = root_path

    os.makedirs(target_dir, exist_ok=True)

    try:
        # Link the Webstudio project
        link_proc = await asyncio.create_subprocess_exec(
            *WEBSTUDIO_CLI.split(), "link", request.project_url,
            cwd=target_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, link_err = await asyncio.wait_for(link_proc.communicate(), timeout=60.0)

        if link_proc.returncode != 0:
            return WebstudioExportResponse(
                status="failed",
                message=f"Link failed: {link_err.decode()}",
            )

        # Build/sync the project
        build_cmd = "build" if request.output_format == "static" else "build"
        build_proc = await asyncio.create_subprocess_exec(
            *WEBSTUDIO_CLI.split(), build_cmd,
            cwd=target_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        build_out, build_err = await asyncio.wait_for(build_proc.communicate(), timeout=120.0)

        if build_proc.returncode != 0:
            return WebstudioExportResponse(
                status="failed",
                message=f"Build failed: {build_err.decode()}",
            )

        # Count created files
        files_created = sum(1 for _ in Path(target_dir).rglob("*") if _.is_file())

        return WebstudioExportResponse(
            status="completed",
            output_path=output_path or ".",
            files_created=files_created,
            message="Webstudio project exported successfully",
        )

    except asyncio.TimeoutError:
        return WebstudioExportResponse(
            status="failed",
            message="Webstudio CLI operation timed out",
        )
    except FileNotFoundError:
        return WebstudioExportResponse(
            status="failed",
            message="Webstudio CLI not found. Install with: npm i -g webstudio",
        )


@router.post(
    "/projects/{project_id}/webstudio/build",
    response_model=WebstudioBuildResponse,
)
async def webstudio_build(
    project_id: str,
    request: WebstudioBuildRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> WebstudioBuildResponse:
    """Build a Webstudio project that's already linked."""
    root_path = await get_project_root(project_id, current_user, db)

    project_path = root_path
    if request.project_path:
        resolved = os.path.realpath(os.path.join(root_path, request.project_path))
        if not resolved.startswith(os.path.realpath(root_path)):
            raise HTTPException(status_code=400, detail="Invalid project path")
        project_path = resolved

    # Check for .webstudio folder
    ws_folder = os.path.join(project_path, ".webstudio")
    if not os.path.isdir(ws_folder):
        return WebstudioBuildResponse(
            status="failed",
            message="No .webstudio folder found. Run export first to link a project.",
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            *WEBSTUDIO_CLI.split(), "build",
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)

        if proc.returncode != 0:
            return WebstudioBuildResponse(
                status="failed",
                message=f"Build failed: {stderr.decode()}",
            )

        # Find build output
        build_path = os.path.join(project_path, "build")
        if not os.path.isdir(build_path):
            build_path = os.path.join(project_path, "dist")

        return WebstudioBuildResponse(
            status="completed",
            build_path=os.path.relpath(build_path, root_path) if os.path.isdir(build_path) else None,
            message="Build completed successfully",
        )

    except asyncio.TimeoutError:
        return WebstudioBuildResponse(status="failed", message="Build timed out")
    except FileNotFoundError:
        return WebstudioBuildResponse(
            status="failed",
            message="Webstudio CLI not found. Install with: npm i -g webstudio",
        )


# --- Mobirise AI Workflow Endpoints ---


@router.post(
    "/projects/{project_id}/mobirise/import",
    response_model=MobiriseImportResponse,
)
async def mobirise_import(
    project_id: str,
    request: MobiriseImportRequest,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> MobiriseImportResponse:
    """Import Mobirise-generated HTML/CSS/JS files into a project."""
    root_path = await get_project_root(project_id, current_user, db)

    # Validate source path
    source = os.path.realpath(request.source_path)
    if not os.path.isdir(source):
        raise HTTPException(
            status_code=400,
            detail=f"Source directory not found: {request.source_path}",
        )

    # Determine target
    if request.target_path:
        target = os.path.realpath(os.path.join(root_path, request.target_path))
        if not target.startswith(os.path.realpath(root_path)):
            raise HTTPException(status_code=400, detail="Invalid target path")
    else:
        target = root_path

    os.makedirs(target, exist_ok=True)

    html_files: list[str] = []
    asset_files: list[str] = []
    files_imported = 0

    # Walk the source directory and copy files
    for dirpath, dirnames, filenames in os.walk(source):
        # Skip hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for filename in filenames:
            src_file = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(src_file, source)
            dst_file = os.path.join(target, rel_path)

            # Create parent directory
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)

            # Determine file type
            ext = os.path.splitext(filename)[1].lower()

            if ext in (".html", ".htm"):
                # Copy HTML files
                shutil.copy2(src_file, dst_file)
                html_files.append(rel_path)
                files_imported += 1
            elif request.import_assets and ext in (
                ".css", ".js", ".png", ".jpg", ".jpeg", ".gif",
                ".svg", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot",
            ):
                # Copy asset files
                shutil.copy2(src_file, dst_file)
                asset_files.append(rel_path)
                files_imported += 1

    logger.info(
        "Mobirise import completed",
        project_id=project_id,
        html_files=len(html_files),
        asset_files=len(asset_files),
    )

    return MobiriseImportResponse(
        status="completed",
        files_imported=files_imported,
        html_files=html_files,
        asset_files=asset_files,
        message=f"Imported {len(html_files)} HTML and {len(asset_files)} asset files",
    )


# --- Integration Status Endpoint ---


@router.get("/status", response_model=IntegrationsStatusResponse)
async def get_integrations_status(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> IntegrationsStatusResponse:
    """Get status of all integration services."""

    # Check NocoBase
    nocobase_healthy = False
    nocobase_version = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{NOCOBASE_URL}/api/app:getInfo")
            if resp.status_code == 200:
                nocobase_healthy = True
                info = resp.json()
                nocobase_version = info.get("data", {}).get("version")
    except Exception:
        pass

    # Check Webstudio CLI
    webstudio_available = False
    try:
        proc = await asyncio.create_subprocess_exec(
            *WEBSTUDIO_CLI.split(), "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        if proc.returncode == 0:
            webstudio_available = True
    except Exception:
        pass

    return IntegrationsStatusResponse(
        grapesjs=IntegrationStatus(
            name="GrapesJS",
            enabled=True,
            healthy=True,
            version="0.21.10",
            message="Embedded in frontend (npm package)",
        ),
        nocobase=IntegrationStatus(
            name="NocoBase",
            enabled=bool(NOCOBASE_API_TOKEN),
            healthy=nocobase_healthy,
            url=NOCOBASE_URL,
            version=nocobase_version,
            message="Running" if nocobase_healthy else "Not connected",
        ),
        webstudio=IntegrationStatus(
            name="Webstudio",
            enabled=webstudio_available,
            healthy=webstudio_available,
            message="CLI available" if webstudio_available else "CLI not installed",
        ),
        mobirise=IntegrationStatus(
            name="Mobirise AI",
            enabled=True,
            healthy=True,
            message="Import-only (desktop app generates, platform imports)",
        ),
    )


# --- Helpers ---


def _map_field_type_to_interface(field_type: str) -> str:
    """Map simple field types to NocoBase interface types."""
    mapping = {
        "string": "input",
        "text": "textarea",
        "integer": "integer",
        "float": "number",
        "boolean": "checkbox",
        "date": "datetime",
        "json": "json",
    }
    return mapping.get(field_type, "input")
