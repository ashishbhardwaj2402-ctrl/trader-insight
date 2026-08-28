from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
INFRA_DIRECTORY = BACKEND_DIRECTORY / "infra"
CONTRACT_SCHEMA = (
    BACKEND_DIRECTORY.parent / "contracts" / "market-data" / "v1" / "market-data.schema.json"
)
if str(INFRA_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(INFRA_DIRECTORY))

from config import RefreshScheduleConfiguration  # noqa: E402, I001


SUPPORTED_UNITS = st.sampled_from(["minute", "minutes", "hour", "hours", "day", "days"])
POSITIVE_INTERVALS = st.integers(min_value=1, max_value=1_000_000)


def test_schedule_configuration_defaults_to_one_minute() -> None:
    configuration = RefreshScheduleConfiguration.from_environment({})

    assert configuration.interval_value == 1
    assert configuration.interval_unit == "minute"
    assert configuration.rate_expression == "rate(1 minute)"


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "one", ""])
def test_schedule_configuration_rejects_invalid_interval_values(value: str) -> None:
    with pytest.raises(ValueError, match="positive whole integer"):
        RefreshScheduleConfiguration.from_environment({"REFRESH_INTERVAL_VALUE": value})


@pytest.mark.parametrize("unit", ["second", "seconds", "cron(0 12 * * ? *)", "week", ""])
def test_schedule_configuration_rejects_invalid_units(unit: str) -> None:
    with pytest.raises(ValueError, match="minute\\(s\\), hour\\(s\\), or day\\(s\\)"):
        RefreshScheduleConfiguration.from_environment({"REFRESH_INTERVAL_UNIT": unit})


# Feature: foundation-scaffolding-and-mock-data-platform, Property 8: Legal refresh settings generate legal rate expressions  # noqa: E501
@settings(max_examples=100)
@given(interval_value=POSITIVE_INTERVALS, interval_unit=SUPPORTED_UNITS)
def test_property_8_legal_refresh_settings_generate_legal_rate_expressions(
    interval_value: int, interval_unit: str
) -> None:
    schema_before = CONTRACT_SCHEMA.read_text(encoding="utf-8")
    configuration = RefreshScheduleConfiguration.from_environment(
        {
            "REFRESH_INTERVAL_VALUE": str(interval_value),
            "REFRESH_INTERVAL_UNIT": interval_unit,
        }
    )
    singular_unit = interval_unit.rstrip("s")
    expected_unit = singular_unit if interval_value == 1 else f"{singular_unit}s"

    assert configuration.rate_expression == f"rate({interval_value} {expected_unit})"
    assert re.fullmatch(
        r"rate\([1-9][0-9]* (minutes?|hours?|days?)\)", configuration.rate_expression
    )
    assert CONTRACT_SCHEMA.read_text(encoding="utf-8") == schema_before
