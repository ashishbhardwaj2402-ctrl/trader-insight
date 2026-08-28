from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from trader_insight.domain import (
    DomainValidationError,
    OptionChainRecord,
    UnderlyingMarketSnapshot,
    build_option_cache_record,
    build_snapshot_cache_record,
    load_fixture,
    validate_fixture,
)

TICKERS = st.sampled_from(["SPY", "QQQ", "IWM", "AAPL", "MSFT"])
OPTION_TYPES = st.sampled_from(["CALL", "PUT"])
STRIKES = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("10000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
TTLS = st.integers(min_value=1, max_value=4_102_444_800)
REFRESH_TIMES = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(UTC),
)


def _snapshot(ticker: str) -> dict[str, object]:
    return {
        "schema_version": "market-data/v1",
        "ticker": ticker,
        "price": Decimal("529.74"),
        "trend": "UPTREND",
        "momentum": "STRONG",
        "expected_move": Decimal("7.21"),
        "expected_move_pct": Decimal("1.36"),
        "iv_30d": Decimal("17.8"),
        "iv_rank": 68,
        "iv_percentile": Decimal("72"),
        "put_call_ratio": Decimal("0.78"),
        "max_pain": Decimal("528.00"),
        "updated_at": "2025-05-22T14:30:00Z",
    }


def _option(ticker: str, option_type: str, strike: Decimal) -> dict[str, object]:
    return {
        "schema_version": "market-data/v1",
        "ticker": ticker,
        "strike": strike,
        "option_type": option_type,
        "expiry": "2025-05-30",
        "days_to_expiry": 8,
        "bid": Decimal("3.25"),
        "ask": Decimal("3.35"),
        "delta": Decimal("0.52") if option_type == "CALL" else Decimal("-0.48"),
        "gamma": Decimal("0.057"),
        "theta": Decimal("-0.18"),
        "vega": Decimal("0.29"),
        "rho": Decimal("0.02"),
        "open_interest": 15_420,
        "volume": 8_930,
        "updated_at": "2025-05-22T14:30:00Z",
    }


def _fixture(ticker: str, option_type: str, strike: Decimal) -> dict[str, object]:
    return {
        "schema_version": "market-data/v1",
        "underlying_snapshots": [_snapshot(ticker)],
        "option_chain_records": [_option(ticker, option_type, strike)],
    }


# Feature: foundation-scaffolding-and-mock-data-platform, Property 1: Normalized records preserve required selection and market fields  # noqa: E501
@settings(max_examples=100)
@given(ticker=TICKERS, option_type=OPTION_TYPES, strike=STRIKES)
def test_property_1_normalized_records_preserve_required_selection_and_market_fields(
    ticker: str, option_type: str, strike: Decimal
) -> None:
    snapshot = UnderlyingMarketSnapshot.model_validate(_snapshot(ticker))
    option = OptionChainRecord.model_validate(_option(ticker, option_type, strike))

    assert set(snapshot.model_dump()) == set(_snapshot(ticker))
    assert set(option.model_dump()) == set(_option(ticker, option_type, strike))
    assert (option.ticker, option.strike, option.option_type, option.expiry) == (
        ticker,
        strike,
        option_type,
        "2025-05-30",
    )


# Feature: foundation-scaffolding-and-mock-data-platform, Property 2: Fixture validation preserves cross-record ticker integrity and rejects invalid option types  # noqa: E501
@settings(max_examples=100)
@given(
    ticker=TICKERS,
    mismatch_ticker=TICKERS,
    unsupported_option_type=st.text(
        alphabet=st.characters(whitelist_categories=("Lu",)), min_size=1, max_size=8
    ).filter(lambda value: value not in {"CALL", "PUT"}),
    strike=STRIKES,
)
def test_property_2_fixture_validation_enforces_ticker_integrity_and_option_types(
    ticker: str, mismatch_ticker: str, unsupported_option_type: str, strike: Decimal
) -> None:
    valid = _fixture(ticker, "CALL", strike)
    assert validate_fixture(valid).option_chain_records[0].ticker == ticker

    mismatched = _fixture(ticker, "CALL", strike)
    mismatched_option = mismatched["option_chain_records"][0]
    assert isinstance(mismatched_option, dict)
    mismatched_option["ticker"] = mismatch_ticker if mismatch_ticker != ticker else "TSLA"
    with pytest.raises(DomainValidationError):
        validate_fixture(mismatched)

    unsupported = _fixture(ticker, "CALL", strike)
    unsupported_option = unsupported["option_chain_records"][0]
    assert isinstance(unsupported_option, dict)
    unsupported_option["option_type"] = unsupported_option_type
    with pytest.raises(DomainValidationError):
        validate_fixture(unsupported)


# Feature: foundation-scaffolding-and-mock-data-platform, Property 3: Fixture loading is deterministic  # noqa: E501
@settings(max_examples=100)
@given(ticker=TICKERS, option_type=OPTION_TYPES, strike=STRIKES)
def test_property_3_fixture_loading_is_deterministic(
    ticker: str, option_type: str, strike: Decimal
) -> None:
    raw_fixture = _fixture(ticker, option_type, strike)
    original = deepcopy(raw_fixture)

    assert load_fixture(raw_fixture) == load_fixture(raw_fixture)
    assert raw_fixture == original


# Feature: foundation-scaffolding-and-mock-data-platform, Property 6: Cache-record mapping yields canonical complete records  # noqa: E501
@settings(max_examples=100)
@given(
    ticker=TICKERS,
    option_type=OPTION_TYPES,
    strike=STRIKES,
    refreshed_at=REFRESH_TIMES,
    ttl=TTLS,
)
def test_property_6_cache_record_mapping_yields_canonical_complete_records(
    ticker: str,
    option_type: str,
    strike: Decimal,
    refreshed_at: datetime,
    ttl: int,
) -> None:
    snapshot = UnderlyingMarketSnapshot.model_validate(_snapshot(ticker))
    option = OptionChainRecord.model_validate(_option(ticker, option_type, strike))
    snapshot_record = build_snapshot_cache_record(snapshot, refreshed_at, ttl)
    option_record = build_option_cache_record(option, refreshed_at, ttl)
    timestamp = refreshed_at.isoformat(timespec="seconds").replace("+00:00", "Z")

    assert snapshot_record.pk == f"TICKER#{ticker}"
    assert snapshot_record.sk == "PRICE#LATEST"
    assert snapshot_record.data == snapshot.model_dump(mode="python")
    assert option_record.pk == f"TICKER#{ticker}"
    assert option_record.sk == f"OPTION#{option_type}#{strike:.2f}#2025-05-30"
    assert option_record.data == option.model_dump(mode="python")
    assert snapshot_record.updated_at == option_record.updated_at == timestamp
    assert snapshot_record.ttl == option_record.ttl == ttl
