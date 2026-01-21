"""
Systemd management tools for the Infra Agent.

Provides service management and systemd unit controls.
"""

import asyncio
import os
import re
from pathlib import Path

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Systemd paths
SYSTEMD_SYSTEM_DIR = Path("/etc/systemd/system")
SYSTEMD_USER_DIR = Path.home() / ".config/systemd/user"


async def _run_systemctl(
    *args: str,
    user: bool = False,
) -> tuple[int, str, str]:
    """Run a systemctl command."""
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(args)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    return (
        process.returncode or 0,
        stdout.decode().strip(),
        stderr.decode().strip(),
    )


async def _run_journalctl(
    *args: str,
    user: bool = False,
) -> tuple[int, str, str]:
    """Run a journalctl command."""
    cmd = ["journalctl"]
    if user:
        cmd.append("--user")
    cmd.extend(args)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    return (
        process.returncode or 0,
        stdout.decode().strip(),
        stderr.decode().strip(),
    )


def _parse_service_status(output: str) -> dict:
    """Parse systemctl status output into structured data."""
    status = {
        "loaded": False,
        "active": False,
        "running": False,
        "enabled": False,
    }

    for line in output.splitlines():
        line = line.strip()

        if line.startswith("Loaded:"):
            status["loaded"] = "loaded" in line.lower()
            status["enabled"] = "enabled" in line.lower()
            # Extract unit file path
            match = re.search(r"\(([^;]+)", line)
            if match:
                status["unit_file"] = match.group(1)

        elif line.startswith("Active:"):
            status["active"] = "active" in line.lower() and "inactive" not in line.lower()
            status["running"] = "running" in line.lower()
            # Extract state
            match = re.search(r"Active:\s+(\S+)", line)
            if match:
                status["state"] = match.group(1)

        elif line.startswith("Main PID:"):
            match = re.search(r"Main PID:\s+(\d+)", line)
            if match:
                status["main_pid"] = int(match.group(1))

        elif line.startswith("Memory:"):
            match = re.search(r"Memory:\s+(\S+)", line)
            if match:
                status["memory"] = match.group(1)

        elif line.startswith("CPU:"):
            match = re.search(r"CPU:\s+(\S+)", line)
            if match:
                status["cpu"] = match.group(1)

        elif line.startswith("CGroup:"):
            match = re.search(r"CGroup:\s+(.+)", line)
            if match:
                status["cgroup"] = match.group(1)

    return status


@tool(
    name="systemd_list_units",
    description="List systemd units (services, timers, etc.)",
    parameters={
        "type": "object",
        "properties": {
            "unit_type": {
                "type": "string",
                "enum": ["service", "timer", "socket", "mount", "target", "path"],
                "description": "Filter by unit type",
            },
            "state": {
                "type": "string",
                "enum": ["running", "failed", "inactive", "active"],
                "description": "Filter by state",
            },
            "user": {
                "type": "boolean",
                "description": "List user units instead of system units",
                "default": False,
            },
        },
    },
)
async def systemd_list_units(
    unit_type: str | None = None,
    state: str | None = None,
    user: bool = False,
) -> ToolResult:
    """List systemd units."""
    try:
        args = ["list-units", "--no-pager", "--no-legend"]

        if unit_type:
            args.extend(["--type", unit_type])

        if state:
            args.extend(["--state", state])

        code, stdout, stderr = await _run_systemctl(*args, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to list units: {stderr}")

        units = []
        for line in stdout.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 4:
                units.append({
                    "unit": parts[0],
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": parts[4] if len(parts) > 4 else "",
                })

        return ToolResult.ok(
            units,
            count=len(units),
            user_mode=user,
        )

    except Exception as e:
        logger.error("List units failed", error=str(e))
        return ToolResult.fail(f"List units failed: {e}")


@tool(
    name="systemd_get_status",
    description="Get detailed status of a systemd unit",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name (e.g., nginx.service)",
            },
            "user": {
                "type": "boolean",
                "description": "Check user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
)
async def systemd_get_status(unit: str, user: bool = False) -> ToolResult:
    """Get status of a systemd unit."""
    try:
        code, stdout, stderr = await _run_systemctl(
            "status", unit, "--no-pager", user=user
        )

        # Status returns non-zero for inactive services, which is OK
        if code != 0 and "could not be found" in stderr.lower():
            return ToolResult.fail(f"Unit not found: {unit}")

        status = _parse_service_status(stdout)
        status["unit"] = unit
        status["raw_output"] = stdout[:2000]  # Truncate long output

        return ToolResult.ok(status)

    except Exception as e:
        logger.error("Get status failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Get status failed: {e}")


@tool(
    name="systemd_start",
    description="Start a systemd unit",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to start",
            },
            "user": {
                "type": "boolean",
                "description": "Start user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
    permission_level=2,
)
async def systemd_start(unit: str, user: bool = False) -> ToolResult:
    """Start a systemd unit."""
    try:
        code, stdout, stderr = await _run_systemctl("start", unit, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to start {unit}: {stderr}")

        # Verify it started
        _, status_out, _ = await _run_systemctl(
            "is-active", unit, user=user
        )

        return ToolResult.ok(
            f"Unit {unit} started successfully",
            unit=unit,
            active=status_out.strip() == "active",
        )

    except Exception as e:
        logger.error("Start unit failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Start unit failed: {e}")


@tool(
    name="systemd_stop",
    description="Stop a systemd unit",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to stop",
            },
            "user": {
                "type": "boolean",
                "description": "Stop user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
    permission_level=2,
)
async def systemd_stop(unit: str, user: bool = False) -> ToolResult:
    """Stop a systemd unit."""
    try:
        code, stdout, stderr = await _run_systemctl("stop", unit, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to stop {unit}: {stderr}")

        return ToolResult.ok(
            f"Unit {unit} stopped successfully",
            unit=unit,
        )

    except Exception as e:
        logger.error("Stop unit failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Stop unit failed: {e}")


@tool(
    name="systemd_restart",
    description="Restart a systemd unit",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to restart",
            },
            "user": {
                "type": "boolean",
                "description": "Restart user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
    permission_level=2,
)
async def systemd_restart(unit: str, user: bool = False) -> ToolResult:
    """Restart a systemd unit."""
    try:
        code, stdout, stderr = await _run_systemctl("restart", unit, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to restart {unit}: {stderr}")

        # Verify it's running
        _, status_out, _ = await _run_systemctl(
            "is-active", unit, user=user
        )

        return ToolResult.ok(
            f"Unit {unit} restarted successfully",
            unit=unit,
            active=status_out.strip() == "active",
        )

    except Exception as e:
        logger.error("Restart unit failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Restart unit failed: {e}")


@tool(
    name="systemd_reload",
    description="Reload a systemd unit configuration",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to reload",
            },
            "user": {
                "type": "boolean",
                "description": "Reload user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
    permission_level=2,
)
async def systemd_reload(unit: str, user: bool = False) -> ToolResult:
    """Reload a systemd unit configuration."""
    try:
        code, stdout, stderr = await _run_systemctl("reload", unit, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to reload {unit}: {stderr}")

        return ToolResult.ok(
            f"Unit {unit} reloaded successfully",
            unit=unit,
        )

    except Exception as e:
        logger.error("Reload unit failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Reload unit failed: {e}")


@tool(
    name="systemd_enable",
    description="Enable a systemd unit to start at boot",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to enable",
            },
            "now": {
                "type": "boolean",
                "description": "Also start the unit immediately",
                "default": False,
            },
            "user": {
                "type": "boolean",
                "description": "Enable user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
    permission_level=2,
)
async def systemd_enable(
    unit: str,
    now: bool = False,
    user: bool = False,
) -> ToolResult:
    """Enable a systemd unit."""
    try:
        args = ["enable", unit]
        if now:
            args.append("--now")

        code, stdout, stderr = await _run_systemctl(*args, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to enable {unit}: {stderr}")

        return ToolResult.ok(
            f"Unit {unit} enabled successfully",
            unit=unit,
            started=now,
        )

    except Exception as e:
        logger.error("Enable unit failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Enable unit failed: {e}")


@tool(
    name="systemd_disable",
    description="Disable a systemd unit from starting at boot",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to disable",
            },
            "now": {
                "type": "boolean",
                "description": "Also stop the unit immediately",
                "default": False,
            },
            "user": {
                "type": "boolean",
                "description": "Disable user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
    permission_level=2,
)
async def systemd_disable(
    unit: str,
    now: bool = False,
    user: bool = False,
) -> ToolResult:
    """Disable a systemd unit."""
    try:
        args = ["disable", unit]
        if now:
            args.append("--now")

        code, stdout, stderr = await _run_systemctl(*args, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to disable {unit}: {stderr}")

        return ToolResult.ok(
            f"Unit {unit} disabled successfully",
            unit=unit,
            stopped=now,
        )

    except Exception as e:
        logger.error("Disable unit failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Disable unit failed: {e}")


@tool(
    name="systemd_daemon_reload",
    description="Reload systemd daemon configuration (after modifying unit files)",
    parameters={
        "type": "object",
        "properties": {
            "user": {
                "type": "boolean",
                "description": "Reload user daemon instead of system daemon",
                "default": False,
            },
        },
    },
    permission_level=2,
)
async def systemd_daemon_reload(user: bool = False) -> ToolResult:
    """Reload systemd daemon configuration."""
    try:
        code, stdout, stderr = await _run_systemctl("daemon-reload", user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to reload daemon: {stderr}")

        return ToolResult.ok("Systemd daemon configuration reloaded")

    except Exception as e:
        logger.error("Daemon reload failed", error=str(e))
        return ToolResult.fail(f"Daemon reload failed: {e}")


@tool(
    name="systemd_view_logs",
    description="View journal logs for a systemd unit",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to view logs for",
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to show",
                "default": 100,
            },
            "since": {
                "type": "string",
                "description": "Show logs since (e.g., '1 hour ago', 'today', '2024-01-01')",
            },
            "until": {
                "type": "string",
                "description": "Show logs until",
            },
            "priority": {
                "type": "string",
                "enum": ["emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"],
                "description": "Filter by priority level",
            },
            "user": {
                "type": "boolean",
                "description": "View user unit logs",
                "default": False,
            },
        },
        "required": ["unit"],
    },
)
async def systemd_view_logs(
    unit: str,
    lines: int = 100,
    since: str | None = None,
    until: str | None = None,
    priority: str | None = None,
    user: bool = False,
) -> ToolResult:
    """View journal logs for a unit."""
    try:
        args = ["-u", unit, "--no-pager", "-n", str(lines)]

        if since:
            args.extend(["--since", since])
        if until:
            args.extend(["--until", until])
        if priority:
            args.extend(["-p", priority])

        code, stdout, stderr = await _run_journalctl(*args, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to get logs: {stderr}")

        log_lines = stdout.splitlines()

        return ToolResult.ok(
            log_lines,
            unit=unit,
            line_count=len(log_lines),
        )

    except Exception as e:
        logger.error("View logs failed", unit=unit, error=str(e))
        return ToolResult.fail(f"View logs failed: {e}")


@tool(
    name="systemd_read_unit_file",
    description="Read the content of a systemd unit file",
    parameters={
        "type": "object",
        "properties": {
            "unit": {
                "type": "string",
                "description": "Unit name to read",
            },
            "user": {
                "type": "boolean",
                "description": "Read user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["unit"],
    },
)
async def systemd_read_unit_file(unit: str, user: bool = False) -> ToolResult:
    """Read a systemd unit file."""
    try:
        # Get the unit file path
        code, stdout, stderr = await _run_systemctl(
            "show", unit, "-p", "FragmentPath", "--value", user=user
        )

        if code != 0 or not stdout.strip():
            return ToolResult.fail(f"Unit file not found for: {unit}")

        unit_path = Path(stdout.strip())

        if not unit_path.exists():
            return ToolResult.fail(f"Unit file does not exist: {unit_path}")

        content = unit_path.read_text()

        return ToolResult.ok(
            content,
            unit=unit,
            path=str(unit_path),
        )

    except Exception as e:
        logger.error("Read unit file failed", unit=unit, error=str(e))
        return ToolResult.fail(f"Read unit file failed: {e}")


@tool(
    name="systemd_create_service",
    description="Create a new systemd service unit file",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Service name (without .service extension)",
            },
            "description": {
                "type": "string",
                "description": "Service description",
            },
            "exec_start": {
                "type": "string",
                "description": "Command to start the service",
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for the service",
            },
            "user": {
                "type": "string",
                "description": "User to run the service as",
            },
            "group": {
                "type": "string",
                "description": "Group to run the service as",
            },
            "restart": {
                "type": "string",
                "enum": ["no", "on-success", "on-failure", "on-abnormal", "on-watchdog", "on-abort", "always"],
                "description": "Restart policy",
                "default": "on-failure",
            },
            "restart_sec": {
                "type": "integer",
                "description": "Time to wait before restarting (seconds)",
                "default": 5,
            },
            "environment": {
                "type": "object",
                "description": "Environment variables (key-value pairs)",
            },
            "environment_file": {
                "type": "string",
                "description": "Path to environment file",
            },
            "after": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Units to start after",
            },
            "wants": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Units this service wants",
            },
            "service_type": {
                "type": "string",
                "enum": ["simple", "exec", "forking", "oneshot", "dbus", "notify", "idle"],
                "description": "Service type",
                "default": "simple",
            },
            "user_unit": {
                "type": "boolean",
                "description": "Create as user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["name", "description", "exec_start"],
    },
    permission_level=2,
)
async def systemd_create_service(
    name: str,
    description: str,
    exec_start: str,
    working_directory: str | None = None,
    user: str | None = None,
    group: str | None = None,
    restart: str = "on-failure",
    restart_sec: int = 5,
    environment: dict | None = None,
    environment_file: str | None = None,
    after: list[str] | None = None,
    wants: list[str] | None = None,
    service_type: str = "simple",
    user_unit: bool = False,
) -> ToolResult:
    """Create a new systemd service unit file."""
    try:
        # Validate service name
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            return ToolResult.fail("Invalid service name")

        # Build unit file content
        lines = ["[Unit]", f"Description={description}"]

        if after:
            lines.append(f"After={' '.join(after)}")
        else:
            lines.append("After=network.target")

        if wants:
            lines.append(f"Wants={' '.join(wants)}")

        lines.extend(["", "[Service]", f"Type={service_type}", f"ExecStart={exec_start}"])

        if working_directory:
            lines.append(f"WorkingDirectory={working_directory}")

        if user and not user_unit:
            lines.append(f"User={user}")

        if group and not user_unit:
            lines.append(f"Group={group}")

        lines.extend([f"Restart={restart}", f"RestartSec={restart_sec}"])

        if environment:
            for key, value in environment.items():
                lines.append(f"Environment={key}={value}")

        if environment_file:
            lines.append(f"EnvironmentFile={environment_file}")

        lines.extend(["", "[Install]", "WantedBy=multi-user.target"])

        unit_content = "\n".join(lines) + "\n"

        # Determine path
        if user_unit:
            SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
            unit_path = SYSTEMD_USER_DIR / f"{name}.service"
        else:
            unit_path = SYSTEMD_SYSTEM_DIR / f"{name}.service"

        # Write the unit file
        unit_path.write_text(unit_content)

        # Reload daemon
        await _run_systemctl("daemon-reload", user=user_unit)

        return ToolResult.ok(
            f"Service {name}.service created successfully",
            path=str(unit_path),
            content=unit_content,
        )

    except PermissionError as e:
        return ToolResult.fail(f"Permission denied: {e}")
    except Exception as e:
        logger.error("Create service failed", name=name, error=str(e))
        return ToolResult.fail(f"Create service failed: {e}")


@tool(
    name="systemd_create_timer",
    description="Create a systemd timer unit for scheduled execution",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Timer name (without .timer extension)",
            },
            "description": {
                "type": "string",
                "description": "Timer description",
            },
            "on_calendar": {
                "type": "string",
                "description": "Calendar expression (e.g., 'daily', 'hourly', '*-*-* 04:00:00')",
            },
            "on_boot_sec": {
                "type": "string",
                "description": "Time after boot to trigger (e.g., '5min')",
            },
            "on_unit_active_sec": {
                "type": "string",
                "description": "Time after service was last activated (e.g., '1h')",
            },
            "persistent": {
                "type": "boolean",
                "description": "Run immediately if missed while system was off",
                "default": False,
            },
            "user_unit": {
                "type": "boolean",
                "description": "Create as user unit instead of system unit",
                "default": False,
            },
        },
        "required": ["name", "description"],
    },
    permission_level=2,
)
async def systemd_create_timer(
    name: str,
    description: str,
    on_calendar: str | None = None,
    on_boot_sec: str | None = None,
    on_unit_active_sec: str | None = None,
    persistent: bool = False,
    user_unit: bool = False,
) -> ToolResult:
    """Create a systemd timer unit."""
    try:
        # Validate timer name
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            return ToolResult.fail("Invalid timer name")

        if not any([on_calendar, on_boot_sec, on_unit_active_sec]):
            return ToolResult.fail(
                "At least one trigger (on_calendar, on_boot_sec, on_unit_active_sec) is required"
            )

        # Build timer file content
        lines = ["[Unit]", f"Description={description}", "", "[Timer]"]

        if on_calendar:
            lines.append(f"OnCalendar={on_calendar}")
        if on_boot_sec:
            lines.append(f"OnBootSec={on_boot_sec}")
        if on_unit_active_sec:
            lines.append(f"OnUnitActiveSec={on_unit_active_sec}")

        if persistent:
            lines.append("Persistent=true")

        lines.extend(["", "[Install]", "WantedBy=timers.target"])

        timer_content = "\n".join(lines) + "\n"

        # Determine path
        if user_unit:
            SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
            timer_path = SYSTEMD_USER_DIR / f"{name}.timer"
        else:
            timer_path = SYSTEMD_SYSTEM_DIR / f"{name}.timer"

        # Write the timer file
        timer_path.write_text(timer_content)

        # Reload daemon
        await _run_systemctl("daemon-reload", user=user_unit)

        return ToolResult.ok(
            f"Timer {name}.timer created successfully",
            path=str(timer_path),
            content=timer_content,
            note=f"Create a matching {name}.service file for the timer to execute",
        )

    except PermissionError as e:
        return ToolResult.fail(f"Permission denied: {e}")
    except Exception as e:
        logger.error("Create timer failed", name=name, error=str(e))
        return ToolResult.fail(f"Create timer failed: {e}")


@tool(
    name="systemd_list_timers",
    description="List all active timers",
    parameters={
        "type": "object",
        "properties": {
            "show_all": {
                "type": "boolean",
                "description": "Show all timers (including inactive)",
                "default": False,
            },
            "user": {
                "type": "boolean",
                "description": "List user timers instead of system timers",
                "default": False,
            },
        },
    },
)
async def systemd_list_timers(
    show_all: bool = False,
    user: bool = False,
) -> ToolResult:
    """List all timers."""
    try:
        args = ["list-timers", "--no-pager", "--no-legend"]
        if show_all:
            args.append("--all")

        code, stdout, stderr = await _run_systemctl(*args, user=user)

        if code != 0:
            return ToolResult.fail(f"Failed to list timers: {stderr}")

        timers = []
        for line in stdout.splitlines():
            parts = line.split(None, 5)
            if len(parts) >= 5:
                timers.append({
                    "next": parts[0] + " " + parts[1] if len(parts) > 1 else parts[0],
                    "left": parts[2] if len(parts) > 2 else "",
                    "last": parts[3] if len(parts) > 3 else "",
                    "passed": parts[4] if len(parts) > 4 else "",
                    "unit": parts[5] if len(parts) > 5 else "",
                })

        return ToolResult.ok(
            timers,
            count=len(timers),
        )

    except Exception as e:
        logger.error("List timers failed", error=str(e))
        return ToolResult.fail(f"List timers failed: {e}")
