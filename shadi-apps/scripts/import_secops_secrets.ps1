$ErrorActionPreference = 'Stop'

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

$pythonBin = if ($env:SHADI_PYTHON) { $env:SHADI_PYTHON } else { (Join-Path $rootDir '.venv\Scripts\python.exe') }

Push-Location $rootDir
try {
	uv run --no-project --python $pythonBin agents/secops/import_secops_secrets.py
}
finally {
	Pop-Location
}