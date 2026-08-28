"""CDK resources for the isolated Trader Insight market-data foundation."""

from __future__ import annotations

from pathlib import Path

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_scheduler as scheduler
from constructs import Construct

from config import RefreshScheduleConfiguration


class TraderInsightFoundationStack(Stack):
    """Create only the cache, refresh function, and its Scheduler invocation path."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        schedule_configuration = RefreshScheduleConfiguration.from_environment()
        table = dynamodb.Table(
            self,
            "MarketData",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            stream=dynamodb.StreamViewType.NEW_IMAGE,
            removal_policy=RemovalPolicy.DESTROY,
        )

        log_group = logs.LogGroup(
            self,
            "RefreshOperationLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        refresh_role = iam.Role(
            self,
            "RefreshOperationExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege execution role for the scheduled mock refresh.",
        )
        refresh_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[log_group.log_group_arn + ":*"],
            )
        )
        refresh_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:TransactWriteItems"],
                resources=[table.table_arn],
            )
        )

        repository_root = Path(__file__).resolve().parents[3]
        refresh_function = lambda_.Function(
            self,
            "RefreshOperation",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="trader_insight.handlers.refresh.lambda_handler",
            code=lambda_.Code.from_asset(
                str(repository_root),
                exclude=[
                    ".git",
                    ".kiro",
                    "backend/.venv",
                    "backend/.hypothesis",
                    "backend/.mypy_cache",
                    "backend/.pytest_cache",
                    "backend/.ruff_cache",
                    "backend/tests",
                    "frontend/node_modules",
                    "frontend/dist",
                    "cdk.out",
                    "design_image.png",
                    "trader-insight-project-plan-for-kiro.md",
                ],
            ),
            role=refresh_role,
            timeout=Duration.seconds(30),
            environment={
                "PYTHONPATH": "/var/task/backend/src",
                "MARKET_DATA_TABLE_NAME": table.table_name,
                "FIXTURE_TICKERS": "SPY",
                "CACHE_TTL_SECONDS": "3600",
            },
            log_group=log_group,
        )

        scheduler_role = iam.Role(
            self,
            "RefreshScheduleExecutionRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
            description="Permits the declared Scheduler schedule to invoke the refresh Lambda.",
        )
        scheduler_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[refresh_function.function_arn],
            )
        )
        refresh_schedule = scheduler.CfnSchedule(
            self,
            "RefreshSchedule",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
            schedule_expression=schedule_configuration.rate_expression,
            target=scheduler.CfnSchedule.TargetProperty(
                arn=refresh_function.function_arn,
                role_arn=scheduler_role.role_arn,
            ),
        )
        refresh_function.add_permission(
            "AllowSchedulerInvoke",
            principal=iam.ServicePrincipal("scheduler.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_account=self.account,
            source_arn=refresh_schedule.attr_arn,
        )

        self.market_data_table = table
        self.refresh_function = refresh_function
