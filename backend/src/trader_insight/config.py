"""Non-secret runtime configuration for the scheduled refresh operation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from trader_insight.domain.errors import DomainValidationError

_DEFAULT_FIXTURE_TICKERS = ("SPY",)
_DEFAULT_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True, slots=True)
class RefreshConfiguration:
    """Validated values needed by the refresh service and Lambda wiring."""

    fixture_tickers: tuple[str, ...]
    cache_ttl_seconds: int

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> RefreshConfiguration:
        """Load the explicit development ticker allow-list and cache retention TTL."""
        raw_tickers = environment.get("FIXTURE_TICKERS", ",".join(_DEFAULT_FIXTURE_TICKERS))
        tickers = tuple(
            ticker.strip().upper() for ticker in raw_tickers.split(",") if ticker.strip()
        )
        if not tickers:
            raise DomainValidationError(
                "FIXTURE_TICKERS must include at least one ticker", "FIXTURE_TICKERS"
            )
        if len(set(tickers)) != len(tickers):
            raise DomainValidationError(
                "FIXTURE_TICKERS must not contain duplicates", "FIXTURE_TICKERS"
            )

        raw_ttl = environment.get("CACHE_TTL_SECONDS", str(_DEFAULT_CACHE_TTL_SECONDS))
        try:
            cache_ttl_seconds = int(raw_ttl)
        except ValueError as error:
            raise DomainValidationError(
                "CACHE_TTL_SECONDS must be a positive integer", "CACHE_TTL_SECONDS"
            ) from error
        if cache_ttl_seconds <= 0:
            raise DomainValidationError(
                "CACHE_TTL_SECONDS must be a positive integer", "CACHE_TTL_SECONDS"
            )

        return cls(fixture_tickers=tickers, cache_ttl_seconds=cache_ttl_seconds)
