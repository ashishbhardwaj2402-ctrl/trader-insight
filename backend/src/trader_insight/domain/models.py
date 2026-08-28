"""Pure validated models for the market-data/v1 contract."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "market-data/v1"
TICKER_PATTERN = r"^[A-Z][A-Z0-9.]{0,9}$"
UTC_TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"

PositiveDecimal = Annotated[Decimal, Field(gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
Percentage = Annotated[Decimal, Field(ge=0, le=100)]


class ContractModel(BaseModel):
    """Base model that preserves the closed v1 schema shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TimestampedModel(ContractModel):
    updated_at: str

    @field_validator("updated_at")
    @classmethod
    def validate_utc_timestamp(cls, value: str) -> str:
        if not re.fullmatch(UTC_TIMESTAMP_PATTERN, value):
            raise ValueError("must be a UTC ISO 8601 timestamp with a Z suffix")
        try:
            parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError as error:
            raise ValueError("must be a valid UTC ISO 8601 timestamp") from error
        if parsed.tzinfo != UTC:
            raise ValueError("must use the UTC Z suffix")
        return value


class UnderlyingMarketSnapshot(TimestampedModel):
    schema_version: Literal["market-data/v1"]
    ticker: Annotated[str, Field(pattern=TICKER_PATTERN)]
    price: PositiveDecimal
    trend: Literal["UPTREND", "DOWNTREND", "NEUTRAL"]
    momentum: Literal["STRONG", "MODERATE", "WEAK"]
    expected_move: NonNegativeDecimal
    expected_move_pct: NonNegativeDecimal
    iv_30d: NonNegativeDecimal
    iv_rank: Annotated[int, Field(ge=0, le=100)]
    iv_percentile: Percentage
    put_call_ratio: NonNegativeDecimal
    max_pain: PositiveDecimal


class OptionChainRecord(TimestampedModel):
    schema_version: Literal["market-data/v1"]
    ticker: Annotated[str, Field(pattern=TICKER_PATTERN)]
    strike: PositiveDecimal
    option_type: Literal["CALL", "PUT"]
    expiry: str
    days_to_expiry: Annotated[int, Field(ge=0)]
    bid: NonNegativeDecimal
    ask: NonNegativeDecimal
    delta: Annotated[Decimal, Field(ge=-1, le=1)]
    gamma: NonNegativeDecimal
    theta: Decimal
    vega: NonNegativeDecimal
    rho: Decimal
    open_interest: Annotated[int, Field(ge=0)]
    volume: Annotated[int, Field(ge=0)]

    @field_validator("expiry")
    @classmethod
    def validate_expiry(cls, value: str) -> str:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("must be an ISO date in YYYY-MM-DD format") from error
        if parsed.isoformat() != value:
            raise ValueError("must be an ISO date in YYYY-MM-DD format")
        return value

    @model_validator(mode="after")
    def validate_bid_ask(self) -> OptionChainRecord:
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")
        return self


class MarketDataFixture(ContractModel):
    schema_version: Literal["market-data/v1"]
    underlying_snapshots: Annotated[list[UnderlyingMarketSnapshot], Field(min_length=1)]
    option_chain_records: Annotated[list[OptionChainRecord], Field(min_length=1, max_length=24)]

    @model_validator(mode="after")
    def validate_option_ticker_overlap(self) -> MarketDataFixture:
        snapshot_tickers = {snapshot.ticker for snapshot in self.underlying_snapshots}
        unmatched = sorted(
            {record.ticker for record in self.option_chain_records} - snapshot_tickers
        )
        if unmatched:
            raise ValueError(
                "option record tickers must match a ticker in underlying_snapshots: "
                + ", ".join(unmatched)
            )
        return self
