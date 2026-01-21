"""
Agent management routes.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ai_core import AgentStatus, AgentType, get_logger
from ai_messaging import PubSubManager, RedisClient

from ..dependencies import AdminUserDep, CurrentUserDep, get_redis
from ..schemas.agent import AgentToolsResponse, ToolInfo

logger = get_logger(__name__)

# Load agents configuration from YAML
AGENTS_CONFIG_PATH = Path("/home/wyld-core/config/agents.yaml")


def load_agents_config() -> dict[str, Any]:
    """Load agents configuration from YAML file."""
    try:
        if AGENTS_CONFIG_PATH.exists():
            with open(AGENTS_CONFIG_PATH) as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Failed to load agents config", error=str(e))
    return {}


# Tool descriptions and categories
TOOL_METADATA = {
    "git": {
        "description": "Git version control operations (clone, pull, push, commit, branch)",
        "category": "git",
        "permission_level": 2,
    },
    "file_reader": {
        "description": "Read files from the filesystem",
        "category": "file",
        "permission_level": 0,
    },
    "file_writer": {
        "description": "Write and modify files on the filesystem",
        "category": "file",
        "permission_level": 1,
    },
    "code_analyzer": {
        "description": "Analyze code for patterns, complexity, and quality metrics",
        "category": "file",
        "permission_level": 0,
    },
    "test_runner": {
        "description": "Execute test suites and report results",
        "category": "system",
        "permission_level": 2,
    },
    "sql_executor": {
        "description": "Execute SQL queries against databases",
        "category": "database",
        "permission_level": 2,
    },
    "data_analyzer": {
        "description": "Analyze data patterns and generate insights",
        "category": "database",
        "permission_level": 0,
    },
    "backup_manager": {
        "description": "Create and manage database backups",
        "category": "database",
        "permission_level": 2,
    },
    "docker_manager": {
        "description": "Manage Docker containers, images, and networks",
        "category": "docker",
        "permission_level": 3,
    },
    "nginx_manager": {
        "description": "Configure and manage Nginx web server",
        "category": "network",
        "permission_level": 3,
    },
    "certbot_manager": {
        "description": "Manage SSL/TLS certificates with Let's Encrypt",
        "category": "security",
        "permission_level": 3,
    },
    "cloudflare_api": {
        "description": "Interact with Cloudflare DNS and CDN services",
        "category": "network",
        "permission_level": 2,
    },
    "service_manage": {
        "description": "Manage systemd services",
        "category": "system",
        "permission_level": 3,
    },
    "package_install": {
        "description": "Install and manage system packages",
        "category": "system",
        "permission_level": 3,
    },
    "web_search": {
        "description": "Search the web for information",
        "category": "network",
        "permission_level": 1,
    },
    "documentation_reader": {
        "description": "Fetch and parse documentation from URLs",
        "category": "network",
        "permission_level": 1,
    },
    "code_reviewer": {
        "description": "Review code for issues, best practices, and improvements",
        "category": "file",
        "permission_level": 0,
    },
    "security_scanner": {
        "description": "Scan code and systems for security vulnerabilities",
        "category": "security",
        "permission_level": 2,
    },
}

router = APIRouter(prefix="/agents", tags=["Agents"])


# Agent metadata
AGENT_INFO = {
    "wyld": {
        "type": AgentType.SUPERVISOR,
        "description": "Primary AI assistant - Task routing and orchestration",
        "capabilities": ["route_task", "delegate_task", "check_status", "escalate", "user_interaction"],
    },
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


@router.get("/{agent_name}/tools", response_model=AgentToolsResponse)
async def get_agent_tools(
    agent_name: str,
    current_user: CurrentUserDep,
) -> AgentToolsResponse:
    """
    Get tools and capabilities available to an agent.

    Reads from config/agents.yaml and provides detailed tool information.
    """
    # Load config
    config = load_agents_config()
    agents_list = config.get("agents", [])

    # Find agent
    agent_config = None
    for agent in agents_list:
        if agent.get("name") == agent_name:
            agent_config = agent
            break

    if not agent_config:
        # Fall back to static AGENT_INFO
        if agent_name not in AGENT_INFO:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_name} not found",
            )
        info = AGENT_INFO[agent_name]
        return AgentToolsResponse(
            agent_name=agent_name,
            agent_type=info["type"].value,
            description=info["description"],
            permission_level=0,
            tools=[],
            capabilities=info["capabilities"],
            allowed_capabilities=[],
        )

    # Build tools list from config
    tools = []
    for tool_name in agent_config.get("tools", []):
        tool_meta = TOOL_METADATA.get(tool_name, {})
        tools.append(
            ToolInfo(
                name=tool_name,
                description=tool_meta.get("description", f"{tool_name} tool"),
                category=tool_meta.get("category", "general"),
                permission_level=tool_meta.get(
                    "permission_level", agent_config.get("permission_level", 0)
                ),
            )
        )

    return AgentToolsResponse(
        agent_name=agent_name,
        agent_type=agent_config.get("type", "unknown"),
        description=agent_config.get("description", "").strip(),
        permission_level=agent_config.get("permission_level", 0),
        tools=tools,
        capabilities=agent_config.get("capabilities", []),
        allowed_capabilities=agent_config.get("allowed_capabilities", []),
    )


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
