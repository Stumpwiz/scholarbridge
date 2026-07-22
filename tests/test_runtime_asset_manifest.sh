#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source deploy/runtime-assets-lib.sh

test_dir=$(mktemp -d)
trap 'rm -rf "${test_dir}"' EXIT

source_manifest="${test_dir}/runtime-assets.txt"
normalized_manifest="${test_dir}/normalized.txt"
expected_manifest="${test_dir}/expected.txt"

printf '%s\n' \
  '# Documentation comment' \
  '' \
  '   # Indented documentation comment   ' \
  '  docs/private/img/signature.jpg  ' \
  $'\t docs/private/letter_templates/template.docx\t' \
  > "${source_manifest}"

printf '%s\n' \
  'docs/private/img/signature.jpg' \
  'docs/private/letter_templates/template.docx' \
  > "${expected_manifest}"

normalize_runtime_asset_manifest "${source_manifest}" "${normalized_manifest}"
cmp "${expected_manifest}" "${normalized_manifest}"

# A GitHub Actions-style code-only deployment must not require the ignored
# manifest or private files to exist in its checkout.
code_only_checkout="${test_dir}/code-only-checkout"
fake_bin="${test_dir}/bin"
mkdir -p "${code_only_checkout}/scripts" "${code_only_checkout}/deploy" "${fake_bin}"
cp scripts/deploy_via_ssh.sh "${code_only_checkout}/scripts/"
cp deploy/rsync-exclude.txt "${code_only_checkout}/deploy/"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "${fake_bin}/rsync"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "${fake_bin}/ssh"
chmod +x "${fake_bin}/rsync" "${fake_bin}/ssh"

(
  cd "${code_only_checkout}"
  PATH="${fake_bin}:${PATH}" \
    DEPLOY_HOST=example.invalid \
    DEPLOY_USER=deploy \
    DEPLOY_SYNC_RUNTIME_ASSETS=false \
    bash scripts/deploy_via_ssh.sh
)
