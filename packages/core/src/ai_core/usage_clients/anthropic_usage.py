"""
Anthropic Usage API client.

Fetches usage and cost data from Anthropic's Admin API.
Requires an Admin API key (sk-ant-admin-...).
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from ..config import get_settings
from ..logging import get_logger
from .base import BaseUsageClient, CostRecord, UsageRecord

logger = get_logger(__name__)


class AnthropicUsageClient(BaseUsageClient):
    """
    Client for Anthropic's Admin Usage API.

    Endpoints:
    - GET /v1/organizations/usage_report/messages - Token usage
    - GET /v1/organizations/cost_report - Cost breakdown
    """

    BASE_URL = "https://api.anthropic.com"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str | None = None):
        """
        Initialize the client.

        Args:
            api_key: Anthropic Admin API key. If not provided,
                     will use ANTHROPIC_ADMIN_API_KEY from settings.
        """
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        """Get the API key, loading from settings if needed."""
        if self._api_key:
            return self._api_key
        settings = get_settings()
        # Try admin key first, fall back to regular key
        admin_key = settings.api.anthropic_admin_api_key.get_secret_value()
        if admin_key:
            return admin_key
        return settings.api.anthropic_api_key.get_secret_value()

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

    async def is_configured(self) -> bool:
        """Check if the client has valid API credentials configured."""
        key = self.api_key
        # Accept both admin keys (sk-ant-admin-) and regular keys (sk-ant-api)
        return bool(key and (key.startswith("sk-ant-admin-") or key.startswith("sk-ant-api")))

    async def test_connection(self) -> tuple[bool, str | None]:
        """Test the API connection."""
        if not await self.is_configured():
            return False, "Anthropic Admin API key not configured"

        try:
            async with httpx.AsyncClient() as client:
                # Try to fetch a minimal usage report to test credentials
                response = await client.get(
                    f"{self.BASE_URL}/v1/organizations/usage_report/messages",
                    headers=self._get_headers(),
                    params={
                        "start_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "end_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "group_by": "model",
                    },
                    timeout=30.0,
                )
                if response.status_code == 200:
                    return True, None
                elif response.status_code == 401:
                    return False, "Invalid Anthropic Admin API key"
                elif response.status_code == 403:
                    return False, "API key does not have admin permissions"
                else:
                    return False, f"API error: {response.status_code} - {response.text}"
        except httpx.RequestError as e:
            return False, f"Connection error: {str(e)}"

    async def get_usage(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[UsageRecord]:
        """
        Fetch usage data from Anthropic's Usage API.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of usage records
        """
        if not await self.is_configured():
            logger.warning("Anthropic Admin API key not configured")
            return []

        records: list[UsageRecord] = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/v1/organizations/usage_report/messages",
                    headers=self._get_headers(),
                    params={
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "group_by": "model",
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

                # Process usage data
                for item in data.get("data", []):
                    # Parse date from the response
                    report_date = datetime.fromisoformat(
                        item.get("date", start_date.isoformat())
                    )

                    record = UsageRecord(
                        provider="anthropic",
                        model=item.get("model", "unknown"),
                        report_date=report_date,
                        input_tokens=item.get("input_tokens", 0),
                        output_tokens=item.get("output_tokens", 0),
                        cached_tokens=item.get("cache_read_input_tokens", 0),
                        cost_usd=Decimal("0"),  # Will be filled from cost API
                        workspace_id=item.get("workspace_id"),
                        raw_response=item,
                    )
                    records.append(record)

        except httpx.HTTPStatusError as e:
            logger.error(
                "Anthropic usage API error",
                status_code=e.response.status_code,
                error=str(e),
            )
        except httpx.RequestError as e:
            logger.error("Anthropic usage API connection error", error=str(e))
        except Exception as e:
            logger.error("Anthropic usage API unexpected error", error=str(e))

        return records

    async def get_costs(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CostRecord]:
        """
        Fetch cost data from Anthropic's Cost API.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of cost records
        """
        if not await self.is_configured():
            logger.warning("Anthropic Admin API key not configured")
            return []

        records: list[CostRecord] = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/v1/organizations/cost_report",
                    headers=self._get_headers(),
                    params={
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "group_by": "model",
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

                # Process cost data
                for item in data.get("data", []):
                    report_date = datetime.fromisoformat(
                        item.get("date", start_date.isoformat())
                    )

                    # Cost is typically in USD cents, convert to dollars
                    cost_cents = item.get("cost_usd_cents", 0)
                    cost_usd = Decimal(str(cost_cents)) / Decimal("100")

                    record = CostRecord(
                        provider="anthropic",
                        model=item.get("model", "unknown"),
                        report_date=report_date,
                        cost_usd=cost_usd,
                        workspace_id=item.get("workspace_id"),
                        raw_response=item,
                    )
                    records.append(record)

        except httpx.HTTPStatusError as e:
            logger.error(
                "Anthropic cost API error",
                status_code=e.response.status_code,
                error=str(e),
            )
        except httpx.RequestError as e:
            logger.error("Anthropic cost API connection error", error=str(e))
        except Exception as e:
            logger.error("Anthropic cost API unexpected error", error=str(e))

        return records

    async def get_usage_with_costs(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[UsageRecord]:
        """
        Fetch both usage and cost data, merging them into UsageRecords.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of usage records with costs populated
        """
        # Fetch both in parallel
        usage_records = await self.get_usage(start_date, end_date)
        cost_records = await self.get_costs(start_date, end_date)

        # Build a lookup for costs by (date, model)
        cost_lookup: dict[tuple[str, str], Decimal] = {}
        for cost in cost_records:
            key = (cost.report_date.strftime("%Y-%m-%d"), cost.model)
            cost_lookup[key] = cost_lookup.get(key, Decimal("0")) + cost.cost_usd

        # Merge costs into usage records
        for record in usage_records:
            key = (record.report_date.strftime("%Y-%m-%d"), record.model)
            record.cost_usd = cost_lookup.get(key, Decimal("0"))

        return usage_records
