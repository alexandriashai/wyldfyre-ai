"""
Usage Sync Service.

Background service that periodically syncs usage data from provider APIs
(Anthropic, OpenAI) and stores it in the provider_usage table.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ai_core import (
    AnthropicUsageClient,
    OpenAIUsageClient,
    UsageRecord,
    get_logger,
)
from database.models import APIProvider, ProviderUsage, SyncType, UsageSyncLog
from database.models.base import generate_uuid

from ..database import db_session_context

logger = get_logger(__name__)

# Sync interval: 1 hour
SYNC_INTERVAL_SECONDS = 3600
# Default lookback period: 7 days
DEFAULT_LOOKBACK_DAYS = 7


class UsageSyncService:
    """
    Background service that syncs usage data from provider APIs.

    Runs hourly, fetching the last 7 days of data and upserting
    to the provider_usage table.
    """

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._anthropic_client = AnthropicUsageClient()
        self._openai_client = OpenAIUsageClient()

    async def start(self) -> None:
        """Start the usage sync background loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Usage sync service started")

    async def stop(self) -> None:
        """Stop the usage sync service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Usage sync service stopped")

    async def _run_loop(self) -> None:
        """Main sync loop."""
        # Initial delay to let the app start up
        await asyncio.sleep(30)

        while self._running:
            try:
                await self.sync_all_providers()
            except Exception as e:
                logger.error("Usage sync loop error", error=str(e))

            await asyncio.sleep(SYNC_INTERVAL_SECONDS)

    async def sync_all_providers(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        sync_type: SyncType = SyncType.INCREMENTAL,
    ) -> dict[str, dict]:
        """
        Sync usage data from all configured providers.

        Args:
            lookback_days: Number of days to look back
            sync_type: Type of sync operation

        Returns:
            Dict with sync results for each provider
        """
        results = {}

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=lookback_days)

        # Sync Anthropic
        if await self._anthropic_client.is_configured():
            results["anthropic"] = await self._sync_provider(
                provider=APIProvider.ANTHROPIC,
                client=self._anthropic_client,
                start_date=start_date,
                end_date=end_date,
                sync_type=sync_type,
            )
        else:
            results["anthropic"] = {"configured": False}

        # Sync OpenAI
        if await self._openai_client.is_configured():
            results["openai"] = await self._sync_provider(
                provider=APIProvider.OPENAI,
                client=self._openai_client,
                start_date=start_date,
                end_date=end_date,
                sync_type=sync_type,
            )
        else:
            results["openai"] = {"configured": False}

        return results

    async def _sync_provider(
        self,
        provider: APIProvider,
        client: AnthropicUsageClient | OpenAIUsageClient,
        start_date: datetime,
        end_date: datetime,
        sync_type: SyncType,
    ) -> dict:
        """
        Sync usage data from a single provider.

        Args:
            provider: The provider enum
            client: The usage client instance
            start_date: Start of date range
            end_date: End of date range
            sync_type: Type of sync operation

        Returns:
            Dict with sync results
        """
        started_at = datetime.now(timezone.utc)
        sync_log_id = generate_uuid()

        try:
            # Create sync log entry
            async with db_session_context() as db:
                sync_log = UsageSyncLog(
                    id=sync_log_id,
                    provider=provider,
                    sync_type=sync_type,
                    started_at=started_at,
                    sync_start_date=start_date,
                    sync_end_date=end_date,
                    success=False,
                    records_synced=0,
                )
                db.add(sync_log)
                await db.commit()

            # Fetch usage data with costs
            logger.info(
                f"Fetching {provider.value} usage data",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )

            records = await client.get_usage_with_costs(start_date, end_date)
            logger.info(f"Fetched {len(records)} usage records from {provider.value}")

            # Upsert records
            synced_count = 0
            for record in records:
                await self._upsert_usage_record(provider, record)
                synced_count += 1

            # Update sync log with success
            completed_at = datetime.now(timezone.utc)
            async with db_session_context() as db:
                sync_log = await db.get(UsageSyncLog, sync_log_id)
                if sync_log:
                    sync_log.completed_at = completed_at
                    sync_log.success = True
                    sync_log.records_synced = synced_count
                    await db.commit()

            return {
                "configured": True,
                "success": True,
                "records_synced": synced_count,
                "duration_seconds": (completed_at - started_at).total_seconds(),
            }

        except Exception as e:
            logger.error(
                f"Failed to sync {provider.value} usage",
                error=str(e),
            )

            # Update sync log with failure
            async with db_session_context() as db:
                sync_log = await db.get(UsageSyncLog, sync_log_id)
                if sync_log:
                    sync_log.completed_at = datetime.now(timezone.utc)
                    sync_log.success = False
                    sync_log.error_message = str(e)
                    await db.commit()

            return {
                "configured": True,
                "success": False,
                "error": str(e),
            }

    async def _upsert_usage_record(
        self,
        provider: APIProvider,
        record: UsageRecord,
    ) -> None:
        """
        Upsert a single usage record.

        Uses a manual check-then-insert/update approach to handle NULL workspace_id
        properly (PostgreSQL unique indexes treat NULLs as distinct).
        """
        async with db_session_context() as db:
            # Prepare raw response as JSON string
            raw_response_str = None
            if record.raw_response:
                raw_response_str = json.dumps(record.raw_response)

            # Check if record exists (handling NULL workspace_id)
            if record.workspace_id:
                existing_stmt = select(ProviderUsage).where(
                    ProviderUsage.provider == provider,
                    ProviderUsage.report_date == record.report_date,
                    ProviderUsage.model == record.model,
                    ProviderUsage.workspace_id == record.workspace_id,
                )
            else:
                existing_stmt = select(ProviderUsage).where(
                    ProviderUsage.provider == provider,
                    ProviderUsage.report_date == record.report_date,
                    ProviderUsage.model == record.model,
                    ProviderUsage.workspace_id.is_(None),
                )

            result = await db.execute(existing_stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing record
                existing.input_tokens = record.input_tokens
                existing.output_tokens = record.output_tokens
                existing.cached_tokens = record.cached_tokens
                existing.cost_usd = record.cost_usd
                existing.raw_response = raw_response_str
            else:
                # Insert new record
                new_record = ProviderUsage(
                    id=generate_uuid(),
                    provider=provider,
                    report_date=record.report_date,
                    model=record.model,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    cached_tokens=record.cached_tokens,
                    cost_usd=record.cost_usd,
                    workspace_id=record.workspace_id,
                    raw_response=raw_response_str,
                )
                db.add(new_record)

            await db.commit()

    async def get_sync_status(self) -> dict:
        """
        Get the current sync status for all providers.

        Returns:
            Dict with configuration and last sync info for each provider
        """
        status = {}

        # Check Anthropic configuration
        anthropic_configured = await self._anthropic_client.is_configured()
        status["anthropic"] = {
            "configured": anthropic_configured,
            "last_sync": None,
        }

        # Check OpenAI configuration
        openai_configured = await self._openai_client.is_configured()
        status["openai"] = {
            "configured": openai_configured,
            "last_sync": None,
        }

        # Get last successful sync for each provider
        async with db_session_context() as db:
            for provider_name, provider_enum in [
                ("anthropic", APIProvider.ANTHROPIC),
                ("openai", APIProvider.OPENAI),
            ]:
                result = await db.execute(
                    select(UsageSyncLog)
                    .where(
                        UsageSyncLog.provider == provider_enum,
                        UsageSyncLog.success == True,
                    )
                    .order_by(UsageSyncLog.completed_at.desc())
                    .limit(1)
                )
                last_sync = result.scalar_one_or_none()

                if last_sync:
                    status[provider_name]["last_sync"] = {
                        "completed_at": last_sync.completed_at.isoformat()
                        if last_sync.completed_at
                        else None,
                        "records_synced": last_sync.records_synced,
                        "sync_type": last_sync.sync_type.value,
                    }

        return status

    async def test_providers(self) -> dict[str, dict]:
        """
        Test connection to all configured providers.

        Returns:
            Dict with test results for each provider
        """
        results = {}

        # Test Anthropic
        if await self._anthropic_client.is_configured():
            success, error = await self._anthropic_client.test_connection()
            results["anthropic"] = {
                "configured": True,
                "connected": success,
                "error": error,
            }
        else:
            results["anthropic"] = {
                "configured": False,
                "connected": False,
                "error": "Admin API key not configured",
            }

        # Test OpenAI
        if await self._openai_client.is_configured():
            success, error = await self._openai_client.test_connection()
            results["openai"] = {
                "configured": True,
                "connected": success,
                "error": error,
            }
        else:
            results["openai"] = {
                "configured": False,
                "connected": False,
                "error": "Admin API key not configured",
            }

        return results


# Global instance
_usage_sync_service: UsageSyncService | None = None


def get_usage_sync_service() -> UsageSyncService:
    """Get or create the global usage sync service."""
    global _usage_sync_service
    if _usage_sync_service is None:
        _usage_sync_service = UsageSyncService()
    return _usage_sync_service
