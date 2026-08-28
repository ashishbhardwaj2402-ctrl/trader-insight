"""Entry point for strict local synthesis of the Trader Insight foundation stack."""

from aws_cdk import App

from stacks.foundation_stack import TraderInsightFoundationStack

app = App()
TraderInsightFoundationStack(app, "TraderInsightFoundationStack")
app.synth()
