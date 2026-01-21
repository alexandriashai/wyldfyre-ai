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
                {"message": "Configuration test passed", "output": output, "valid": True},
            )
        else:
            return ToolResult.ok(
                {"message": "Configuration test failed", "output": output, "valid": False, "errors": _parse_nginx_errors(output)},
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


@tool(
    name="nginx_read_site_config",
    description="Read the configuration of a site",
    parameters={
        "type": "object",
        "properties": {
            "site_name": {
                "type": "string",
                "description": "Name of the site configuration file",
            },
        },
        "required": ["site_name"],
    },
)
async def nginx_read_site_config(site_name: str) -> ToolResult:
    """Read a site configuration file."""
    try:
        config_path = NGINX_SITES_AVAILABLE / site_name

        if not config_path.exists():
            return ToolResult.fail(f"Site config not found: {site_name}")

        async with aiofiles.open(config_path, "r") as f:
            content = await f.read()

        # Check if enabled
        enabled_path = NGINX_SITES_ENABLED / site_name
        is_enabled = enabled_path.exists() and enabled_path.is_symlink()

        return ToolResult.ok(
            content,
            site=site_name,
            enabled=is_enabled,
            path=str(config_path),
        )

    except Exception as e:
        logger.error("Read site config failed", site=site_name, error=str(e))
        return ToolResult.fail(f"Read site config failed: {e}")


@tool(
    name="nginx_create_site",
    description="Create a new Nginx site configuration from template",
    parameters={
        "type": "object",
        "properties": {
            "site_name": {
                "type": "string",
                "description": "Name for the site configuration file",
            },
            "server_name": {
                "type": "string",
                "description": "Domain name(s) for the server_name directive",
            },
            "site_type": {
                "type": "string",
                "enum": ["static", "proxy", "php"],
                "description": "Type of site configuration",
                "default": "static",
            },
            "root_path": {
                "type": "string",
                "description": "Web root path (for static/php sites)",
            },
            "upstream_url": {
                "type": "string",
                "description": "Upstream URL (for proxy sites, e.g., 'localhost:8000')",
            },
            "ssl": {
                "type": "boolean",
                "description": "Include SSL configuration placeholder",
                "default": False,
            },
        },
        "required": ["site_name", "server_name"],
    },
    permission_level=2,
)
async def nginx_create_site(
    site_name: str,
    server_name: str,
    site_type: str = "static",
    root_path: str | None = None,
    upstream_url: str | None = None,
    ssl: bool = False,
) -> ToolResult:
    """Create a new site configuration."""
    try:
        config_path = NGINX_SITES_AVAILABLE / site_name

        if config_path.exists():
            return ToolResult.fail(f"Site config already exists: {site_name}")

        # Generate configuration based on type
        if site_type == "static":
            web_root = root_path or f"/var/www/{server_name.split()[0]}"
            config = _generate_static_config(server_name, web_root, ssl)
        elif site_type == "proxy":
            if not upstream_url:
                return ToolResult.fail("upstream_url required for proxy sites")
            config = _generate_proxy_config(server_name, upstream_url, ssl)
        elif site_type == "php":
            web_root = root_path or f"/var/www/{server_name.split()[0]}"
            config = _generate_php_config(server_name, web_root, ssl)
        else:
            return ToolResult.fail(f"Unknown site type: {site_type}")

        # Ensure directory exists
        NGINX_SITES_AVAILABLE.mkdir(parents=True, exist_ok=True)

        # Write configuration
        async with aiofiles.open(config_path, "w") as f:
            await f.write(config)

        return ToolResult.ok(
            f"Created site configuration: {site_name}",
            site=site_name,
            path=str(config_path),
            type=site_type,
        )

    except Exception as e:
        logger.error("Create site failed", site=site_name, error=str(e))
        return ToolResult.fail(f"Create site failed: {e}")


def _generate_static_config(server_name: str, root_path: str, ssl: bool) -> str:
    """Generate static site configuration."""
    config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {server_name};

    root {root_path};
    index index.html index.htm;

    location / {{
        try_files $uri $uri/ =404;
    }}

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/{server_name.split()[0]}.access.log;
    error_log /var/log/nginx/{server_name.split()[0]}.error.log;
}}
"""
    if ssl:
        config += f"""
# SSL configuration - uncomment after obtaining certificate
# server {{
#     listen 443 ssl http2;
#     listen [::]:443 ssl http2;
#     server_name {server_name};
#
#     ssl_certificate /etc/letsencrypt/live/{server_name.split()[0]}/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/{server_name.split()[0]}/privkey.pem;
#     include /etc/nginx/snippets/ssl-params.conf;
#
#     root {root_path};
#     index index.html index.htm;
#
#     location / {{
#         try_files $uri $uri/ =404;
#     }}
# }}
"""
    return config


def _generate_proxy_config(server_name: str, upstream_url: str, ssl: bool) -> str:
    """Generate reverse proxy configuration."""
    config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {server_name};

    location / {{
        proxy_pass http://{upstream_url};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }}

    # Logging
    access_log /var/log/nginx/{server_name.split()[0]}.access.log;
    error_log /var/log/nginx/{server_name.split()[0]}.error.log;
}}
"""
    if ssl:
        config += f"""
# SSL configuration - uncomment after obtaining certificate
# server {{
#     listen 443 ssl http2;
#     listen [::]:443 ssl http2;
#     server_name {server_name};
#
#     ssl_certificate /etc/letsencrypt/live/{server_name.split()[0]}/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/{server_name.split()[0]}/privkey.pem;
#     include /etc/nginx/snippets/ssl-params.conf;
#
#     location / {{
#         proxy_pass http://{upstream_url};
#         proxy_http_version 1.1;
#         proxy_set_header Upgrade $http_upgrade;
#         proxy_set_header Connection 'upgrade';
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto $scheme;
#     }}
# }}
"""
    return config


def _generate_php_config(server_name: str, root_path: str, ssl: bool) -> str:
    """Generate PHP-FPM site configuration."""
    config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {server_name};

    root {root_path};
    index index.php index.html index.htm;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        fastcgi_pass unix:/var/run/php/php-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
        include fastcgi_params;
    }}

    location ~ /\\.ht {{
        deny all;
    }}

    # Logging
    access_log /var/log/nginx/{server_name.split()[0]}.access.log;
    error_log /var/log/nginx/{server_name.split()[0]}.error.log;
}}
"""
    return config


@tool(
    name="nginx_enable_site",
    description="Enable a site by creating symlink in sites-enabled",
    parameters={
        "type": "object",
        "properties": {
            "site_name": {
                "type": "string",
                "description": "Name of the site to enable",
            },
            "reload": {
                "type": "boolean",
                "description": "Reload Nginx after enabling",
                "default": True,
            },
        },
        "required": ["site_name"],
    },
    permission_level=2,
)
async def nginx_enable_site(site_name: str, reload: bool = True) -> ToolResult:
    """Enable a site."""
    try:
        available_path = NGINX_SITES_AVAILABLE / site_name
        enabled_path = NGINX_SITES_ENABLED / site_name

        if not available_path.exists():
            return ToolResult.fail(f"Site config not found: {site_name}")

        if enabled_path.exists():
            return ToolResult.ok(f"Site already enabled: {site_name}")

        # Ensure sites-enabled directory exists
        NGINX_SITES_ENABLED.mkdir(parents=True, exist_ok=True)

        # Create symlink
        enabled_path.symlink_to(available_path)

        # Test and reload if requested
        if reload:
            test_code, test_stdout, test_stderr = await _run_nginx_command(["-t"])
            test_output = test_stderr if test_stderr else test_stdout

            if test_code != 0 or "successful" not in test_output.lower():
                # Remove symlink on failure
                enabled_path.unlink()
                return ToolResult.fail(
                    f"Config test failed, site not enabled: {test_output}"
                )

            await _run_systemctl_command(["reload", "nginx"])

        return ToolResult.ok(
            f"Site enabled: {site_name}",
            site=site_name,
            reloaded=reload,
        )

    except Exception as e:
        logger.error("Enable site failed", site=site_name, error=str(e))
        return ToolResult.fail(f"Enable site failed: {e}")


@tool(
    name="nginx_disable_site",
    description="Disable a site by removing symlink from sites-enabled",
    parameters={
        "type": "object",
        "properties": {
            "site_name": {
                "type": "string",
                "description": "Name of the site to disable",
            },
            "reload": {
                "type": "boolean",
                "description": "Reload Nginx after disabling",
                "default": True,
            },
        },
        "required": ["site_name"],
    },
    permission_level=2,
)
async def nginx_disable_site(site_name: str, reload: bool = True) -> ToolResult:
    """Disable a site."""
    try:
        enabled_path = NGINX_SITES_ENABLED / site_name

        if not enabled_path.exists():
            return ToolResult.ok(f"Site already disabled: {site_name}")

        # Remove symlink
        enabled_path.unlink()

        # Reload if requested
        if reload:
            await _run_systemctl_command(["reload", "nginx"])

        return ToolResult.ok(
            f"Site disabled: {site_name}",
            site=site_name,
            reloaded=reload,
        )

    except Exception as e:
        logger.error("Disable site failed", site=site_name, error=str(e))
        return ToolResult.fail(f"Disable site failed: {e}")


@tool(
    name="nginx_view_logs",
    description="View Nginx access or error logs",
    parameters={
        "type": "object",
        "properties": {
            "log_type": {
                "type": "string",
                "enum": ["access", "error"],
                "description": "Type of log to view",
                "default": "error",
            },
            "site": {
                "type": "string",
                "description": "Specific site logs (uses main logs if not specified)",
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to show",
                "default": 100,
            },
        },
    },
)
async def nginx_view_logs(
    log_type: str = "error",
    site: str | None = None,
    lines: int = 100,
) -> ToolResult:
    """View Nginx logs."""
    try:
        log_dir = Path("/var/log/nginx")

        if site:
            log_file = log_dir / f"{site}.{log_type}.log"
        else:
            log_file = log_dir / f"{log_type}.log"

        if not log_file.exists():
            return ToolResult.fail(f"Log file not found: {log_file}")

        # Use tail to get last N lines
        process = await asyncio.create_subprocess_exec(
            "tail",
            "-n",
            str(lines),
            str(log_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return ToolResult.fail(f"Failed to read log: {stderr.decode()}")

        log_content = stdout.decode()

        return ToolResult.ok(
            log_content,
            log_type=log_type,
            site=site,
            file=str(log_file),
            lines=len(log_content.splitlines()),
        )

    except Exception as e:
        logger.error("View logs failed", error=str(e))
        return ToolResult.fail(f"View logs failed: {e}")
