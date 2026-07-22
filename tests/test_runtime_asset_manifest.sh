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
