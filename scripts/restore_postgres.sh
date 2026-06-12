#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  restore_postgres.sh <backup.sql.gz> [env_file]

Environment variables (or env_file values):
  DB_NAME (default: scholarbridge)
  DB_USER (default: scholarbridge_app)
  DB_HOST (default: 127.0.0.1)
  DB_PORT (default: 5432)
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ -n "${2:-}" ]]; then
  # shellcheck disable=SC1090
  source "$2"
fi

DB_NAME="${DB_NAME:-scholarbridge}"
DB_USER="${DB_USER:-scholarbridge_app}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"

echo "Restoring into database: $DB_NAME on $DB_HOST:$DB_PORT"
echo "This command is destructive for existing rows in that database."
read -r -p "Type 'restore' to continue: " confirm
if [[ "$confirm" != "restore" ]]; then
  echo "Restore cancelled."
  exit 1
fi

gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
echo "Restore completed."
