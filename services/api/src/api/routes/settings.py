"""
User settings routes.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger

from ..database import get_db_session
from ..dependencies import CurrentUserDep
from ..schemas import SuccessResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])


class NotificationSettings(BaseModel):
    """User notification preferences."""

    task_completions: bool = True
    agent_errors: bool = True
    ssl_expiration: bool = True
    system_updates: bool = True


@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> NotificationSettings:
    """
    Get current user's notification preferences.
    """
    from ai_db import User

    result = await db.execute(
        select(User).where(User.id == current_user.sub)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Parse preferences from JSON
    if user.preferences:
        try:
            prefs = json.loads(user.preferences)
            notifications = prefs.get("notifications", {})
            return NotificationSettings(
                task_completions=notifications.get("task_completions", True),
                agent_errors=notifications.get("agent_errors", True),
                ssl_expiration=notifications.get("ssl_expiration", True),
                system_updates=notifications.get("system_updates", True),
            )
        except json.JSONDecodeError:
            pass

    # Return defaults
    return NotificationSettings()


@router.put("/notifications", response_model=SuccessResponse)
async def update_notification_settings(
    request: NotificationSettings,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    """
    Update current user's notification preferences.
    """
    from ai_db import User

    result = await db.execute(
        select(User).where(User.id == current_user.sub)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Load existing preferences or create new
    prefs: dict[str, Any] = {}
    if user.preferences:
        try:
            prefs = json.loads(user.preferences)
        except json.JSONDecodeError:
            pass

    # Update notification settings
    prefs["notifications"] = request.model_dump()
    user.preferences = json.dumps(prefs)

    await db.flush()

    logger.info("Notification settings updated", user_id=current_user.sub)
    return SuccessResponse(message="Notification settings updated")
