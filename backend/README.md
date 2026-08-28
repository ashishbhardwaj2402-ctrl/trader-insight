# Backend boundary

Reserved for serverless domain code, market-data adapters, handlers, backend tests, tooling, and infrastructure definitions.

Backend code may consume the versioned contract semantics, but must not redefine contracts.

## Local infrastructure tooling

The official AWS CDK CLI is pinned locally in `package.json` and locked in `package-lock.json` to match `aws-cdk-lib==2.177.0`. Run `npm --prefix backend ci` once after checkout, then use `uv run --directory backend cdk synth --strict`. The Python `cdk` entry point delegates only to that backend-local CLI installation, keeping the documented `uv run` validation command portable without a global CDK installation.
