#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

source .venv/bin/activate

echo "Running ScholarBridge test suite..."
uv run pytest

echo
echo "Checking whitespace..."
git diff --check