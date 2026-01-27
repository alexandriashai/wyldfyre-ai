"""
Anthropic Usage API client.

Fetches usage and cost data from Anthropic's Admin API.
Requires an Admin API key (sk-ant-admin-...).
"""

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
        # Accept admin keys (sk-ant-admin- or sk-ant-admin01-) and regular keys (sk-ant-api)
        return bool(key and (key.startswith("sk-ant-admin") or key.startswith("sk-ant-api")))

    async def test_connection(self) -> tuple[bool, str | None]:
        """Test the API connection."""
        if not await self.is_configured():
            return False, "Anthropic Admin API key not configured"

        try:
            async with httpx.AsyncClient() as client:
                # Try to fetch a minimal usage report to test credentials
                # Anthropic uses RFC 3339 timestamps and array parameters
                now = datetime.now(timezone.utc)
                response = await client.get(
                    f"{self.BASE_URL}/v1/organizations/usage_report/messages",
                    headers=self._get_headers(),
                    params=[
                        ("starting_at", now.strftime("%Y-%m-%dT00:00:00Z")),
                        ("group_by[]", "model"),
                    ],
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
                # Anthropic uses RFC 3339 timestamps and requires array params
                # Use 1d bucket width for daily aggregation
                page = None
                while True:
                    params = [
                        ("starting_at", start_date.strftime("%Y-%m-%dT00:00:00Z")),
                        ("ending_at", end_date.strftime("%Y-%m-%dT23:59:59Z")),
                        ("bucket_width", "1d"),
                        ("group_by[]", "model"),
                    ]
                    if page:
                        params.append(("page", page))

                    response = await client.get(
                        f"{self.BASE_URL}/v1/organizations/usage_report/messages",
                        headers=self._get_headers(),
                        params=params,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Process usage data - data is array of time buckets
                    for bucket in data.get("data", []):
                        # Parse date from the bucket's starting_at
                        bucket_start = bucket.get("starting_at", start_date.isoformat())
                        report_date = datetime.fromisoformat(
                            bucket_start.replace("Z", "+00:00")
                        )

                        # Each bucket has results array
                        for item in bucket.get("results", []):
                            record = UsageRecord(
                                provider="anthropic",
                                model=item.get("model", "unknown"),
                                report_date=report_date,
                                input_tokens=item.get("uncached_input_tokens", 0),
                                output_tokens=item.get("output_tokens", 0),
                                cached_tokens=item.get("cache_read_input_tokens", 0),
                                cost_usd=Decimal("0"),  # Will be filled from cost API
                                workspace_id=item.get("workspace_id"),
                                raw_response=item,
                            )
                            records.append(record)

                    # Check for next page
                    if data.get("has_more", False):
                        page = data.get("next_page")
                    else:
                        break

        except httpx.HTTPStatusError as e:
            logger.error(
                "Anthropic usage API error",
                status_code=e.response.status_code,
                error=str(e),
                response_text=e.response.text,
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
                # Anthropic uses RFC 3339 timestamps and requires array params
                # group_by description gives us model breakdown
                page = None
                while True:
                    params = [
                        ("starting_at", start_date.strftime("%Y-%m-%dT00:00:00Z")),
                        ("ending_at", end_date.strftime("%Y-%m-%dT23:59:59Z")),
                        ("bucket_width", "1d"),
                        ("group_by[]", "description"),
                    ]
                    if page:
                        params.append(("page", page))

                    response = await client.get(
                        f"{self.BASE_URL}/v1/organizations/cost_report",
                        headers=self._get_headers(),
                        params=params,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Process cost data - data is array of time buckets
                    for bucket in data.get("data", []):
                        bucket_start = bucket.get("starting_at", start_date.isoformat())
                        report_date = datetime.fromisoformat(
                            bucket_start.replace("Z", "+00:00")
                        )

                        # Each bucket has results array
                        for item in bucket.get("results", []):
                            # Cost amount is in lowest currency units (cents) as string
                            # e.g., "123.45" in USD represents $1.2345
                            amount_str = item.get("amount", "0")
                            cost_cents = Decimal(amount_str)
                            cost_usd = cost_cents / Decimal("100")

                            # Model comes from description grouping
                            model = item.get("model", "unknown") or "unknown"

                            record = CostRecord(
                                provider="anthropic",
                                model=model,
                                report_date=report_date,
                                cost_usd=cost_usd,
                                workspace_id=item.get("workspace_id"),
                                raw_response=item,
                            )
                            records.append(record)

                    # Check for next page
                    if data.get("has_more", False):
                        page = data.get("next_page")
                    else:
                        break

        except httpx.HTTPStatusError as e:
            logger.error(
                "Anthropic cost API error",
                status_code=e.response.status_code,
                error=str(e),
                response_text=e.response.text,
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
