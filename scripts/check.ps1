$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create backend/.venv and install requirements-dev.lock first; see README.'
}
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Check failed: $Program $Arguments" }
}
Push-Location (Join-Path $taskRoot 'backend')
try {
    Invoke-Checked $taskPython @('-m', 'pip', 'check')
    Invoke-Checked $taskPython @('-m', 'ruff', 'check', 'app', 'tests', 'migrations')
    Invoke-Checked $taskPython @('-m', 'ruff', 'format', '--check', 'app', 'tests', 'migrations')
    Invoke-Checked $taskPython @('-m', 'mypy', 'app')
    Invoke-Checked $taskPython @('-m', 'pytest', '-q')
    Invoke-Checked $taskPython @('-m', 'alembic', 'upgrade', 'head', '--sql')
} finally { Pop-Location }
Push-Location (Join-Path $taskRoot 'frontend')
try { Invoke-Checked 'npm.cmd' @('run', 'check') } finally { Pop-Location }
Push-Location $taskRoot
try {
    Invoke-Checked 'node' @('scripts/check-docs.mjs')
    Invoke-Checked 'docker' @('compose', '--env-file', '.env.example', '--profile', 'app', 'config', '--quiet')
    Invoke-Checked 'git' @('diff', '--check')
} finally { Pop-Location }
Write-Output 'Source checks passed. Containers and live infrastructure were not tested.'
