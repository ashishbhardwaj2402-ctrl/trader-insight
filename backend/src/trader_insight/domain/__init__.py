"""Vendor-neutral, pure market-data domain contracts and mappings."""

from trader_insight.domain.cache import (
    CacheRecord,
    build_option_cache_record,
    build_snapshot_cache_record,
)
from trader_insight.domain.errors import DomainValidationError, SourceDataError
from trader_insight.domain.fixtures import load_fixture, validate_fixture
from trader_insight.domain.models import (
    MarketDataFixture,
    OptionChainRecord,
    UnderlyingMarketSnapshot,
)
from trader_insight.domain.repository import MarketDataRepository

__all__ = [
    "CacheRecord",
    "DomainValidationError",
    "MarketDataFixture",
    "MarketDataRepository",
    "OptionChainRecord",
    "SourceDataError",
    "UnderlyingMarketSnapshot",
    "build_option_cache_record",
    "build_snapshot_cache_record",
    "load_fixture",
    "validate_fixture",
]
