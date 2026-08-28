import pathlib

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[3]
FOUNDATION_GUIDE = REPOSITORY_ROOT / "docs" / "foundation.md"
CONTRACT_GUIDE = REPOSITORY_ROOT / "contracts" / "market-data" / "v1" / "README.md"


def test_foundation_guide_preserves_repository_contract_and_adapter_boundaries() -> None:
    guide = FOUNDATION_GUIDE.read_text(encoding="utf-8")

    required_statements = (
        "`contracts/`",
        "`frontend/`",
        "`backend/`",
        "`docs/`",
        "`scripts/`",
        "frontend and backend may consume contract semantics, but they must not import one another",
        "cannot redefine a contract",
        "contracts/market-data/v1/market-data.schema.json",
        "contracts/market-data/v1/fixtures/",
        "adapter boundary only",
        "cache consumers never receive raw provider responses",
        "explicit versioned contract change",
    )

    for statement in required_statements:
        assert statement in guide


def test_foundation_guide_preserves_local_commands_cache_and_safety_statements() -> None:
    guide = FOUNDATION_GUIDE.read_text(encoding="utf-8")

    required_statements = (
        "npm --prefix frontend ci",
        "npm --prefix frontend run format",
        "npm --prefix frontend run typecheck",
        "npm --prefix frontend run build",
        "npm --prefix backend ci",
        "uv sync --directory backend",
        "uv run --directory backend ruff format --check .",
        "uv run --directory backend ruff check .",
        "uv run --directory backend mypy src",
        "uv run --directory backend pytest -q",
        "python -m trader_insight.tools.validate_fixtures",
        "uv run --directory backend cdk synth --strict",
        "scripts/verify-foundation.sh",
        "PRICE#LATEST",
        "OPTION#<CALL|PUT>#<two-decimal strike>#<YYYY-MM-DD expiry>",
        "Unix-epoch-seconds",
        "DynamoDB TTL deletion is asynchronous retention cleanup, not a freshness timer",
        "NEW_IMAGE",
        "DynamoDB's `REMOVE` event",
        "rate(1 minute)",
        "minute`/`minutes`, `hour`/`hours`, or `day`/`days",
        "Seconds and arbitrary cron expressions are rejected",
        "REFRESH_INTERVAL_VALUE",
        "REFRESH_INTERVAL_UNIT",
        "CACHE_TTL_SECONDS",
        "FIXTURE_TICKERS",
        "never be committed, placed in fixtures, echoed by scripts, or exposed to "
        "frontend variables",
        "advisory-only",
        "synthetic development data",
    )

    for statement in required_statements:
        assert statement in guide


def test_foundation_guide_preserves_deployed_smoke_gates_and_deferred_scope() -> None:
    guide = FOUNDATION_GUIDE.read_text(encoding="utf-8")

    required_statements = (
        "excluded from aggregate local verification",
        "explicit user confirmation",
        "approved isolated deployment target",
        "FOUNDATION_SMOKE_CONFIRM=RUN_DEPLOYED_FOUNDATION_SMOKE",
        "FOUNDATION_SMOKE_ISOLATED_TARGET=APPROVED_ISOLATED_STACK",
        "does not run `cdk deploy` or create, update, or delete AWS resources",
        "invokes the already deployed refresh Lambda once",
        "polls within fixed limits",
        "pre-existing TTL record must already exist and already be eligible",
        "AppSync",
        "AI engine",
        "Amazon Bedrock",
        "AgentCore",
        "decision scoring",
        "dashboard feature implementation and workflows",
        "option analysis",
        "live market-data vendor integration",
        "authentication",
        "multi-user behavior",
        "trade execution",
    )

    for statement in required_statements:
        assert statement in guide


def test_contract_guide_links_vendor_replacement_to_the_adapter_boundary() -> None:
    contract_guide = CONTRACT_GUIDE.read_text(encoding="utf-8")

    assert "Adapter replacement boundary" in contract_guide
    assert "adapter boundary only" in contract_guide
    assert "versioned contract change" in contract_guide
