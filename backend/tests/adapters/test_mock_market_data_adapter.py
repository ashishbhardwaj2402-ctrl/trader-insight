from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from trader_insight.adapters.mock_market_data_adapter import MockMarketDataAdapter
from trader_insight.domain import OptionChainRecord, SourceDataError, UnderlyingMarketSnapshot
from trader_insight.domain.source import MarketDataSource

_FIXTURE_DIRECTORY = (
    Path(__file__).resolve().parents[3] / "contracts" / "market-data" / "v1" / "fixtures"
)
_SUPPORTED_TICKERS = tuple(sorted(path.stem.upper() for path in _FIXTURE_DIRECTORY.glob("*.json")))
_UNSUPPORTED_TICKERS = st.from_regex(r"[A-Za-z]{1,10}", fullmatch=True).filter(
    lambda ticker: ticker.upper() not in _SUPPORTED_TICKERS
)


@pytest.mark.parametrize("ticker", _SUPPORTED_TICKERS)
def test_mock_adapter_contract_returns_normalized_models_for_each_fixture_ticker(
    ticker: str,
) -> None:
    """Exercise both source operations for every checked-in fixture ticker."""
    adapter = MockMarketDataAdapter()

    snapshot = adapter.get_underlying_snapshot(ticker.lower())
    records = adapter.get_option_chain_records(ticker.lower())

    assert isinstance(snapshot, UnderlyingMarketSnapshot)
    assert snapshot.ticker == ticker
    assert records
    assert all(isinstance(record, OptionChainRecord) for record in records)
    assert {record.ticker for record in records} == {ticker}
    assert all(record.schema_version == snapshot.schema_version for record in records)


# Feature: foundation-scaffolding-and-mock-data-platform, Property 4: Supported adapter reads are deterministic  # noqa: E501
@settings(max_examples=100)
@given(ticker=st.sampled_from(_SUPPORTED_TICKERS))
def test_supported_adapter_reads_are_deterministic(ticker: str) -> None:
    adapter = MockMarketDataAdapter()

    assert adapter.get_underlying_snapshot(ticker.lower()) == adapter.get_underlying_snapshot(
        ticker
    )
    assert adapter.get_option_chain_records(ticker.lower()) == adapter.get_option_chain_records(
        ticker
    )


# Feature: foundation-scaffolding-and-mock-data-platform, Property 5: Unsupported tickers retain typed error identity  # noqa: E501
@settings(max_examples=100)
@given(ticker=_UNSUPPORTED_TICKERS)
def test_unsupported_tickers_retain_typed_error_identity(ticker: str) -> None:
    adapter = MockMarketDataAdapter()
    normalized_ticker = ticker.upper()

    for operation in (adapter.get_underlying_snapshot, adapter.get_option_chain_records):
        with pytest.raises(SourceDataError) as error:
            operation(ticker)
        assert error.value.ticker == normalized_ticker
        assert normalized_ticker in str(error.value)


def test_mock_adapter_implements_market_data_source_protocol() -> None:
    source: MarketDataSource = MockMarketDataAdapter()

    assert source.get_underlying_snapshot(_SUPPORTED_TICKERS[0]).ticker == _SUPPORTED_TICKERS[0]
