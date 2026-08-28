"""Scheduler-compatible Lambda entry point for the mock market-data refresh."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import boto3  # type: ignore[import-untyped]

from trader_insight.adapters.dynamodb_market_data_repository import DynamoDBMarketDataRepository
from trader_insight.adapters.mock_market_data_adapter import MockMarketDataAdapter
from trader_insight.config import RefreshConfiguration
from trader_insight.domain.refresh_service import RefreshFailedError, RefreshService, RefreshSummary

_LOGGER = logging.getLogger(__name__)


def lambda_handler(event: Mapping[str, object], context: Any) -> dict[str, object]:
    """Delegate a Scheduler invocation without exposing an API or publishing streams."""
    del event
    service = build_refresh_service(os.environ)
    request_id = getattr(context, "aws_request_id", None)
    try:
        summary = service.refresh()
    except RefreshFailedError as error:
        _log("refresh_failed", request_id, error.summary)
        raise

    _log("refresh_succeeded", request_id, summary)
    return summary.to_log_fields()


def build_refresh_service(environment: Mapping[str, str]) -> RefreshService:
    """Wire the only runtime dependencies needed by the Lambda handler."""
    configuration = RefreshConfiguration.from_environment(environment)
    table_name = environment.get("MARKET_DATA_TABLE_NAME")
    if not table_name:
        raise ValueError("MARKET_DATA_TABLE_NAME is required")
    repository = DynamoDBMarketDataRepository(boto3.client("dynamodb"), table_name)
    return RefreshService(
        MockMarketDataAdapter(),
        repository,
        lambda: datetime.now(UTC),
        fixture_tickers=configuration.fixture_tickers,
        cache_ttl_seconds=configuration.cache_ttl_seconds,
    )


def _log(event_name: str, request_id: str | None, summary: RefreshSummary) -> None:
    fields: dict[str, object] = {"event": event_name, **summary.to_log_fields()}
    if request_id:
        fields["request_id"] = request_id
    _LOGGER.info("%s", json.dumps(fields, sort_keys=True))
