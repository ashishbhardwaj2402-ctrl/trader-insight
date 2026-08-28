"""Offline validator for all checked-in market-data v1 fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]
from jsonschema.exceptions import ValidationError  # type: ignore[import-untyped]

from trader_insight.domain.errors import DomainValidationError
from trader_insight.domain.fixtures import validate_fixture


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def validate_checked_in_fixtures() -> list[Path]:
    """Validate schema and domain semantics for every checked-in v1 fixture."""
    contract_directory = _repository_root() / "contracts" / "market-data" / "v1"
    schema = _load_json(contract_directory / "market-data.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    fixture_paths = sorted((contract_directory / "fixtures").glob("*.json"))
    if not fixture_paths:
        raise DomainValidationError("no checked-in market-data fixtures were found")

    for fixture_path in fixture_paths:
        raw_fixture = _load_json(fixture_path)
        try:
            validator.validate(raw_fixture)
        except ValidationError as error:
            location = ".".join(str(part) for part in error.absolute_path) or None
            raise DomainValidationError(error.message, location) from error
        try:
            validate_fixture(raw_fixture)
        except DomainValidationError as error:
            raise DomainValidationError(str(error), str(fixture_path)) from error
    return fixture_paths


def main() -> int:
    try:
        fixture_paths = validate_checked_in_fixtures()
    except (DomainValidationError, OSError, json.JSONDecodeError) as error:
        print(f"Fixture validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(fixture_paths)} market-data fixture(s) offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
