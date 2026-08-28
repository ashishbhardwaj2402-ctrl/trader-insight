from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from trader_insight.domain import (
    build_option_cache_record,
    build_snapshot_cache_record,
    load_fixture,
)


def _fixture() -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[3]
    fixture_path = repository_root / "contracts" / "market-data" / "v1" / "fixtures" / "spy.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_fixture_load_and_cache_mapping_are_deterministic() -> None:
    raw_fixture = _fixture()
    fixture = load_fixture(raw_fixture)
    refresh_time = datetime(2025, 5, 22, 14, 31, tzinfo=UTC)

    snapshot_cache_record = build_snapshot_cache_record(
        fixture.underlying_snapshots[0], refresh_time, 1_748_010_460
    )
    option_cache_record = build_option_cache_record(
        fixture.option_chain_records[2], refresh_time, 1_748_010_460
    )

    assert load_fixture(raw_fixture) == fixture
    assert snapshot_cache_record.pk == "TICKER#SPY"
    assert snapshot_cache_record.sk == "PRICE#LATEST"
    assert option_cache_record.sk == "OPTION#CALL#530.00#2025-05-30"
    assert snapshot_cache_record.updated_at == "2025-05-22T14:31:00Z"
    assert option_cache_record.ttl == 1_748_010_460
