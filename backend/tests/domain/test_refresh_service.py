from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fakes.in_memory_market_data_repository import InMemoryMarketDataRepository
from trader_insight.adapters.mock_market_data_adapter import MockMarketDataAdapter
from trader_insight.domain import CacheRecord, SourceDataError
from trader_insight.domain.refresh_service import RefreshFailedError, RefreshService

_REFRESH_TIME = datetime(2025, 5, 22, 14, 31, tzinfo=UTC)


class UnsupportedTickerSource:
    def get_underlying_snapshot(self, ticker: str):
        raise SourceDataError(ticker)

    def get_option_chain_records(self, ticker: str):
        raise AssertionError("option records must not be requested after source failure")


class RecordingRepository(InMemoryMarketDataRepository):
    def __init__(self) -> None:
        super().__init__()
        self.transactions: list[list[CacheRecord]] = []

    def replace_ticker_records_atomically(self, records: list[CacheRecord]) -> None:
        self.transactions.append(records)
        super().replace_ticker_records_atomically(records)


def _source_failure_state(ticker: str, version: int) -> CacheRecord:
    return CacheRecord(
        pk=f"TICKER#{ticker}",
        sk="PRICE#LATEST",
        entity_type="UNDERLYING_SNAPSHOT",
        schema_version="market-data/v1",
        data={"ticker": ticker, "version": version},
        updated_at="2025-05-22T14:30:00Z",
        ttl=1_748_010_460,
    )


def _cache_record_projection(
    record: CacheRecord,
) -> tuple[str, str, str, str, str, str, int]:
    """Return a hashable, order-independent test projection of a cache record."""
    return (
        record.pk,
        record.sk,
        record.entity_type,
        record.schema_version,
        json.dumps(record.data, default=str, sort_keys=True),
        record.updated_at,
        record.ttl,
    )


def test_refresh_uses_only_the_injected_adapter_and_commits_one_complete_transaction() -> None:
    repository = RecordingRepository()
    adapter = MockMarketDataAdapter()
    service = RefreshService(
        adapter,
        repository,
        lambda: _REFRESH_TIME,
        fixture_tickers=("spy",),
        cache_ttl_seconds=300,
    )

    summary = service.refresh()

    assert summary.refreshed_tickers == ("SPY",)
    assert summary.records_written == len(repository.records)
    assert len(repository.transactions) == 1
    assert {_cache_record_projection(record) for record in repository.transactions[0]} == {
        _cache_record_projection(record) for record in repository.records
    }
    assert {record.sk for record in repository.records} >= {"PRICE#LATEST"}
    assert all(record.updated_at == "2025-05-22T14:31:00Z" for record in repository.records)
    assert all(record.ttl == 1_747_924_560 for record in repository.records)


# Feature: foundation-scaffolding-and-mock-data-platform, Property 9: Valid fixture refresh maps every normalized record to the cache  # noqa: E501
@settings(max_examples=100)
@given(seconds=st.integers(min_value=1_700_000_000, max_value=1_800_000_000))
def test_valid_fixture_refresh_maps_every_normalized_record_to_cache(seconds: int) -> None:
    refreshed_at = datetime.fromtimestamp(seconds, UTC)
    adapter = MockMarketDataAdapter()
    expected_snapshot = adapter.get_underlying_snapshot("SPY")
    expected_options = adapter.get_option_chain_records("SPY")
    repository = RecordingRepository()
    service = RefreshService(
        adapter,
        repository,
        lambda: refreshed_at,
        fixture_tickers=("SPY",),
        cache_ttl_seconds=300,
    )

    summary = service.refresh()

    assert summary.records_written == 1 + len(expected_options)
    assert len(repository.transactions) == 1
    assert len(repository.records) == 1 + len(expected_options)
    assert {(record.pk, record.sk) for record in repository.records} == {
        (f"TICKER#{expected_snapshot.ticker}", "PRICE#LATEST"),
        *{
            (
                f"TICKER#{option.ticker}",
                f"OPTION#{option.option_type}#{option.strike:.2f}#{option.expiry}",
            )
            for option in expected_options
        },
    }
    expected_timestamp = refreshed_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    assert all(record.updated_at == expected_timestamp for record in repository.records)
    assert all(record.ttl == seconds + 300 for record in repository.records)


# Feature: foundation-scaffolding-and-mock-data-platform, Property 10: Source failures are non-mutating for the failed ticker  # noqa: E501
@settings(max_examples=100)
@given(
    ticker=st.from_regex(r"[A-Z]{1,10}", fullmatch=True).filter(lambda ticker: ticker != "SPY"),
    version=st.integers(min_value=0, max_value=1_000_000),
)
def test_source_failures_leave_existing_failed_ticker_records_unchanged(
    ticker: str, version: int
) -> None:
    repository = RecordingRepository()
    existing_record = _source_failure_state(ticker, version)
    repository.replace_ticker_records_atomically([existing_record])
    original_records = repository.records
    original_transaction_count = len(repository.transactions)
    service = RefreshService(
        UnsupportedTickerSource(),
        repository,
        lambda: _REFRESH_TIME,
        fixture_tickers=(ticker,),
        cache_ttl_seconds=300,
    )

    with pytest.raises(RefreshFailedError) as error:
        service.refresh()

    assert repository.records == original_records
    assert len(repository.transactions) == original_transaction_count
    assert error.value.summary.failures == (error.value.summary.failures[0],)
    assert error.value.summary.failures[0].ticker == ticker
    assert error.value.summary.failures[0].error_class == "SourceDataError"


def test_source_failure_leaves_existing_failed_ticker_records_unchanged() -> None:
    repository = InMemoryMarketDataRepository()
    existing = RefreshService(
        MockMarketDataAdapter(),
        repository,
        lambda: _REFRESH_TIME,
        fixture_tickers=("SPY",),
        cache_ttl_seconds=300,
    )
    existing.refresh()
    original_records = repository.records
    service = RefreshService(
        UnsupportedTickerSource(),
        repository,
        lambda: _REFRESH_TIME,
        fixture_tickers=("SPY",),
        cache_ttl_seconds=300,
    )

    with pytest.raises(RefreshFailedError) as error:
        service.refresh()

    assert repository.records == original_records
    assert error.value.summary.failures[0].ticker == "SPY"
    assert error.value.summary.failures[0].error_class == "SourceDataError"
