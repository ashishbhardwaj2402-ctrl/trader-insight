"""Pure cache-record mapping for normalized market-data v1 models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import Field, field_validator

from trader_insight.domain.errors import DomainValidationError
from trader_insight.domain.models import (
    ContractModel,
    OptionChainRecord,
    UnderlyingMarketSnapshot,
)

_TWO_DECIMAL_PLACES = Decimal("0.01")


class CacheRecord(ContractModel):
    pk: str
    sk: str
    entity_type: Literal["UNDERLYING_SNAPSHOT", "OPTION_CHAIN_RECORD"]
    schema_version: Literal["market-data/v1"]
    data: dict[str, object]
    updated_at: str
    ttl: Annotated[int, Field(gt=0)]

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value[:-1] + "+00:00") if value.endswith("Z") else None
        except ValueError as error:
            raise ValueError("must be a UTC ISO 8601 timestamp with a Z suffix") from error
        if parsed is None or parsed.tzinfo != UTC:
            raise ValueError("must be a UTC ISO 8601 timestamp with a Z suffix")
        return value


def _format_refresh_time(refreshed_at: datetime) -> str:
    if refreshed_at.tzinfo is None or refreshed_at.utcoffset() != UTC.utcoffset(refreshed_at):
        raise DomainValidationError("refreshed_at must be a UTC-aware datetime", "refreshed_at")
    return refreshed_at.isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_ttl(ttl: int) -> int:
    if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
        raise DomainValidationError("ttl must be a positive integer epoch-second value", "ttl")
    return ttl


def _canonical_strike(strike: Decimal) -> str:
    try:
        normalized = strike.quantize(_TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise DomainValidationError(
            "strike cannot be formatted as a two-decimal value", "strike"
        ) from error
    return format(normalized, ".2f")


def build_snapshot_cache_record(
    snapshot: UnderlyingMarketSnapshot, refreshed_at: datetime, ttl: int
) -> CacheRecord:
    """Map a validated snapshot to its canonical cache record."""
    return CacheRecord(
        pk=f"TICKER#{snapshot.ticker}",
        sk="PRICE#LATEST",
        entity_type="UNDERLYING_SNAPSHOT",
        schema_version=snapshot.schema_version,
        data=snapshot.model_dump(mode="python"),
        updated_at=_format_refresh_time(refreshed_at),
        ttl=_validate_ttl(ttl),
    )


def build_option_cache_record(
    record: OptionChainRecord, refreshed_at: datetime, ttl: int
) -> CacheRecord:
    """Map a validated option record to its canonical cache record."""
    return CacheRecord(
        pk=f"TICKER#{record.ticker}",
        sk=f"OPTION#{record.option_type}#{_canonical_strike(record.strike)}#{record.expiry}",
        entity_type="OPTION_CHAIN_RECORD",
        schema_version=record.schema_version,
        data=record.model_dump(mode="python"),
        updated_at=_format_refresh_time(refreshed_at),
        ttl=_validate_ttl(ttl),
    )
