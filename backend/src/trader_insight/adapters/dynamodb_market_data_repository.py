"""DynamoDB implementation of the normalized market-data cache repository."""

from __future__ import annotations

from typing import Any, Protocol

from boto3.dynamodb.types import TypeSerializer  # type: ignore[import-untyped]

from trader_insight.domain.cache import CacheRecord
from trader_insight.domain.repository import validate_transaction_records


class DynamoDBTransactionClient(Protocol):
    """Minimal low-level DynamoDB client surface used by this adapter."""

    def transact_write_items(self, *, TransactItems: list[dict[str, Any]]) -> object:
        """Apply an atomic DynamoDB transaction."""
        ...


class DynamoDBMarketDataRepository:
    """Persist cache records using Put-only DynamoDB transactions."""

    def __init__(self, client: DynamoDBTransactionClient, table_name: str) -> None:
        self._client = client
        self._table_name = table_name
        self._serializer = TypeSerializer()

    def replace_ticker_records_atomically(self, records: list[CacheRecord]) -> None:
        """Atomically replace supplied cache keys with their normalized values."""
        validate_transaction_records(records)
        if not records:
            return

        transact_items = [
            {
                "Put": {
                    "TableName": self._table_name,
                    "Item": self._serialize_record(record),
                }
            }
            for record in records
        ]
        self._client.transact_write_items(TransactItems=transact_items)

    def _serialize_record(self, record: CacheRecord) -> dict[str, Any]:
        normalized_item = {
            "pk": record.pk,
            "sk": record.sk,
            "entity_type": record.entity_type,
            "schema_version": record.schema_version,
            "data": record.data,
            "updated_at": record.updated_at,
            "ttl": record.ttl,
        }
        return {name: self._serializer.serialize(value) for name, value in normalized_item.items()}
