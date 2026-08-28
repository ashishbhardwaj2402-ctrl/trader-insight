"""Validated, non-secret CDK configuration for the foundation stack."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_SUPPORTED_UNITS = {
    "minute": "minute",
    "minutes": "minutes",
    "hour": "hour",
    "hours": "hours",
    "day": "day",
    "days": "days",
}


@dataclass(frozen=True, slots=True)
class RefreshScheduleConfiguration:
    """A foundation-supported EventBridge Scheduler rate expression."""

    interval_value: int
    interval_unit: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> RefreshScheduleConfiguration:
        """Read only positive whole minute, hour, or day refresh intervals."""
        values = os.environ if environment is None else environment
        raw_value = values.get("REFRESH_INTERVAL_VALUE", "1")
        raw_unit = values.get("REFRESH_INTERVAL_UNIT", "minute").lower()

        try:
            interval_value = int(raw_value)
        except ValueError as error:
            raise ValueError("REFRESH_INTERVAL_VALUE must be a positive whole integer") from error
        if interval_value <= 0 or str(interval_value) != raw_value.strip():
            raise ValueError("REFRESH_INTERVAL_VALUE must be a positive whole integer")

        interval_unit = _SUPPORTED_UNITS.get(raw_unit)
        if interval_unit is None:
            raise ValueError(
                "REFRESH_INTERVAL_UNIT must be minute(s), hour(s), or day(s); "
                "seconds and cron expressions are not supported"
            )
        return cls(interval_value=interval_value, interval_unit=interval_unit)

    @property
    def rate_expression(self) -> str:
        """Return the Scheduler-compatible rate expression."""
        singular_unit = self.interval_unit.rstrip("s")
        unit = singular_unit if self.interval_value == 1 else f"{singular_unit}s"
        return f"rate({self.interval_value} {unit})"
