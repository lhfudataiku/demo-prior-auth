#!/usr/bin/env bash
set -euo pipefail

PROJECT_KEY="${1:-DEMO_PRIOR_AUTH_AGENT}"
WEBAPP_ID="${2:-Oa6EjMT}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_FILE="${SCRIPT_DIR}/standard-webapp.definition.patch.json"
TMP_BASE="$(mktemp)"
TMP_MERGED="$(mktemp)"

cleanup() {
  rm -f "${TMP_BASE}" "${TMP_MERGED}"
}
trap cleanup EXIT

dku webapp get-definition "${WEBAPP_ID}" -P "${PROJECT_KEY}" -o json > "${TMP_BASE}"

jq -s '
  .[0] as $base
  | .[1] as $patch
  | ($base * $patch)
  | .params = (($base.params // {}) * ($patch.params // {}))
' "${TMP_BASE}" "${PATCH_FILE}" > "${TMP_MERGED}"

echo "Prepared merged definition for ${PROJECT_KEY}/${WEBAPP_ID}" >&2
echo "Applying updated standard webapp definition from ${PATCH_FILE}" >&2

dku webapp set-definition "${WEBAPP_ID}" "${PROJECT_KEY}" "@${TMP_MERGED}"
