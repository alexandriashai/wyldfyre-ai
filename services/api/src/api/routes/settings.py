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
from ..dependencies import AdminUserDep, CurrentUserDep, RedisDep
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


# --- System AI Configuration (Admin-only) ---

# Redis key mappings for system AI config
_SYSTEM_AI_REDIS_KEYS = {
    "router_enabled": "llm:router_enabled",
    "router_up_threshold": "llm:router_up_threshold",
    "router_down_threshold": "llm:router_down_threshold",
    "router_latency_budget_ms": "llm:router_latency_budget_ms",
    "router_type": "llm:router_type",
    "aider_enabled": "llm:aider_enabled",
    "aider_default_model": "llm:aider_default_model",
    "aider_edit_format": "llm:aider_edit_format",
    "aider_map_tokens": "llm:aider_map_tokens",
}


class SystemAIConfig(BaseModel):
    """System-wide AI configuration for LLMRouter and Aider."""

    router_enabled: bool = True
    router_up_threshold: float = 0.75
    router_down_threshold: float = 0.30
    router_latency_budget_ms: int = 50
    router_type: str = "mf"
    aider_enabled: bool = True
    aider_default_model: str = "claude-sonnet-4-20250514"
    aider_edit_format: str = "diff"
    aider_map_tokens: int = 2048


@router.get("/system/ai", response_model=SystemAIConfig)
async def get_system_ai_config(
    current_user: AdminUserDep,
    redis: RedisDep,
) -> SystemAIConfig:
    """
    Get system AI configuration (admin-only).

    Reads current values from Redis, falling back to defaults for missing keys.
    """
    data: dict[str, Any] = {}
    defaults = SystemAIConfig()

    for field, redis_key in _SYSTEM_AI_REDIS_KEYS.items():
        val = await redis.get(redis_key)
        if val is not None:
            # Convert string values to appropriate types
            field_default = getattr(defaults, field)
            if isinstance(field_default, bool):
                data[field] = val == "1"
            elif isinstance(field_default, float):
                data[field] = float(val)
            elif isinstance(field_default, int):
                data[field] = int(val)
            else:
                data[field] = val

    return SystemAIConfig(**data)


@router.put("/system/ai", response_model=SuccessResponse)
async def update_system_ai_config(
    request: SystemAIConfig,
    current_user: AdminUserDep,
    redis: RedisDep,
) -> SuccessResponse:
    """
    Update system AI configuration (admin-only).

    Writes all values to Redis and updates in-memory singletons.
    """
    for field, redis_key in _SYSTEM_AI_REDIS_KEYS.items():
        value = getattr(request, field)
        # Convert Python types to Redis string values
        if isinstance(value, bool):
            await redis.set(redis_key, "1" if value else "0")
        else:
            await redis.set(redis_key, str(value))

    # Update in-memory ContentRouter singleton if available
    try:
        from ai_core.content_router import get_content_router
        router_instance = get_content_router()
        router_instance.update_config(
            enabled=request.router_enabled,
            up_threshold=request.router_up_threshold,
            down_threshold=request.router_down_threshold,
            latency_budget_ms=request.router_latency_budget_ms,
            router_type=request.router_type,
        )
    except Exception:
        pass  # Router may not be initialized in API process

    logger.info("System AI config updated", user_id=current_user.sub)
    return SuccessResponse(message="System AI configuration updated")
