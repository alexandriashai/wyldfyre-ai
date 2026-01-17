"""
Agent management routes.
"""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ai_core import AgentStatus, AgentType, get_logger
from ai_messaging import PubSubManager, RedisClient

from ..dependencies import AdminUserDep, CurrentUserDep, get_redis

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])


# Agent metadata
AGENT_INFO = {
    "supervisor": {
        "type": AgentType.SUPERVISOR,
        "description": "Task routing and orchestration",
        "capabilities": ["route_task", "delegate_task", "check_status", "escalate"],
    },
    "code-agent": {
        "type": AgentType.CODE,
        "description": "Git, file operations, code analysis, testing",
        "capabilities": ["read_file", "write_file", "git_operations", "search_files"],
    },
    "data-agent": {
        "type": AgentType.DATA,
        "description": "SQL, data analysis, ETL, backups",
        "capabilities": ["execute_query", "export_data", "import_data", "backups"],
    },
    "infra-agent": {
        "type": AgentType.INFRA,
        "description": "Docker, Nginx, SSL, domain management",
        "capabilities": [
            "docker_operations",
            "nginx_config",
            "ssl_certificates",
            "domain_management",
            "cloudflare",
            "systemd",
        ],
    },
    "research-agent": {
        "type": AgentType.RESEARCH,
        "description": "Web search, documentation, synthesis",
        "capabilities": ["web_search", "fetch_url", "documentation"],
    },
    "qa-agent": {
        "type": AgentType.QA,
        "description": "Testing, code review, security, validation",
        "capabilities": ["run_tests", "code_review", "security_scan", "lint"],
    },
}


@router.get("")
async def list_agents(
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> list[dict[str, Any]]:
    """
    List all agents with their current status.
    """
    agents = []

    for agent_name, info in AGENT_INFO.items():
        agent_data = {
            "name": agent_name,
            "type": info["type"].value,
            "description": info["description"],
            "capabilities": info["capabilities"],
            "status": AgentStatus.OFFLINE.value,
            "last_heartbeat": None,
            "current_task": None,
        }

        # Get live status from Redis
        try:
            heartbeat_key = f"agent:heartbeat:{agent_name}"
            heartbeat_data = await redis.get(heartbeat_key)

            if heartbeat_data:
                data = json.loads(heartbeat_data)
                last_heartbeat = datetime.fromisoformat(data.get("timestamp", ""))
                age_seconds = (
                    datetime.now(timezone.utc) - last_heartbeat
                ).total_seconds()

                if age_seconds < 60:
                    agent_data["status"] = data.get("status", AgentStatus.IDLE.value)
                    agent_data["current_task"] = data.get("current_task")

                agent_data["last_heartbeat"] = last_heartbeat.isoformat()

        except Exception as e:
            logger.warning(
                "Failed to get agent status",
                agent=agent_name,
                error=str(e),
            )

        agents.append(agent_data)

    return agents


@router.get("/{agent_name}")
async def get_agent(
    agent_name: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> dict[str, Any]:
    """
    Get detailed information about a specific agent.
    """
    if agent_name not in AGENT_INFO:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_name} not found",
        )

    info = AGENT_INFO[agent_name]
    agent_data = {
        "name": agent_name,
        "type": info["type"].value,
        "description": info["description"],
        "capabilities": info["capabilities"],
        "status": AgentStatus.OFFLINE.value,
        "last_heartbeat": None,
        "current_task": None,
        "metrics": {},
    }

    # Get live status from Redis
    try:
        heartbeat_key = f"agent:heartbeat:{agent_name}"
        heartbeat_data = await redis.get(heartbeat_key)

        if heartbeat_data:
            data = json.loads(heartbeat_data)
            last_heartbeat = datetime.fromisoformat(data.get("timestamp", ""))
            age_seconds = (
                datetime.now(timezone.utc) - last_heartbeat
            ).total_seconds()

            if age_seconds < 60:
                agent_data["status"] = data.get("status", AgentStatus.IDLE.value)
                agent_data["current_task"] = data.get("current_task")

            agent_data["last_heartbeat"] = last_heartbeat.isoformat()
            agent_data["metrics"] = data.get("metrics", {})

    except Exception as e:
        logger.warning(
            "Failed to get agent status",
            agent=agent_name,
            error=str(e),
        )

    return agent_data


@router.get("/{agent_name}/logs")
async def get_agent_logs(
    agent_name: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """
    Get recent logs for an agent.
    """
    if agent_name not in AGENT_INFO:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_name} not found",
        )

    try:
        # Get logs from Redis list
        log_key = f"agent:logs:{agent_name}"
        logs = await redis.lrange(log_key, 0, limit - 1)

        return {
            "agent": agent_name,
            "logs": [json.loads(log) for log in logs] if logs else [],
            "count": len(logs) if logs else 0,
        }

    except Exception as e:
        logger.warning(
            "Failed to get agent logs",
            agent=agent_name,
            error=str(e),
        )
        return {
            "agent": agent_name,
            "logs": [],
            "count": 0,
            "error": str(e),
        }


@router.post("/{agent_name}/restart")
async def restart_agent(
    agent_name: str,
    current_user: AdminUserDep,  # Admin only
    redis: RedisClient = Depends(get_redis),
) -> dict[str, Any]:
    """
    Request agent restart.

    This publishes a restart command that the Tmux Manager should pick up.
    """
    if agent_name not in AGENT_INFO:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_name} not found",
        )

    try:
        # Publish restart command
        pubsub = PubSubManager(redis)
        await pubsub.publish(
            channel="system:commands",
            message={
                "command": "restart_agent",
                "agent": agent_name,
                "requested_by": current_user.sub,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            "Agent restart requested",
            agent=agent_name,
            requested_by=current_user.sub,
        )

        return {
            "success": True,
            "message": f"Restart command sent for {agent_name}",
        }

    except Exception as e:
        logger.error(
            "Failed to request agent restart",
            agent=agent_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart agent: {e}",
        )
