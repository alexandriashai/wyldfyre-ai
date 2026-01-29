"""
Browser debug service routes.

REST API endpoints for browser automation control.
"""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ai_core import get_logger
from ai_messaging import RedisClient

from ..dependencies import CurrentUserDep, get_redis

logger = get_logger(__name__)

router = APIRouter(prefix="/browser", tags=["Browser"])

# Redis channels
BROWSER_TASKS_CHANNEL = "browser:tasks"


def event_channel(project_id: str) -> str:
    """Get event channel for project."""
    return f"browser:{project_id}:event"


# Request/Response models

class NavigateRequest(BaseModel):
    """Navigate to URL request."""

    url: str
    wait_until: str = "load"


class ClickRequest(BaseModel):
    """Click action request."""

    selector: str | None = None
    x: int | None = None
    y: int | None = None
    button: str = "left"


class TypeRequest(BaseModel):
    """Type text request."""

    text: str
    selector: str | None = None
    clear: bool = False
    mask: bool = False  # For password fields


class WaitRequest(BaseModel):
    """Wait for element request."""

    selector: str | None = None
    state: str = "visible"
    timeout: int | None = None


class EvaluateRequest(BaseModel):
    """JavaScript evaluation request."""

    expression: str


class ScreenshotRequest(BaseModel):
    """Screenshot request."""

    full_page: bool = False
    quality: int | None = None
    format: str = "jpeg"


class GetContentRequest(BaseModel):
    """Get page content request."""

    selector: str | None = None
    format: str = "text"  # text or html


class FindElementsRequest(BaseModel):
    """Find elements request."""

    selector: str


class BrowserSessionResponse(BaseModel):
    """Browser session info response."""

    project_id: str
    session_id: str | None
    url: str | None
    title: str | None
    is_streaming: bool
    created_at: str | None
    last_used: str | None


class BrowserActionResponse(BaseModel):
    """Generic browser action response."""

    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None


async def send_browser_command(
    redis: RedisClient,
    project_id: str,
    user_id: str,
    command_type: str,
    **kwargs: Any,
) -> None:
    """Send command to browser service via Redis."""
    message = {
        "type": command_type,
        "project_id": project_id,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

    await redis.publish(
        BROWSER_TASKS_CHANNEL,
        json.dumps(message),
    )


@router.get("/session/{project_id}")
async def get_session(
    project_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserSessionResponse:
    """
    Get browser session info for a project.
    """
    try:
        # Get session info from Redis
        session_key = f"browser:session:{project_id}"
        session_data = await redis.get(session_key)

        if session_data:
            data = json.loads(session_data)
            return BrowserSessionResponse(
                project_id=project_id,
                session_id=data.get("session_id"),
                url=data.get("url"),
                title=data.get("title"),
                is_streaming=data.get("is_streaming", False),
                created_at=data.get("created_at"),
                last_used=data.get("last_used"),
            )

        return BrowserSessionResponse(
            project_id=project_id,
            session_id=None,
            url=None,
            title=None,
            is_streaming=False,
            created_at=None,
            last_used=None,
        )

    except Exception as e:
        logger.error(
            "Failed to get browser session",
            project_id=project_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {e}",
        )


@router.post("/session/{project_id}/navigate")
async def navigate(
    project_id: str,
    request: NavigateRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Navigate browser to URL.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "navigate",
            url=request.url,
            wait_until=request.wait_until,
        )

        return BrowserActionResponse(
            success=True,
            result={"url": request.url},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/click")
async def click(
    project_id: str,
    request: ClickRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Click element or coordinates.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "click",
            selector=request.selector,
            x=request.x,
            y=request.y,
            button=request.button,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "click"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/type")
async def type_text(
    project_id: str,
    request: TypeRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Type text into element.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "type",
            text=request.text,
            selector=request.selector,
            clear=request.clear,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "type", "masked": request.mask},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/screenshot")
async def screenshot(
    project_id: str,
    request: ScreenshotRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Take screenshot.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "screenshot",
            full_page=request.full_page,
            quality=request.quality,
            format=request.format,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "screenshot"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/wait")
async def wait_for(
    project_id: str,
    request: WaitRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Wait for element or navigation.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "wait",
            selector=request.selector,
            state=request.state,
            timeout=request.timeout,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "wait"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/evaluate")
async def evaluate(
    project_id: str,
    request: EvaluateRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Execute JavaScript in page context.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "evaluate",
            expression=request.expression,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "evaluate"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/content")
async def get_content(
    project_id: str,
    request: GetContentRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Get page or element content.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "get_content",
            selector=request.selector,
            format=request.format,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "get_content"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/find")
async def find_elements(
    project_id: str,
    request: FindElementsRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Find elements matching selector.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "find_elements",
            selector=request.selector,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "find_elements"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.get("/session/{project_id}/console")
async def get_console_errors(
    project_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    errors_only: bool = Query(True),
    clear: bool = Query(False),
) -> BrowserActionResponse:
    """
    Get console messages/errors from browser.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "get_console",
            errors_only=errors_only,
            clear=clear,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "get_console"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.get("/session/{project_id}/network")
async def get_network_errors(
    project_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    errors_only: bool = Query(True),
    url_filter: str | None = Query(None),
    clear: bool = Query(False),
) -> BrowserActionResponse:
    """
    Get network requests/errors from browser.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "get_network",
            errors_only=errors_only,
            url_filter=url_filter,
            clear=clear,
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "get_network"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.post("/session/{project_id}/check-auth")
async def check_auth(
    project_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Check if current page is a login page.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "check_auth",
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "check_auth"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )


@router.delete("/session/{project_id}")
async def close_session(
    project_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> BrowserActionResponse:
    """
    Close browser session.
    """
    try:
        await send_browser_command(
            redis,
            project_id,
            current_user.sub,
            "close",
        )

        return BrowserActionResponse(
            success=True,
            result={"action": "close"},
        )

    except Exception as e:
        return BrowserActionResponse(
            success=False,
            error=str(e),
        )
