#!/usr/bin/env bash
# Runs the same checks as CI (.github/workflows/ci.yml). Run from anywhere: ./scripts/check.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

echo "== backend: lint =="
cd "$root/backend"
py=".venv/bin"
[ -x "$py/pytest" ] || py="$(dirname "$(command -v python3)")"
"$py/ruff" check .
"$py/ruff" format --check .

echo "== backend: tests =="
"$py/pytest" -q

echo "== mobile: typecheck =="
cd "$root/mobile"
npm run -s typecheck

echo "== mobile: tests =="
npm test -s

echo "All checks passed."
