"""
Nginx operation tools for the Infra Agent.
"""

import asyncio
import os
from pathlib import Path

import aiofiles

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Nginx configuration paths
NGINX_CONFIG_DIR = Path(os.environ.get("NGINX_CONFIG_DIR", "/etc/nginx"))
NGINX_SITES_AVAILABLE = NGINX_CONFIG_DIR / "sites-available"
NGINX_SITES_ENABLED = NGINX_CONFIG_DIR / "sites-enabled"


async def _run_nginx_command(args: list[str]) -> tuple[int, str, str]:
    """Run an nginx command and return (returncode, stdout, stderr)."""
    process = await asyncio.create_subprocess_exec(
        "nginx",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    return (
        process.returncode or 0,
        stdout.decode().strip(),
        stderr.decode().strip(),
    )


async def _run_systemctl_command(args: list[str]) -> tuple[int, str, str]:
    """Run a systemctl command for nginx."""
    process = await asyncio.create_subprocess_exec(
        "systemctl",
        *args,
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
    name="nginx_status",
    description="Get Nginx service status and configuration info",
    parameters={
        "type": "object",
        "properties": {},
    },
)
async def nginx_status() -> ToolResult:
    """Get Nginx status."""
    try:
        # Get service status
        code, stdout, stderr = await _run_systemctl_command(
            ["status", "nginx", "--no-pager"]
        )

        # Parse service status
        is_active = "active (running)" in stdout.lower()

        # Get nginx version
        v_code, v_stdout, v_stderr = await _run_nginx_command(["-v"])
        version = v_stderr if v_stderr else v_stdout  # nginx outputs version to stderr

        # List enabled sites
        enabled_sites = []
        if NGINX_SITES_ENABLED.exists():
            enabled_sites = [
                f.name for f in NGINX_SITES_ENABLED.iterdir() if f.is_symlink()
            ]

        # List available sites
        available_sites = []
        if NGINX_SITES_AVAILABLE.exists():
            available_sites = [
                f.name for f in NGINX_SITES_AVAILABLE.iterdir() if f.is_file()
            ]

        result = {
            "active": is_active,
            "version": version,
            "enabled_sites": enabled_sites,
            "available_sites": available_sites,
            "config_dir": str(NGINX_CONFIG_DIR),
            "status_output": stdout[:500] if stdout else "Unable to get status",
        }

        return ToolResult.ok(result)

    except Exception as e:
        logger.error("Nginx status failed", error=str(e))
        return ToolResult.fail(f"Nginx status failed: {e}")


@tool(
    name="nginx_test_config",
    description="Test Nginx configuration for syntax errors",
    parameters={
        "type": "object",
        "properties": {
            "config_file": {
                "type": "string",
                "description": "Specific config file to test (optional)",
            },
        },
    },
)
async def nginx_test_config(config_file: str | None = None) -> ToolResult:
    """Test Nginx configuration."""
    try:
        args = ["-t"]

        if config_file:
            args.extend(["-c", config_file])

        code, stdout, stderr = await _run_nginx_command(args)

        # nginx outputs test results to stderr
        output = stderr if stderr else stdout
        success = code == 0 and "successful" in output.lower()

        if success:
            return ToolResult.ok(
                "Configuration test passed",
                output=output,
                valid=True,
            )
        else:
            return ToolResult.ok(
                "Configuration test failed",
                output=output,
                valid=False,
                errors=_parse_nginx_errors(output),
            )

    except Exception as e:
        logger.error("Nginx test config failed", error=str(e))
        return ToolResult.fail(f"Nginx test config failed: {e}")


def _parse_nginx_errors(output: str) -> list[dict[str, str]]:
    """Parse Nginx error messages from output."""
    errors = []
    for line in output.splitlines():
        if "emerg" in line.lower() or "error" in line.lower():
            errors.append({"message": line.strip()})
    return errors


@tool(
    name="nginx_reload",
    description="Reload Nginx configuration (graceful restart)",
    parameters={
        "type": "object",
        "properties": {
            "test_first": {
                "type": "boolean",
                "description": "Test configuration before reloading",
                "default": True,
            },
        },
    },
    permission_level=2,
)
async def nginx_reload(test_first: bool = True) -> ToolResult:
    """Reload Nginx configuration."""
    try:
        # Test configuration first if requested
        if test_first:
            test_code, test_stdout, test_stderr = await _run_nginx_command(["-t"])
            test_output = test_stderr if test_stderr else test_stdout

            if test_code != 0 or "successful" not in test_output.lower():
                return ToolResult.fail(
                    f"Configuration test failed, reload aborted: {test_output}"
                )

        # Reload nginx
        code, stdout, stderr = await _run_systemctl_command(["reload", "nginx"])

        if code != 0:
            return ToolResult.fail(f"Reload failed: {stderr}")

        return ToolResult.ok(
            "Nginx configuration reloaded successfully",
            tested=test_first,
        )

    except Exception as e:
        logger.error("Nginx reload failed", error=str(e))
        return ToolResult.fail(f"Nginx reload failed: {e}")
