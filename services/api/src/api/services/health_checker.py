"""
Domain health checker service.

Periodically checks domain availability and response times.
Stores results in the Domain model and can trigger notifications.
"""

import asyncio
import ipaddress
import socket
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from database.models import Domain
from database.models.domain import DomainStatus

from ..database import db_session_context

logger = get_logger(__name__)

# Check interval: 5 minutes for active domains
CHECK_INTERVAL_SECONDS = 300
# Timeout for health check requests
REQUEST_TIMEOUT_SECONDS = 10
# Private IP ranges (for SSRF prevention)
PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in PRIVATE_NETWORKS)
    except ValueError:
        return True  # Invalid IPs treated as private (reject)


async def resolve_domain(domain_name: str) -> str | None:
    """Resolve domain to IP, returns None if private/internal."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, socket.gethostbyname, domain_name
        )
        if is_private_ip(result):
            logger.warning(
                "Domain resolves to private IP, skipping health check",
                domain=domain_name,
                ip=result,
            )
            return None
        return result
    except socket.gaierror:
        return None


async def check_domain_health(domain_name: str) -> tuple[str, int | None]:
    """
    Check health of a single domain.
    Returns (status, response_time_ms).
    Status: 'up', 'down', 'degraded'
    """
    # Resolve and check for SSRF
    ip = await resolve_domain(domain_name)
    if ip is None:
        return "down", None

    url = f"https://{domain_name}"
    start_time = time.monotonic()

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            verify=False,  # Don't fail on self-signed certs
        ) as client:
            response = await client.get(url)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if response.status_code < 400:
            if elapsed_ms > 5000:
                return "degraded", elapsed_ms
            return "up", elapsed_ms
        elif response.status_code < 500:
            return "degraded", elapsed_ms
        else:
            return "down", elapsed_ms

    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        return "down", elapsed_ms
    except Exception as e:
        logger.debug("Health check failed", domain=domain_name, error=str(e))
        return "down", None


class HealthCheckerService:
    """Background service that periodically checks domain health."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the health checker background loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Health checker service started")

    async def stop(self) -> None:
        """Stop the health checker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health checker service stopped")

    async def _run_loop(self) -> None:
        """Main check loop."""
        while self._running:
            try:
                await self._check_all_domains()
            except Exception as e:
                logger.error("Health check loop error", error=str(e))

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    async def _check_all_domains(self) -> None:
        """Check all active domains."""
        async with db_session_context() as db:
            result = await db.execute(
                select(Domain).where(
                    Domain.status == DomainStatus.ACTIVE,
                )
            )
            domains = list(result.scalars().all())

        if not domains:
            return

        logger.debug(f"Checking health of {len(domains)} domains")

        for domain in domains:
            if not self._running:
                break

            health_status, response_time = await check_domain_health(domain.domain_name)

            # Update domain health status
            async with db_session_context() as db:
                await db.execute(
                    update(Domain)
                    .where(Domain.id == domain.id)
                    .values(
                        health_status=health_status,
                        response_time_ms=response_time,
                        last_health_check_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()

            # Small delay between checks to avoid hammering
            await asyncio.sleep(1)

    async def check_single(self, domain_name: str) -> tuple[str, int | None]:
        """Check a single domain on demand."""
        return await check_domain_health(domain_name)


# Global instance
_health_checker: HealthCheckerService | None = None


def get_health_checker() -> HealthCheckerService:
    """Get or create the global health checker service."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthCheckerService()
    return _health_checker
