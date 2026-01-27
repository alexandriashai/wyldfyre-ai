"""
OpenAI Usage API client.

Fetches usage and cost data from OpenAI's Admin API.
Requires an Admin API key from organization admin settings.
"""

from datetime import datetime, timezone
from decimal import Decimal

import httpx

from ..config import get_settings
from ..logging import get_logger
from .base import BaseUsageClient, CostRecord, UsageRecord

logger = get_logger(__name__)


class OpenAIUsageClient(BaseUsageClient):
    """
    Client for OpenAI's Admin Usage API.

    Endpoints:
    - GET /v1/organization/usage/completions - Token usage (1m, 1h, 1d buckets)
    - GET /v1/organization/costs - Cost breakdown (daily buckets)
    """

    BASE_URL = "https://api.openai.com"

    def __init__(self, api_key: str | None = None):
        """
        Initialize the client.

        Args:
            api_key: OpenAI Admin API key. If not provided,
                     will use OPENAI_ADMIN_API_KEY from settings.
        """
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        """Get the API key, loading from settings if needed."""
        if self._api_key:
            return self._api_key
        settings = get_settings()
        # Try admin key first, fall back to regular key
        admin_key = settings.api.openai_admin_api_key.get_secret_value()
        if admin_key:
            return admin_key
        return settings.api.openai_api_key.get_secret_value()

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def is_configured(self) -> bool:
        """Check if the client has valid API credentials configured."""
        key = self.api_key
        # Accept any valid-looking key
        return bool(key and len(key) > 10)

    async def test_connection(self) -> tuple[bool, str | None]:
        """Test the API connection."""
        if not await self.is_configured():
            return False, "OpenAI Admin API key not configured"

        try:
            async with httpx.AsyncClient() as client:
                # Try to fetch costs endpoint to test credentials
                now = datetime.now(timezone.utc)
                start_time = int(now.timestamp()) - 86400  # 1 day ago

                response = await client.get(
                    f"{self.BASE_URL}/v1/organization/costs",
                    headers=self._get_headers(),
                    params={
                        "start_time": start_time,
                        "limit": 1,
                    },
                    timeout=30.0,
                )
                if response.status_code == 200:
                    return True, None
                elif response.status_code == 401:
                    return False, "Invalid OpenAI Admin API key"
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
        Fetch usage data from OpenAI's Usage API.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of usage records
        """
        if not await self.is_configured():
            logger.warning("OpenAI Admin API key not configured")
            return []

        records: list[UsageRecord] = []

        try:
            async with httpx.AsyncClient() as client:
                # Convert dates to Unix timestamps
                start_time = int(start_date.timestamp())
                end_time = int(end_date.timestamp())

                # Fetch all pages
                page = None
                while True:
                    params = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "bucket_width": "1d",  # Daily buckets
                        "group_by": ["model"],
                        "limit": 100,
                    }
                    if page:
                        params["page"] = page

                    response = await client.get(
                        f"{self.BASE_URL}/v1/organization/usage/completions",
                        headers=self._get_headers(),
                        params=params,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Process usage data
                    for bucket in data.get("data", []):
                        bucket_start = bucket.get("start_time", start_time)
                        report_date = datetime.fromtimestamp(
                            bucket_start, tz=timezone.utc
                        )

                        for result in bucket.get("results", []):
                            record = UsageRecord(
                                provider="openai",
                                model=result.get("model", "unknown"),
                                report_date=report_date,
                                input_tokens=result.get("input_tokens", 0),
                                output_tokens=result.get("output_tokens", 0),
                                cached_tokens=result.get("input_cached_tokens", 0),
                                cost_usd=Decimal("0"),  # Will be filled from cost API
                                workspace_id=result.get("project_id"),
                                raw_response=result,
                            )
                            records.append(record)

                    # Check for next page
                    if data.get("has_more", False):
                        page = data.get("next_page")
                    else:
                        break

        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenAI usage API error",
                status_code=e.response.status_code,
                error=str(e),
            )
        except httpx.RequestError as e:
            logger.error("OpenAI usage API connection error", error=str(e))
        except Exception as e:
            logger.error("OpenAI usage API unexpected error", error=str(e))

        return records

    async def get_costs(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CostRecord]:
        """
        Fetch cost data from OpenAI's Costs API.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of cost records
        """
        if not await self.is_configured():
            logger.warning("OpenAI Admin API key not configured")
            return []

        records: list[CostRecord] = []

        try:
            async with httpx.AsyncClient() as client:
                # Convert dates to Unix timestamps
                start_time = int(start_date.timestamp())
                end_time = int(end_date.timestamp())

                # Fetch all pages
                page = None
                while True:
                    params = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "group_by": ["line_item"],  # Group by model/feature
                        "limit": 100,
                    }
                    if page:
                        params["page"] = page

                    response = await client.get(
                        f"{self.BASE_URL}/v1/organization/costs",
                        headers=self._get_headers(),
                        params=params,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Process cost data
                    for bucket in data.get("data", []):
                        bucket_start = bucket.get("start_time", start_time)
                        report_date = datetime.fromtimestamp(
                            bucket_start, tz=timezone.utc
                        )

                        for result in bucket.get("results", []):
                            # OpenAI returns cost as a float in USD
                            amount = result.get("amount", {})
                            cost_value = amount.get("value", 0)
                            cost_usd = Decimal(str(cost_value))

                            # Extract model from line_item or object
                            model = result.get("line_item", result.get("object", "unknown"))

                            record = CostRecord(
                                provider="openai",
                                model=model,
                                report_date=report_date,
                                cost_usd=cost_usd,
                                workspace_id=result.get("project_id"),
                                raw_response=result,
                            )
                            records.append(record)

                    # Check for next page
                    if data.get("has_more", False):
                        page = data.get("next_page")
                    else:
                        break

        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenAI cost API error",
                status_code=e.response.status_code,
                error=str(e),
            )
        except httpx.RequestError as e:
            logger.error("OpenAI cost API connection error", error=str(e))
        except Exception as e:
            logger.error("OpenAI cost API unexpected error", error=str(e))

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
