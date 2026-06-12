#!/usr/bin/env bash
set -euo pipefail

# Optional env file: DB_NAME, DB_USER, DB_HOST, DB_PORT, BACKUP_ROOT
if [[ -f "${1:-}" ]]; then
  # shellcheck disable=SC1090
  source "$1"
fi

DB_NAME="${DB_NAME:-scholarbridge}"
DB_USER="${DB_USER:-scholarbridge_app}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/scholarbridge}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

APP_ROOT="${APP_ROOT:-/opt/scholarbridge}"
GENERATED_DIR="${GENERATED_DIR:-$APP_ROOT/instance/generated_letters}"
AVATAR_UPLOADS_DIR="${AVATAR_UPLOADS_DIR:-$APP_ROOT/app/static/img/avatars/uploads}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_ROOT/postgres" "$BACKUP_ROOT/files"

pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --format=plain --no-owner --no-privileges "$DB_NAME" \
  | gzip -9 > "$BACKUP_ROOT/postgres/${DB_NAME}_${timestamp}.sql.gz"

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

include_any=0
if [[ -d "$GENERATED_DIR" ]]; then
  mkdir -p "$tmp_dir/generated_letters"
  cp -a "$GENERATED_DIR/." "$tmp_dir/generated_letters/" || true
  include_any=1
fi

if [[ -d "$AVATAR_UPLOADS_DIR" ]]; then
  mkdir -p "$tmp_dir/avatar_uploads"
  cp -a "$AVATAR_UPLOADS_DIR/." "$tmp_dir/avatar_uploads/" || true
  include_any=1
fi

if [[ "$include_any" -eq 1 ]]; then
  tar -C "$tmp_dir" -czf "$BACKUP_ROOT/files/file_backup_${timestamp}.tar.gz" .
fi

find "$BACKUP_ROOT/postgres" -type f -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_ROOT/files" -type f -name "*.tar.gz" -mtime +"$RETENTION_DAYS" -delete

echo "Backup completed: $timestamp"
