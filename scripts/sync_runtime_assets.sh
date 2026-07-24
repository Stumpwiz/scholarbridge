#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  cat <<'USAGE'
Synchronize the private runtime assets in deploy/runtime-assets.txt to production.

Usage:
  scripts/sync_runtime_assets.sh

Configuration is read from docs/private/deploymentDetails.txt by default.
Optional overrides:
  RUNTIME_ASSET_DEPLOYMENT_DETAILS  Deployment details file
  RUNTIME_ASSET_HOST                Production SSH host
  RUNTIME_ASSET_SSH_USER            Production SSH user
  RUNTIME_ASSET_SSH_KEY             SSH private-key path
  RUNTIME_ASSET_SSH_PORT            SSH port (default: 22)
  RUNTIME_ASSET_DESTINATION         Application directory on production
  RUNTIME_ASSET_APP_USER            Installed-file owner (default: scholarbridge)
USAGE
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
esac

manifest_file="deploy/runtime-assets.txt"
manifest_library="deploy/runtime-assets-lib.sh"
deployment_details=${RUNTIME_ASSET_DEPLOYMENT_DETAILS:-docs/private/deploymentDetails.txt}

for required_file in "$manifest_file" "$manifest_library" "$deployment_details"; do
  if [[ ! -f "$required_file" ]]; then
    echo "Missing required file: $required_file" >&2
    exit 1
  fi
done

for required_command in awk mktemp rsync sed ssh; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    echo "Required command not found: $required_command" >&2
    exit 1
  fi
done

# shellcheck source=../deploy/runtime-assets-lib.sh
source "$manifest_library"

normalized_manifest=$(mktemp "${TMPDIR:-/tmp}/scholarbridge-runtime-assets.XXXXXX")
remote_stage=""
cleanup() {
  rm -f "$normalized_manifest"
  if [[ "$remote_stage" =~ ^/tmp/scholarbridge-runtime-assets\.[A-Za-z0-9]+$ ]]; then
    ssh "${ssh_options[@]}" "$remote" "rm -rf -- '$remote_stage'" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

normalize_runtime_asset_manifest "$manifest_file" "$normalized_manifest"

if [[ ! -s "$normalized_manifest" ]]; then
  echo "Runtime asset manifest contains no assets: $manifest_file" >&2
  exit 1
fi

while IFS= read -r runtime_asset; do
  if [[ "$runtime_asset" == /* || "$runtime_asset" == ".." || "$runtime_asset" == ../* || "$runtime_asset" == */../* ]]; then
    echo "Unsafe runtime asset path in manifest: $runtime_asset" >&2
    exit 1
  fi
  if [[ ! -f "$runtime_asset" ]]; then
    echo "Missing required runtime asset: $runtime_asset" >&2
    exit 1
  fi
done < "$normalized_manifest"

configured_ssh_command=$(awk '/^ssh -i [^ ]+ [^ ]+@[^ ]+$/ { print; exit }' "$deployment_details")
configured_destination=$(awk '/^The app is \/[^ ]+$/ { print $4; exit }' "$deployment_details")

configured_key=""
configured_user=""
configured_host=""
if [[ "$configured_ssh_command" =~ ^ssh[[:space:]]+-i[[:space:]]+([^[:space:]]+)[[:space:]]+([^@[:space:]]+)@([^[:space:]]+)$ ]]; then
  configured_key=${BASH_REMATCH[1]}
  configured_user=${BASH_REMATCH[2]}
  configured_host=${BASH_REMATCH[3]}
fi

if [[ "$configured_key" == "~/"* ]]; then
  configured_key="$HOME/${configured_key#\~/}"
fi

sync_host=${RUNTIME_ASSET_HOST:-$configured_host}
sync_user=${RUNTIME_ASSET_SSH_USER:-$configured_user}
sync_key=${RUNTIME_ASSET_SSH_KEY:-$configured_key}
sync_port=${RUNTIME_ASSET_SSH_PORT:-22}
sync_destination=${RUNTIME_ASSET_DESTINATION:-$configured_destination}
sync_app_user=${RUNTIME_ASSET_APP_USER:-scholarbridge}

if [[ -z "$sync_host" || -z "$sync_user" || -z "$sync_key" || -z "$sync_destination" ]]; then
  echo "Could not resolve complete deployment configuration from $deployment_details." >&2
  echo "Set the RUNTIME_ASSET_* overrides shown by --help if needed." >&2
  exit 1
fi

if [[ ! -f "$sync_key" ]]; then
  echo "SSH private key not found: $sync_key" >&2
  exit 1
fi
if [[ ! "$sync_port" =~ ^[0-9]+$ ]]; then
  echo "RUNTIME_ASSET_SSH_PORT must be numeric." >&2
  exit 1
fi
if [[ ! "$sync_user" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ || ! "$sync_app_user" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
  echo "Invalid SSH or application user." >&2
  exit 1
fi
if [[ ! "$sync_host" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "Invalid deployment host." >&2
  exit 1
fi
if [[ ! "$sync_destination" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  echo "Invalid production destination path." >&2
  exit 1
fi

remote="${sync_user}@${sync_host}"
ssh_options=(
  -i "$sync_key"
  -p "$sync_port"
  -o BatchMode=yes
  -o StrictHostKeyChecking=yes
)
printf -v rsync_ssh 'ssh -i %q -p %q -o BatchMode=yes -o StrictHostKeyChecking=yes' \
  "$sync_key" "$sync_port"

echo "Validated runtime assets:"
sed 's/^/  /' "$normalized_manifest"

remote_stage=$(ssh "${ssh_options[@]}" "$remote" \
  'mktemp -d /tmp/scholarbridge-runtime-assets.XXXXXX')
if [[ ! "$remote_stage" =~ ^/tmp/scholarbridge-runtime-assets\.[A-Za-z0-9]+$ ]]; then
  echo "Production server returned an unsafe staging path: $remote_stage" >&2
  remote_stage=""
  exit 1
fi

# Retain manifest-relative paths exactly, matching deploy_via_ssh.sh.
rsync -az --relative \
  --files-from="$normalized_manifest" \
  -e "$rsync_ssh" \
  ./ "$remote:${remote_stage}/"
rsync -az -e "$rsync_ssh" \
  "$normalized_manifest" "$remote:${remote_stage}/.runtime-assets.txt"

ssh "${ssh_options[@]}" "$remote" \
  bash -s -- "$remote_stage" "$sync_destination" "$sync_app_user" <<'REMOTE_SCRIPT'
set -euo pipefail

stage=${1:?staging directory is required}
destination=${2:?destination directory is required}
app_user=${3:?application user is required}
manifest="${stage}/.runtime-assets.txt"

while IFS= read -r runtime_asset; do
  if [[ ! -f "${stage}/${runtime_asset}" ]]; then
    echo "Missing staged runtime asset: $runtime_asset" >&2
    exit 1
  fi
done < "$manifest"

sudo -n mkdir -p "$destination"
sudo -n rsync -az --relative \
  --chown="${app_user}:www-data" \
  --files-from="$manifest" \
  "${stage}/" "${destination}/"
REMOTE_SCRIPT

echo "Synchronized runtime assets to ${remote}:${sync_destination}:"
sed 's/^/  /' "$normalized_manifest"
