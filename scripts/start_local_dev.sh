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
echo "URL: http://0.0.0.0:5000 (all interfaces)"
echo

exec uv run flask --app run.py run \
    --host 0.0.0.0 \
    --port 5000 \
    --debug