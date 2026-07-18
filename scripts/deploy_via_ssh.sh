#!/usr/bin/env bash
set -euo pipefail

DEPLOY_HOST=${DEPLOY_HOST:?DEPLOY_HOST is required}
DEPLOY_USER=${DEPLOY_USER:?DEPLOY_USER is required}
DEPLOY_SSH_PORT=${DEPLOY_SSH_PORT:-22}
DEPLOY_PATH=${DEPLOY_PATH:-/opt/scholarbridge}
DEPLOY_STAGING_PATH=${DEPLOY_STAGING_PATH:-/tmp/scholarbridge-release}
DEPLOY_APP_USER=${DEPLOY_APP_USER:-scholarbridge}
DEPLOY_SERVICE=${DEPLOY_SERVICE:-scholarbridge.service}
DEPLOY_ENV_FILE=${DEPLOY_ENV_FILE:-/etc/scholarbridge/scholarbridge.env}
DEPLOY_HEALTHCHECK_URL=${DEPLOY_HEALTHCHECK_URL:-http://127.0.0.1:8000/health}

REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"
SSH_OPTS=(-p "${DEPLOY_SSH_PORT}" -o BatchMode=yes -o StrictHostKeyChecking=yes)
EXCLUDE_FILE="deploy/rsync-exclude.txt"

if [[ ! -f "${EXCLUDE_FILE}" ]]; then
  echo "Missing ${EXCLUDE_FILE}" >&2
  exit 1
fi

rsync -az --delete \
  --exclude-from="${EXCLUDE_FILE}" \
  -e "ssh ${SSH_OPTS[*]}" \
  ./ "${REMOTE}:${DEPLOY_STAGING_PATH}/"

ssh "${SSH_OPTS[@]}" "${REMOTE}" \
  DEPLOY_PATH="${DEPLOY_PATH}" \
  DEPLOY_STAGING_PATH="${DEPLOY_STAGING_PATH}" \
  DEPLOY_APP_USER="${DEPLOY_APP_USER}" \
  DEPLOY_SERVICE="${DEPLOY_SERVICE}" \
  DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE}" \
  DEPLOY_HEALTHCHECK_URL="${DEPLOY_HEALTHCHECK_URL}" \
  'bash -se' <<'REMOTE_SCRIPT'
set -euo pipefail

DEPLOY_PATH=${DEPLOY_PATH:?}
DEPLOY_STAGING_PATH=${DEPLOY_STAGING_PATH:?}
DEPLOY_APP_USER=${DEPLOY_APP_USER:?}
DEPLOY_SERVICE=${DEPLOY_SERVICE:?}
DEPLOY_ENV_FILE=${DEPLOY_ENV_FILE:?}
DEPLOY_HEALTHCHECK_URL=${DEPLOY_HEALTHCHECK_URL:?}
EXCLUDE_FILE="${DEPLOY_STAGING_PATH}/deploy/rsync-exclude.txt"

if [[ ! -f "${EXCLUDE_FILE}" ]]; then
  echo "Missing remote exclude file: ${EXCLUDE_FILE}" >&2
  exit 1
fi

sudo mkdir -p "${DEPLOY_PATH}"

sudo rsync -az --delete \
  --chown="${DEPLOY_APP_USER}:www-data" \
  --exclude-from="${EXCLUDE_FILE}" \
  "${DEPLOY_STAGING_PATH}/" "${DEPLOY_PATH}/"

sudo -u "${DEPLOY_APP_USER}" /bin/bash -lc '
  set -euo pipefail
  export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
  cd "'"${DEPLOY_PATH}"'"
  uv sync --frozen
'

sudo -u "${DEPLOY_APP_USER}" /bin/bash -lc '
  set -euo pipefail
  export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
  cd "'"${DEPLOY_PATH}"'"
  set -a
  source "'"${DEPLOY_ENV_FILE}"'"
  set +a
  uv run flask --app run.py db current
  uv run flask --app run.py db heads
  uv run flask --app run.py db upgrade
'

sudo systemctl restart "${DEPLOY_SERVICE}"
sudo systemctl is-active --quiet "${DEPLOY_SERVICE}"

for _ in $(seq 1 30); do
  if curl --fail --silent --show-error "${DEPLOY_HEALTHCHECK_URL}" >/dev/null; then
    exit 0
  fi
  sleep 2
done

echo "Health check failed: ${DEPLOY_HEALTHCHECK_URL}" >&2
sudo systemctl status "${DEPLOY_SERVICE}" --no-pager || true
exit 1
REMOTE_SCRIPT
