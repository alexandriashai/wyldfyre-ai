"""
Domain management service.

Coordinates domain operations with direct provisioning code path.
Auto-provisions domains on creation (DNS, Nginx, SSL) without LLM agent.
"""

import asyncio
import os
import socket
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import AgentType, DomainStatus, TaskStatus, get_logger
from ai_messaging import PubSubManager, RedisClient

logger = get_logger(__name__)

# Server configuration for auto-provisioning
SERVER_IP = os.environ.get("SERVER_IP", "51.89.11.38")
SSL_EMAIL = os.environ.get("SSL_EMAIL", "alexandria.shai.eden@gmail.com")
WEB_ROOT_BASE = os.environ.get("WEB_ROOT_BASE", "/home/wyld-web/static")

# Nginx / SSL paths for direct provisioning
NGINX_SITES_AVAILABLE = "/etc/nginx/sites-available"
NGINX_SITES_ENABLED = "/etc/nginx/sites-enabled"
CERTBOT_PATH = os.environ.get("CERTBOT_PATH", "certbot")
WEB_USER = os.environ.get("WEB_USER", "www-data")
WEB_GROUP = os.environ.get("WEB_GROUP", "www-data")

# Cloudflare API
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CF_API_EMAIL = os.environ.get("CLOUDFLARE_EMAIL", "")
CF_API_KEY = os.environ.get("CLOUDFLARE_API_KEY", "")
CF_API_BASE = "https://api.cloudflare.com/client/v4"

# Deduplication constants
FAST_FAILURE_THRESHOLD = 10  # seconds - failures faster than this are suspicious
GRACE_WINDOW = 30  # seconds - wait for a possible "completed" after a failure


class DomainService:
    """Service for domain management operations."""

    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
        self.pubsub = PubSubManager(redis)

    async def list_domains(
        self,
        status: DomainStatus | None = None,
        project_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any]:
        """
        List all managed domains.

        Args:
            status: Optional status filter
            project_id: Optional project filter
            limit: Max results to return
            offset: Pagination offset

        Returns:
            List of Domain objects
        """
        from ai_db import Domain
        from sqlalchemy.orm import selectinload

        query = select(Domain).options(selectinload(Domain.project)).order_by(Domain.domain_name)

        if status:
            query = query.where(Domain.status == status)

        if project_id:
            query = query.where(Domain.project_id == project_id)

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_domain(self, domain_name: str) -> Any | None:
        """Get a domain by name."""
        from ai_db import Domain

        result = await self.db.execute(
            select(Domain).where(Domain.domain_name == domain_name)
        )
        return result.scalar_one_or_none()

    async def get_domain_by_id(self, domain_id: str) -> Any | None:
        """Get a domain by ID."""
        from ai_db import Domain

        result = await self.db.execute(
            select(Domain).where(Domain.id == domain_id)
        )
        return result.scalar_one_or_none()

    async def create_domain(
        self,
        domain_name: str,
        proxy_target: str | None = None,
        web_root: str | None = None,
        ssl_enabled: bool = True,
        dns_provider: str = "cloudflare",
        project_id: str | None = None,
        auto_provision: bool = True,
    ) -> Any:
        """
        Create a new domain record and auto-provision infrastructure.

        Creates the DB record then triggers the Infra Agent to:
        1. Create DNS A record pointing to server IP
        2. Create web root directory
        3. Configure Nginx virtual host
        4. Request SSL certificate via Let's Encrypt

        Args:
            domain_name: The domain name
            proxy_target: Optional proxy target (e.g., localhost:3000)
            web_root: Optional web root directory (defaults to /var/www/{domain})
            ssl_enabled: Whether to enable SSL (default: True)
            dns_provider: DNS provider name
            project_id: Optional project to associate with
            auto_provision: Whether to auto-provision (default: True)

        Returns:
            Created Domain object

        Raises:
            ValueError: If domain already exists
        """
        from ai_db import Domain
        from sqlalchemy.orm import selectinload

        # Check for existing domain
        existing = await self.get_domain(domain_name)
        if existing:
            raise ValueError(f"Domain {domain_name} already exists")

        # Validate domain name
        if not self._validate_domain_name(domain_name):
            raise ValueError(f"Invalid domain name: {domain_name}")

        # Default web root
        if not web_root:
            web_root = f"{WEB_ROOT_BASE}/{domain_name}"

        # Create domain record
        domain = Domain(
            domain_name=domain_name,
            proxy_target=proxy_target,
            web_root=web_root,
            ssl_enabled=ssl_enabled,
            dns_provider=dns_provider,
            project_id=project_id,
            status=DomainStatus.PENDING,
        )

        self.db.add(domain)
        await self.db.flush()

        # Refresh with project relationship loaded
        result = await self.db.execute(
            select(Domain).options(selectinload(Domain.project)).where(Domain.id == domain.id)
        )
        domain = result.scalar_one()

        logger.info("Domain created", domain=domain_name, id=domain.id, project_id=project_id)

        # Auto-provision: trigger full infrastructure setup
        if auto_provision:
            try:
                await self.provision_domain(domain_name)
                logger.info("Auto-provisioning triggered", domain=domain_name)
            except Exception as e:
                logger.error("Auto-provision failed to dispatch", domain=domain_name, error=str(e))

            # Re-load domain after provisioning changed status/timestamps
            result = await self.db.execute(
                select(Domain).options(selectinload(Domain.project)).where(Domain.id == domain.id)
            )
            domain = result.scalar_one()

        return domain

    async def update_domain(
        self,
        domain_name: str,
        **updates: Any,
    ) -> Any:
        """
        Update a domain's configuration.

        Args:
            domain_name: The domain to update
            **updates: Fields to update

        Returns:
            Updated Domain object

        Raises:
            ValueError: If domain not found
        """
        domain = await self.get_domain(domain_name)
        if not domain:
            raise ValueError(f"Domain {domain_name} not found")

        # Apply allowed updates
        allowed_fields = {
            "proxy_target",
            "web_root",
            "ssl_enabled",
            "ssl_auto_renew",
            "notes",
            "status",
            "error_message",
            "project_id",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(domain, field, value)

        await self.db.flush()
        await self.db.refresh(domain)

        logger.info("Domain updated", domain=domain_name, updates=list(updates.keys()))
        return domain

    async def delete_domain(self, domain_name: str) -> bool:
        """
        Delete a domain record.

        Args:
            domain_name: The domain to delete

        Returns:
            True if deleted, False if not found
        """
        domain = await self.get_domain(domain_name)
        if not domain:
            return False

        await self.db.delete(domain)
        await self.db.flush()

        logger.info("Domain deleted", domain=domain_name)
        return True

    async def provision_domain(self, domain_name: str) -> dict[str, Any]:
        """
        Provision a domain using direct code path (DNS → Nginx → SSL → Verify).

        Executes provisioning steps directly without LLM agent involvement.
        Returns immediately; background task updates domain status on completion.

        Args:
            domain_name: The domain to provision

        Returns:
            Task submission result with task_id for tracking
        """
        from ai_db import Task

        domain = await self.get_domain(domain_name)
        if not domain:
            raise ValueError(f"Domain {domain_name} not found")

        # Update status to provisioning
        domain.status = DomainStatus.PROVISIONING
        await self.db.flush()

        # Generate task ID and create DB record (fixes FK errors in api_usage)
        task_id = str(uuid4())
        task_record = Task(
            id=task_id,
            task_type="provision",
            title=f"Provision domain {domain_name}",
            status=TaskStatus.PENDING,
            priority=8,
            agent_type=AgentType.INFRA,
        )
        self.db.add(task_record)
        await self.db.flush()

        # Launch background provisioning (non-blocking)
        asyncio.create_task(
            self._execute_provisioning(task_id, domain_name, domain)
        )

        logger.info(
            "Domain provisioning started (direct)",
            domain=domain_name,
            task_id=task_id,
            server_ip=SERVER_IP,
            ssl_enabled=domain.ssl_enabled,
        )

        return {
            "success": True,
            "task_id": task_id,
            "message": f"Provisioning started for {domain_name}",
        }

    async def _execute_provisioning(
        self, task_id: str, domain_name: str, domain: Any
    ) -> None:
        """
        Background task: runs DNS + nginx + SSL + verify, updates status.

        Uses standalone DB sessions since the request-scoped session is closed.
        """
        from ..database import db_session_context
        from ai_db import Domain, Task

        started_at = datetime.now(timezone.utc)

        try:
            # Step 1: Create DNS record via Cloudflare API
            logger.info("Provisioning step 1: DNS record", domain=domain_name)
            await self._create_dns_record(domain_name, domain)

            # Step 2: Provision nginx + web root
            logger.info("Provisioning step 2: Nginx + web root", domain=domain_name)
            await self._provision_nginx(domain_name, domain)

            # Step 3: Request SSL (only if not Cloudflare-proxied)
            if not self._is_cloudflare_proxied(domain):
                logger.info("Provisioning step 3: SSL certificate", domain=domain_name)
                await self._request_ssl_certificate(domain_name, domain)
            else:
                logger.info("Provisioning step 3: Skipping SSL (Cloudflare-proxied)", domain=domain_name)

            # Step 4: Verify
            logger.info("Provisioning step 4: Verification", domain=domain_name)
            await self._verify_domain_direct(domain_name)

            # Update status to ACTIVE
            async with db_session_context() as session:
                result = await session.execute(
                    select(Domain).where(Domain.domain_name == domain_name)
                )
                d = result.scalar_one_or_none()
                if d:
                    d.status = DomainStatus.ACTIVE

                # Update task record
                task_result = await session.execute(
                    select(Task).where(Task.id == task_id)
                )
                task = task_result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now(timezone.utc)
                    task.duration_ms = int(
                        (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
                    )

            logger.info("Domain provisioned successfully (direct)", domain=domain_name, task_id=task_id)

        except Exception as e:
            logger.error(
                "Domain provisioning failed (direct)",
                domain=domain_name,
                task_id=task_id,
                error=str(e),
            )
            async with db_session_context() as session:
                result = await session.execute(
                    select(Domain).where(Domain.domain_name == domain_name)
                )
                d = result.scalar_one_or_none()
                if d:
                    d.status = DomainStatus.PENDING
                    d.error_message = str(e)[:500]

                # Update task record
                task_result = await session.execute(
                    select(Task).where(Task.id == task_id)
                )
                task = task_result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)[:500]
                    task.completed_at = datetime.now(timezone.utc)
                    task.duration_ms = int(
                        (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
                    )

    def _is_cloudflare_proxied(self, domain: Any) -> bool:
        """Check if domain uses Cloudflare proxy (orange cloud), skipping local SSL."""
        return getattr(domain, "dns_provider", "") == "cloudflare"

    async def _create_dns_record(self, domain_name: str, domain: Any) -> None:
        """Create DNS A record via Cloudflare API."""
        headers = self._get_cf_headers()
        if not headers:
            raise RuntimeError("Cloudflare API credentials not configured")

        root_domain = self._get_root_domain(domain_name)
        dns_name = self._get_dns_name(domain_name)

        # Look up zone ID
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CF_API_BASE}/zones",
                headers=headers,
                params={"name": root_domain},
            ) as resp:
                result = await resp.json()
                if resp.status >= 400 or not result.get("result"):
                    raise RuntimeError(f"Zone not found for domain: {root_domain}")
                zone_id = result["result"][0]["id"]

            # Create A record
            data = {
                "type": "A",
                "name": dns_name,
                "content": SERVER_IP,
                "ttl": 1,
                "proxied": True,
            }
            async with session.post(
                f"{CF_API_BASE}/zones/{zone_id}/dns_records",
                headers=headers,
                json=data,
            ) as resp:
                result = await resp.json()
                if resp.status >= 400:
                    errors = result.get("errors", [])
                    # Ignore "already exists" errors (code 81057)
                    if errors and errors[0].get("code") == 81057:
                        logger.info("DNS record already exists", domain=domain_name)
                        return
                    error_msg = errors[0].get("message") if errors else "Unknown error"
                    raise RuntimeError(f"Failed to create DNS record: {error_msg}")

        logger.info("DNS record created", domain=domain_name, ip=SERVER_IP)

    async def _provision_nginx(self, domain_name: str, domain: Any) -> None:
        """Create web root directory, nginx config, enable site, and reload."""
        web_root = domain.web_root or f"{WEB_ROOT_BASE}/{domain_name}"
        site_type = "proxy" if domain.proxy_target else "static"

        # Step 1: Create web root directory (via host command for proper permissions)
        webroot_cmd = (
            f"mkdir -p {web_root} && "
            f"chown {WEB_USER}:{WEB_GROUP} {web_root} && "
            f"chmod 755 {web_root}"
        )
        if site_type == "static":
            # Also create a default index.html if none exists
            default_html = (
                f"<!DOCTYPE html><html><head><title>{domain_name}</title></head>"
                f"<body><h1>{domain_name}</h1><p>Site provisioned successfully.</p></body></html>"
            )
            escaped_html = default_html.replace("'", "'\\''")
            webroot_cmd += (
                f" && [ ! -f {web_root}/index.html ] && "
                f"printf '%s' '{escaped_html}' > {web_root}/index.html && "
                f"chown {WEB_USER}:{WEB_GROUP} {web_root}/index.html && "
                f"chmod 644 {web_root}/index.html || true"
            )

        code, _, stderr = await self._run_command(["bash", "-c", webroot_cmd])
        if code != 0:
            logger.warning("Web root setup had issues", domain=domain_name, error=stderr)

        # Step 2: Build nginx config content
        if site_type == "static":
            config_content = (
                f"server {{\n"
                f"    listen 80;\n"
                f"    listen [::]:80;\n"
                f"    server_name {domain_name};\n\n"
                f"    root {web_root};\n"
                f"    index index.html index.htm;\n\n"
                f"    location / {{\n"
                f"        try_files $uri $uri/ =404;\n"
                f"    }}\n\n"
                f"    access_log /var/log/nginx/{domain_name}.access.log;\n"
                f"    error_log /var/log/nginx/{domain_name}.error.log;\n"
                f"}}\n"
            )
        else:  # proxy
            config_content = (
                f"server {{\n"
                f"    listen 80;\n"
                f"    listen [::]:80;\n"
                f"    server_name {domain_name};\n\n"
                f"    location / {{\n"
                f"        proxy_pass {domain.proxy_target};\n"
                f"        proxy_http_version 1.1;\n"
                f"        proxy_set_header Upgrade $http_upgrade;\n"
                f"        proxy_set_header Connection 'upgrade';\n"
                f"        proxy_set_header Host $host;\n"
                f"        proxy_set_header X-Real-IP $remote_addr;\n"
                f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
                f"        proxy_set_header X-Forwarded-Proto $scheme;\n"
                f"        proxy_read_timeout 86400;\n"
                f"    }}\n\n"
                f"    access_log /var/log/nginx/{domain_name}.access.log;\n"
                f"    error_log /var/log/nginx/{domain_name}.error.log;\n"
                f"}}\n"
            )

        # Steps 2-4: Write config, enable site, test and reload (via host supervisor)
        nginx_available = f"/etc/nginx/sites-available/{domain_name}.conf"
        nginx_enabled = f"/etc/nginx/sites-enabled/{domain_name}.conf"
        escaped_config = config_content.replace("'", "'\\''")
        provision_cmd = (
            f"printf '%s' '{escaped_config}' > {nginx_available} && "
            f"ln -sf {nginx_available} {nginx_enabled} && "
            f"nginx -t && nginx -s reload"
        )
        code, _, stderr = await self._run_command(["bash", "-c", provision_cmd])
        if code != 0:
            raise RuntimeError(f"Nginx provisioning failed: {stderr}")

        logger.info("Nginx provisioned", domain=domain_name, site_type=site_type)

    async def _request_ssl_certificate(self, domain_name: str, domain: Any) -> None:
        """Request SSL certificate via certbot."""
        web_root = domain.web_root or f"{WEB_ROOT_BASE}/{domain_name}"

        ssl_args = [
            CERTBOT_PATH, "certonly",
            "--webroot", "-w", web_root,
            "-d", domain_name,
            "--email", SSL_EMAIL,
            "--agree-tos", "--non-interactive",
        ]

        code, stdout, stderr = await self._run_command(ssl_args)
        if code != 0:
            raise RuntimeError(f"SSL certificate request failed: {stderr or stdout}")

        # Update nginx config with SSL (via host command since /etc/nginx is read-only)
        nginx_path = f"/etc/nginx/sites-available/{domain_name}.conf"

        if domain.proxy_target:
            location_block = (
                f"    location / {{\n"
                f"        proxy_pass {domain.proxy_target};\n"
                f"        proxy_http_version 1.1;\n"
                f"        proxy_set_header Upgrade $http_upgrade;\n"
                f"        proxy_set_header Connection 'upgrade';\n"
                f"        proxy_set_header Host $host;\n"
                f"        proxy_set_header X-Real-IP $remote_addr;\n"
                f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
                f"        proxy_set_header X-Forwarded-Proto $scheme;\n"
                f"        proxy_read_timeout 86400;\n"
                f"    }}\n"
            )
        else:
            location_block = (
                f"    root {web_root};\n"
                f"    index index.html index.htm;\n\n"
                f"    location / {{\n"
                f"        try_files $uri $uri/ =404;\n"
                f"    }}\n"
            )

        ssl_config = (
            f"server {{\n"
            f"    listen 80;\n"
            f"    listen [::]:80;\n"
            f"    listen 443 ssl;\n"
            f"    listen [::]:443 ssl;\n"
            f"    server_name {domain_name};\n\n"
            f"    ssl_certificate /etc/letsencrypt/live/{domain_name}/fullchain.pem;\n"
            f"    ssl_certificate_key /etc/letsencrypt/live/{domain_name}/privkey.pem;\n"
            f"    ssl_protocols TLSv1.2 TLSv1.3;\n\n"
            f"{location_block}\n"
            f"    access_log /var/log/nginx/{domain_name}.access.log;\n"
            f"    error_log /var/log/nginx/{domain_name}.error.log;\n"
            f"}}\n"
        )

        escaped_config = ssl_config.replace("'", "'\\''")
        ssl_nginx_cmd = (
            f"printf '%s' '{escaped_config}' > {nginx_path} && "
            f"nginx -t && nginx -s reload"
        )
        code, _, stderr = await self._run_command(["bash", "-c", ssl_nginx_cmd])
        if code != 0:
            logger.error("Failed to update nginx with SSL config", domain=domain_name, error=stderr)
            raise RuntimeError(f"SSL nginx config update failed: {stderr}")

        logger.info("SSL certificate provisioned", domain=domain_name)

    async def _verify_domain_direct(self, domain_name: str) -> None:
        """Verify domain DNS resolution and HTTP accessibility."""
        # Check DNS resolution (with retry for propagation)
        for attempt in range(3):
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, socket.gethostbyname, domain_name)
                break
            except socket.gaierror:
                if attempt == 2:
                    logger.warning("DNS not yet resolving (may still be propagating)", domain=domain_name)
                    return  # Non-fatal: DNS propagation can take time
                await asyncio.sleep(5)

        # Check HTTP accessibility
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"http://{domain_name}/", allow_redirects=False) as resp:
                    if resp.status in (200, 301, 302, 307, 308):
                        logger.info("Domain verified accessible", domain=domain_name, status=resp.status)
                    else:
                        logger.warning("Domain returned unexpected status", domain=domain_name, status=resp.status)
        except Exception as e:
            logger.warning("Domain HTTP check failed (may need propagation time)", domain=domain_name, error=str(e))

    def _get_cf_headers(self) -> dict[str, str]:
        """Get Cloudflare API authentication headers."""
        if CF_API_TOKEN:
            return {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}
        elif CF_API_EMAIL and CF_API_KEY:
            return {"X-Auth-Email": CF_API_EMAIL, "X-Auth-Key": CF_API_KEY, "Content-Type": "application/json"}
        return {}

    async def _run_command(self, cmd: list[str]) -> tuple[int, str, str]:
        """
        Run a command on the HOST via the supervisor agent.

        The API container cannot run nginx/certbot commands directly.
        This delegates to the supervisor agent which runs on the host with root access.
        Uses raw Redis pubsub for the response channel.
        """
        import json

        command_str = " ".join(cmd)
        command_id = str(uuid4())
        response_channel = f"host_command:{command_id}:response"

        try:
            # Use raw Redis pubsub for subscribing to the response
            ps = self.redis.client.pubsub()
            await ps.subscribe(response_channel)

            # Publish command to supervisor via raw Redis publish
            task_payload = json.dumps({
                "type": "task_request",
                "task_type": "host_command",
                "payload": {
                    "command_id": command_id,
                    "command": command_str,
                },
            })
            await self.redis.client.publish("agent:supervisor:tasks", task_payload)

            logger.info("Host command dispatched", command_id=command_id, command=command_str[:80])

            # Wait for response (max 60s)
            try:
                response = await asyncio.wait_for(
                    self._wait_for_host_response(ps, response_channel),
                    timeout=60,
                )
                return (
                    response.get("returncode", 1),
                    response.get("stdout", ""),
                    response.get("stderr", ""),
                )
            except asyncio.TimeoutError:
                logger.error("Host command timed out", command=command_str)
                return (1, "", "Host command timed out after 60s")
            finally:
                await ps.unsubscribe(response_channel)
                await ps.close()

        except Exception as e:
            logger.error("Host command failed", command=command_str, error=str(e))
            return (1, "", str(e))

    async def _wait_for_host_response(self, ps, channel: str) -> dict:
        """Wait for a response message on the raw Redis pubsub channel."""
        import json

        while True:
            message = await ps.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None:
                if message.get("type") == "message":
                    data = message.get("data", b"{}")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    return json.loads(data)
            await asyncio.sleep(0.1)

    async def _wait_for_provision_complete(
        self, task_id: str, domain_name: str, timeout: int = 600
    ) -> None:
        """
        Background task that listens for task completion via Redis pubsub.

        Includes deduplication: ignores suspiciously fast failures and waits
        a grace window for a possible "completed" after receiving a failure.

        Args:
            task_id: The task ID to listen for
            domain_name: The domain to update
            timeout: Max wait time in seconds
        """
        import json

        pubsub = None
        try:
            channel = f"task:{task_id}:response"

            pubsub = self.redis.client.pubsub()
            await pubsub.subscribe(channel)

            start = asyncio.get_event_loop().time()
            pending_failure: dict | None = None
            pending_failure_at: float = 0

            while (asyncio.get_event_loop().time() - start) < timeout:
                # If we have a pending failure and grace window expired, accept it
                if pending_failure and (asyncio.get_event_loop().time() - pending_failure_at) >= GRACE_WINDOW:
                    await self._update_domain_status(
                        domain_name, task_id, "failed",
                        error=pending_failure.get("error", "Provisioning failed"),
                    )
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=5.0
                )
                if message and message.get("type") == "message":
                    data = json.loads(message["data"])
                    status = data.get("status", "")
                    elapsed = asyncio.get_event_loop().time() - start

                    logger.info(
                        "Provision response received",
                        domain=domain_name,
                        task_id=task_id,
                        status=status,
                        elapsed=f"{elapsed:.1f}s",
                    )

                    if status == "completed":
                        # Completed is always definitive
                        await self._update_domain_status(domain_name, task_id, "completed")
                        break
                    elif status == "failed":
                        if elapsed < FAST_FAILURE_THRESHOLD:
                            # Suspiciously fast failure - likely stale process, ignore
                            logger.warning(
                                "Ignoring suspiciously fast failure",
                                domain=domain_name,
                                elapsed=f"{elapsed:.1f}s",
                            )
                            continue
                        else:
                            # Store as pending, wait grace window for possible completion
                            pending_failure = data
                            pending_failure_at = asyncio.get_event_loop().time()
                            continue

        except Exception as e:
            logger.error("Provision completion listener failed", domain=domain_name, error=str(e))
        finally:
            if pubsub:
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.close()
                except Exception:
                    pass

    async def _update_domain_status(
        self, domain_name: str, task_id: str, status: str, error: str | None = None
    ) -> None:
        """Update domain and task status in a standalone DB session."""
        from ..database import db_session_context
        from ai_db import Domain, Task

        async with db_session_context() as session:
            result = await session.execute(
                select(Domain).where(Domain.domain_name == domain_name)
            )
            domain = result.scalar_one_or_none()
            if domain:
                if status == "completed":
                    domain.status = DomainStatus.ACTIVE
                    logger.info("Domain provisioned successfully", domain=domain_name)
                else:
                    domain.status = DomainStatus.PENDING
                    domain.error_message = error or "Provisioning failed"
                    logger.error("Domain provisioning failed", domain=domain_name, error=error)

            # Update task record status
            task_result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = task_result.scalar_one_or_none()
            if task:
                task.status = TaskStatus.COMPLETED if status == "completed" else TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc)
                if error:
                    task.error_message = error

    def _get_root_domain(self, domain_name: str) -> str:
        """Extract root domain (e.g., 'example.com' from 'sub.example.com')."""
        parts = domain_name.split(".")
        if len(parts) > 2:
            return ".".join(parts[-2:])
        return domain_name

    def _get_dns_name(self, domain_name: str) -> str:
        """Get the DNS record name (e.g., '@' for root, 'sub' for subdomain)."""
        parts = domain_name.split(".")
        if len(parts) > 2:
            return ".".join(parts[:-2])
        return "@"

    async def verify_domain(self, domain_name: str) -> dict[str, Any]:
        """
        Verify domain accessibility and SSL.

        Args:
            domain_name: The domain to verify

        Returns:
            Task submission result with task_id for tracking
        """
        task_id = str(uuid4())

        await self.pubsub.publish(
            channel=f"agent:{AgentType.INFRA.value}:tasks",
            message={
                "id": task_id,
                "type": "task_request",
                "task_type": "verify",
                "target_agent": AgentType.INFRA.value,
                "payload": {
                    "content": (
                        f"Verify the domain '{domain_name}' is properly configured:\n"
                        f"Use verify_domain with domain='{domain_name}'\n"
                        f"Check DNS resolution, nginx config, HTTP/HTTPS accessibility, and SSL certificate status."
                    ),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info("Domain verification requested", domain=domain_name, task_id=task_id)

        return {
            "success": True,
            "task_id": task_id,
            "message": f"Verification started for {domain_name}",
        }

    async def renew_ssl(self, domain_name: str) -> dict[str, Any]:
        """
        Request SSL certificate renewal via Infra Agent.

        Args:
            domain_name: The domain to renew SSL for

        Returns:
            Task submission result with task_id for tracking
        """
        task_id = str(uuid4())

        await self.pubsub.publish(
            channel=f"agent:{AgentType.INFRA.value}:tasks",
            message={
                "id": task_id,
                "type": "task_request",
                "task_type": "ssl_renew",
                "target_agent": AgentType.INFRA.value,
                "payload": {
                    "content": (
                        f"Renew the SSL certificate for '{domain_name}':\n"
                        f"Run: certbot renew --cert-name {domain_name} --force-renewal\n"
                        f"Then reload nginx: nginx -s reload"
                    ),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info("SSL renewal requested", domain=domain_name, task_id=task_id)

        return {
            "success": True,
            "task_id": task_id,
            "message": f"SSL renewal started for {domain_name}",
        }

    async def sync_domain_config(self, domain_name: str) -> dict[str, Any]:
        """
        Sync domain configuration from nginx config file.

        Reads the nginx config directly and updates the domain record
        with web_root and nginx_config_path.

        Args:
            domain_name: The domain to sync

        Returns:
            Result with updated values
        """
        import os
        import re

        domain = await self.get_domain(domain_name)
        if not domain:
            raise ValueError(f"Domain {domain_name} not found")

        # Try to find and read the nginx config
        nginx_dir = "/etc/nginx/sites-available"
        possible_configs = [
            f"{nginx_dir}/{domain_name}.conf",
            f"{nginx_dir}/{domain_name}",
        ]

        config_content = None
        config_path = None

        for path in possible_configs:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        config_content = f.read()
                    config_path = path
                    break
                except Exception as e:
                    logger.warning(f"Could not read {path}: {e}")

        if not config_content:
            return {
                "success": False,
                "message": f"No nginx config found for {domain_name}",
            }

        # Extract root directive from nginx config
        root_match = re.search(r'^\s*root\s+([^;]+);', config_content, re.MULTILINE)
        web_root = root_match.group(1).strip() if root_match else None

        # Update domain record
        updates = {}
        if web_root:
            updates["web_root"] = web_root
        if config_path:
            updates["nginx_config_path"] = config_path

        if updates:
            for field, value in updates.items():
                setattr(domain, field, value)
            await self.db.flush()
            await self.db.refresh(domain)

        logger.info(
            "Domain config synced",
            domain=domain_name,
            web_root=web_root,
            nginx_config_path=config_path,
        )

        return {
            "success": True,
            "message": f"Config synced for {domain_name}",
            "web_root": web_root,
            "nginx_config_path": config_path,
        }

    def _validate_domain_name(self, domain_name: str) -> bool:
        """Validate domain name format."""
        import re

        # Basic domain validation
        pattern = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        return bool(re.match(pattern, domain_name))
