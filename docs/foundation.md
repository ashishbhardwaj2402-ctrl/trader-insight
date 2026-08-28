# Trader Insight foundation

Trader Insight is a single-user, desktop-only **advisory-only** options-insight foundation. It does not execute trades or provide investment advice. Market-data fixtures are deterministic, **synthetic development data**: they are not live market data, vendor payloads, recommendations, trade instructions, or a source for credentials.

## Repository ownership and dependency rules

The repository has five root boundaries:

| Area | Owns | Allowed dependencies | Prohibited dependencies |
| --- | --- | --- | --- |
| `contracts/` | Versioned JSON Schemas, fixture JSON, contract guidance | None of the application packages | Frontend/backend implementations, AWS SDKs, CDK, and vendor integrations |
| `frontend/` | Vite + React + TypeScript desktop-client bootstrap and future client code | Published or derived contract types | Python backend source, CDK, Lambda handlers, DynamoDB, and AWS implementation code |
| `backend/` | Domain models, adapters, handlers, tests, tooling, and CDK infrastructure | Contract semantics | Redefining contracts; frontend source imports |
| `docs/` | Architecture, setup, and operational guidance | Public repository artifacts | Secrets, local credentials, and environment-specific values |
| `scripts/` | Repeatable developer and verification commands | Public repository tooling | Secrets and deployment automation in local verification |

Dependencies flow toward the stable contract boundary: frontend and backend may consume contract semantics, but they must not import one another. `contracts/` remains implementation-neutral. Contract changes require explicit versioned review; backend code cannot redefine a contract. The fuller initial boundary rationale is in [scaffold-boundaries.md](scaffold-boundaries.md).

## Contracts and fixtures

The canonical v1 market-data contract is [`contracts/market-data/v1/market-data.schema.json`](../contracts/market-data/v1/market-data.schema.json). Its checked-in fixtures are in [`contracts/market-data/v1/fixtures/`](../contracts/market-data/v1/fixtures/), and the field, versioning, decimal, timestamp, option-type, and synthetic-fixture rules are in the [contract README](../contracts/market-data/v1/README.md).

Use `market-data/v1` as the normalized boundary between market-data sourcing, cache storage, and future consumers. Fixtures must be validated offline before adapter or test use. They contain no secrets, API keys, provider payloads, advice, live prices, or broker integration.

## Local commands

Run these commands from the repository root. They are non-watch verification commands unless noted otherwise, and an unsuccessful command exits nonzero.

| Purpose | Command | Notes |
| --- | --- | --- |
| Install frontend dependencies | `npm --prefix frontend ci` | Uses `frontend/package-lock.json`. |
| Format frontend | `npm --prefix frontend run format` | Writes formatting changes. |
| Type-check frontend | `npm --prefix frontend run typecheck` | TypeScript only; no watcher. |
| Build frontend bootstrap | `npm --prefix frontend run build` | Verifies the Vite boundary. |
| Manually inspect frontend | `npm --prefix frontend run dev` | Optional development server; not part of verification. |
| Install CDK CLI | `npm --prefix backend ci` | Installs the pinned backend-local CDK CLI. |
| Install backend dependencies | `uv sync --directory backend` | Python 3.12 project and locked dependencies. |
| Check backend formatting | `uv run --directory backend ruff format --check .` | Does not rewrite files. |
| Run backend static analysis | `uv run --directory backend ruff check .` | Offline static check. |
| Type-check backend | `uv run --directory backend mypy src` | Strict source type check. |
| Run offline backend tests | `uv run --directory backend pytest -q` | Includes unit, property, contract, infrastructure, integration-script, and documentation assertions. |
| Run documentation-content tests | `uv run --directory backend pytest -q tests/docs` | Offline assertions for this guide and contract boundary. |
| Validate fixtures | `uv run --directory backend python -m trader_insight.tools.validate_fixtures` | Validates every checked-in fixture without network, vendor, AWS account, or credentials. |
| Synthesize infrastructure | `uv run --directory backend cdk synth --strict` | Validates the CDK assembly only; it does not deploy. |
| Run aggregate local verification | `scripts/verify-foundation.sh` | Runs applicable non-watch checks and stops on the first failing command. |

`verify-foundation.sh` never deploys a CDK stack, starts the frontend server, or invokes the deployed smoke harness.

## Mock adapter and future vendor replacement

`backend/src/trader_insight/adapters/mock_market_data_adapter.py` is the sole source-facing implementation in this foundation. The refresh service obtains normalized snapshots and option records only through the `MarketDataSource` interface; cache consumers never receive raw provider responses.

When a market-data vendor is selected, replace the implementation **at the adapter boundary only**: add or replace the adapter implementation and select it with non-secret configuration. Do not change cache consumers, cache-key formats, handlers, frontend code, or shared contracts merely to accommodate a vendor. A vendor need for new normalized fields requires an explicit versioned contract change before it crosses the adapter boundary.

The mock source needs no secret configuration. Foundation configuration is non-secret and may include `REFRESH_INTERVAL_VALUE`, `REFRESH_INTERVAL_UNIT`, `CACHE_TTL_SECONDS`, and `FIXTURE_TICKERS`; use local `.env.example` templates where needed, while actual `.env` files remain ignored. A future credential identifier may be configuration, but its secret value must never be committed, placed in fixtures, echoed by scripts, or exposed to frontend variables.

## Cache, TTL, stream, and refresh schedule

`MarketData` is the normalized DynamoDB cache. Every record has `pk`, `sk`, `entity_type`, `schema_version`, `data`, `updated_at`, and `ttl`. The stable key patterns are:

- Snapshot: `pk = TICKER#<UPPERCASE_TICKER>`, `sk = PRICE#LATEST`.
- Option: `pk = TICKER#<UPPERCASE_TICKER>`, `sk = OPTION#<CALL|PUT>#<two-decimal strike>#<YYYY-MM-DD expiry>`.

A write with the same `pk` and `sk` replaces the normalized payload and `updated_at`. `ttl` is a required, positive Unix-epoch-seconds expiration timestamp. DynamoDB TTL deletion is asynchronous retention cleanup, not a freshness timer; consumers that need freshness must compare `updated_at` or `ttl` themselves.

The cache stream uses `NEW_IMAGE`. Cache creates and replacements emit a record containing keys and the post-write image. A native TTL deletion emits DynamoDB's `REMOVE` event and has no new image. This foundation creates no stream consumer, AppSync resource, AI component, scoring component, or dashboard component.

The EventBridge Scheduler default is `rate(1 minute)`. Configure only a positive whole-number `REFRESH_INTERVAL_VALUE` and `REFRESH_INTERVAL_UNIT` of `minute`/`minutes`, `hour`/`hours`, or `day`/`days`. Seconds and arbitrary cron expressions are rejected. Changing this cadence does not change a shared contract.

## Confirmation-gated deployed smoke harness

[`scripts/run-deployed-foundation-smoke.sh`](../scripts/run-deployed-foundation-smoke.sh) is an opt-in, deployed-only harness and is excluded from aggregate local verification. Do not run it without explicit user confirmation and an already approved isolated deployment target. Before its first AWS API request, it requires both `FOUNDATION_SMOKE_CONFIRM=RUN_DEPLOYED_FOUNDATION_SMOKE` and `FOUNDATION_SMOKE_ISOLATED_TARGET=APPROVED_ISOLATED_STACK`, plus the required stack, table, function, stream, ticker, and pre-existing TTL-record identifiers.

The harness does not run `cdk deploy` or create, update, or delete AWS resources. It confirms an existing stable stack and active `NEW_IMAGE` stream, invokes the already deployed refresh Lambda once, verifies snapshot and option cache records, and polls within fixed limits for create/replace stream images and a native DynamoDB TTL `REMOVE` event. TTL cleanup remains asynchronous, so the bounded poll may require a later, separately confirmed retry. The pre-existing TTL record must already exist and already be eligible for native expiration; the harness never writes it.

## Deferred capabilities

The following are explicitly deferred and are not implemented by this foundation: AppSync, an AI engine, Amazon Bedrock, AgentCore, decision scoring, dashboard feature implementation and workflows, option analysis, live market-data vendor integration, authentication, multi-user behavior, and trade execution. No component sends broker orders or recommends execution.
