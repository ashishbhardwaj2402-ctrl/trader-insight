"""Repository boundary for atomic normalized market-data cache writes."""

from __future__ import annotations

from typing import Protocol

from trader_insight.domain.cache import CacheRecord
from trader_insight.domain.errors import DomainValidationError

_MAX_TRANSACTION_RECORDS = 25


class MarketDataRepository(Protocol):
    """Replaces a ticker's complete normalized cache record set atomically."""

    def replace_ticker_records_atomically(self, records: list[CacheRecord]) -> None:
        """Replace the supplied cache keys as one atomic write."""
        ...


def validate_transaction_records(records: list[CacheRecord]) -> None:
    """Validate DynamoDB transaction bounds and TTLs before persistence."""
    if len(records) > _MAX_TRANSACTION_RECORDS:
        raise DomainValidationError(
            f"a transaction may contain at most {_MAX_TRANSACTION_RECORDS} cache records",
            "records",
        )

    for index, record in enumerate(records):
        ttl = record.ttl
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
            raise DomainValidationError(
                "ttl must be a positive integer epoch-second value",
                f"records[{index}].ttl",
            )
