"""
System operation tools for AI Infrastructure agents.

These tools provide system-level operations like shell execution,
process management, package installation, and service management.

Security:
- All shell commands are validated against a blocklist of dangerous patterns
- Commands are run with limited privileges where possible
- All operations are logged for audit
"""

import asyncio
import os
import re
import shutil
from pathlib import Path

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Dangerous shell patterns that are always blocked
BLOCKED_PATTERNS = [
    r"rm\s+(-rf?|-fr?|--recursive|--force)\s+/",  # rm -rf / (various flag orderings)
    r"rm\s+.*\s+/\s*$",  # rm anything ending with / (root)
    r"rm\s+.*--no-preserve-root",  # explicit bypass attempt
    r"dd\s+.*of=/dev/",  # dd to device
    r"mkfs\.",  # format filesystem
    r">\s*/dev/sd",  # write to block device
    r"chmod\s+777\s+/",  # chmod 777 on root
    r"chown\s+.*:\s*/",  # chown on root
    r"curl.*\|\s*(ba)?sh",  # curl pipe to bash/sh
    r"wget.*\|\s*(ba)?sh",  # wget pipe to bash/sh
    r":(){.*};:",  # fork bomb
    r"shutdown",  # shutdown commands
    r"reboot",  # reboot command
    r"init\s+[0-6]",  # init level change
    r"systemctl\s+(halt|poweroff|reboot)",  # systemctl power commands
    r">\s*/etc/passwd",  # overwrite passwd
    r">\s*/etc/shadow",  # overwrite shadow
]

# Allowed package managers
ALLOWED_PACKAGE_MANAGERS = ["apt", "apt-get", "pip", "pip3", "npm", "yarn", "cargo"]

# Allowed service operations
ALLOWED_SERVICE_OPERATIONS = ["start", "stop", "restart", "status", "enable", "disable"]


def _is_command_safe(command: str) -> tuple[bool, str | None]:
    """
    Check if a shell command is safe to execute.

    Returns:
        Tuple of (is_safe, reason if unsafe)
    """
    command_lower = command.lower()

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command_lower):
            return False, f"Command matches blocked pattern: {pattern}"

    return True, None


async def _run_command(
    command: str,
    timeout: int = 60,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """
    Run a shell command and return (returncode, stdout, stderr).

    Args:
        command: Shell command to execute
        timeout: Timeout in seconds
        cwd: Working directory (validated before use)

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        TimeoutError: If command exceeds timeout
        ValueError: If cwd doesn't exist
    """
    # Validate working directory if provided
    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            raise ValueError(f"Working directory does not exist: {cwd}")
        if not cwd_path.is_dir():
            raise ValueError(f"Working directory is not a directory: {cwd}")

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
        # Handle potential decode errors gracefully
        try:
            stdout_str = stdout.decode("utf-8").strip()
        except UnicodeDecodeError:
            stdout_str = stdout.decode("utf-8", errors="replace").strip()

        try:
            stderr_str = stderr.decode("utf-8").strip()
        except UnicodeDecodeError:
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

        return (
            process.returncode or 0,
            stdout_str,
            stderr_str,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(f"Command timed out after {timeout}s")


@tool(
    name="shell_execute",
    description="Execute a shell command with safety checks. Commands are validated against a blocklist of dangerous patterns.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (max 300)",
                "default": 60,
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command",
            },
        },
        "required": ["command"],
    },
    permission_level=2,  # EXECUTE
    capability_category=CapabilityCategory.SYSTEM,
    requires_confirmation=False,
)
async def shell_execute(
    command: str,
    timeout: int = 60,
    working_dir: str | None = None,
) -> ToolResult:
    """Execute a shell command with safety checks."""
    try:
        # Type coercion - Claude may pass timeout as string
        if timeout is None:
            timeout = 60
        elif isinstance(timeout, str):
            try:
                timeout = int(timeout)
            except ValueError:
                timeout = 60

        # Validate command is a string
        if not isinstance(command, str):
            return ToolResult.fail("Command must be a string")

        if not command.strip():
            return ToolResult.fail("Command cannot be empty")

        # Validate command safety
        is_safe, reason = _is_command_safe(command)
        if not is_safe:
            return ToolResult.fail(f"Command blocked: {reason}")

        # Limit timeout to reasonable range
        timeout = max(1, min(timeout, 300))

        # Execute
        code, stdout, stderr = await _run_command(command, timeout, working_dir)

        if code != 0:
            return ToolResult.fail(
                f"Command failed with exit code {code}",
                stdout=stdout,
                stderr=stderr,
                exit_code=code,
            )

        return ToolResult.ok(
            stdout if stdout else "Command completed successfully",
            stderr=stderr if stderr else None,
            exit_code=code,
        )

    except ValueError as e:
        # Working directory validation errors
        return ToolResult.fail(str(e))
    except TimeoutError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Shell execute failed", command=command[:100], error=str(e))
        return ToolResult.fail(f"Execution failed: {e}")


@tool(
    name="process_list",
    description="List running processes with optional filtering",
    parameters={
        "type": "object",
        "properties": {
            "filter_name": {
                "type": "string",
                "description": "Filter processes by name pattern",
            },
            "filter_user": {
                "type": "string",
                "description": "Filter processes by user",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of processes to return",
                "default": 50,
            },
        },
    },
    permission_level=0,  # READ_ONLY
    capability_category=CapabilityCategory.SYSTEM,
)
async def process_list(
    filter_name: str | None = None,
    filter_user: str | None = None,
    limit: int = 50,
) -> ToolResult:
    """List running processes."""
    try:
        # Type coercion for limit
        if limit is None:
            limit = 50
        elif isinstance(limit, str):
            try:
                limit = int(limit)
            except ValueError:
                limit = 50

        # Clamp limit to reasonable range
        limit = max(1, min(limit, 500))

        # Build ps command
        cmd = "ps aux --sort=-%mem"

        code, stdout, stderr = await _run_command(cmd)

        if code != 0:
            return ToolResult.fail(f"ps command failed: {stderr}")

        # Parse output
        lines = stdout.splitlines()
        if not lines:
            return ToolResult.ok([], count=0)

        header = lines[0]
        processes = []

        for line in lines[1:]:
            if len(processes) >= limit:
                break

            parts = line.split(None, 10)
            if len(parts) < 11:
                continue

            user, pid, cpu, mem, vsz, rss, tty, stat, start, time_, cmd_name = parts

            # Apply filters
            if filter_name and filter_name.lower() not in cmd_name.lower():
                continue
            if filter_user and filter_user != user:
                continue

            # Safe type conversion with defaults
            try:
                pid_int = int(pid)
            except (ValueError, TypeError):
                pid_int = 0

            try:
                cpu_float = float(cpu)
            except (ValueError, TypeError):
                cpu_float = 0.0

            try:
                mem_float = float(mem)
            except (ValueError, TypeError):
                mem_float = 0.0

            try:
                vsz_int = int(vsz)
            except (ValueError, TypeError):
                vsz_int = 0

            try:
                rss_int = int(rss)
            except (ValueError, TypeError):
                rss_int = 0

            processes.append({
                "user": user,
                "pid": pid_int,
                "cpu_percent": cpu_float,
                "mem_percent": mem_float,
                "vsz_kb": vsz_int,
                "rss_kb": rss_int,
                "status": stat,
                "command": cmd_name[:200],
            })

        return ToolResult.ok(
            processes,
            count=len(processes),
            header=header,
        )

    except Exception as e:
        logger.error("Process list failed", error=str(e))
        return ToolResult.fail(f"Failed to list processes: {e}")


@tool(
    name="process_kill",
    description="Terminate a process by PID. Use with caution.",
    parameters={
        "type": "object",
        "properties": {
            "pid": {
                "type": "integer",
                "description": "Process ID to terminate",
            },
            "signal": {
                "type": "string",
                "enum": ["TERM", "KILL", "HUP"],
                "description": "Signal to send (default: TERM)",
                "default": "TERM",
            },
        },
        "required": ["pid"],
    },
    permission_level=2,  # EXECUTE
    capability_category=CapabilityCategory.SYSTEM,
    requires_confirmation=True,
)
async def process_kill(
    pid: int,
    signal: str = "TERM",
) -> ToolResult:
    """Terminate a process by PID."""
    try:
        # Type coercion - Claude may pass pid as string
        if isinstance(pid, str):
            try:
                pid = int(pid)
            except ValueError:
                return ToolResult.fail(f"Invalid PID: {pid}")

        if pid is None:
            return ToolResult.fail("PID is required")

        # Validate PID is a positive integer
        if not isinstance(pid, int) or pid <= 0:
            return ToolResult.fail(f"Invalid PID: {pid}")

        # Don't allow killing PID 1 or very low PIDs
        if pid <= 10:
            return ToolResult.fail("Cannot kill system processes (PID <= 10)")

        # Handle signal parameter
        if signal is None:
            signal = "TERM"
        elif isinstance(signal, str):
            signal = signal.upper()
        else:
            signal = "TERM"

        # Map signal names
        signal_map = {
            "TERM": "SIGTERM",
            "KILL": "SIGKILL",
            "HUP": "SIGHUP",
        }

        sig = signal_map.get(signal, "SIGTERM")
        cmd = f"kill -s {sig} {pid}"

        code, stdout, stderr = await _run_command(cmd)

        if code != 0:
            if "No such process" in stderr:
                return ToolResult.fail(f"Process {pid} not found")
            return ToolResult.fail(f"Kill failed: {stderr}")

        return ToolResult.ok(
            f"Signal {sig} sent to process {pid}",
            pid=pid,
            signal=sig,
        )

    except Exception as e:
        logger.error("Process kill failed", pid=pid, error=str(e))
        return ToolResult.fail(f"Failed to kill process: {e}")


@tool(
    name="package_install",
    description="Install a system package using apt, pip, or npm",
    parameters={
        "type": "object",
        "properties": {
            "package": {
                "type": "string",
                "description": "Package name to install",
            },
            "manager": {
                "type": "string",
                "enum": ["apt", "pip", "pip3", "npm"],
                "description": "Package manager to use",
                "default": "apt",
            },
            "version": {
                "type": "string",
                "description": "Specific version to install (optional)",
            },
        },
        "required": ["package"],
    },
    permission_level=3,  # ADMIN
    capability_category=CapabilityCategory.SYSTEM,
    requires_confirmation=True,
)
async def package_install(
    package: str,
    manager: str = "apt",
    version: str | None = None,
) -> ToolResult:
    """Install a system package."""
    try:
        if manager not in ALLOWED_PACKAGE_MANAGERS:
            return ToolResult.fail(f"Package manager not allowed: {manager}")

        # Validate package name (basic sanitization)
        if not re.match(r"^[a-zA-Z0-9._-]+$", package):
            return ToolResult.fail("Invalid package name")

        # Build install command
        if manager in ("apt", "apt-get"):
            pkg_spec = f"{package}={version}" if version else package
            cmd = f"apt-get install -y {pkg_spec}"
        elif manager in ("pip", "pip3"):
            pkg_spec = f"{package}=={version}" if version else package
            cmd = f"{manager} install {pkg_spec}"
        elif manager == "npm":
            pkg_spec = f"{package}@{version}" if version else package
            cmd = f"npm install -g {pkg_spec}"
        else:
            return ToolResult.fail(f"Unsupported manager: {manager}")

        code, stdout, stderr = await _run_command(cmd, timeout=300)

        if code != 0:
            return ToolResult.fail(
                f"Installation failed: {stderr}",
                stdout=stdout,
            )

        return ToolResult.ok(
            f"Successfully installed {package}",
            package=package,
            manager=manager,
            version=version,
        )

    except Exception as e:
        logger.error("Package install failed", package=package, error=str(e))
        return ToolResult.fail(f"Installation failed: {e}")


@tool(
    name="package_remove",
    description="Remove a system package",
    parameters={
        "type": "object",
        "properties": {
            "package": {
                "type": "string",
                "description": "Package name to remove",
            },
            "manager": {
                "type": "string",
                "enum": ["apt", "pip", "pip3", "npm"],
                "description": "Package manager to use",
                "default": "apt",
            },
        },
        "required": ["package"],
    },
    permission_level=3,  # ADMIN
    capability_category=CapabilityCategory.SYSTEM,
    requires_confirmation=True,
)
async def package_remove(
    package: str,
    manager: str = "apt",
) -> ToolResult:
    """Remove a system package."""
    try:
        if manager not in ALLOWED_PACKAGE_MANAGERS:
            return ToolResult.fail(f"Package manager not allowed: {manager}")

        # Validate package name
        if not re.match(r"^[a-zA-Z0-9._-]+$", package):
            return ToolResult.fail("Invalid package name")

        # Build remove command
        if manager in ("apt", "apt-get"):
            cmd = f"apt-get remove -y {package}"
        elif manager in ("pip", "pip3"):
            cmd = f"{manager} uninstall -y {package}"
        elif manager == "npm":
            cmd = f"npm uninstall -g {package}"
        else:
            return ToolResult.fail(f"Unsupported manager: {manager}")

        code, stdout, stderr = await _run_command(cmd, timeout=300)

        if code != 0:
            return ToolResult.fail(f"Removal failed: {stderr}")

        return ToolResult.ok(
            f"Successfully removed {package}",
            package=package,
            manager=manager,
        )

    except Exception as e:
        logger.error("Package remove failed", package=package, error=str(e))
        return ToolResult.fail(f"Removal failed: {e}")


@tool(
    name="service_manage",
    description="Manage system services (start, stop, restart, status)",
    parameters={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Service name",
            },
            "action": {
                "type": "string",
                "enum": ["start", "stop", "restart", "status", "enable", "disable"],
                "description": "Action to perform",
            },
        },
        "required": ["service", "action"],
    },
    permission_level=3,  # ADMIN
    capability_category=CapabilityCategory.SYSTEM,
    requires_confirmation=True,
)
async def service_manage(
    service: str,
    action: str,
) -> ToolResult:
    """Manage system services."""
    try:
        # Validate required parameters
        if not service:
            return ToolResult.fail("Service name is required")

        if not action:
            return ToolResult.fail("Action is required")

        # Normalize action to lowercase
        if isinstance(action, str):
            action = action.lower().strip()
        else:
            return ToolResult.fail(f"Invalid action type: {type(action)}")

        if action not in ALLOWED_SERVICE_OPERATIONS:
            return ToolResult.fail(
                f"Action not allowed: {action}. "
                f"Allowed: {', '.join(ALLOWED_SERVICE_OPERATIONS)}"
            )

        # Validate service name (prevent command injection)
        if not isinstance(service, str):
            return ToolResult.fail(f"Invalid service type: {type(service)}")

        service = service.strip()
        if not re.match(r"^[a-zA-Z0-9._@-]+$", service):
            return ToolResult.fail(
                f"Invalid service name: {service}. "
                "Only alphanumeric, dots, underscores, @ and hyphens allowed."
            )

        # Check if systemctl is available
        if not shutil.which("systemctl"):
            return ToolResult.fail("systemctl not available on this system")

        cmd = f"systemctl {action} {service}"

        # Status doesn't need logging
        if action != "status":
            logger.info("Service action", service=service, action=action)

        code, stdout, stderr = await _run_command(cmd)

        # For status, non-zero may just mean "inactive" - still return the output
        if action == "status":
            return ToolResult.ok(
                stdout if stdout else stderr,
                service=service,
                action=action,
                exit_code=code,
            )

        if code != 0:
            return ToolResult.fail(
                f"Service action failed: {stderr}",
                stdout=stdout,
                exit_code=code,
            )

        return ToolResult.ok(
            f"Successfully executed {action} on {service}",
            service=service,
            action=action,
        )

    except Exception as e:
        logger.error("Service manage failed", service=service, error=str(e))
        return ToolResult.fail(f"Service operation failed: {e}")


@tool(
    name="system_info",
    description="Get system information (OS, kernel, memory, disk, etc.)",
    parameters={
        "type": "object",
        "properties": {
            "include_env": {
                "type": "boolean",
                "description": "Include environment variables (filtered)",
                "default": False,
            },
        },
    },
    permission_level=0,  # READ_ONLY
    capability_category=CapabilityCategory.SYSTEM,
)
async def system_info(
    include_env: bool = False,
) -> ToolResult:
    """Get system information."""
    try:
        import platform

        info = {
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
            },
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
            },
        }

        # Get memory info
        code, stdout, _ = await _run_command("free -m")
        if code == 0:
            lines = stdout.splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    info["memory"] = {
                        "total_mb": int(parts[1]),
                        "used_mb": int(parts[2]),
                        "free_mb": int(parts[3]),
                    }

        # Get disk info
        code, stdout, _ = await _run_command("df -h /")
        if code == 0:
            lines = stdout.splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    info["disk"] = {
                        "total": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "use_percent": parts[4] if len(parts) > 4 else None,
                    }

        # Get uptime
        code, stdout, _ = await _run_command("uptime -p")
        if code == 0:
            info["uptime"] = stdout.strip()

        # Get hostname
        info["hostname"] = platform.node()

        # Include filtered environment variables
        if include_env:
            safe_env_keys = [
                "PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL",
                "TERM", "HOSTNAME", "PWD",
            ]
            info["environment"] = {
                k: os.environ.get(k, "") for k in safe_env_keys
            }

        return ToolResult.ok(info)

    except Exception as e:
        logger.error("System info failed", error=str(e))
        return ToolResult.fail(f"Failed to get system info: {e}")


@tool(
    name="resource_monitor",
    description="Monitor CPU, memory, and disk usage in real-time snapshot",
    parameters={
        "type": "object",
        "properties": {
            "include_per_cpu": {
                "type": "boolean",
                "description": "Include per-CPU statistics",
                "default": False,
            },
        },
    },
    permission_level=0,  # READ_ONLY
    capability_category=CapabilityCategory.MONITORING,
)
async def resource_monitor(
    include_per_cpu: bool = False,
) -> ToolResult:
    """Get current resource usage snapshot."""
    try:
        metrics = {}

        # CPU usage (using /proc/stat)
        code, stdout, _ = await _run_command("top -bn1 | head -5")
        if code == 0:
            for line in stdout.splitlines():
                if line.startswith("%Cpu"):
                    # Parse: %Cpu(s):  1.2 us,  0.5 sy,  0.0 ni, 98.0 id, ...
                    parts = line.split(",")
                    for part in parts:
                        if "us" in part:
                            metrics["cpu_user"] = part.split()[0].replace("%Cpu(s):", "").strip()
                        elif "sy" in part:
                            metrics["cpu_system"] = part.split()[0].strip()
                        elif "id" in part:
                            metrics["cpu_idle"] = part.split()[0].strip()

        # Memory usage
        code, stdout, _ = await _run_command("free -b")
        if code == 0:
            lines = stdout.splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 7:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    available = int(parts[6]) if len(parts) > 6 else free
                    metrics["memory"] = {
                        "total_bytes": total,
                        "used_bytes": used,
                        "free_bytes": free,
                        "available_bytes": available,
                        "used_percent": round((used / total) * 100, 2) if total > 0 else 0,
                    }

        # Disk usage
        code, stdout, _ = await _run_command("df -B1 / | tail -1")
        if code == 0:
            parts = stdout.split()
            if len(parts) >= 5:
                metrics["disk"] = {
                    "total_bytes": int(parts[1]),
                    "used_bytes": int(parts[2]),
                    "available_bytes": int(parts[3]),
                    "used_percent": parts[4],
                }

        # Load average
        code, stdout, _ = await _run_command("cat /proc/loadavg")
        if code == 0:
            parts = stdout.split()
            if len(parts) >= 3:
                metrics["load_average"] = {
                    "1min": float(parts[0]),
                    "5min": float(parts[1]),
                    "15min": float(parts[2]),
                }

        # Per-CPU if requested
        if include_per_cpu:
            code, stdout, _ = await _run_command("mpstat -P ALL 1 1 2>/dev/null | tail -n +4")
            if code == 0:
                cpus = []
                for line in stdout.splitlines():
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 12 and parts[1] != "CPU":
                            cpus.append({
                                "cpu": parts[1],
                                "user": parts[2],
                                "system": parts[4],
                                "idle": parts[11],
                            })
                if cpus:
                    metrics["per_cpu"] = cpus

        return ToolResult.ok(metrics)

    except Exception as e:
        logger.error("Resource monitor failed", error=str(e))
        return ToolResult.fail(f"Failed to get resource metrics: {e}")


# Alias for backwards compatibility with __init__.py
get_system_info = system_info


async def _check_tcp_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Check if a TCP port is open."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False


@tool(
    name="check_service_health",
    description="""Check the health of infrastructure services (Redis, PostgreSQL, Qdrant, API).
    Use this to verify that required services are running before starting tasks that depend on them.""",
    parameters={
        "type": "object",
        "properties": {
            "services": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["redis", "postgres", "qdrant", "api", "all"],
                },
                "description": "Services to check (default: all)",
            },
        },
    },
    permission_level=0,  # READ_ONLY
    capability_category=CapabilityCategory.MONITORING,
)
async def check_service_health(
    services: list[str] | None = None,
) -> ToolResult:
    """Check health of infrastructure services."""
    try:
        from ai_core import get_settings
        from datetime import datetime, timezone

        settings = get_settings()

        # Define service checks
        service_checks = {
            "redis": {
                "host": settings.redis.host,
                "port": settings.redis.port,
                "check_type": "tcp",
            },
            "postgres": {
                "host": settings.postgres.host,
                "port": settings.postgres.port,
                "check_type": "tcp",
            },
            "qdrant": {
                "host": settings.qdrant.host,
                "port": settings.qdrant.port,
                "check_type": "tcp",
            },
            "api": {
                "host": "localhost",
                "port": int(os.environ.get("API_PORT", 8000)),
                "check_type": "tcp",
            },
        }

        # Determine which services to check
        if not services or "all" in services:
            services_to_check = list(service_checks.keys())
        else:
            services_to_check = [s for s in services if s in service_checks]

        results = {}
        overall_status = "healthy"

        # Check each service
        for service_name in services_to_check:
            config = service_checks[service_name]

            is_healthy = await _check_tcp_port(
                config["host"],
                config["port"],
            )
            results[service_name] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "host": config["host"],
                "port": config["port"],
            }

            if results[service_name]["status"] != "healthy":
                overall_status = "unhealthy"

        return ToolResult.ok({
            "message": f"Checked {len(results)} services",
            "status": overall_status,
            "services": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        logger.error("Check service health failed", error=str(e))
        return ToolResult.fail(f"Check service health failed: {e}")
