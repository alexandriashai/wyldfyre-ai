"""
Domain management tools for the Infra Agent.

Provides complete domain provisioning workflow including:
- Web root creation and permissions
- Nginx configuration
- SSL certificate provisioning
- Domain verification
"""

import asyncio
import os
import pwd
import grp
import socket
from pathlib import Path

import aiohttp

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Configuration paths
WEB_ROOT_BASE = Path(os.environ.get("WEB_ROOT_BASE", "/var/www"))
NGINX_SITES_AVAILABLE = Path(
    os.environ.get("NGINX_SITES_AVAILABLE", "/etc/nginx/sites-available")
)
NGINX_SITES_ENABLED = Path(
    os.environ.get("NGINX_SITES_ENABLED", "/etc/nginx/sites-enabled")
)
CERT_DIR = Path(os.environ.get("CERT_DIR", "/etc/letsencrypt/live"))
CERTBOT_PATH = os.environ.get("CERTBOT_PATH", "certbot")

# Default web server user/group
WEB_USER = os.environ.get("WEB_USER", "www-data")
WEB_GROUP = os.environ.get("WEB_GROUP", "www-data")


def _validate_domain(domain: str) -> tuple[bool, str]:
    """Validate domain name format."""
    if not domain:
        return False, "Domain cannot be empty"

    # Basic domain validation
    if len(domain) > 253:
        return False, "Domain too long (max 253 chars)"

    # Check each label
    labels = domain.split(".")
    if len(labels) < 2:
        return False, "Domain must have at least two parts"

    for label in labels:
        if not label:
            return False, "Empty label in domain"
        if len(label) > 63:
            return False, f"Label '{label}' too long (max 63 chars)"
        if not label[0].isalnum():
            return False, "Labels must start with alphanumeric"
        if not label[-1].isalnum():
            return False, "Labels must end with alphanumeric"
        if not all(c.isalnum() or c == "-" for c in label):
            return False, "Labels can only contain alphanumeric and hyphens"

    return True, ""


def _is_safe_path(path: Path, base: Path) -> bool:
    """Check if path is safely within base directory."""
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _get_domain_status(domain: str) -> dict:
    """Get comprehensive status for a domain."""
    web_root = WEB_ROOT_BASE / domain
    nginx_config = NGINX_SITES_AVAILABLE / domain
    nginx_enabled = NGINX_SITES_ENABLED / domain
    cert_path = CERT_DIR / domain / "fullchain.pem"

    return {
        "domain": domain,
        "web_root": {
            "path": str(web_root),
            "exists": web_root.exists(),
            "is_dir": web_root.is_dir() if web_root.exists() else False,
        },
        "nginx": {
            "config_path": str(nginx_config),
            "config_exists": nginx_config.exists(),
            "enabled": nginx_enabled.exists() or nginx_enabled.is_symlink(),
        },
        "ssl": {
            "cert_path": str(cert_path),
            "has_certificate": cert_path.exists(),
        },
    }


async def _run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
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


async def _check_domain_resolves(domain: str) -> tuple[bool, str | None]:
    """Check if domain resolves to an IP address."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, socket.gethostbyname, domain)
        return True, result
    except socket.gaierror as e:
        return False, str(e)


async def _check_domain_accessible(
    domain: str,
    use_https: bool = False,
    timeout: int = 10,
) -> tuple[bool, int | None, str | None]:
    """Check if domain is accessible via HTTP(S)."""
    scheme = "https" if use_https else "http"
    url = f"{scheme}://{domain}/"

    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(url, allow_redirects=False) as response:
                return True, response.status, None
    except aiohttp.ClientError as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, str(e)


@tool(
    name="list_domains",
    description="List all configured domains with their status",
    parameters={
        "type": "object",
        "properties": {
            "include_disabled": {
                "type": "boolean",
                "description": "Include disabled domains",
                "default": True,
            },
        },
    },
)
async def list_domains(include_disabled: bool = True) -> ToolResult:
    """List all configured domains."""
    try:
        domains = []

        # Check sites-available for all configured domains
        if NGINX_SITES_AVAILABLE.exists():
            for config_file in NGINX_SITES_AVAILABLE.iterdir():
                if config_file.is_file():
                    domain = config_file.name
                    # Skip default config
                    if domain in ("default", "default.conf"):
                        continue

                    status = _get_domain_status(domain)

                    # Skip disabled if not requested
                    if not include_disabled and not status["nginx"]["enabled"]:
                        continue

                    domains.append(status)

        # Sort by domain name
        domains.sort(key=lambda x: x["domain"])

        return ToolResult.ok(
            domains,
            count=len(domains),
        )

    except Exception as e:
        logger.error("List domains failed", error=str(e))
        return ToolResult.fail(f"List domains failed: {e}")


@tool(
    name="get_domain_status",
    description="Get detailed status of a specific domain",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain name to check",
            },
            "check_dns": {
                "type": "boolean",
                "description": "Check if DNS resolves",
                "default": False,
            },
            "check_http": {
                "type": "boolean",
                "description": "Check HTTP accessibility",
                "default": False,
            },
        },
        "required": ["domain"],
    },
)
async def get_domain_status(
    domain: str,
    check_dns: bool = False,
    check_http: bool = False,
) -> ToolResult:
    """Get detailed status of a domain."""
    try:
        # Validate domain
        valid, reason = _validate_domain(domain)
        if not valid:
            return ToolResult.fail(f"Invalid domain: {reason}")

        status = _get_domain_status(domain)

        # Optional DNS check
        if check_dns:
            resolves, ip_or_error = await _check_domain_resolves(domain)
            status["dns"] = {
                "resolves": resolves,
                "ip": ip_or_error if resolves else None,
                "error": None if resolves else ip_or_error,
            }

        # Optional HTTP check
        if check_http:
            http_ok, http_status, http_error = await _check_domain_accessible(
                domain, use_https=False
            )
            https_ok, https_status, https_error = await _check_domain_accessible(
                domain, use_https=True
            )

            status["http"] = {
                "accessible": http_ok,
                "status_code": http_status,
                "error": http_error,
            }
            status["https"] = {
                "accessible": https_ok,
                "status_code": https_status,
                "error": https_error,
            }

        # Determine overall provisioning status
        nginx_ok = status["nginx"]["config_exists"] and status["nginx"]["enabled"]
        web_ok = status["web_root"]["exists"] and status["web_root"]["is_dir"]
        ssl_ok = status["ssl"]["has_certificate"]

        if nginx_ok and web_ok and ssl_ok:
            status["provisioning_status"] = "complete"
        elif nginx_ok and web_ok:
            status["provisioning_status"] = "no_ssl"
        elif web_ok:
            status["provisioning_status"] = "web_root_only"
        else:
            status["provisioning_status"] = "not_provisioned"

        return ToolResult.ok(status)

    except Exception as e:
        logger.error("Get domain status failed", domain=domain, error=str(e))
        return ToolResult.fail(f"Get domain status failed: {e}")


@tool(
    name="provision_domain",
    description="Provision a new domain with web root, Nginx config, and optional SSL",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain name to provision",
            },
            "site_type": {
                "type": "string",
                "enum": ["static", "proxy", "php"],
                "description": "Type of site configuration",
                "default": "static",
            },
            "upstream_url": {
                "type": "string",
                "description": "Upstream URL for proxy sites",
            },
            "request_ssl": {
                "type": "boolean",
                "description": "Request SSL certificate from Let's Encrypt",
                "default": False,
            },
            "ssl_email": {
                "type": "string",
                "description": "Email for SSL certificate notifications",
            },
            "create_index": {
                "type": "boolean",
                "description": "Create a default index.html for static sites",
                "default": True,
            },
        },
        "required": ["domain"],
    },
    permission_level=2,
)
async def provision_domain(
    domain: str,
    site_type: str = "static",
    upstream_url: str | None = None,
    request_ssl: bool = False,
    ssl_email: str | None = None,
    create_index: bool = True,
) -> ToolResult:
    """Provision a new domain with all necessary configuration."""
    try:
        # Validate domain
        valid, reason = _validate_domain(domain)
        if not valid:
            return ToolResult.fail(f"Invalid domain: {reason}")

        # Validate site type requirements
        if site_type == "proxy" and not upstream_url:
            return ToolResult.fail("Proxy sites require upstream_url")

        if request_ssl and not ssl_email:
            return ToolResult.fail("SSL requests require ssl_email")

        steps_completed = []
        steps_failed = []

        # Step 1: Create web root directory
        web_root = WEB_ROOT_BASE / domain
        if not _is_safe_path(web_root, WEB_ROOT_BASE):
            return ToolResult.fail("Invalid domain path")

        try:
            web_root.mkdir(parents=True, exist_ok=True)

            # Set ownership
            try:
                uid = pwd.getpwnam(WEB_USER).pw_uid
                gid = grp.getgrnam(WEB_GROUP).gr_gid
                os.chown(web_root, uid, gid)
            except KeyError:
                logger.warning(
                    "Could not set ownership",
                    user=WEB_USER,
                    group=WEB_GROUP,
                )

            # Set permissions (755)
            os.chmod(web_root, 0o755)
            steps_completed.append("web_root_created")

            # Create default index.html for static sites
            if site_type == "static" and create_index:
                index_path = web_root / "index.html"
                if not index_path.exists():
                    index_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Welcome to {domain}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .container {{ text-align: center; }}
        h1 {{ font-size: 3rem; margin-bottom: 0.5rem; }}
        p {{ font-size: 1.2rem; opacity: 0.8; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{domain}</h1>
        <p>Your site has been provisioned successfully.</p>
    </div>
</body>
</html>
"""
                    index_path.write_text(index_content)
                    steps_completed.append("index_created")

        except PermissionError as e:
            steps_failed.append(f"web_root: {e}")
            return ToolResult.fail(f"Failed to create web root: {e}")

        # Step 2: Create Nginx configuration
        nginx_config = NGINX_SITES_AVAILABLE / domain
        try:
            if site_type == "static":
                config_content = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};

    root {web_root};
    index index.html index.htm;

    location / {{
        try_files $uri $uri/ =404;
    }}

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/{domain}.access.log;
    error_log /var/log/nginx/{domain}.error.log;
}}
"""
            elif site_type == "proxy":
                config_content = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};

    location / {{
        proxy_pass {upstream_url};
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

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/{domain}.access.log;
    error_log /var/log/nginx/{domain}.error.log;
}}
"""
            else:  # php
                config_content = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};

    root {web_root};
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

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/{domain}.access.log;
    error_log /var/log/nginx/{domain}.error.log;
}}
"""

            nginx_config.write_text(config_content)
            steps_completed.append("nginx_config_created")

        except PermissionError as e:
            steps_failed.append(f"nginx_config: {e}")

        # Step 3: Enable the site
        nginx_enabled = NGINX_SITES_ENABLED / domain
        try:
            if not nginx_enabled.exists():
                nginx_enabled.symlink_to(nginx_config)
            steps_completed.append("site_enabled")
        except PermissionError as e:
            steps_failed.append(f"enable_site: {e}")

        # Step 4: Test and reload Nginx
        code, stdout, stderr = await _run_command(["nginx", "-t"])
        if code == 0:
            await _run_command(["nginx", "-s", "reload"])
            steps_completed.append("nginx_reloaded")
        else:
            steps_failed.append(f"nginx_test: {stderr}")

        # Step 5: Request SSL certificate if requested
        if request_ssl and ssl_email:
            ssl_args = [
                CERTBOT_PATH,
                "certonly",
                "--webroot",
                "-w",
                str(web_root),
                "-d",
                domain,
                "--email",
                ssl_email,
                "--agree-tos",
                "--non-interactive",
            ]

            code, stdout, stderr = await _run_command(ssl_args)
            if code == 0:
                steps_completed.append("ssl_requested")

                # Update Nginx config with SSL
                ssl_config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {domain};

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    root {web_root};
    index index.html index.htm;

    location / {{
        try_files $uri $uri/ =404;
    }}

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/{domain}.access.log;
    error_log /var/log/nginx/{domain}.error.log;
}}
"""
                nginx_config.write_text(ssl_config)
                await _run_command(["nginx", "-s", "reload"])
                steps_completed.append("ssl_config_applied")
            else:
                steps_failed.append(f"ssl_request: {stderr}")

        # Determine final status
        if steps_failed:
            return ToolResult.ok(
                "Provisioning completed with some failures",
                domain=domain,
                web_root=str(web_root),
                steps_completed=steps_completed,
                steps_failed=steps_failed,
            )

        return ToolResult.ok(
            "Domain provisioned successfully",
            domain=domain,
            web_root=str(web_root),
            site_type=site_type,
            ssl_enabled=request_ssl and "ssl_config_applied" in steps_completed,
            steps_completed=steps_completed,
        )

    except Exception as e:
        logger.error("Provision domain failed", domain=domain, error=str(e))
        return ToolResult.fail(f"Provision domain failed: {e}")


@tool(
    name="remove_domain",
    description="Remove a domain configuration (optionally keeping web root)",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain name to remove",
            },
            "remove_web_root": {
                "type": "boolean",
                "description": "Also remove the web root directory",
                "default": False,
            },
            "remove_logs": {
                "type": "boolean",
                "description": "Also remove Nginx log files",
                "default": False,
            },
        },
        "required": ["domain"],
    },
    permission_level=2,
)
async def remove_domain(
    domain: str,
    remove_web_root: bool = False,
    remove_logs: bool = False,
) -> ToolResult:
    """Remove a domain configuration."""
    try:
        # Validate domain
        valid, reason = _validate_domain(domain)
        if not valid:
            return ToolResult.fail(f"Invalid domain: {reason}")

        steps_completed = []
        steps_failed = []

        # Step 1: Disable the site
        nginx_enabled = NGINX_SITES_ENABLED / domain
        try:
            if nginx_enabled.exists() or nginx_enabled.is_symlink():
                nginx_enabled.unlink()
                steps_completed.append("site_disabled")
        except PermissionError as e:
            steps_failed.append(f"disable_site: {e}")

        # Step 2: Remove Nginx configuration
        nginx_config = NGINX_SITES_AVAILABLE / domain
        try:
            if nginx_config.exists():
                nginx_config.unlink()
                steps_completed.append("config_removed")
        except PermissionError as e:
            steps_failed.append(f"remove_config: {e}")

        # Step 3: Reload Nginx
        code, _, stderr = await _run_command(["nginx", "-s", "reload"])
        if code == 0:
            steps_completed.append("nginx_reloaded")
        else:
            steps_failed.append(f"nginx_reload: {stderr}")

        # Step 4: Remove web root if requested
        if remove_web_root:
            web_root = WEB_ROOT_BASE / domain
            if _is_safe_path(web_root, WEB_ROOT_BASE) and web_root.exists():
                try:
                    import shutil

                    shutil.rmtree(web_root)
                    steps_completed.append("web_root_removed")
                except PermissionError as e:
                    steps_failed.append(f"remove_web_root: {e}")

        # Step 5: Remove logs if requested
        if remove_logs:
            log_dir = Path("/var/log/nginx")
            for log_pattern in [f"{domain}.access.log", f"{domain}.error.log"]:
                log_file = log_dir / log_pattern
                try:
                    if log_file.exists():
                        log_file.unlink()
                    # Also remove rotated logs
                    for rotated in log_dir.glob(f"{log_pattern}.*"):
                        rotated.unlink()
                    steps_completed.append(f"log_removed:{log_pattern}")
                except PermissionError as e:
                    steps_failed.append(f"remove_log:{log_pattern}: {e}")

        if steps_failed:
            return ToolResult.ok(
                "Removal completed with some failures",
                domain=domain,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
            )

        return ToolResult.ok(
            "Domain removed successfully",
            domain=domain,
            steps_completed=steps_completed,
        )

    except Exception as e:
        logger.error("Remove domain failed", domain=domain, error=str(e))
        return ToolResult.fail(f"Remove domain failed: {e}")


@tool(
    name="verify_domain",
    description="Verify domain is properly configured and accessible",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain name to verify",
            },
            "expected_content": {
                "type": "string",
                "description": "Expected content in the response (optional)",
            },
        },
        "required": ["domain"],
    },
)
async def verify_domain(
    domain: str,
    expected_content: str | None = None,
) -> ToolResult:
    """Verify a domain is properly configured and accessible."""
    try:
        # Validate domain
        valid, reason = _validate_domain(domain)
        if not valid:
            return ToolResult.fail(f"Invalid domain: {reason}")

        checks = {}

        # Check 1: DNS resolution
        resolves, ip_or_error = await _check_domain_resolves(domain)
        checks["dns"] = {
            "passed": resolves,
            "ip": ip_or_error if resolves else None,
            "error": None if resolves else ip_or_error,
        }

        # Check 2: Nginx configuration exists
        nginx_config = NGINX_SITES_AVAILABLE / domain
        nginx_enabled = NGINX_SITES_ENABLED / domain
        checks["nginx_config"] = {
            "passed": nginx_config.exists(),
            "enabled": nginx_enabled.exists() or nginx_enabled.is_symlink(),
        }

        # Check 3: Web root exists
        web_root = WEB_ROOT_BASE / domain
        checks["web_root"] = {
            "passed": web_root.exists() and web_root.is_dir(),
            "path": str(web_root),
        }

        # Check 4: HTTP accessibility
        http_ok, http_status, http_error = await _check_domain_accessible(domain)
        checks["http"] = {
            "passed": http_ok and http_status in [200, 301, 302, 303, 307, 308],
            "status_code": http_status,
            "error": http_error,
        }

        # Check 5: HTTPS accessibility (if certificate exists)
        cert_path = CERT_DIR / domain / "fullchain.pem"
        if cert_path.exists():
            https_ok, https_status, https_error = await _check_domain_accessible(
                domain, use_https=True
            )
            checks["https"] = {
                "passed": https_ok and https_status in [200, 301, 302, 303, 307, 308],
                "status_code": https_status,
                "error": https_error,
            }
        else:
            checks["https"] = {
                "passed": False,
                "skipped": True,
                "reason": "No SSL certificate",
            }

        # Check 6: Content verification if requested
        if expected_content and http_ok:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://{domain}/") as response:
                        content = await response.text()
                        checks["content"] = {
                            "passed": expected_content in content,
                            "found": expected_content in content,
                        }
            except Exception as e:
                checks["content"] = {
                    "passed": False,
                    "error": str(e),
                }

        # Determine overall status
        critical_checks = ["nginx_config", "web_root"]
        all_passed = all(
            checks.get(check, {}).get("passed", False) for check in critical_checks
        )

        return ToolResult.ok(
            checks,
            domain=domain,
            all_checks_passed=all_passed,
            recommendation="Domain is properly configured"
            if all_passed
            else "Some checks failed, review the results",
        )

    except Exception as e:
        logger.error("Verify domain failed", domain=domain, error=str(e))
        return ToolResult.fail(f"Verify domain failed: {e}")
