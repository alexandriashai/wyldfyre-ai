"""
Domain management service.

Coordinates between API and Infra Agent for domain operations.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import DomainStatus, get_logger
from ai_messaging import MessageBus, RedisClient

logger = get_logger(__name__)


class DomainService:
    """Service for domain management operations."""

    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
        self.message_bus = MessageBus(redis)

    async def list_domains(
        self,
        status: DomainStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any]:
        """
        List all managed domains.

        Args:
            status: Optional status filter
            limit: Max results to return
            offset: Pagination offset

        Returns:
            List of Domain objects
        """
        from database.models import Domain

        query = select(Domain).order_by(Domain.domain_name)

        if status:
            query = query.where(Domain.status == status)

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_domain(self, domain_name: str) -> Any | None:
        """Get a domain by name."""
        from database.models import Domain

        result = await self.db.execute(
            select(Domain).where(Domain.domain_name == domain_name)
        )
        return result.scalar_one_or_none()

    async def get_domain_by_id(self, domain_id: str) -> Any | None:
        """Get a domain by ID."""
        from database.models import Domain

        result = await self.db.execute(
            select(Domain).where(Domain.id == domain_id)
        )
        return result.scalar_one_or_none()

    async def create_domain(
        self,
        domain_name: str,
        proxy_target: str | None = None,
        ssl_enabled: bool = True,
        dns_provider: str = "cloudflare",
    ) -> Any:
        """
        Create a new domain record.

        Args:
            domain_name: The domain name
            proxy_target: Optional proxy target (e.g., localhost:3000)
            ssl_enabled: Whether to enable SSL
            dns_provider: DNS provider name

        Returns:
            Created Domain object

        Raises:
            ValueError: If domain already exists
        """
        from database.models import Domain

        # Check for existing domain
        existing = await self.get_domain(domain_name)
        if existing:
            raise ValueError(f"Domain {domain_name} already exists")

        # Validate domain name
        if not self._validate_domain_name(domain_name):
            raise ValueError(f"Invalid domain name: {domain_name}")

        # Create domain record
        domain = Domain(
            domain_name=domain_name,
            proxy_target=proxy_target,
            ssl_enabled=ssl_enabled,
            dns_provider=dns_provider,
            status=DomainStatus.PENDING,
        )

        self.db.add(domain)
        await self.db.flush()
        await self.db.refresh(domain)

        logger.info("Domain created", domain=domain_name, id=domain.id)
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
            "ssl_enabled",
            "ssl_auto_renew",
            "notes",
            "status",
            "error_message",
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
        Request domain provisioning via Infra Agent.

        This sends a task to the Infra Agent to:
        1. Create web root directory
        2. Set up Nginx configuration
        3. Request SSL certificate
        4. Configure DNS (if applicable)

        Args:
            domain_name: The domain to provision

        Returns:
            Task submission result
        """
        domain = await self.get_domain(domain_name)
        if not domain:
            raise ValueError(f"Domain {domain_name} not found")

        # Update status to provisioning
        domain.status = DomainStatus.PROVISIONING
        await self.db.flush()

        # Send task to infra agent via message bus
        task_result = await self.message_bus.request(
            target="infra-agent",
            action="provision_domain",
            payload={
                "domain": domain_name,
                "proxy_target": domain.proxy_target,
                "ssl_enabled": domain.ssl_enabled,
            },
            timeout=120.0,  # Domain provisioning can take time
        )

        logger.info(
            "Domain provisioning requested",
            domain=domain_name,
            task_id=task_result.get("task_id"),
        )
        return task_result

    async def verify_domain(self, domain_name: str) -> dict[str, Any]:
        """
        Verify domain accessibility and SSL.

        Args:
            domain_name: The domain to verify

        Returns:
            Verification results
        """
        task_result = await self.message_bus.request(
            target="infra-agent",
            action="verify_domain",
            payload={"domain": domain_name},
            timeout=30.0,
        )

        # Update domain status based on verification
        domain = await self.get_domain(domain_name)
        if domain and task_result.get("success"):
            domain.status = DomainStatus.ACTIVE
            await self.db.flush()

        return task_result

    async def renew_ssl(self, domain_name: str) -> dict[str, Any]:
        """
        Request SSL certificate renewal via Infra Agent.

        Args:
            domain_name: The domain to renew SSL for

        Returns:
            Task submission result
        """
        task_result = await self.message_bus.request(
            target="infra-agent",
            action="renew_certificate",
            payload={"domain": domain_name},
            timeout=60.0,
        )

        # Update SSL expiry if successful
        if task_result.get("success") and task_result.get("expires_at"):
            domain = await self.get_domain(domain_name)
            if domain:
                domain.ssl_expires_at = datetime.fromisoformat(
                    task_result["expires_at"]
                )
                await self.db.flush()

        return task_result

    def _validate_domain_name(self, domain_name: str) -> bool:
        """Validate domain name format."""
        import re

        # Basic domain validation
        pattern = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        return bool(re.match(pattern, domain_name))
