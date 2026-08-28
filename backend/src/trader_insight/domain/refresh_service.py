"""Vendor-neutral orchestration for atomic per-ticker market-data refreshes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from trader_insight.domain.cache import (
    CacheRecord,
    build_option_cache_record,
    build_snapshot_cache_record,
)
from trader_insight.domain.errors import DomainValidationError, SourceDataError
from trader_insight.domain.fixtures import validate_fixture
from trader_insight.domain.repository import MarketDataRepository
from trader_insight.domain.source import MarketDataSource


@dataclass(frozen=True, slots=True)
class RefreshFailure:
    """Safe operational details for one ticker that could not be refreshed."""

    ticker: str
    error_class: str


@dataclass(frozen=True, slots=True)
class RefreshSummary:
    """Structured diagnostic result from one scheduled refresh invocation."""

    refreshed_tickers: tuple[str, ...]
    records_written: int
    failures: tuple[RefreshFailure, ...]

    def to_log_fields(self) -> dict[str, object]:
        """Return safe, payload-free diagnostic fields for structured logging."""
        return {
            "refreshed_tickers": list(self.refreshed_tickers),
            "records_written": self.records_written,
            "failures": [
                {"ticker": failure.ticker, "error_class": failure.error_class}
                for failure in self.failures
            ],
        }


class RefreshFailedError(RuntimeError):
    """Signals a failed scheduled invocation while retaining safe diagnostics."""

    def __init__(self, summary: RefreshSummary) -> None:
        self.summary = summary
        super().__init__("One or more market-data tickers failed to refresh")


class RefreshService:
    """Load only injected source data and atomically replace each valid ticker cache set."""

    def __init__(
        self,
        adapter: MarketDataSource,
        repository: MarketDataRepository,
        clock: Callable[[], datetime],
        *,
        fixture_tickers: Sequence[str],
        cache_ttl_seconds: int,
    ) -> None:
        self._adapter = adapter
        self._repository = repository
        self._clock = clock
        self._fixture_tickers = _normalize_allow_list(fixture_tickers)
        if cache_ttl_seconds <= 0:
            raise DomainValidationError("cache_ttl_seconds must be positive", "cache_ttl_seconds")
        self._cache_ttl_seconds = cache_ttl_seconds

    def refresh(self) -> RefreshSummary:
        """Refresh allow-listed tickers, committing each complete ticker set once."""
        refreshed_tickers: list[str] = []
        failures: list[RefreshFailure] = []
        records_written = 0

        for ticker in self._fixture_tickers:
            try:
                records = self._load_and_build_records(ticker)
            except (SourceDataError, DomainValidationError) as error:
                failures.append(RefreshFailure(ticker=ticker, error_class=type(error).__name__))
                continue

            self._repository.replace_ticker_records_atomically(records)
            refreshed_tickers.append(ticker)
            records_written += len(records)

        summary = RefreshSummary(
            refreshed_tickers=tuple(refreshed_tickers),
            records_written=records_written,
            failures=tuple(failures),
        )
        if failures:
            raise RefreshFailedError(summary)
        return summary

    def _load_and_build_records(self, ticker: str) -> list[CacheRecord]:
        snapshot = self._adapter.get_underlying_snapshot(ticker)
        option_records = self._adapter.get_option_chain_records(ticker)
        fixture = validate_fixture(
            {
                "schema_version": snapshot.schema_version,
                "underlying_snapshots": [snapshot.model_dump(mode="json")],
                "option_chain_records": [
                    record.model_dump(mode="json") for record in option_records
                ],
            }
        )
        if snapshot.ticker != ticker or any(record.ticker != ticker for record in option_records):
            raise DomainValidationError("source data must match the requested ticker", "ticker")

        refreshed_at = self._clock()
        if refreshed_at.tzinfo is None or refreshed_at.utcoffset() != UTC.utcoffset(refreshed_at):
            raise DomainValidationError("clock must return a UTC-aware datetime", "clock")
        ttl = int(refreshed_at.timestamp()) + self._cache_ttl_seconds
        return [
            build_snapshot_cache_record(fixture.underlying_snapshots[0], refreshed_at, ttl),
            *[
                build_option_cache_record(record, refreshed_at, ttl)
                for record in fixture.option_chain_records
            ],
        ]


def _normalize_allow_list(tickers: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(ticker.upper() for ticker in tickers)
    if not normalized or any(not ticker for ticker in normalized):
        raise DomainValidationError(
            "fixture_tickers must include at least one ticker", "fixture_tickers"
        )
    if len(set(normalized)) != len(normalized):
        raise DomainValidationError(
            "fixture_tickers must not contain duplicates", "fixture_tickers"
        )
    return normalized
