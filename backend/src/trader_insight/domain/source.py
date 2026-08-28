"""Vendor-neutral source interface for normalized market data."""

from __future__ import annotations

from typing import Protocol

from trader_insight.domain.models import OptionChainRecord, UnderlyingMarketSnapshot


class MarketDataSource(Protocol):
    """Obtains normalized market data without exposing provider-specific payloads."""

    def get_underlying_snapshot(self, ticker: str) -> UnderlyingMarketSnapshot:
        """Return the latest normalized snapshot for a ticker."""
        ...

    def get_option_chain_records(self, ticker: str) -> list[OptionChainRecord]:
        """Return normalized option-chain records for a ticker."""
        ...
