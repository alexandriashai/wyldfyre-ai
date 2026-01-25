"""
Container management service for Dockerized project environments.

Handles:
- Building project-specific Docker images
- Container lifecycle (create, start, stop, remove)
- Executing commands in containers
- Container health monitoring
"""

import asyncio
import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ai_core import get_logger

logger = get_logger(__name__)

DOCKER_TEMPLATES_PATH = Path("/home/wyld-core/infrastructure/docker/templates")
WYLD_NETWORK = "wyld-projects"


class ProjectType(str, Enum):
    NODE = "node"
    PHP = "php"
    PYTHON = "python"
    CUSTOM = "custom"


class ContainerStatus(str, Enum):
    BUILDING = "building"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    NOT_FOUND = "not_found"


@dataclass
class ContainerConfig:
    """Configuration for a project container."""
    project_id: str
    project_name: str
    project_type: ProjectType
    root_path: str

    # Version overrides
    node_version: str = "20"
    php_version: str = "8.3"
    python_version: str = "3.12"

    # Resource limits
    memory_limit: str = "2g"
    cpu_limit: str = "2.0"

    # Network
    expose_ports: list[int] | None = None

    # Environment
    env_vars: dict[str, str] | None = None


class ContainerService:
    """Manages Docker containers for Wyld projects."""

    def __init__(self):
        self._network_ensured = False

    def _ensure_network_sync(self) -> None:
        """Ensure the Wyld Docker network exists (synchronous version)."""
        if self._network_ensured:
            return

        try:
            import subprocess
            result = subprocess.run(
                ["docker", "network", "inspect", WYLD_NETWORK],
                capture_output=True,
            )
            if result.returncode != 0:
                subprocess.run(
                    ["docker", "network", "create", WYLD_NETWORK],
                    capture_output=True,
                )
            self._network_ensured = True
        except Exception as e:
            logger.warning(f"Failed to ensure Docker network: {e}")

    async def _run_command(
        self,
        cmd: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run a shell command asynchronously."""
        try:
            full_env = os.environ.copy()
            if env:
                full_env.update(env)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=full_env,
            )
            stdout, stderr = await proc.communicate()

            return {
                "returncode": proc.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def _get_container_name(self, project_id: str) -> str:
        """Generate container name from project ID."""
        return f"wyld-project-{project_id[:12]}"

    def _get_image_name(self, project_id: str) -> str:
        """Generate image name from project ID."""
        return f"wyld-project:{project_id[:12]}"

    async def get_status(self, project_id: str) -> ContainerStatus:
        """Get the current status of a project's container."""
        container_name = self._get_container_name(project_id)

        result = await self._run_command([
            "docker", "inspect", "-f", "{{.State.Status}}", container_name
        ])

        if result["returncode"] != 0:
            return ContainerStatus.NOT_FOUND

        status = result["stdout"].strip()
        if status == "running":
            return ContainerStatus.RUNNING
        elif status in ("exited", "created"):
            return ContainerStatus.STOPPED
        else:
            return ContainerStatus.ERROR

    async def build_image(self, config: ContainerConfig) -> dict[str, Any]:
        """Build a Docker image for the project."""
        image_name = self._get_image_name(config.project_id)

        # Select Dockerfile template
        template_map = {
            ProjectType.NODE: "node.Dockerfile",
            ProjectType.PHP: "php.Dockerfile",
            ProjectType.PYTHON: "python.Dockerfile",
            ProjectType.CUSTOM: "base.Dockerfile",
        }
        dockerfile = DOCKER_TEMPLATES_PATH / template_map.get(config.project_type, "base.Dockerfile")

        if not dockerfile.exists():
            return {"success": False, "error": f"Dockerfile not found: {dockerfile}"}

        # Build args for version customization
        build_args = []
        if config.project_type == ProjectType.NODE:
            build_args.extend(["--build-arg", f"NODE_VERSION={config.node_version}"])
        elif config.project_type == ProjectType.PHP:
            build_args.extend(["--build-arg", f"PHP_VERSION={config.php_version}"])
        elif config.project_type == ProjectType.PYTHON:
            build_args.extend(["--build-arg", f"PYTHON_VERSION={config.python_version}"])

        cmd = [
            "docker", "build",
            "-t", image_name,
            "-f", str(dockerfile),
            *build_args,
            "/home/wyld-core",  # Build context
        ]

        logger.info(f"Building Docker image: {image_name}", project_id=config.project_id)
        result = await self._run_command(cmd)

        if result["returncode"] == 0:
            logger.info(f"Image built successfully: {image_name}")
            return {"success": True, "image": image_name}
        else:
            logger.error(f"Image build failed: {result['stderr']}")
            return {"success": False, "error": result["stderr"]}

    async def create_container(self, config: ContainerConfig) -> dict[str, Any]:
        """Create a container for the project."""
        # Ensure Docker network exists
        self._ensure_network_sync()

        container_name = self._get_container_name(config.project_id)
        image_name = self._get_image_name(config.project_id)

        # Check if image exists, build if not
        result = await self._run_command(["docker", "image", "inspect", image_name])
        if result["returncode"] != 0:
            build_result = await self.build_image(config)
            if not build_result.get("success"):
                return build_result

        # Remove existing container if any
        await self._run_command(["docker", "rm", "-f", container_name])

        # Build environment variables
        env_args = []
        base_env = {
            "PAI_PROJECT_ID": config.project_id,
            "PAI_PROJECT_NAME": config.project_name,
            "PAI_PROJECT_ROOT": "/app",
            "PAI_API_URL": os.environ.get("API_BASE_URL", "http://host.docker.internal:8000"),
        }
        if config.env_vars:
            base_env.update(config.env_vars)

        for key, value in base_env.items():
            env_args.extend(["-e", f"{key}={value}"])

        # Build port mappings
        port_args = []
        if config.expose_ports:
            for port in config.expose_ports:
                port_args.extend(["-p", f"{port}:{port}"])

        cmd = [
            "docker", "create",
            "--name", container_name,
            "--network", WYLD_NETWORK,
            # Mount project directory
            "-v", f"{config.root_path}:/app",
            # Mount Claude CLI credentials (read-write needed for session state)
            "-v", "/home/wyld-api/.claude:/home/wyld/.claude",
            # Resource limits
            "--memory", config.memory_limit,
            "--cpus", config.cpu_limit,
            # Allow access to host services
            "--add-host", "host.docker.internal:host-gateway",
            # Environment
            *env_args,
            # Ports
            *port_args,
            # Labels
            "--label", f"wyld.project.id={config.project_id}",
            "--label", f"wyld.project.type={config.project_type.value}",
            # Image
            image_name,
        ]

        logger.info(f"Creating container: {container_name}", project_id=config.project_id)
        result = await self._run_command(cmd)

        if result["returncode"] == 0:
            return {"success": True, "container": container_name}
        else:
            return {"success": False, "error": result["stderr"]}

    async def start_container(self, project_id: str) -> dict[str, Any]:
        """Start a project's container."""
        container_name = self._get_container_name(project_id)

        result = await self._run_command(["docker", "start", container_name])

        if result["returncode"] == 0:
            logger.info(f"Container started: {container_name}")
            return {"success": True}
        else:
            return {"success": False, "error": result["stderr"]}

    async def stop_container(self, project_id: str) -> dict[str, Any]:
        """Stop a project's container."""
        container_name = self._get_container_name(project_id)

        result = await self._run_command(["docker", "stop", container_name])

        if result["returncode"] == 0:
            logger.info(f"Container stopped: {container_name}")
            return {"success": True}
        else:
            return {"success": False, "error": result["stderr"]}

    async def remove_container(self, project_id: str) -> dict[str, Any]:
        """Remove a project's container."""
        container_name = self._get_container_name(project_id)

        result = await self._run_command(["docker", "rm", "-f", container_name])

        if result["returncode"] == 0:
            logger.info(f"Container removed: {container_name}")
            return {"success": True}
        else:
            return {"success": False, "error": result["stderr"]}

    async def exec_command(
        self,
        project_id: str,
        command: list[str],
        user: str = "wyld",
        workdir: str = "/app",
    ) -> dict[str, Any]:
        """Execute a command in the project's container."""
        container_name = self._get_container_name(project_id)

        cmd = [
            "docker", "exec",
            "-u", user,
            "-w", workdir,
            container_name,
            *command,
        ]

        return await self._run_command(cmd)

    async def get_container_info(self, project_id: str) -> dict[str, Any]:
        """Get detailed information about a project's container."""
        container_name = self._get_container_name(project_id)

        result = await self._run_command([
            "docker", "inspect", container_name
        ])

        if result["returncode"] != 0:
            return {"exists": False}

        try:
            info = json.loads(result["stdout"])[0]
            return {
                "exists": True,
                "status": info["State"]["Status"],
                "running": info["State"]["Running"],
                "created": info["Created"],
                "image": info["Config"]["Image"],
                "memory_limit": info["HostConfig"]["Memory"],
                "cpu_limit": info["HostConfig"]["NanoCpus"],
                "mounts": [m["Source"] for m in info["Mounts"]],
            }
        except (json.JSONDecodeError, KeyError, IndexError):
            return {"exists": False, "error": "Failed to parse container info"}

    async def get_container_logs(
        self,
        project_id: str,
        tail: int = 100,
    ) -> str:
        """Get recent logs from a project's container."""
        container_name = self._get_container_name(project_id)

        result = await self._run_command([
            "docker", "logs", "--tail", str(tail), container_name
        ])

        return result["stdout"] + result["stderr"]


# Global instance
container_service = ContainerService()
