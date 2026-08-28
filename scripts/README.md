# Scripts boundary

Reserved for repeatable local developer and verification commands.

Scripts may coordinate public repository tooling, but must not embed secrets, environment-specific values, application behavior, or deployment actions in this scaffold.

## Opt-in deployed foundation smoke test

`scripts/run-deployed-foundation-smoke.sh` is intentionally excluded from `scripts/verify-foundation.sh` and from offline test execution. It is a separately invoked, cost-aware check for an already deployed, approved, isolated Trader Insight foundation stack. It never deploys, creates, updates, or deletes AWS resources. The only application mutation is one synchronous invocation of the existing refresh Lambda, which writes the stack's existing market-data cache records.

Before its first AWS request, the operator must set both explicit acknowledgements and all target identifiers:

```bash
export FOUNDATION_SMOKE_CONFIRM=RUN_DEPLOYED_FOUNDATION_SMOKE
export FOUNDATION_SMOKE_ISOLATED_TARGET=APPROVED_ISOLATED_STACK
export FOUNDATION_SMOKE_STACK_NAME=<existing-isolated-stack-name>
export FOUNDATION_SMOKE_TABLE_NAME=<existing-market-data-table-name>
export FOUNDATION_SMOKE_FUNCTION_NAME=<existing-refresh-function-name>
export FOUNDATION_SMOKE_STREAM_ARN=<existing-market-data-stream-arn>
export FOUNDATION_SMOKE_TICKER=SPY
export FOUNDATION_SMOKE_TTL_PK=<dedicated-pre-existing-ttl-record-pk>
export FOUNDATION_SMOKE_TTL_SK=<dedicated-pre-existing-ttl-record-sk>
./scripts/run-deployed-foundation-smoke.sh
```

The stack name must resolve to a stable deployed stack, and the supplied table and stream ARN must describe the same active `NEW_IMAGE` stream. The target must be a disposable isolated environment, not a shared or production environment. The harness requires AWS credentials only when the operator explicitly invokes it.

The test invokes the already deployed refresh function once, then performs consistent reads to check the `PRICE#LATEST` snapshot and at least one `OPTION#...` cache record for the configured ticker. It verifies cache metadata (`updated_at`, positive `ttl`, entity type, and schema version) plus key representative normalized fields. It captures stream iterators before the invocation and confirms matching `INSERT` or `MODIFY` records carry required new images for both snapshot and option records.

TTL cleanup is asynchronous. Before running the harness, prepare a dedicated, pre-existing cache record in the isolated target that has its `ttl` already eligible for native DynamoDB expiration. Do not use the refreshed ticker's records for this target. The harness neither creates nor changes that record; it polls the existing stream for the matching native `REMOVE` event, requiring no new image and the DynamoDB service identity. If the event is not observed within the bounded default window of 12 polls at five seconds each, the command fails rather than polling indefinitely. The optional `FOUNDATION_SMOKE_MAX_POLLS`, `FOUNDATION_SMOKE_POLL_SECONDS`, `FOUNDATION_SMOKE_MAX_SHARDS`, and `FOUNDATION_SMOKE_MAX_RECORDS` values may only reduce or stay within the documented limits of 12, 10 seconds, 4, and 25 respectively.

This harness intentionally has no deployment or resource-provisioning behavior. Use the offline static test below to validate its safety properties without AWS access:

```bash
uv run --directory backend pytest -q tests/integration/test_deployed_foundation_smoke_script.py
bash -n scripts/run-deployed-foundation-smoke.sh
```
