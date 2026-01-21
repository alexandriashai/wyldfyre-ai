"""
Docker operation tools for the Infra Agent.

Provides comprehensive Docker and Docker Compose management capabilities.
"""

import asyncio
import json
import os
from pathlib import Path

from ai_core import CapabilityCategory, get_logger
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
            "show_all": {
                "type": "boolean",
                "description": "Show all containers (including stopped)",
                "default": False,
            },
            "name_filter": {
                "type": "string",
                "description": "Filter by name pattern",
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.DOCKER,
)
async def docker_ps(
    show_all: bool = False,
    name_filter: str | None = None,
) -> ToolResult:
    """List Docker containers."""
    try:
        args = [
            "ps",
            "--format",
            '{"id":"{{.ID}}","name":"{{.Names}}","image":"{{.Image}}","status":"{{.Status}}","ports":"{{.Ports}}"}',
        ]

        if show_all:
            args.insert(1, "-a")

        if name_filter:
            args.extend(["--filter", f"name={name_filter}"])

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
    capability_category=CapabilityCategory.DOCKER,
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
    capability_category=CapabilityCategory.DOCKER,
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
    capability_category=CapabilityCategory.DOCKER,
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


@tool(
    name="docker_images",
    description="List Docker images",
    parameters={
        "type": "object",
        "properties": {
            "name_filter": {
                "type": "string",
                "description": "Filter images by name pattern",
            },
            "show_all": {
                "type": "boolean",
                "description": "Show all images (including intermediate)",
                "default": False,
            },
        },
    },
)
async def docker_images(
    name_filter: str | None = None,
    show_all: bool = False,
) -> ToolResult:
    """List Docker images."""
    try:
        args = [
            "images",
            "--format",
            '{"repository":"{{.Repository}}","tag":"{{.Tag}}","id":"{{.ID}}","size":"{{.Size}}","created":"{{.CreatedSince}}"}',
        ]

        if show_all:
            args.insert(1, "-a")

        if name_filter:
            args.extend(["--filter", f"reference={name_filter}"])

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker error: {stderr}")

        # Parse JSON lines
        images = []
        for line in stdout.splitlines():
            if line.strip():
                images.append(json.loads(line))

        return ToolResult.ok(
            images,
            count=len(images),
        )

    except Exception as e:
        logger.error("Docker images failed", error=str(e))
        return ToolResult.fail(f"Docker images failed: {e}")


@tool(
    name="docker_pull",
    description="Pull a Docker image from registry",
    parameters={
        "type": "object",
        "properties": {
            "image": {
                "type": "string",
                "description": "Image name with optional tag (e.g., 'nginx:latest')",
            },
        },
        "required": ["image"],
    },
    permission_level=2,
)
async def docker_pull(image: str) -> ToolResult:
    """Pull a Docker image."""
    try:
        args = ["pull", image]

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Pull failed: {stderr}")

        return ToolResult.ok({
            "message": f"Successfully pulled: {image}",
            "image": image,
            "output": stdout,
        })

    except Exception as e:
        logger.error("Docker pull failed", image=image, error=str(e))
        return ToolResult.fail(f"Docker pull failed: {e}")


@tool(
    name="docker_build",
    description="Build a Docker image from a Dockerfile",
    parameters={
        "type": "object",
        "properties": {
            "tag": {
                "type": "string",
                "description": "Tag for the image (e.g., 'myapp:latest')",
            },
            "dockerfile": {
                "type": "string",
                "description": "Path to Dockerfile (relative to infrastructure dir)",
                "default": "Dockerfile",
            },
            "context": {
                "type": "string",
                "description": "Build context path",
                "default": ".",
            },
            "no_cache": {
                "type": "boolean",
                "description": "Build without cache",
                "default": False,
            },
        },
        "required": ["tag"],
    },
    permission_level=2,
)
async def docker_build(
    tag: str,
    dockerfile: str = "Dockerfile",
    context: str = ".",
    no_cache: bool = False,
) -> ToolResult:
    """Build a Docker image."""
    try:
        dockerfile_path = COMPOSE_DIR / dockerfile
        context_path = COMPOSE_DIR / context

        args = ["build", "-t", tag, "-f", str(dockerfile_path)]

        if no_cache:
            args.append("--no-cache")

        args.append(str(context_path))

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Build failed: {stderr}")

        return ToolResult.ok({
            "message": f"Successfully built: {tag}",
            "tag": tag,
            "output": stdout[-2000:] if len(stdout) > 2000 else stdout,
        })

    except Exception as e:
        logger.error("Docker build failed", tag=tag, error=str(e))
        return ToolResult.fail(f"Docker build failed: {e}")


@tool(
    name="docker_stats",
    description="Get resource usage statistics for containers",
    parameters={
        "type": "object",
        "properties": {
            "container": {
                "type": "string",
                "description": "Specific container name (all if not specified)",
            },
        },
    },
)
async def docker_stats(container: str | None = None) -> ToolResult:
    """Get container resource usage."""
    try:
        args = [
            "stats",
            "--no-stream",
            "--format",
            '{"name":"{{.Name}}","cpu":"{{.CPUPerc}}","memory":"{{.MemUsage}}","mem_percent":"{{.MemPerc}}","net_io":"{{.NetIO}}","block_io":"{{.BlockIO}}","pids":"{{.PIDs}}"}',
        ]

        if container:
            if not _is_allowed_container(container):
                return ToolResult.fail(f"Container not in allowed list: {container}")
            args.append(container)

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker error: {stderr}")

        # Parse JSON lines
        stats = []
        for line in stdout.splitlines():
            if line.strip():
                stat = json.loads(line)
                # Only include allowed containers
                if _is_allowed_container(stat["name"]):
                    stats.append(stat)

        return ToolResult.ok(
            stats,
            count=len(stats),
        )

    except Exception as e:
        logger.error("Docker stats failed", error=str(e))
        return ToolResult.fail(f"Docker stats failed: {e}")


@tool(
    name="docker_health_check",
    description="Check health status of containers",
    parameters={
        "type": "object",
        "properties": {
            "container": {
                "type": "string",
                "description": "Specific container to check (all if not specified)",
            },
        },
    },
)
async def docker_health_check(container: str | None = None) -> ToolResult:
    """Check container health status."""
    try:
        args = [
            "ps",
            "--format",
            '{"name":"{{.Names}}","status":"{{.Status}}","health":"{{.Status}}"}',
        ]

        if container:
            if not _is_allowed_container(container):
                return ToolResult.fail(f"Container not in allowed list: {container}")
            args.extend(["--filter", f"name={container}"])

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Docker error: {stderr}")

        # Parse and enrich with health info
        containers = []
        for line in stdout.splitlines():
            if line.strip():
                info = json.loads(line)
                if not _is_allowed_container(info["name"]):
                    continue

                # Extract health status from status string
                status = info["status"].lower()
                if "healthy" in status:
                    health = "healthy"
                elif "unhealthy" in status:
                    health = "unhealthy"
                elif "starting" in status:
                    health = "starting"
                elif "up" in status:
                    health = "running"
                else:
                    health = "unknown"

                info["health_status"] = health
                containers.append(info)

        # Summary
        healthy = sum(1 for c in containers if c["health_status"] == "healthy")
        unhealthy = sum(1 for c in containers if c["health_status"] == "unhealthy")
        running = sum(1 for c in containers if c["health_status"] in ("running", "healthy"))

        return ToolResult.ok(
            containers,
            count=len(containers),
            summary={
                "healthy": healthy,
                "unhealthy": unhealthy,
                "running": running,
                "total": len(containers),
            },
        )

    except Exception as e:
        logger.error("Docker health check failed", error=str(e))
        return ToolResult.fail(f"Docker health check failed: {e}")


@tool(
    name="docker_system_prune",
    description="Remove unused Docker data (images, containers, volumes, networks)",
    parameters={
        "type": "object",
        "properties": {
            "prune_all": {
                "type": "boolean",
                "description": "Remove all unused images, not just dangling ones",
                "default": False,
            },
            "volumes": {
                "type": "boolean",
                "description": "Also remove unused volumes",
                "default": False,
            },
        },
    },
    permission_level=2,
    requires_confirmation=True,
)
async def docker_system_prune(
    prune_all: bool = False,
    volumes: bool = False,
) -> ToolResult:
    """Remove unused Docker data."""
    try:
        args = ["system", "prune", "-f"]

        if prune_all:
            args.append("-a")

        if volumes:
            args.append("--volumes")

        code, stdout, stderr = await _run_docker_command(args)

        if code != 0:
            return ToolResult.fail(f"Prune failed: {stderr}")

        return ToolResult.ok({
            "message": "System prune completed",
            "output": stdout,
            "all_images": prune_all,
            "volumes_removed": volumes,
        })

    except Exception as e:
        logger.error("Docker system prune failed", error=str(e))
        return ToolResult.fail(f"Docker system prune failed: {e}")
