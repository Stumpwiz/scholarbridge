#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

source .venv/bin/activate

echo "=== Git Status ==="
git status --short

echo
echo "=== Running Tests ==="
uv run pytest

echo
echo "=== Whitespace Check ==="
git diff --check

echo
echo "=== Starting Development Server ==="
uv run flask --app run.py run --debug