"""
Schemas for visual builder integrations (GrapesJS, NocoBase, Webstudio, Mobirise).
"""

from enum import Enum

from pydantic import BaseModel, Field


# --- Template Library Schemas ---


class TemplateCategory(str, Enum):
    LAYOUT = "layout"
    COMPONENT = "component"
    PAGE = "page"
    SECTION = "section"
    FORM = "form"
    NAVIGATION = "navigation"
    FOOTER = "footer"
    HERO = "hero"
    CUSTOM = "custom"


class TemplateCreate(BaseModel):
    """Create a new template/block."""

    name: str = Field(..., min_length=1, max_length=255)
    category: TemplateCategory = TemplateCategory.CUSTOM
    description: str | None = None
    html: str = Field(..., min_length=1)
    css: str | None = None
    js: str | None = None
    thumbnail_url: str | None = None
    tags: list[str] = []
    is_public: bool = True


class TemplateUpdate(BaseModel):
    """Update an existing template."""

    name: str | None = Field(None, min_length=1, max_length=255)
    category: TemplateCategory | None = None
    description: str | None = None
    html: str | None = None
    css: str | None = None
    js: str | None = None
    thumbnail_url: str | None = None
    tags: list[str] | None = None
    is_public: bool | None = None


class TemplateResponse(BaseModel):
    """Template response."""

    id: str
    name: str
    category: TemplateCategory
    description: str | None = None
    html: str
    css: str | None = None
    js: str | None = None
    thumbnail_url: str | None = None
    tags: list[str] = []
    is_public: bool = True
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TemplateListResponse(BaseModel):
    """List of templates."""

    templates: list[TemplateResponse]
    total: int
    page: int = 1
    per_page: int = 50


class GrapesJSBlock(BaseModel):
    """GrapesJS block format for the Block Manager."""

    id: str
    label: str
    category: str
    content: str
    attributes: dict | None = None


class GrapesJSBlocksResponse(BaseModel):
    """Response with blocks in GrapesJS format."""

    blocks: list[GrapesJSBlock]


# --- NocoBase Integration Schemas ---


class NocoBaseCollectionField(BaseModel):
    """Field definition for a NocoBase collection."""

    name: str
    type: str = "string"  # string, integer, float, boolean, date, text, json
    title: str | None = None
    required: bool = False
    unique: bool = False
    default_value: str | None = None


class NocoBaseCollectionCreate(BaseModel):
    """Create a NocoBase collection (table/model)."""

    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    title: str | None = None
    fields: list[NocoBaseCollectionField] = []


class NocoBaseCollectionResponse(BaseModel):
    """NocoBase collection info."""

    name: str
    title: str | None = None
    fields: list[NocoBaseCollectionField] = []
    created_at: str | None = None


class NocoBaseProxyRequest(BaseModel):
    """Proxy a request to NocoBase API."""

    method: str = "GET"
    path: str = Field(..., min_length=1)
    body: dict | None = None
    params: dict | None = None


class NocoBaseProxyResponse(BaseModel):
    """Response from NocoBase proxy."""

    status_code: int
    data: dict | list | None = None
    error: str | None = None


class NocoBaseAppCreate(BaseModel):
    """Create a NocoBase app for a project."""

    app_name: str = Field(..., min_length=1, max_length=100)


class NocoBaseAppResponse(BaseModel):
    """NocoBase app info."""

    app_name: str
    url: str
    api_base: str
    status: str = "running"


# --- Webstudio Integration Schemas ---


class WebstudioExportRequest(BaseModel):
    """Request to export a Webstudio project."""

    project_url: str = Field(..., description="Webstudio project share URL")
    output_format: str = "static"  # static, remix
    output_path: str | None = None  # Relative to project root


class WebstudioExportResponse(BaseModel):
    """Response from Webstudio export."""

    status: str  # running, completed, failed
    output_path: str | None = None
    files_created: int = 0
    message: str | None = None


class WebstudioBuildRequest(BaseModel):
    """Request to build a Webstudio project."""

    project_path: str | None = None  # Path containing .webstudio folder


class WebstudioBuildResponse(BaseModel):
    """Response from Webstudio build."""

    status: str
    build_path: str | None = None
    message: str | None = None


# --- Mobirise AI Workflow Schemas ---


class MobiriseImportRequest(BaseModel):
    """Import Mobirise-generated HTML into the project."""

    source_path: str = Field(..., description="Path to Mobirise export directory")
    target_path: str = Field(default="", description="Target path in project (default: root)")
    import_assets: bool = True


class MobiriseImportResponse(BaseModel):
    """Response from Mobirise import."""

    status: str
    files_imported: int = 0
    html_files: list[str] = []
    asset_files: list[str] = []
    message: str | None = None


# --- Integration Status Schemas ---


class IntegrationStatus(BaseModel):
    """Status of an integration service."""

    name: str
    enabled: bool
    healthy: bool = False
    url: str | None = None
    version: str | None = None
    message: str | None = None


class IntegrationsStatusResponse(BaseModel):
    """Status of all integration services."""

    grapesjs: IntegrationStatus
    nocobase: IntegrationStatus
    webstudio: IntegrationStatus
    mobirise: IntegrationStatus
