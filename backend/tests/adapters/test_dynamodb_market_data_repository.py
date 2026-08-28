from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fakes.in_memory_market_data_repository import InMemoryMarketDataRepository
from trader_insight.adapters.dynamodb_market_data_repository import DynamoDBMarketDataRepository
from trader_insight.domain import CacheRecord, DomainValidationError
from trader_insight.domain.repository import MarketDataRepository


class RecordingDynamoDBClient:
    def __init__(self) -> None:
        self.transactions: list[list[dict[str, object]]] = []

    def transact_write_items(self, *, TransactItems: list[dict[str, object]]) -> object:
        self.transactions.append(TransactItems)
        return {}


def _record(
    *,
    data: dict[str, object] | None = None,
    updated_at: str = "2025-05-22T14:31:00Z",
) -> CacheRecord:
    return CacheRecord(
        pk="TICKER#SPY",
        sk="PRICE#LATEST",
        entity_type="UNDERLYING_SNAPSHOT",
        schema_version="market-data/v1",
        data=data or {"ticker": "SPY", "price": 529},
        updated_at=updated_at,
        ttl=1_748_010_460,
    )


def test_dynamodb_repository_writes_put_only_normalized_attributes_in_one_transaction() -> None:
    client = RecordingDynamoDBClient()
    repository = DynamoDBMarketDataRepository(client, "MarketData")

    repository.replace_ticker_records_atomically(
        [_record(), _record(data={"ticker": "SPY", "price": 530})]
    )

    assert len(client.transactions) == 1
    transaction = client.transactions[0]
    assert len(transaction) == 2
    for transaction_item in transaction:
        assert set(transaction_item) == {"Put"}
        put = transaction_item["Put"]
        assert isinstance(put, dict)
        assert put["TableName"] == "MarketData"
        item = put["Item"]
        assert isinstance(item, dict)
        assert set(item) == {
            "pk",
            "sk",
            "entity_type",
            "schema_version",
            "data",
            "updated_at",
            "ttl",
        }
        assert item["pk"] == {"S": "TICKER#SPY"}
        assert item["ttl"] == {"N": "1748010460"}


def test_dynamodb_repository_rejects_invalid_ttl_before_aws_call() -> None:
    client = RecordingDynamoDBClient()
    repository = DynamoDBMarketDataRepository(client, "MarketData")
    invalid_ttl_record = _record().model_construct(ttl=0)

    with pytest.raises(DomainValidationError, match="records\\[0\\]\\.ttl"):
        repository.replace_ticker_records_atomically([invalid_ttl_record])

    assert client.transactions == []


def test_dynamodb_repository_rejects_transactions_larger_than_25_before_aws_call() -> None:
    client = RecordingDynamoDBClient()
    repository = DynamoDBMarketDataRepository(client, "MarketData")

    with pytest.raises(DomainValidationError, match="at most 25"):
        repository.replace_ticker_records_atomically([_record() for _ in range(26)])

    assert client.transactions == []


# Feature: foundation-scaffolding-and-mock-data-platform, Property 7: Cache upsert replaces matching keys  # noqa: E501
@settings(max_examples=100)
@given(
    first_price=st.integers(min_value=1, max_value=1_000_000),
    second_price=st.integers(min_value=1, max_value=1_000_000),
    offset_seconds=st.integers(min_value=1, max_value=86_400),
)
def test_in_memory_repository_upsert_replaces_matching_keys(
    first_price: int, second_price: int, offset_seconds: int
) -> None:
    repository: MarketDataRepository = InMemoryMarketDataRepository()
    first_time = datetime(2025, 5, 22, 14, 31, tzinfo=UTC)
    second_time = first_time + timedelta(seconds=offset_seconds)
    first = _record(
        data={"ticker": "SPY", "price": first_price},
        updated_at=first_time.isoformat().replace("+00:00", "Z"),
    )
    second = _record(
        data={"ticker": "SPY", "price": second_price},
        updated_at=second_time.isoformat().replace("+00:00", "Z"),
    )

    repository.replace_ticker_records_atomically([first])
    repository.replace_ticker_records_atomically([second])

    assert isinstance(repository, InMemoryMarketDataRepository)
    assert repository.records == [second]
