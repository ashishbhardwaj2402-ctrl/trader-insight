"""Checked-in fixture implementation of the normalized market-data source."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trader_insight.domain.errors import SourceDataError
from trader_insight.domain.fixtures import load_fixture
from trader_insight.domain.models import (
    MarketDataFixture,
    OptionChainRecord,
    UnderlyingMarketSnapshot,
)

_FIXTURE_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "contracts" / "market-data" / "v1" / "fixtures"
)


class MockMarketDataAdapter:
    """Serve validated, deterministic v1 fixture data through the source boundary."""

    def __init__(self, fixture_directory: Path = _FIXTURE_DIRECTORY) -> None:
        self._fixture_directory = fixture_directory

    def get_underlying_snapshot(self, ticker: str) -> UnderlyingMarketSnapshot:
        """Return the normalized underlying snapshot for a supported ticker."""
        fixture = self._load_ticker_fixture(ticker)
        normalized_ticker = ticker.upper()
        return next(
            snapshot
            for snapshot in fixture.underlying_snapshots
            if snapshot.ticker == normalized_ticker
        )

    def get_option_chain_records(self, ticker: str) -> list[OptionChainRecord]:
        """Return normalized option-chain records for a supported ticker."""
        fixture = self._load_ticker_fixture(ticker)
        normalized_ticker = ticker.upper()
        return [
            record for record in fixture.option_chain_records if record.ticker == normalized_ticker
        ]

    def _load_ticker_fixture(self, ticker: str) -> MarketDataFixture:
        normalized_ticker = ticker.upper()
        fixture_path = self._fixture_directory / f"{normalized_ticker.lower()}.json"
        if not fixture_path.is_file():
            raise SourceDataError(normalized_ticker)

        raw_fixture = _read_fixture(fixture_path)
        fixture = load_fixture(raw_fixture)
        if not any(
            snapshot.ticker == normalized_ticker for snapshot in fixture.underlying_snapshots
        ):
            raise SourceDataError(normalized_ticker)
        return fixture


def _read_fixture(fixture_path: Path) -> Mapping[str, object]:
    """Read one checked-in fixture while keeping file access adapter-private."""
    raw_fixture: Any = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(raw_fixture, Mapping):
        raise ValueError(f"Fixture must be a JSON object: {fixture_path}")
    return raw_fixture
