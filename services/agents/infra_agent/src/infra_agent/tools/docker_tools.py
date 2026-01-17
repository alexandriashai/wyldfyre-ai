"""
Docker operation tools for the Infra Agent.
"""

import asyncio
import json
import os
from pathlib import Path

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Workspace for docker-compose files
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))
COMPOSE_DIR = WORKSPACE_DIR / "infrastructure"

# Allowed container name patterns (prevent accessing system containers)
ALLOWED_CONTAINER_PREFIXES = ["ai-", "ai_", "aiinfra"]


def _is_allowed_container(name: str) -> bool:
    """Check if container name is in allowed list."""
    name_lower = name.lower()
    return any(name_lower.startswith(prefix) for prefix in ALLOWED_CONTAINER_PREFIXES)


async def _run_docker_command(
    args: list[str],
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    """Run a docker command and return (returncode, stdout, stderr)."""
    process = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    return (
        process.returncode or 0,
        stdout.decode().strip(),
        stderr.decode().strip(),
    )


@tool(
    name="docker_ps",
    description="List running Docker containers",
    parameters={
        "type": "object",
        "properties": {
            "all": {
                "type": "boolean",
                "description": "Show all containers (including stopped)",
                "default": False,
            },
            "filter": {
                "type": "string",
                "description": "Filter by name pattern",
            },
        },
    },
)
async def docker_ps(
    all: bool = False,
    filter: str | None = None,
) -> ToolResult:
    """List Docker containers."""
    try:
        args = [
            "ps",
            "--format",
            '{"id":"{{.ID}}","name":"{{.Names}}","image":"{{.Image}}","status":"{{.Status}}","ports":"{{.Ports}}"}',
        ]

        if all:
            args.insert(1, "-a")

        if filter:
            args.extend(["--filter", f"name={filter}"])

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker error: {stderr}")

        # Parse JSON lines
        containers = []
        for line in stdout.splitlines():
            if line.strip():
                container = json.loads(line)
                # Only show allowed containers
                if _is_allowed_container(container["name"]):
                    containers.append(container)

        return ToolResult.ok(
            containers,
            count=len(containers),
        )

    except Exception as e:
        logger.error("Docker ps failed", error=str(e))
        return ToolResult.fail(f"Docker ps failed: {e}")


@tool(
    name="docker_logs",
    description="Get logs from a Docker container",
    parameters={
        "type": "object",
        "properties": {
            "container": {
                "type": "string",
                "description": "Container name or ID",
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to show",
                "default": 100,
            },
            "since": {
                "type": "string",
                "description": "Show logs since timestamp (e.g., '10m', '1h')",
            },
        },
        "required": ["container"],
    },
)
async def docker_logs(
    container: str,
    lines: int = 100,
    since: str | None = None,
) -> ToolResult:
    """Get container logs."""
    try:
        if not _is_allowed_container(container):
            return ToolResult.fail(f"Container not in allowed list: {container}")

        args = ["logs", "--tail", str(lines)]

        if since:
            args.extend(["--since", since])

        args.append(container)

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker error: {stderr}")

        # Docker sends logs to stderr for some containers
        logs = stdout if stdout else stderr

        return ToolResult.ok(
            logs,
            container=container,
            lines=len(logs.splitlines()),
        )

    except Exception as e:
        logger.error("Docker logs failed", container=container, error=str(e))
        return ToolResult.fail(f"Docker logs failed: {e}")


@tool(
    name="docker_exec",
    description="Execute a command in a running container",
    parameters={
        "type": "object",
        "properties": {
            "container": {
                "type": "string",
                "description": "Container name or ID",
            },
            "command": {
                "type": "string",
                "description": "Command to execute",
            },
        },
        "required": ["container", "command"],
    },
    permission_level=2,
)
async def docker_exec(
    container: str,
    command: str,
) -> ToolResult:
    """Execute command in container."""
    try:
        if not _is_allowed_container(container):
            return ToolResult.fail(f"Container not in allowed list: {container}")

        # Split command into args
        args = ["exec", container] + command.split()

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Exec error: {stderr}")

        return ToolResult.ok(
            stdout if stdout else "Command completed",
            container=container,
            command=command,
        )

    except Exception as e:
        logger.error("Docker exec failed", container=container, error=str(e))
        return ToolResult.fail(f"Docker exec failed: {e}")


@tool(
    name="docker_inspect",
    description="Get detailed information about a container",
    parameters={
        "type": "object",
        "properties": {
            "container": {
                "type": "string",
                "description": "Container name or ID",
            },
        },
        "required": ["container"],
    },
)
async def docker_inspect(container: str) -> ToolResult:
    """Inspect a container."""
    try:
        if not _is_allowed_container(container):
            return ToolResult.fail(f"Container not in allowed list: {container}")

        args = ["inspect", container]

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker error: {stderr}")

        info = json.loads(stdout)
        if info:
            # Extract key information
            container_info = info[0]
            result = {
                "id": container_info.get("Id", "")[:12],
                "name": container_info.get("Name", "").lstrip("/"),
                "image": container_info.get("Config", {}).get("Image"),
                "created": container_info.get("Created"),
                "state": container_info.get("State", {}),
                "network": {
                    k: {
                        "ip": v.get("IPAddress"),
                        "gateway": v.get("Gateway"),
                    }
                    for k, v in container_info.get("NetworkSettings", {})
                    .get("Networks", {})
                    .items()
                },
                "mounts": [
                    {
                        "source": m.get("Source"),
                        "destination": m.get("Destination"),
                        "mode": m.get("Mode"),
                    }
                    for m in container_info.get("Mounts", [])
                ],
                "env": container_info.get("Config", {}).get("Env", []),
            }
            return ToolResult.ok(result)

        return ToolResult.fail("Container not found")

    except json.JSONDecodeError as e:
        return ToolResult.fail(f"Failed to parse inspect output: {e}")
    except Exception as e:
        logger.error("Docker inspect failed", container=container, error=str(e))
        return ToolResult.fail(f"Docker inspect failed: {e}")


@tool(
    name="docker_compose_ps",
    description="List containers in a docker-compose project",
    parameters={
        "type": "object",
        "properties": {
            "compose_file": {
                "type": "string",
                "description": "Path to docker-compose.yml (relative to infrastructure dir)",
                "default": "docker-compose.yml",
            },
        },
    },
)
async def docker_compose_ps(compose_file: str = "docker-compose.yml") -> ToolResult:
    """List docker-compose services."""
    try:
        compose_path = COMPOSE_DIR / compose_file
        if not compose_path.exists():
            return ToolResult.fail(f"Compose file not found: {compose_file}")

        args = ["compose", "-f", str(compose_path), "ps", "--format", "json"]

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker compose error: {stderr}")

        if not stdout:
            return ToolResult.ok([], count=0)

        services = json.loads(stdout)
        return ToolResult.ok(
            services,
            count=len(services),
            compose_file=compose_file,
        )

    except json.JSONDecodeError:
        # Fallback parsing for older docker-compose versions
        return ToolResult.ok(stdout, compose_file=compose_file)
    except Exception as e:
        logger.error("Docker compose ps failed", error=str(e))
        return ToolResult.fail(f"Docker compose ps failed: {e}")


@tool(
    name="docker_compose_up",
    description="Start docker-compose services",
    parameters={
        "type": "object",
        "properties": {
            "compose_file": {
                "type": "string",
                "description": "Path to docker-compose.yml",
                "default": "docker-compose.yml",
            },
            "services": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific services to start (all if not specified)",
            },
            "detach": {
                "type": "boolean",
                "description": "Run in background",
                "default": True,
            },
        },
    },
    permission_level=2,
)
async def docker_compose_up(
    compose_file: str = "docker-compose.yml",
    services: list[str] | None = None,
    detach: bool = True,
) -> ToolResult:
    """Start docker-compose services."""
    try:
        compose_path = COMPOSE_DIR / compose_file
        if not compose_path.exists():
            return ToolResult.fail(f"Compose file not found: {compose_file}")

        args = ["compose", "-f", str(compose_path), "up"]

        if detach:
            args.append("-d")

        if services:
            args.extend(services)

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker compose error: {stderr}")

        return ToolResult.ok(
            stdout if stdout else "Services started",
            compose_file=compose_file,
            services=services,
        )

    except Exception as e:
        logger.error("Docker compose up failed", error=str(e))
        return ToolResult.fail(f"Docker compose up failed: {e}")


@tool(
    name="docker_compose_down",
    description="Stop docker-compose services",
    parameters={
        "type": "object",
        "properties": {
            "compose_file": {
                "type": "string",
                "description": "Path to docker-compose.yml",
                "default": "docker-compose.yml",
            },
            "volumes": {
                "type": "boolean",
                "description": "Remove volumes",
                "default": False,
            },
        },
    },
    permission_level=2,
    requires_confirmation=True,
)
async def docker_compose_down(
    compose_file: str = "docker-compose.yml",
    volumes: bool = False,
) -> ToolResult:
    """Stop docker-compose services."""
    try:
        compose_path = COMPOSE_DIR / compose_file
        if not compose_path.exists():
            return ToolResult.fail(f"Compose file not found: {compose_file}")

        args = ["compose", "-f", str(compose_path), "down"]

        if volumes:
            args.append("-v")

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker compose error: {stderr}")

        return ToolResult.ok(
            stdout if stdout else "Services stopped",
            compose_file=compose_file,
            volumes_removed=volumes,
        )

    except Exception as e:
        logger.error("Docker compose down failed", error=str(e))
        return ToolResult.fail(f"Docker compose down failed: {e}")


@tool(
    name="docker_compose_restart",
    description="Restart docker-compose services",
    parameters={
        "type": "object",
        "properties": {
            "compose_file": {
                "type": "string",
                "description": "Path to docker-compose.yml",
                "default": "docker-compose.yml",
            },
            "services": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific services to restart",
            },
        },
    },
    permission_level=2,
)
async def docker_compose_restart(
    compose_file: str = "docker-compose.yml",
    services: list[str] | None = None,
) -> ToolResult:
    """Restart docker-compose services."""
    try:
        compose_path = COMPOSE_DIR / compose_file
        if not compose_path.exists():
            return ToolResult.fail(f"Compose file not found: {compose_file}")

        args = ["compose", "-f", str(compose_path), "restart"]

        if services:
            args.extend(services)

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker compose error: {stderr}")

        return ToolResult.ok(
            stdout if stdout else "Services restarted",
            compose_file=compose_file,
            services=services,
        )

    except Exception as e:
        logger.error("Docker compose restart failed", error=str(e))
        return ToolResult.fail(f"Docker compose restart failed: {e}")


@tool(
    name="docker_compose_logs",
    description="Get logs from docker-compose services",
    parameters={
        "type": "object",
        "properties": {
            "compose_file": {
                "type": "string",
                "description": "Path to docker-compose.yml",
                "default": "docker-compose.yml",
            },
            "services": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific services to get logs from",
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to show",
                "default": 100,
            },
        },
    },
)
async def docker_compose_logs(
    compose_file: str = "docker-compose.yml",
    services: list[str] | None = None,
    lines: int = 100,
) -> ToolResult:
    """Get docker-compose service logs."""
    try:
        compose_path = COMPOSE_DIR / compose_file
        if not compose_path.exists():
            return ToolResult.fail(f"Compose file not found: {compose_file}")

        args = ["compose", "-f", str(compose_path), "logs", "--tail", str(lines)]

        if services:
            args.extend(services)

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker compose error: {stderr}")

        logs = stdout if stdout else stderr

        return ToolResult.ok(
            logs,
            compose_file=compose_file,
            services=services,
            lines=len(logs.splitlines()),
        )

    except Exception as e:
        logger.error("Docker compose logs failed", error=str(e))
        return ToolResult.fail(f"Docker compose logs failed: {e}")
