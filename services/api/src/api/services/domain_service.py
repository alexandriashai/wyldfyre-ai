"""
Domain management service.

Coordinates between API and Infra Agent for domain operations.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import DomainStatus, get_logger
from ai_messaging import PubSubManager, RedisClient

logger = get_logger(__name__)


class DomainService:
    """Service for domain management operations."""

    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
        self.pubsub = PubSubManager(redis)

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
        from ai_db import Domain

        query = select(Domain).order_by(Domain.domain_name)

        if status:
            query = query.where(Domain.status == status)

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
        from ai_db import Domain

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
            Task submission result with task_id for tracking
        """
        from uuid import uuid4

        domain = await self.get_domain(domain_name)
        if not domain:
            raise ValueError(f"Domain {domain_name} not found")

        # Update status to provisioning
        domain.status = DomainStatus.PROVISIONING
        await self.db.flush()

        # Generate task ID for tracking
        task_id = str(uuid4())

        # Publish task to infra agent channel
        await self.pubsub.publish(
            channel="infra-agent:tasks",
            message={
                "task_id": task_id,
                "action": "provision_domain",
                "payload": {
                    "domain": domain_name,
                    "proxy_target": domain.proxy_target,
                    "ssl_enabled": domain.ssl_enabled,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            "Domain provisioning requested",
            domain=domain_name,
            task_id=task_id,
        )

        return {
            "success": True,
            "task_id": task_id,
            "message": f"Provisioning started for {domain_name}",
        }

    async def verify_domain(self, domain_name: str) -> dict[str, Any]:
        """
        Verify domain accessibility and SSL.

        Args:
            domain_name: The domain to verify

        Returns:
            Task submission result with task_id for tracking
        """
        from uuid import uuid4

        task_id = str(uuid4())

        # Publish verification task
        await self.pubsub.publish(
            channel="infra-agent:tasks",
            message={
                "task_id": task_id,
                "action": "verify_domain",
                "payload": {"domain": domain_name},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            "Domain verification requested",
            domain=domain_name,
            task_id=task_id,
        )

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
        from uuid import uuid4

        task_id = str(uuid4())

        # Publish renewal task
        await self.pubsub.publish(
            channel="infra-agent:tasks",
            message={
                "task_id": task_id,
                "action": "renew_certificate",
                "payload": {"domain": domain_name},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            "SSL renewal requested",
            domain=domain_name,
            task_id=task_id,
        )

        return {
            "success": True,
            "task_id": task_id,
            "message": f"SSL renewal started for {domain_name}",
        }

    def _validate_domain_name(self, domain_name: str) -> bool:
        """Validate domain name format."""
        import re

        # Basic domain validation
        pattern = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        return bool(re.match(pattern, domain_name))
