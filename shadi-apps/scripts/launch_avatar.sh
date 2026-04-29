#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${SHADI_TMP_DIR:="${ROOT_DIR}/.tmp"}"
: "${SHADI_AGENT_ID:="avatar-1"}"
: "${SHADI_OPERATOR_PRESENTATION:="local-operator"}"
: "${SHADI_SECOPS_CONFIG:="${SHADI_TMP_DIR}/secops-a.toml"}"
: "${SHADI_POLICY_PATH:="${ROOT_DIR}/policies/demo/avatar.json"}"
: "${SHADI_PYTHON:="${ROOT_DIR}/.venv/bin/python"}"

export SHADI_TMP_DIR
export SHADI_AGENT_ID
export SHADI_OPERATOR_PRESENTATION
export SHADI_SECOPS_CONFIG
export SHADI_POLICY_PATH
export SHADI_PYTHON

# Optional: 1Password backend
if [[ -n "${SHADI_SECRET_BACKEND:-}" ]]; then
	export SHADI_SECRET_BACKEND
fi
if [[ -n "${SHADI_OP_VAULT:-}" ]]; then
	export SHADI_OP_VAULT
fi
if [[ -n "${SHADI_OP_ACCOUNT:-}" ]]; then
	export SHADI_OP_ACCOUNT
fi

: "${SLIM_TLS_CERT:="${SHADI_TMP_DIR}/shadi-slim-mtls/client-avatar.crt"}"
: "${SLIM_TLS_KEY:="${SHADI_TMP_DIR}/shadi-slim-mtls/client-avatar.key"}"
: "${SLIM_TLS_CA:="${SHADI_TMP_DIR}/shadi-slim-mtls/ca.crt"}"

export SLIM_TLS_CERT
export SLIM_TLS_KEY
export SLIM_TLS_CA

export PYTHONUNBUFFERED=1

# Pre-read 1Password secrets in the foreground before entering the sandbox.
# The sandbox blocks op's background biometric prompt; env var fallbacks avoid that.
if [[ "${SHADI_SECRET_BACKEND:-}" == "onepassword" ]]; then
	_OP_ACCOUNT="${SHADI_OP_ACCOUNT:-my.1password.com}"
	_OP_VAULT="${SHADI_OP_VAULT:-shadi}"

	_read_op_secret() {
		local item_name="$1"
		local item_json
		if ! item_json="$(op item get "$item_name" --vault "${_OP_VAULT}" --account "${_OP_ACCOUNT}" --format json 2>/dev/null)" || [[ -z "$item_json" ]]; then
			echo "ERROR: failed to read 1Password item '$item_name' from vault '${_OP_VAULT}' account '${_OP_ACCOUNT}'" >&2
			return 1
		fi
		ITEM_JSON="$item_json" python3 - <<'PY'
import base64
import json
import os
import sys

data = json.loads(os.environ["ITEM_JSON"])
field = next((f for f in data.get("fields", []) if f.get("id") == "notesPlain"), None)
if not field or not field.get("value"):
    print("ERROR: missing notesPlain field in 1Password item", file=sys.stderr)
    raise SystemExit(1)
print(base64.b64decode(field["value"]).decode(), end="")
PY
	}

	export SHADI_SECRET_SECOPS_SLIM_SHARED_SECRET="$(_read_op_secret "secops/slim_shared_secret")"
	export SHADI_SECRET_SECOPS_LLM_PROVIDER="$(_read_op_secret "secops/llm/provider")"
	export SHADI_SECRET_SECOPS_LLM_OPENAI_API_KEY="$(_read_op_secret "secops/llm/openai_api_key")"
	export SHADI_SECRET_SECOPS_LLM_OPENAI_MODEL="$(_read_op_secret "secops/llm/openai_model")"
	export SHADI_SECRET_SECOPS_LLM_OPENAI_ENDPOINT="$(_read_op_secret "secops/llm/openai_endpoint")"
	export SHADI_SECRET_SECOPS_LLM_GOOGLE_API_KEY="$(_read_op_secret "secops/llm/google_api_key")"
	export SHADI_SECRET_SECOPS_LLM_GOOGLE_MODEL="$(_read_op_secret "secops/llm/google_model")"
	export SHADI_SECRET_SECOPS_LLM_GOOGLE_ENDPOINT="$(_read_op_secret "secops/llm/google_endpoint")"
	export SHADI_SECRET_SECOPS_LLM_CLAUDE_API_KEY="$(_read_op_secret "secops/llm/claude_api_key")"
	export SHADI_SECRET_SECOPS_LLM_CLAUDE_MODEL="$(_read_op_secret "secops/llm/claude_model")"
	export SHADI_SECRET_SECOPS_LLM_CLAUDE_ENDPOINT="$(_read_op_secret "secops/llm/claude_endpoint")"
	export SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_API_KEY="$(_read_op_secret "secops/llm/azure_openai_api_key")"
	export SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_DEPLOYMENT_NAME="$(_read_op_secret "secops/llm/azure_openai_deployment_name")"
	export SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_ENDPOINT="$(_read_op_secret "secops/llm/azure_openai_endpoint")"
	export SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_API_VERSION="$(_read_op_secret "secops/llm/azure_openai_api_version")"
fi

cd "${ROOT_DIR}"
uv run --no-project --python "${SHADI_PYTHON}" "${ROOT_DIR}/tools/run_sandboxed_agent.py" \
	--policy "${SHADI_POLICY_PATH}" \
	-- "${SHADI_PYTHON}" "${ROOT_DIR}/agents/avatar/adk_agent/run_shadi_memory.py"
