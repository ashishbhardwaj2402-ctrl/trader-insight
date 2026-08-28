from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SMOKE_SCRIPT = REPOSITORY_ROOT / "scripts" / "run-deployed-foundation-smoke.sh"
AGGREGATE_VERIFIER = REPOSITORY_ROOT / "scripts" / "verify-foundation.sh"


def test_deployed_smoke_script_is_explicitly_confirmed_bounded_and_non_deploying() -> None:
    script = SMOKE_SCRIPT.read_text(encoding="utf-8")
    normalized = script.lower()

    assert 'readonly confirmation_value="run_deployed_foundation_smoke"' in normalized
    assert 'readonly isolated_target_value="approved_isolated_stack"' in normalized
    assert "require_exact_value foundation_smoke_confirm" in normalized
    assert "require_exact_value foundation_smoke_isolated_target" in normalized
    assert "foundation_smoke_stack_name" in normalized
    assert "foundation_smoke_ttl_pk" in normalized
    assert "foundation_smoke_ttl_sk" in normalized
    assert "default_max_polls=12" in normalized
    assert "default_max_shards=4" in normalized
    assert "default_max_records=25" in normalized
    assert "aws cloudformation describe-stacks" in normalized
    assert "aws lambda invoke" in normalized
    assert "aws dynamodb get-item" in normalized
    assert "aws dynamodb query" in normalized
    assert "aws dynamodbstreams get-records" in normalized
    assert "new_image" in normalized
    assert 'record.get("eventname") == "remove"' in normalized
    assert 'identity.get("principalid") == "dynamodb.amazonaws.com"' in normalized

    forbidden_commands = (
        "cdk deploy",
        "aws cloudformation create-stack",
        "aws cloudformation update-stack",
        "aws dynamodb create-table",
        "aws dynamodb put-item",
        "aws dynamodb update-item",
        "aws dynamodb delete-item",
    )
    assert not any(command in normalized for command in forbidden_commands)

    first_aws_call = script.index("aws cloudformation describe-stacks")
    assert script.index("require_exact_value FOUNDATION_SMOKE_CONFIRM") < first_aws_call
    assert script.index("require_exact_value FOUNDATION_SMOKE_ISOLATED_TARGET") < first_aws_call


def test_aggregate_verifier_does_not_run_the_deployed_smoke_harness() -> None:
    verifier = AGGREGATE_VERIFIER.read_text(encoding="utf-8")

    assert "run-deployed-foundation-smoke.sh" not in verifier
    assert "FOUNDATION_SMOKE_" not in verifier
