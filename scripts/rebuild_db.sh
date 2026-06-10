#!/bin/bash
set -e

# SAFETY: ScholarBridge development data must never be overwritten automatically.
# This script is destructive and requires explicit operator opt-in.
if [[ "${SCHOLARBRIDGE_ALLOW_DATA_MUTATION:-0}" != "1" ]]; then
  echo "Refusing to rebuild DB. Set SCHOLARBRIDGE_ALLOW_DATA_MUTATION=1 to proceed."
  exit 1
fi

rm -f instance/scholarbridge.db
uv run flask --app run.py init-db
uv run python scripts/import_people.py --allow-data-mutation
uv run python scripts/import_partners.py --allow-data-mutation
uv run flask --app run.py seed-committee-users --password DemoPass123! --allow-data-mutation
