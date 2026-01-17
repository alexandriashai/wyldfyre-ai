"""
Health check routes.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import AgentStatus, get_logger
from ai_messaging import RedisClient

from ..database import get_db_session
from ..dependencies import get_redis

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def liveness() -> dict[str, Any]:
    """
    Liveness probe - checks if the API is running.

    This should always return 200 if the server is up.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness(
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
) -> dict[str, Any]:
    """
    Readiness probe - checks if the API can handle requests.

    Verifies connectivity to:
    - PostgreSQL database
    - Redis
    """
    checks = {}
    overall_healthy = True

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    return {
        "status": "ready" if overall_healthy else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/agents")
async def agent_health(
    redis: RedisClient = Depends(get_redis),
) -> dict[str, Any]:
    """
    Get health status of all agents.

    Retrieves agent heartbeat information from Redis.
    """
    agents = {}

    # Agent names to check
    agent_names = [
        "supervisor",
        "code-agent",
        "data-agent",
        "infra-agent",
        "research-agent",
        "qa-agent",
    ]

    for agent_name in agent_names:
        try:
            # Get last heartbeat from Redis
            heartbeat_key = f"agent:heartbeat:{agent_name}"
            heartbeat_data = await redis.get(heartbeat_key)

            if heartbeat_data:
                import json

                data = json.loads(heartbeat_data)
                last_heartbeat = datetime.fromisoformat(data.get("timestamp", ""))
                age_seconds = (
                    datetime.now(timezone.utc) - last_heartbeat
                ).total_seconds()

                # Consider agent unhealthy if no heartbeat in 60 seconds
                if age_seconds < 60:
                    status = AgentStatus.IDLE
                else:
                    status = AgentStatus.OFFLINE

                agents[agent_name] = {
                    "status": status.value,
                    "last_heartbeat": last_heartbeat.isoformat(),
                    "age_seconds": int(age_seconds),
                    "current_task": data.get("current_task"),
                }
            else:
                agents[agent_name] = {
                    "status": AgentStatus.OFFLINE.value,
                    "last_heartbeat": None,
                }

        except Exception as e:
            logger.warning(
                "Failed to get agent health",
                agent=agent_name,
                error=str(e),
            )
            agents[agent_name] = {
                "status": "unknown",
                "error": str(e),
            }

    # Calculate overall status
    online_count = sum(
        1 for a in agents.values() if a.get("status") != AgentStatus.OFFLINE.value
    )
    total_count = len(agents)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total_count,
            "online": online_count,
            "offline": total_count - online_count,
        },
        "agents": agents,
    }
