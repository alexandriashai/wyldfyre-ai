"""
Base usage client interface.

Defines the abstract base class for provider usage API clients.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class UsageRecord:
    """A single usage record from a provider."""

    provider: str
    model: str
    report_date: datetime
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: Decimal
    workspace_id: str | None = None
    raw_response: dict[str, Any] | None = None


@dataclass
class CostRecord:
    """A cost record from a provider."""

    provider: str
    model: str
    report_date: datetime
    cost_usd: Decimal
    workspace_id: str | None = None
    raw_response: dict[str, Any] | None = None


class BaseUsageClient(ABC):
    """Abstract base class for provider usage API clients."""

    @abstractmethod
    async def is_configured(self) -> bool:
        """Check if the client has valid API credentials configured."""
        ...

    @abstractmethod
    async def get_usage(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[UsageRecord]:
        """
        Fetch usage data for the given date range.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of usage records
        """
        ...

    @abstractmethod
    async def get_costs(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CostRecord]:
        """
        Fetch cost data for the given date range.

        Args:
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (inclusive)

        Returns:
            List of cost records
        """
        ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str | None]:
        """
        Test the API connection.

        Returns:
            Tuple of (success, error_message)
        """
        ...
