#!/usr/bin/env bash
# Opt-in verification for an existing, isolated Trader Insight foundation deployment.
# This script never deploys, creates, updates, or deletes AWS resources.
set -euo pipefail

readonly CONFIRMATION_VALUE="RUN_DEPLOYED_FOUNDATION_SMOKE"
readonly ISOLATED_TARGET_VALUE="APPROVED_ISOLATED_STACK"
readonly DEFAULT_MAX_POLLS=12
readonly DEFAULT_POLL_SECONDS=5
readonly DEFAULT_MAX_SHARDS=4
readonly DEFAULT_MAX_RECORDS=25

require_value() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$name" >&2
    exit 2
  fi
}

require_exact_value() {
  local name="$1"
  local expected="$2"
  require_value "$name"
  if [[ "${!name}" != "$expected" ]]; then
    printf '%s must equal %q. No AWS request was made.\n' "$name" "$expected" >&2
    exit 2
  fi
}

bounded_positive_integer() {
  local name="$1"
  local maximum="$2"
  local value="${!name}"
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]] || (( value > maximum )); then
    printf '%s must be a positive integer no greater than %s.\n' "$name" "$maximum" >&2
    exit 2
  fi
}

require_exact_value FOUNDATION_SMOKE_CONFIRM "$CONFIRMATION_VALUE"
require_exact_value FOUNDATION_SMOKE_ISOLATED_TARGET "$ISOLATED_TARGET_VALUE"
for required_name in \
  FOUNDATION_SMOKE_STACK_NAME \
  FOUNDATION_SMOKE_TABLE_NAME \
  FOUNDATION_SMOKE_FUNCTION_NAME \
  FOUNDATION_SMOKE_STREAM_ARN \
  FOUNDATION_SMOKE_TICKER \
  FOUNDATION_SMOKE_TTL_PK \
  FOUNDATION_SMOKE_TTL_SK; do
  require_value "$required_name"
done

: "${FOUNDATION_SMOKE_MAX_POLLS:=$DEFAULT_MAX_POLLS}"
: "${FOUNDATION_SMOKE_POLL_SECONDS:=$DEFAULT_POLL_SECONDS}"
: "${FOUNDATION_SMOKE_MAX_SHARDS:=$DEFAULT_MAX_SHARDS}"
: "${FOUNDATION_SMOKE_MAX_RECORDS:=$DEFAULT_MAX_RECORDS}"
bounded_positive_integer FOUNDATION_SMOKE_MAX_POLLS "$DEFAULT_MAX_POLLS"
bounded_positive_integer FOUNDATION_SMOKE_POLL_SECONDS 10
bounded_positive_integer FOUNDATION_SMOKE_MAX_SHARDS "$DEFAULT_MAX_SHARDS"
bounded_positive_integer FOUNDATION_SMOKE_MAX_RECORDS "$DEFAULT_MAX_RECORDS"

if [[ "$FOUNDATION_SMOKE_TTL_PK" == "TICKER#${FOUNDATION_SMOKE_TICKER}" ]]; then
  printf 'FOUNDATION_SMOKE_TTL_PK must identify a dedicated pre-existing TTL smoke record, not the refreshed ticker.\n' >&2
  exit 2
fi

if ! command -v aws >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  printf 'The AWS CLI and Python 3 are required. No AWS request was made.\n' >&2
  exit 2
fi

export AWS_PAGER=""
export AWS_RETRY_MODE="standard"
export AWS_MAX_ATTEMPTS=2

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/trader-insight-foundation-smoke.XXXXXX")"
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT

stack_description="$work_dir/stack.json"
table_description="$work_dir/table.json"
stream_description="$work_dir/stream.json"
invoke_metadata="$work_dir/invoke.json"
invoke_payload="$work_dir/invoke-payload.json"
snapshot_item="$work_dir/snapshot.json"
option_items="$work_dir/options.json"
ttl_item="$work_dir/ttl.json"
stream_records="$work_dir/stream-records.ndjson"
: > "$stream_records"

# All confirmation and target gates above complete before this first AWS API request.
aws cloudformation describe-stacks \
  --stack-name "$FOUNDATION_SMOKE_STACK_NAME" \
  --output json > "$stack_description"
python3 - "$stack_description" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
stacks = payload.get("Stacks", [])
status = stacks[0].get("StackStatus") if stacks else None
if status not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
    raise SystemExit(f"deployed stack must be stable; observed status: {status!r}")
PY

aws dynamodb describe-table \
  --table-name "$FOUNDATION_SMOKE_TABLE_NAME" \
  --output json > "$table_description"
python3 - "$table_description" "$FOUNDATION_SMOKE_STREAM_ARN" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
table = payload.get("Table", {})
stream = table.get("StreamSpecification", {})
if table.get("TableStatus") != "ACTIVE":
    raise SystemExit(f"table is not ACTIVE: {table.get('TableStatus')!r}")
if stream.get("StreamEnabled") is not True or stream.get("StreamViewType") != "NEW_IMAGE":
    raise SystemExit("table must have an enabled NEW_IMAGE stream")
if table.get("LatestStreamArn") != sys.argv[2]:
    raise SystemExit("FOUNDATION_SMOKE_STREAM_ARN does not match the deployed table stream")
PY

aws dynamodbstreams describe-stream \
  --stream-arn "$FOUNDATION_SMOKE_STREAM_ARN" \
  --limit "$FOUNDATION_SMOKE_MAX_SHARDS" \
  --output json > "$stream_description"
mapfile -t shard_ids < <(python3 - "$stream_description" "$FOUNDATION_SMOKE_MAX_SHARDS" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
description = payload.get("StreamDescription", {})
shards = description.get("Shards", [])
limit = int(sys.argv[2])
if description.get("StreamStatus") != "ENABLED":
    raise SystemExit(f"stream is not ENABLED: {description.get('StreamStatus')!r}")
if description.get("StreamViewType") != "NEW_IMAGE":
    raise SystemExit("stream must use NEW_IMAGE")
if description.get("LastEvaluatedShardId") is not None or not 1 <= len(shards) <= limit:
    raise SystemExit("stream shard count exceeds the bounded smoke-test limit")
for shard in shards:
    print(shard["ShardId"])
PY
)

if (( ${#shard_ids[@]} == 0 )); then
  printf 'The deployed stream has no readable shards.\n' >&2
  exit 1
fi

declare -A shard_iterators
for shard_id in "${shard_ids[@]}"; do
  iterator_file="$work_dir/iterator-${shard_id//[^A-Za-z0-9]/_}.json"
  aws dynamodbstreams get-shard-iterator \
    --stream-arn "$FOUNDATION_SMOKE_STREAM_ARN" \
    --shard-id "$shard_id" \
    --shard-iterator-type LATEST \
    --output json > "$iterator_file"
  shard_iterators["$shard_id"]="$(python3 - "$iterator_file" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["ShardIterator"])
PY
)"
done

# The sole mutating application action: invoke the already deployed refresh function once.
# It does not create or modify AWS resources and is intentionally limited to the isolated target.
aws lambda invoke \
  --function-name "$FOUNDATION_SMOKE_FUNCTION_NAME" \
  --invocation-type RequestResponse \
  --cli-binary-format raw-in-base64-out \
  --payload '{}' \
  --output json "$invoke_payload" > "$invoke_metadata"
python3 - "$invoke_metadata" <<'PY'
import json
import sys

metadata = json.load(open(sys.argv[1]))
if metadata.get("StatusCode") != 200 or metadata.get("FunctionError"):
    raise SystemExit(f"refresh invocation failed: {metadata}")
PY

aws dynamodb get-item \
  --table-name "$FOUNDATION_SMOKE_TABLE_NAME" \
  --consistent-read \
  --key "{\"pk\":{\"S\":\"TICKER#${FOUNDATION_SMOKE_TICKER}\"},\"sk\":{\"S\":\"PRICE#LATEST\"}}" \
  --output json > "$snapshot_item"
aws dynamodb query \
  --table-name "$FOUNDATION_SMOKE_TABLE_NAME" \
  --consistent-read \
  --key-condition-expression "pk = :pk AND begins_with(sk, :option_prefix)" \
  --expression-attribute-values "{\":pk\":{\"S\":\"TICKER#${FOUNDATION_SMOKE_TICKER}\"},\":option_prefix\":{\"S\":\"OPTION#\"}}" \
  --limit "$FOUNDATION_SMOKE_MAX_RECORDS" \
  --output json > "$option_items"
python3 - "$snapshot_item" "$option_items" "$FOUNDATION_SMOKE_TICKER" <<'PY'
import json
import sys

snapshot = json.load(open(sys.argv[1])).get("Item")
options = json.load(open(sys.argv[2])).get("Items", [])
ticker = sys.argv[3]

def require_string(item, name):
    value = item.get(name, {}).get("S")
    if not value:
        raise SystemExit(f"cache record is missing string {name!r}")
    return value

def require_record_metadata(item):
    require_string(item, "entity_type")
    require_string(item, "schema_version")
    require_string(item, "updated_at")
    ttl = item.get("ttl", {}).get("N")
    if ttl is None or int(ttl) <= 0:
        raise SystemExit("cache record is missing a positive ttl")

if not snapshot:
    raise SystemExit("refresh did not produce the required snapshot record")
if require_string(snapshot, "pk") != f"TICKER#{ticker}" or require_string(snapshot, "sk") != "PRICE#LATEST":
    raise SystemExit("snapshot record has an unexpected cache key")
require_record_metadata(snapshot)
snapshot_data = snapshot.get("data", {}).get("M", {})
for field in ("ticker", "price", "trend", "momentum", "expected_move"):
    if field not in snapshot_data:
        raise SystemExit(f"snapshot data is missing {field!r}")

if not options:
    raise SystemExit("refresh did not produce any option cache records")
for option in options:
    if require_string(option, "pk") != f"TICKER#{ticker}" or not require_string(option, "sk").startswith("OPTION#"):
        raise SystemExit("option record has an unexpected cache key")
    require_record_metadata(option)
    option_data = option.get("data", {}).get("M", {})
    for field in ("ticker", "strike", "option_type", "expiry", "bid", "ask"):
        if field not in option_data:
            raise SystemExit(f"option data is missing {field!r}")
PY

# The supplied TTL record must already exist in the isolated deployment and already be eligible.
# The harness never writes it, so DynamoDB remains the sole deletion source.
aws dynamodb get-item \
  --table-name "$FOUNDATION_SMOKE_TABLE_NAME" \
  --consistent-read \
  --key "{\"pk\":{\"S\":\"${FOUNDATION_SMOKE_TTL_PK}\"},\"sk\":{\"S\":\"${FOUNDATION_SMOKE_TTL_SK}\"}}" \
  --output json > "$ttl_item"
python3 - "$ttl_item" "$FOUNDATION_SMOKE_TTL_PK" "$FOUNDATION_SMOKE_TTL_SK" <<'PY'
import json
import sys
import time

item = json.load(open(sys.argv[1])).get("Item")
if not item:
    raise SystemExit("pre-existing TTL smoke record was not found; seed it before running this harness")
if item.get("pk", {}).get("S") != sys.argv[2] or item.get("sk", {}).get("S") != sys.argv[3]:
    raise SystemExit("TTL smoke record key does not match the supplied target")
ttl = item.get("ttl", {}).get("N")
if ttl is None or int(ttl) > int(time.time()):
    raise SystemExit("TTL smoke record must already be eligible for native DynamoDB expiration")
PY

stream_requirements_met=false
for ((poll = 1; poll <= FOUNDATION_SMOKE_MAX_POLLS; poll++)); do
  for shard_id in "${shard_ids[@]}"; do
    records_file="$work_dir/records-${poll}-${shard_id//[^A-Za-z0-9]/_}.json"
    aws dynamodbstreams get-records \
      --shard-iterator "${shard_iterators[$shard_id]}" \
      --limit "$FOUNDATION_SMOKE_MAX_RECORDS" \
      --output json > "$records_file"
    python3 - "$records_file" >> "$stream_records" <<'PY'
import json
import sys
for record in json.load(open(sys.argv[1])).get("Records", []):
    print(json.dumps(record, separators=(",", ":")))
PY
    shard_iterators["$shard_id"]="$(python3 - "$records_file" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1])).get("NextShardIterator", ""))
PY
)"
  done

  if python3 - "$stream_records" "$FOUNDATION_SMOKE_TICKER" "$FOUNDATION_SMOKE_TTL_PK" "$FOUNDATION_SMOKE_TTL_SK" <<'PY'
import json
import sys

path, ticker, ttl_pk, ttl_sk = sys.argv[1:]
snapshot_image = False
option_image = False
ttl_remove = False
with open(path) as records:
    for line in records:
        record = json.loads(line)
        image = record.get("dynamodb", {}).get("NewImage", {})
        keys = record.get("dynamodb", {}).get("Keys", {})
        pk = keys.get("pk", {}).get("S")
        sk = keys.get("sk", {}).get("S")
        if record.get("eventName") in {"INSERT", "MODIFY"} and pk == f"TICKER#{ticker}":
            if sk == "PRICE#LATEST" and {"pk", "sk", "updated_at", "ttl", "data"} <= image.keys():
                snapshot_image = True
            if sk and sk.startswith("OPTION#") and {"pk", "sk", "updated_at", "ttl", "data"} <= image.keys():
                option_image = True
        identity = record.get("userIdentity", {})
        if (
            record.get("eventName") == "REMOVE"
            and pk == ttl_pk
            and sk == ttl_sk
            and not image
            and identity.get("type") == "Service"
            and identity.get("principalId") == "dynamodb.amazonaws.com"
        ):
            ttl_remove = True
if snapshot_image and option_image and ttl_remove:
    raise SystemExit(0)
raise SystemExit(1)
PY
  then
    stream_requirements_met=true
    break
  fi

  if (( poll < FOUNDATION_SMOKE_MAX_POLLS )); then
    sleep "$FOUNDATION_SMOKE_POLL_SECONDS"
  fi
done

if [[ "$stream_requirements_met" != true ]]; then
  printf 'Did not observe all required stream events within %ss. TTL cleanup is asynchronous; inspect the isolated target and retry only after confirming the pre-existing TTL record remains appropriate.\n' \
    "$((FOUNDATION_SMOKE_MAX_POLLS * FOUNDATION_SMOKE_POLL_SECONDS))" >&2
  exit 1
fi

printf 'Deployed foundation smoke test passed for isolated stack %s.\n' "$FOUNDATION_SMOKE_STACK_NAME"
