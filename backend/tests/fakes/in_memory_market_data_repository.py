"""Deterministic in-memory implementation of the market-data repository."""

from __future__ import annotations

from trader_insight.domain.cache import CacheRecord
from trader_insight.domain.repository import validate_transaction_records


class InMemoryMarketDataRepository:
    """Store normalized records with the same key replacement semantics as DynamoDB Put."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], CacheRecord] = {}

    def replace_ticker_records_atomically(self, records: list[CacheRecord]) -> None:
        """Replace supplied records by their partition and sort key."""
        validate_transaction_records(records)
        replacement_state = self._records.copy()
        for record in records:
            replacement_state[(record.pk, record.sk)] = record
        self._records = replacement_state

    @property
    def records(self) -> list[CacheRecord]:
        """Return the current records in deterministic key order for test assertions."""
        return [self._records[key] for key in sorted(self._records)]
