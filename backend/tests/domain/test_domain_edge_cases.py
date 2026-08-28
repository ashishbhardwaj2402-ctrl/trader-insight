from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trader_insight.domain import (
    DomainValidationError,
    OptionChainRecord,
    UnderlyingMarketSnapshot,
    build_option_cache_record,
    build_snapshot_cache_record,
    validate_fixture,
)


def _snapshot() -> dict[str, object]:
    return {
        "schema_version": "market-data/v1",
        "ticker": "SPY",
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


def _option() -> dict[str, object]:
    return {
        "schema_version": "market-data/v1",
        "ticker": "SPY",
        "strike": Decimal("530.00"),
        "option_type": "CALL",
        "expiry": "2025-05-30",
        "days_to_expiry": 8,
        "bid": Decimal("3.25"),
        "ask": Decimal("3.35"),
        "delta": Decimal("0.52"),
        "gamma": Decimal("0.057"),
        "theta": Decimal("-0.18"),
        "vega": Decimal("0.29"),
        "rho": Decimal("0.02"),
        "open_interest": 15_420,
        "volume": 8_930,
        "updated_at": "2025-05-22T14:30:00Z",
    }


def _fixture() -> dict[str, object]:
    return {
        "schema_version": "market-data/v1",
        "underlying_snapshots": [_snapshot()],
        "option_chain_records": [_option()],
    }


@pytest.mark.parametrize("selection_field", ["ticker", "strike", "option_type", "expiry"])
def test_fixture_rejects_missing_required_selection_field(selection_field: str) -> None:
    fixture = _fixture()
    option = fixture["option_chain_records"][0]
    assert isinstance(option, dict)
    del option[selection_field]

    with pytest.raises(DomainValidationError) as error:
        validate_fixture(fixture)

    assert selection_field in str(error.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("updated_at", "2025-05-22 14:30:00"),
        ("price", "not-a-number"),
        ("strike", "not-a-number"),
    ],
)
def test_fixture_rejects_malformed_timestamps_and_numbers(field: str, value: object) -> None:
    fixture = _fixture()
    target = (
        fixture["underlying_snapshots"][0]
        if field == "price"
        else fixture["option_chain_records"][0]
    )
    assert isinstance(target, dict)
    target[field] = value

    with pytest.raises(DomainValidationError):
        validate_fixture(fixture)


def test_fixture_rejects_cross_record_ticker_mismatch() -> None:
    fixture = _fixture()
    option = fixture["option_chain_records"][0]
    assert isinstance(option, dict)
    option["ticker"] = "QQQ"

    with pytest.raises(DomainValidationError, match="option record tickers"):
        validate_fixture(fixture)


def test_fixture_rejects_unsupported_option_type() -> None:
    fixture = _fixture()
    option = fixture["option_chain_records"][0]
    assert isinstance(option, dict)
    option["option_type"] = "STRADDLE"

    with pytest.raises(DomainValidationError):
        validate_fixture(fixture)


@pytest.mark.parametrize("ttl", [None, 0, -1, True, "3600"])
def test_cache_builders_reject_missing_or_invalid_ttl(ttl: object) -> None:
    snapshot = UnderlyingMarketSnapshot.model_validate(_snapshot())
    refreshed_at = datetime(2025, 5, 22, 14, 31, tzinfo=UTC)

    with pytest.raises(DomainValidationError, match="ttl"):
        build_snapshot_cache_record(snapshot, refreshed_at, ttl)  # type: ignore[arg-type]


def test_cache_builders_use_representative_canonical_keys() -> None:
    snapshot = UnderlyingMarketSnapshot.model_validate(_snapshot())
    option = OptionChainRecord.model_validate(_option())
    refreshed_at = datetime(2025, 5, 22, 14, 31, tzinfo=UTC)

    snapshot_record = build_snapshot_cache_record(snapshot, refreshed_at, 1_748_010_460)
    option_record = build_option_cache_record(option, refreshed_at, 1_748_010_460)

    assert (snapshot_record.pk, snapshot_record.sk) == ("TICKER#SPY", "PRICE#LATEST")
    assert (option_record.pk, option_record.sk) == (
        "TICKER#SPY",
        "OPTION#CALL#530.00#2025-05-30",
    )
