#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Copy the ScholarBridge production PostgreSQL database to local development.

Usage:
  SCHOLARBRIDGE_PROD_SSH_HOST=<host> scripts/copy_production_db_to_local.sh [--yes]

Required environment:
  SCHOLARBRIDGE_PROD_SSH_HOST  Production EC2 hostname or IP address.

Optional environment:
  SCHOLARBRIDGE_PROD_SSH_USER  SSH user (default: ubuntu)
  SCHOLARBRIDGE_PROD_SSH_PORT  SSH port (default: 22)
  PROD_DB_NAME                 Remote database (default: scholarbridge)
  LOCAL_DB_HOST                Local host (default: localhost; loopback only)
  LOCAL_DB_PORT                Local port (default: 5432)
  LOCAL_DB_NAME                Local database (default: scholarbridge)
  LOCAL_DB_USER                Local user (default: scholarbridge)
  PGPASSWORD                   Local database password, if needed

The SSH user must be able to run `sudo -u postgres pg_dump` without a password.
The local user must own (or be able to replace) the public schema. The script
does not write the production dump into the repository.
USAGE
}

assume_yes=0
case "${1:-}" in
  --yes) assume_yes=1 ;;
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
esac

for command_name in ssh pg_restore psql; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name" >&2
    exit 1
  fi
done

prod_ssh_host=${SCHOLARBRIDGE_PROD_SSH_HOST:?SCHOLARBRIDGE_PROD_SSH_HOST is required}
prod_ssh_user=${SCHOLARBRIDGE_PROD_SSH_USER:-ubuntu}
prod_ssh_port=${SCHOLARBRIDGE_PROD_SSH_PORT:-22}
prod_db_name=${PROD_DB_NAME:-scholarbridge}

local_db_host=${LOCAL_DB_HOST:-localhost}
local_db_port=${LOCAL_DB_PORT:-5432}
local_db_name=${LOCAL_DB_NAME:-scholarbridge}
local_db_user=${LOCAL_DB_USER:-scholarbridge}

case "$local_db_host" in
  localhost|127.0.0.1|::1) ;;
  *)
    echo "Refusing destructive restore to non-loopback host: $local_db_host" >&2
    exit 1
    ;;
esac

identifier_pattern='^[A-Za-z_][A-Za-z0-9_]*$'
for database_name in "$prod_db_name" "$local_db_name"; do
  if [[ ! "$database_name" =~ $identifier_pattern ]]; then
    echo "Invalid database name: $database_name" >&2
    exit 1
  fi
done

if [[ ! "$prod_ssh_port" =~ ^[0-9]+$ || ! "$local_db_port" =~ ^[0-9]+$ ]]; then
  echo "SSH and database ports must be numeric." >&2
  exit 1
fi

echo "Source:      ${prod_ssh_user}@${prod_ssh_host}:${prod_db_name} (production)"
echo "Destination: ${local_db_user}@${local_db_host}:${local_db_port}/${local_db_name}"
echo "WARNING: all objects and data in the destination public schema will be deleted."

if [[ "$assume_yes" -ne 1 ]]; then
  read -r -p "Type 'copy production to local' to continue: " confirmation
  if [[ "$confirmation" != "copy production to local" ]]; then
    echo "Copy cancelled."
    exit 1
  fi
fi

dump_file=$(mktemp "${TMPDIR:-/tmp}/scholarbridge-production.XXXXXX.dump")
cleanup() {
  rm -f "$dump_file"
}
trap cleanup EXIT

ssh_options=(-p "$prod_ssh_port" -o BatchMode=yes -o StrictHostKeyChecking=yes)
remote="${prod_ssh_user}@${prod_ssh_host}"

echo "Creating an encrypted-in-transit production dump over SSH..."
ssh "${ssh_options[@]}" "$remote" \
  sudo -n -u postgres pg_dump \
    --format=custom --no-owner --no-privileges --dbname="$prod_db_name" \
  > "$dump_file"

if [[ ! -s "$dump_file" ]]; then
  echo "Production dump was empty; local database was not changed." >&2
  exit 1
fi

# Validate the archive before making any destructive local change.
pg_restore --list "$dump_file" >/dev/null

psql_options=(
  --host="$local_db_host"
  --port="$local_db_port"
  --username="$local_db_user"
  --dbname="$local_db_name"
  --set=ON_ERROR_STOP=1
)

echo "Resetting the local public schema..."
psql "${psql_options[@]}" <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public AUTHORIZATION CURRENT_USER;
SQL

echo "Restoring production data locally..."
pg_restore \
  --host="$local_db_host" \
  --port="$local_db_port" \
  --username="$local_db_user" \
  --dbname="$local_db_name" \
  --no-owner --no-privileges --exit-on-error \
  "$dump_file"

echo "Production database copied successfully to ${local_db_name}@${local_db_host}."
