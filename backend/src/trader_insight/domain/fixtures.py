"""Pure market-data fixture validation and deterministic normalization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from trader_insight.domain.errors import DomainValidationError
from trader_insight.domain.models import MarketDataFixture


def _field_path(error: Mapping[str, Any]) -> str | None:
    location = error.get("loc", ())
    if not location:
        return None
    return ".".join(str(part) for part in location)


def validate_fixture(raw_fixture: Mapping[str, object]) -> MarketDataFixture:
    """Validate a raw v1 fixture without performing file or network I/O."""
    try:
        return MarketDataFixture.model_validate(raw_fixture)
    except ValidationError as error:
        first_error = error.errors()[0]
        raise DomainValidationError(
            message=first_error["msg"], field_path=_field_path(first_error)
        ) from error


def load_fixture(raw_fixture: Mapping[str, object]) -> MarketDataFixture:
    """Deterministically convert a raw fixture mapping to immutable domain models."""
    return validate_fixture(raw_fixture)
