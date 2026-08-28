#!/usr/bin/env bash
# Run the local, non-watch foundation checks that are available in the current scaffold.
# Later tasks add frontend, fixture, CDK, and documentation inputs; this script picks them
# up automatically once their conventional files exist.
set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"

run() {
  printf '\n==> %s\n' "$*"
  "$@"
}

skip() {
  printf '\n==> SKIP: %s\n' "$1"
}

if [[ -f frontend/package.json && -f frontend/package-lock.json ]]; then
  run npm --prefix frontend ci

  if grep -Eq '"format:check"[[:space:]]*:' frontend/package.json; then
    run npm --prefix frontend run format:check
  elif grep -Eq '"format"[[:space:]]*:[[:space:]]*"[^"[:cntrl:]]*(--check|--dry-run)' frontend/package.json; then
    run npm --prefix frontend run format
  else
    skip "frontend does not yet expose a non-mutating format-check command"
  fi

  run npm --prefix frontend run typecheck
  run npm --prefix frontend run build
else
  skip "frontend bootstrap and lock file are not available yet"
fi

if [[ -f backend/package.json && -f backend/package-lock.json ]]; then
  run npm --prefix backend ci
fi

run uv sync --directory backend
run uv run --directory backend ruff format --check .
run uv run --directory backend ruff check .
run uv run --directory backend mypy src

if [[ -d backend/tests ]] && compgen -G 'backend/tests/**/*.py' > /dev/null; then
  run uv run --directory backend pytest -q
else
  skip "backend tests are not available yet"
fi

if [[ -f backend/src/trader_insight/tools/validate_fixtures.py ]] && [[ -d contracts/market-data/v1/fixtures ]]; then
  run uv run --directory backend python -m trader_insight.tools.validate_fixtures
else
  skip "fixture validator or checked-in fixtures are not available yet"
fi

if [[ -f backend/cdk.json && -f backend/infra/app.py ]]; then
  run uv run --directory backend cdk synth --strict
else
  skip "CDK application is not available yet"
fi

if [[ -d backend/tests/docs ]] && compgen -G 'backend/tests/docs/*.py' > /dev/null; then
  run uv run --directory backend pytest -q tests/docs
else
  skip "documentation checks are not available yet"
fi
