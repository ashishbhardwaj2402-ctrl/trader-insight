from __future__ import annotations

import logging

import pytest

from trader_insight.config import RefreshConfiguration
from trader_insight.domain.refresh_service import RefreshFailedError, RefreshFailure, RefreshSummary
from trader_insight.handlers import refresh


class Context:
    aws_request_id = "request-123"


class SuccessfulService:
    def refresh(self) -> RefreshSummary:
        return RefreshSummary(refreshed_tickers=("SPY",), records_written=2, failures=())


class FailingService:
    def refresh(self) -> RefreshSummary:
        raise RefreshFailedError(
            RefreshSummary(
                refreshed_tickers=(),
                records_written=0,
                failures=(RefreshFailure(ticker="SPY", error_class="SourceDataError"),),
            )
        )


def test_handler_delegates_to_wired_service_and_logs_safe_summary(monkeypatch, caplog) -> None:
    monkeypatch.setattr(refresh, "build_refresh_service", lambda environment: SuccessfulService())

    with caplog.at_level(logging.INFO):
        response = refresh.lambda_handler({}, Context())

    assert response == {"refreshed_tickers": ["SPY"], "records_written": 2, "failures": []}
    assert "refresh_succeeded" in caplog.text
    assert "request-123" in caplog.text


def test_handler_surfaces_refresh_failure_and_logs_safe_fields(monkeypatch, caplog) -> None:
    monkeypatch.setattr(refresh, "build_refresh_service", lambda environment: FailingService())

    with caplog.at_level(logging.INFO), pytest.raises(RefreshFailedError):
        refresh.lambda_handler({}, Context())

    assert "refresh_failed" in caplog.text
    assert "SourceDataError" in caplog.text


def test_refresh_configuration_uses_allow_list_and_configured_ttl() -> None:
    configuration = RefreshConfiguration.from_environment(
        {"FIXTURE_TICKERS": "spy", "CACHE_TTL_SECONDS": "300"}
    )

    assert configuration.fixture_tickers == ("SPY",)
    assert configuration.cache_ttl_seconds == 300
