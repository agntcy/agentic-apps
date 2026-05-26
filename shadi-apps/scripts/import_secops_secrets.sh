#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${SHADI_TMP_DIR:="${ROOT_DIR}/.tmp"}"
: "${SHADI_AGENT_ID:="secops-a"}"
: "${SHADI_OPERATOR_PRESENTATION:="local-operator"}"

export SHADI_TMP_DIR
export SHADI_AGENT_ID
export SHADI_OPERATOR_PRESENTATION

# Optional: 1Password backend (set SHADI_SECRET_BACKEND=onepassword to enable)
if [[ -n "${SHADI_SECRET_BACKEND:-}" ]]; then
	export SHADI_SECRET_BACKEND
fi
if [[ -n "${SHADI_OP_VAULT:-}" ]]; then
	export SHADI_OP_VAULT
fi
if [[ -n "${SHADI_OP_ACCOUNT:-}" ]]; then
	export SHADI_OP_ACCOUNT
fi

cd "${ROOT_DIR}"
uv run agents/secops/import_secops_secrets.py
