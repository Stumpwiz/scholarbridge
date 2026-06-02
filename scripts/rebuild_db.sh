#!/bin/bash
set -e
rm -f instance/scholarbridge.db
uv run flask --app run.py init-db
uv run python scripts/import_people.py
uv run python scripts/import_partners.py
uv run flask --app run.py seed-committee-users --password DemoPass123!
