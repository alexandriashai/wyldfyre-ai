"""
TELOS routes for managing mission, beliefs, narratives, and goals.

Supports both system-level (global) and project-level TELOS.
Includes a wizard chat endpoint for guided content creation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ai_core import LLMClient, get_logger

from ..dependencies import AdminUserDep, CurrentUserDep, DbSessionDep

logger = get_logger(__name__)

router = APIRouter(prefix="/telos", tags=["TELOS"])

# TELOS directory paths
SYSTEM_TELOS_DIR = Path("/home/wyld-core/pai/TELOS")
PROJECT_TELOS_SUBDIR = "projects"

# Static files that can be edited via wizard
STATIC_FILES = ["MISSION.md", "BELIEFS.md", "NARRATIVES.md", "MODELS.md"]

# Dynamic files (auto-populated by system)
DYNAMIC_FILES = ["GOALS.md", "PROJECTS.md", "CHALLENGES.md", "IDEAS.md", "LEARNED.md", "STRATEGIES.md"]

# All TELOS files
ALL_FILES = STATIC_FILES + DYNAMIC_FILES


# === Models ===

class TelosFile(BaseModel):
    """A TELOS file."""
    filename: str
    content: str
    is_static: bool
    last_modified: str | None = None


class TelosFileList(BaseModel):
    """List of TELOS files."""
    files: list[dict[str, Any]]
    scope: str  # "system" or "project"
    project_id: str | None = None


class UpdateTelosFileRequest(BaseModel):
    """Request to update a TELOS file."""
    content: str = Field(..., max_length=20000, description="File content (max 20000 characters)")
    project_id: str | None = None


class WizardMessage(BaseModel):
    """A message in the wizard chat."""
    role: str  # "user" or "assistant"
    content: str


class WizardChatRequest(BaseModel):
    """Request for wizard chat."""
    messages: list[WizardMessage]
    target_file: str  # MISSION, BELIEFS, NARRATIVES, or MODELS
    project_id: str | None = None  # None = system level
    project_name: str | None = None  # For context in project-level wizard


class WizardChatResponse(BaseModel):
    """Response from wizard chat."""
    message: str
    suggested_content: str | None = None  # When wizard has a draft ready
    is_complete: bool = False  # True when wizard has final content


# === Wizard System Prompts ===

WIZARD_PROMPTS = {
    "MISSION": """You are a TELOS Mission Consultant helping define an organization's or project's core mission.

Your role is to:
1. Ask thoughtful, probing questions ONE AT A TIME
2. Listen carefully and reflect back what you hear
3. Help them discover and articulate what truly matters
4. Eventually synthesize their answers into a well-structured MISSION.md

{scope_context}

Current conversation stage: Guide them through these areas (in order):
1. **The Problem**: What frustration or gap led to this? What's broken today?
2. **The Vision**: When this works perfectly, what does that look like?
3. **The Beneficiaries**: Who benefits most? How does their life improve?
4. **The Unique Approach**: What makes your approach different?

When you have enough information to draft a mission statement:
- Propose a draft and ask for feedback
- Refine based on their input
- When they approve, output the final content in a code block marked ```mission

Keep questions conversational and one at a time. Never rush.""",

    "BELIEFS": """You are a TELOS Values Consultant helping define core beliefs and principles.

Your role is to:
1. Ask thoughtful questions about values and principles ONE AT A TIME
2. Help them discover what they truly believe through examples and tradeoffs
3. Synthesize into a structured BELIEFS.md

{scope_context}

Guide them through:
1. **Core Values**: What 3-5 values are non-negotiable? Ask for examples.
2. **Tradeoffs**: When values conflict (speed vs quality, autonomy vs safety), which wins?
3. **Red Lines**: What would you NEVER do, even if convenient?
4. **Guiding Principles**: What rules should guide daily decisions?

When ready, propose a draft in a code block marked ```beliefs
Refine based on feedback until approved.""",

    "NARRATIVES": """You are a TELOS Narrative Consultant helping capture the story and context.

Your role is to:
1. Draw out the origin story and important context
2. Understand what background an AI assistant needs to know
3. Capture the narrative in a structured NARRATIVES.md

{scope_context}

Guide them through:
1. **Origin Story**: How did this start? What was the catalyst moment?
2. **Key Context**: What does someone need to know to understand this project/org?
3. **Domain Knowledge**: What industry/technical context is essential?
4. **Stakeholders**: Who are the key people or groups involved?

When ready, propose a draft in a code block marked ```narratives
This helps the AI understand the "why" behind everything.""",

    "MODELS": """You are a TELOS Mental Models Consultant helping define thinking frameworks.

Your role is to:
1. Identify the mental models and frameworks that guide decision-making
2. Document how problems should be approached
3. Create a MODELS.md that shapes AI reasoning

{scope_context}

Guide them through:
1. **Decision Frameworks**: How do you evaluate options? What criteria matter?
2. **Problem-Solving Approach**: Exploration-first? Iterative? Test-driven?
3. **Quality Standards**: What does "good enough" look like? When to polish vs ship?
4. **Learning Philosophy**: How should mistakes be handled? How to improve?

When ready, propose a draft in a code block marked ```models
These models will guide how the AI thinks about problems.""",
}


def _get_scope_context(project_id: str | None, project_name: str | None) -> str:
    """Get scope-specific context for wizard prompts."""
    if project_id:
        name = project_name or "this project"
        return f"""SCOPE: Project-level TELOS for "{name}"
Focus on project-specific context. This complements (doesn't replace) the system-level TELOS.
Ask about what makes THIS project unique and what context is specific to it."""
    else:
        return """SCOPE: System-level TELOS (organization-wide)
Focus on organization-wide mission, values, and context that apply to ALL projects.
This is the foundation that all project-level TELOS builds upon."""


# === Helper Functions ===

def _get_telos_path(project_id: str | None = None) -> Path:
    """Get the TELOS directory path for system or project."""
    if project_id:
        return SYSTEM_TELOS_DIR / PROJECT_TELOS_SUBDIR / project_id
    return SYSTEM_TELOS_DIR


async def _read_telos_file(filename: str, project_id: str | None = None) -> str | None:
    """Read a TELOS file."""
    telos_dir = _get_telos_path(project_id)
    file_path = telos_dir / filename

    if not file_path.exists():
        return None

    async with aiofiles.open(file_path, "r") as f:
        return await f.read()


async def _write_telos_file(filename: str, content: str, project_id: str | None = None) -> None:
    """Write a TELOS file with timestamp."""
    telos_dir = _get_telos_path(project_id)
    telos_dir.mkdir(parents=True, exist_ok=True)

    file_path = telos_dir / filename

    # Add timestamp footer
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if not content.rstrip().endswith("---"):
        content = content.rstrip() + f"\n\n---\n*Last updated: {timestamp}*\n"

    async with aiofiles.open(file_path, "w") as f:
        await f.write(content)


async def _get_project_info(db, project_id: str) -> dict[str, Any] | None:
    """Get project info from database."""
    try:
        from sqlalchemy import select
        from database.models.project import Project

        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            return {
                "id": project.id,
                "name": project.name,
                "root_path": project.root_path,
            }
    except Exception as e:
        logger.warning("Failed to get project info", project_id=project_id, error=str(e))
    return None


# === Routes ===

@router.get("/files")
async def list_telos_files(
    current_user: AdminUserDep,
    project_id: str | None = Query(None, description="Project ID for project-level TELOS"),
) -> TelosFileList:
    """
    List all TELOS files for system or project level.

    System level: Returns global TELOS files
    Project level: Returns project-specific TELOS files
    """
    telos_dir = _get_telos_path(project_id)
    files = []

    for filename in ALL_FILES:
        file_path = telos_dir / filename
        exists = file_path.exists()

        file_info = {
            "filename": filename,
            "exists": exists,
            "is_static": filename in STATIC_FILES,
            "last_modified": None,
        }

        if exists:
            stat = file_path.stat()
            file_info["last_modified"] = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

        files.append(file_info)

    return TelosFileList(
        files=files,
        scope="project" if project_id else "system",
        project_id=project_id,
    )


@router.get("/file/{filename}")
async def get_telos_file(
    filename: str,
    current_user: AdminUserDep,
    project_id: str | None = Query(None, description="Project ID for project-level TELOS"),
) -> TelosFile:
    """
    Get a specific TELOS file's content.
    """
    if filename not in ALL_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid TELOS file: {filename}. Valid files: {ALL_FILES}",
        )

    content = await _read_telos_file(filename, project_id)

    if content is None:
        # Return empty content for non-existent files
        content = f"# {filename.replace('.md', '')}\n\n*Not yet configured. Use the wizard to set this up.*\n"

    telos_dir = _get_telos_path(project_id)
    file_path = telos_dir / filename
    last_modified = None
    if file_path.exists():
        stat = file_path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    return TelosFile(
        filename=filename,
        content=content,
        is_static=filename in STATIC_FILES,
        last_modified=last_modified,
    )


@router.put("/file/{filename}")
async def update_telos_file(
    filename: str,
    request: UpdateTelosFileRequest,
    current_user: AdminUserDep,
) -> dict[str, Any]:
    """
    Update a TELOS file's content.
    """
    if filename not in ALL_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid TELOS file: {filename}. Valid files: {ALL_FILES}",
        )

    await _write_telos_file(filename, request.content, request.project_id)

    logger.info(
        "TELOS file updated",
        filename=filename,
        project_id=request.project_id,
        user_id=current_user.sub,
    )

    return {
        "message": f"{filename} updated successfully",
        "filename": filename,
        "scope": "project" if request.project_id else "system",
    }


@router.post("/wizard/chat")
async def wizard_chat(
    request: WizardChatRequest,
    current_user: AdminUserDep,
    db: DbSessionDep,
) -> WizardChatResponse:
    """
    Chat with the TELOS wizard for guided content creation.

    The wizard asks probing questions to help articulate mission, beliefs, etc.
    When complete, it provides suggested content for the target file.
    """
    target = request.target_file.upper().replace(".MD", "")
    if target not in WIZARD_PROMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target file: {target}. Valid: {list(WIZARD_PROMPTS.keys())}",
        )

    # Get project info if project-level
    project_name = request.project_name
    if request.project_id and not project_name:
        project_info = await _get_project_info(db, request.project_id)
        if project_info:
            project_name = project_info.get("name")

    # Build system prompt with scope context
    scope_context = _get_scope_context(request.project_id, project_name)
    system_prompt = WIZARD_PROMPTS[target].format(scope_context=scope_context)

    # Convert messages to LLM format
    llm_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
    ]

    # Call LLM
    llm = LLMClient()
    try:
        response = await llm.create_message(
            model="balanced",  # Use balanced for thoughtful responses
            max_tokens=1500,
            system=system_prompt,
            messages=llm_messages,
        )
        assistant_message = response.text_content
    except Exception as e:
        logger.error("Wizard LLM call failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Wizard chat failed: {str(e)}",
        )

    # Check if the response contains final content
    suggested_content = None
    is_complete = False

    # Look for code block with final content
    code_markers = [f"```{target.lower()}", "```markdown", "```md"]
    for marker in code_markers:
        if marker in assistant_message.lower():
            # Extract content from code block
            parts = assistant_message.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Inside code block
                    # Remove language identifier if present
                    lines = part.strip().split("\n")
                    if lines[0].lower() in [target.lower(), "markdown", "md", ""]:
                        lines = lines[1:]
                    suggested_content = "\n".join(lines).strip()
                    is_complete = True
                    break
            break

    return WizardChatResponse(
        message=assistant_message,
        suggested_content=suggested_content,
        is_complete=is_complete,
    )


@router.post("/wizard/save")
async def wizard_save(
    target_file: str,
    content: str,
    current_user: AdminUserDep,
    project_id: str | None = Query(None),
) -> dict[str, Any]:
    """
    Save wizard-generated content to a TELOS file.
    """
    filename = target_file.upper()
    if not filename.endswith(".md"):
        filename += ".md"

    if filename not in STATIC_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Wizard can only save to static files: {STATIC_FILES}",
        )

    await _write_telos_file(filename, content, project_id)

    logger.info(
        "TELOS wizard content saved",
        filename=filename,
        project_id=project_id,
        user_id=current_user.sub,
    )

    return {
        "message": f"{filename} saved successfully",
        "filename": filename,
        "scope": "project" if project_id else "system",
    }


@router.get("/context")
async def get_telos_context(
    current_user: CurrentUserDep,
    project_id: str | None = Query(None, description="Project ID for merged context"),
    task_type: str | None = Query(None, description="Task type for relevance filtering"),
) -> dict[str, Any]:
    """
    Get formatted TELOS context for agent injection.

    Returns merged global + project TELOS in a format suitable for
    injection into agent system prompts.
    """
    context_parts = []

    # Load system TELOS
    mission = await _read_telos_file("MISSION.md")
    if mission:
        # Extract first meaningful paragraph
        lines = [l for l in mission.split("\n") if l.strip() and not l.startswith("#")]
        if lines:
            context_parts.append(f"[Mission] {lines[0][:200]}")

    beliefs = await _read_telos_file("BELIEFS.md")
    if beliefs:
        lines = [l for l in beliefs.split("\n") if l.strip() and l.startswith("-")]
        if lines:
            context_parts.append(f"[Beliefs] {' '.join(lines[:3])[:200]}")

    # Load project TELOS if specified
    if project_id:
        project_context = await _read_telos_file("MISSION.md", project_id)
        if project_context:
            lines = [l for l in project_context.split("\n") if l.strip() and not l.startswith("#")]
            if lines:
                context_parts.append(f"[Project Context] {lines[0][:200]}")

    return {
        "context": "\n".join(context_parts),
        "scope": "project" if project_id else "system",
        "project_id": project_id,
    }
