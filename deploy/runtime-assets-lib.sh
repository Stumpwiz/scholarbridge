#!/usr/bin/env bash

normalize_runtime_asset_manifest() {
  local source_file=${1:?source manifest is required}
  local output_file=${2:?output manifest is required}
  local runtime_asset

  : > "${output_file}"
  while IFS= read -r runtime_asset || [[ -n "${runtime_asset}" ]]; do
    runtime_asset="${runtime_asset#"${runtime_asset%%[![:space:]]*}"}"
    runtime_asset="${runtime_asset%"${runtime_asset##*[![:space:]]}"}"

    if [[ -z "${runtime_asset}" || "${runtime_asset}" == \#* ]]; then
      continue
    fi

    printf '%s\n' "${runtime_asset}" >> "${output_file}"
  done < "${source_file}"
}
