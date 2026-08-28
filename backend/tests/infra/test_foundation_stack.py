from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from aws_cdk import App
from aws_cdk.assertions import Match, Template

INFRA_DIRECTORY = Path(__file__).resolve().parents[2] / "infra"
if str(INFRA_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(INFRA_DIRECTORY))

from stacks.foundation_stack import TraderInsightFoundationStack  # noqa: E402


@pytest.fixture
def foundation_template(monkeypatch: pytest.MonkeyPatch) -> Template:
    """Build the CDK template locally without AWS credentials or deployment."""
    monkeypatch.delenv("REFRESH_INTERVAL_VALUE", raising=False)
    monkeypatch.delenv("REFRESH_INTERVAL_UNIT", raising=False)
    app = App()
    stack = TraderInsightFoundationStack(app, "TraderInsightFoundationStack")
    return Template.from_stack(stack)


def test_market_data_table_has_required_key_ttl_and_stream_configuration(
    foundation_template: Template,
) -> None:
    foundation_template.resource_count_is("AWS::DynamoDB::Table", 1)
    foundation_template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "AttributeDefinitions": [
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            "KeySchema": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "TimeToLiveSpecification": {"AttributeName": "ttl", "Enabled": True},
            "StreamSpecification": {"StreamViewType": "NEW_IMAGE"},
        },
    )


def test_refresh_lambda_and_scheduler_target_are_configured(
    foundation_template: Template,
) -> None:
    foundation_template.resource_count_is("AWS::Lambda::Function", 1)
    foundation_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "trader_insight.handlers.refresh.lambda_handler",
            "Role": Match.any_value(),
        },
    )
    foundation_template.resource_count_is("AWS::Scheduler::Schedule", 1)
    foundation_template.has_resource_properties(
        "AWS::Scheduler::Schedule",
        {
            "ScheduleExpression": "rate(1 minute)",
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "Target": {"Arn": Match.any_value(), "RoleArn": Match.any_value()},
        },
    )
    foundation_template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    {
                        "Action": "sts:AssumeRole",
                        "Effect": "Allow",
                        "Principal": {"Service": "scheduler.amazonaws.com"},
                    }
                ],
                "Version": "2012-10-17",
            }
        },
    )
    foundation_template.has_resource_properties(
        "AWS::Lambda::Permission",
        {
            "Action": "lambda:InvokeFunction",
            "Principal": "scheduler.amazonaws.com",
            "SourceAccount": Match.any_value(),
            "SourceArn": Match.any_value(),
        },
    )


def test_execution_roles_are_limited_to_required_log_table_and_invoke_actions(
    foundation_template: Template,
) -> None:
    policies = foundation_template.find_resources("AWS::IAM::Policy")
    assert len(policies) == 2

    permitted_actions = {
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "dynamodb:TransactWriteItems",
        "lambda:InvokeFunction",
    }
    observed_actions: set[str] = set()
    for policy in policies.values():
        document = policy["Properties"]["PolicyDocument"]
        statements = document["Statement"]
        assert isinstance(statements, list)
        for statement in statements:
            assert statement["Effect"] == "Allow"
            assert statement["Resource"] != "*"
            actions = statement["Action"]
            values = actions if isinstance(actions, list) else [actions]
            assert set(values).issubset(permitted_actions)
            observed_actions.update(values)

    assert observed_actions == permitted_actions


def test_stack_contains_only_the_foundation_resource_boundary(
    foundation_template: Template,
) -> None:
    resources: dict[str, dict[str, Any]] = foundation_template.to_json()["Resources"]
    resource_types = {resource["Type"] for resource in resources.values()}

    assert resource_types <= {
        "AWS::CDK::Metadata",
        "AWS::DynamoDB::Table",
        "AWS::IAM::Policy",
        "AWS::IAM::Role",
        "AWS::Lambda::Function",
        "AWS::Lambda::Permission",
        "AWS::Logs::LogGroup",
        "AWS::Scheduler::Schedule",
    }
    assert not any(
        deferred in resource_type
        for deferred in ("AppSync", "Bedrock", "Amplify", "CloudFront", "SageMaker")
        for resource_type in resource_types
    )
