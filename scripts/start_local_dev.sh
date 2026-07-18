#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== ScholarBridge Local Development ==="

# Verify virtual environment exists
if [[ ! -d .venv ]]; then
    echo "ERROR: .venv not found."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Display database in use
echo "DATABASE_URL=${DATABASE_URL:-"(from .env)"}"

# Ensure database schema is current
echo
echo "Running database migrations..."
uv run flask --app run.py db upgrade

echo
echo "Starting Flask development server..."
echo "URL: http://127.0.0.1:5000"
echo

exec uv run flask --app run.py run --debug