$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not $env:SHADI_TMP_DIR) {
	$env:SHADI_TMP_DIR = Join-Path $rootDir '.tmp'
}
if (-not $env:SHADI_AGENT_ID) {
	$env:SHADI_AGENT_ID = 'secops-a'
}
if (-not $env:SHADI_OPERATOR_PRESENTATION) {
	$env:SHADI_OPERATOR_PRESENTATION = 'local-operator'
}
if (-not $env:SHADI_SECOPS_CONFIG) {
	$env:SHADI_SECOPS_CONFIG = Join-Path $env:SHADI_TMP_DIR 'secops-a.toml'
}
if (-not $env:SHADI_POLICY_PATH) {
	$env:SHADI_POLICY_PATH = Join-Path $rootDir 'policies/demo/secops-a.json'
}
if (-not $env:SHADI_PYTHON) {
	$env:SHADI_PYTHON = Join-Path $rootDir '.venv\Scripts\python.exe'
}
if (-not $env:SLIM_TLS_CERT) {
	$env:SLIM_TLS_CERT = Join-Path $env:SHADI_TMP_DIR 'shadi-slim-mtls/client-secops-a.crt'
}
if (-not $env:SLIM_TLS_KEY) {
	$env:SLIM_TLS_KEY = Join-Path $env:SHADI_TMP_DIR 'shadi-slim-mtls/client-secops-a.key'
}
if (-not $env:SLIM_TLS_CA) {
	$env:SLIM_TLS_CA = Join-Path $env:SHADI_TMP_DIR 'shadi-slim-mtls/ca.crt'
}

$env:PYTHONUNBUFFERED = '1'

if ($env:SHADI_SECRET_BACKEND -eq 'onepassword') {
	$opAccount = if ($env:SHADI_OP_ACCOUNT) { $env:SHADI_OP_ACCOUNT } else { 'my.1password.com' }
	$opVault = if ($env:SHADI_OP_VAULT) { $env:SHADI_OP_VAULT } else { 'shadi' }

	$env:SHADI_SECRET_SECOPS_SLIM_SHARED_SECRET = Get-OnePasswordSecret -ItemName 'secops/slim_shared_secret' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_GITHUB_TOKEN = Get-OnePasswordSecret -ItemName 'secops/github_token' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_WORKSPACE_DIR = Get-OnePasswordSecret -ItemName 'secops/workspace_dir' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_MEMORY_KEY = Get-OnePasswordSecret -ItemName 'secops/memory_key' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_PROVIDER = Get-OnePasswordSecret -ItemName 'secops/llm/provider' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_OPENAI_API_KEY = Get-OnePasswordSecret -ItemName 'secops/llm/openai_api_key' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_OPENAI_MODEL = Get-OnePasswordSecret -ItemName 'secops/llm/openai_model' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_OPENAI_ENDPOINT = Get-OnePasswordSecret -ItemName 'secops/llm/openai_endpoint' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_GOOGLE_API_KEY = Get-OnePasswordSecret -ItemName 'secops/llm/google_api_key' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_GOOGLE_MODEL = Get-OnePasswordSecret -ItemName 'secops/llm/google_model' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_GOOGLE_ENDPOINT = Get-OnePasswordSecret -ItemName 'secops/llm/google_endpoint' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_CLAUDE_API_KEY = Get-OnePasswordSecret -ItemName 'secops/llm/claude_api_key' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_CLAUDE_MODEL = Get-OnePasswordSecret -ItemName 'secops/llm/claude_model' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_CLAUDE_ENDPOINT = Get-OnePasswordSecret -ItemName 'secops/llm/claude_endpoint' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_API_KEY = Get-OnePasswordSecret -ItemName 'secops/llm/azure_openai_api_key' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_DEPLOYMENT_NAME = Get-OnePasswordSecret -ItemName 'secops/llm/azure_openai_deployment_name' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_ENDPOINT = Get-OnePasswordSecret -ItemName 'secops/llm/azure_openai_endpoint' -Vault $opVault -Account $opAccount
	$env:SHADI_SECRET_SECOPS_LLM_AZURE_OPENAI_API_VERSION = Get-OnePasswordSecret -ItemName 'secops/llm/azure_openai_api_version' -Vault $opVault -Account $opAccount
}

Push-Location $rootDir
try {
	uv run --no-project --python $env:SHADI_PYTHON tools/run_sandboxed_agent.py --policy $env:SHADI_POLICY_PATH -- $env:SHADI_PYTHON agents/secops/a2a_server.py
}
finally {
	Pop-Location
}