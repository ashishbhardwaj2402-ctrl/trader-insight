"""Typed errors for vendor-neutral market-data domain validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainValidationError(ValueError):
    """Raised when input does not satisfy the market-data v1 domain contract."""

    message: str
    field_path: str | None = None

    def __str__(self) -> str:
        if self.field_path:
            return f"{self.field_path}: {self.message}"
        return self.message


@dataclass(frozen=True, slots=True)
class SourceDataError(ValueError):
    """Identifies a normalized ticker unavailable from a market-data source."""

    ticker: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.upper())

    def __str__(self) -> str:
        return f"Unsupported market-data ticker: {self.ticker}"
