# Trader Insight Market Data Contract v1

`market-data.schema.json` is the canonical, vendor-neutral JSON Schema for `market-data/v1`. It defines `UnderlyingMarketSnapshot`, `OptionChainRecord`, and the aggregate `MarketDataFixture`. Fixture files in `fixtures/` are checked-in contract examples, not source-provider responses.

## Versioning

Every snapshot, option record, and fixture has `schema_version: "market-data/v1"`. Changes that narrow validation, rename/remove a field, or alter a field's meaning require a new versioned contract directory. Additive changes also require explicit contract review. Backend and frontend implementations may consume this version but must not redefine it.

## Option identities and types

Each `OptionChainRecord` requires all selection fields: `ticker`, `strike`, `option_type`, and `expiry`. Supported `option_type` values are exactly `CALL` and `PUT`. Tickers are uppercase symbols. Every fixture must contain at least one snapshot and at least one option record, and every option record ticker must match a ticker in that fixture's snapshots. This last cross-array equality rule is a semantic fixture-validator rule because portable JSON Schema cannot compare arbitrary values in separate arrays.

## Numeric and timestamp conventions

JSON numbers represent monetary amounts and decimal market metrics at the contract edge. Consumers that construct cache keys or persist decimal values should convert numbers safely to decimal types rather than use binary floating-point string formatting. Prices, strikes, expected moves, implied-volatility metrics, ratios, Greeks, open interest, and volume follow the field bounds in the schema. `ask` must be greater than or equal to `bid`; this semantic comparison is enforced by the fixture validator for the same portability reason.

Timestamps use UTC RFC 3339 / ISO 8601 strings with a `Z` suffix, for example `2025-05-22T14:30:00Z`. Expiries are ISO calendar dates (`YYYY-MM-DD`).

## Synthetic-fixture policy

Fixtures are deterministic synthetic development data: repeated loads return the same values and embedded timestamps. They must contain no vendor payloads, credentials, API keys, live data, investment advice, recommendations, trade instructions, or broker integration. Keep each fixture at 24 option records or fewer so one snapshot plus its options fits the foundation's 25-item cache transaction limit. `fixtures/spy.json` has one `SPY` snapshot and eight matching option records.

Validate every checked-in fixture offline against this schema and the documented semantic rules before it is used by an adapter or test suite. No network access, market-data account, or AWS credential is needed.

## Adapter replacement boundary

The mock adapter at `backend/src/trader_insight/adapters/mock_market_data_adapter.py` is the sole source-facing implementation for this contract. When a vendor is selected, replace the integration at the **adapter boundary only** and select it with non-secret configuration. Cache consumers, cache-key formats, handlers, frontend code, and this normalized contract remain unchanged. If a vendor needs new normalized fields, introduce them through an explicit versioned contract change rather than leaking provider data beyond the adapter. See [the foundation guide](../../../docs/foundation.md) for repository boundaries, cache semantics, local commands, and the confirmation-gated deployed smoke harness.
