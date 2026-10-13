param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
function Invoke-Docker {
    param([string[]]$Arguments)
    & docker compose --profile app --profile test @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Compose check failed: $Arguments" }
}
Push-Location $taskRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) { throw 'Run ./scripts/init-env.ps1 first.' }
    if (-not $SkipBuild) { Invoke-Docker @('build', 'api', 'frontend', 'tests') }
    Invoke-Docker @('up', '-d', '--no-build', '--wait', '--wait-timeout', '180', 'postgres', 'redis', 'rabbitmq', 'mailpit', 'api', 'worker', 'beat', 'frontend')
    Invoke-Docker @('exec', '-T', 'api', 'python', '-m', 'alembic', 'upgrade', 'head')
    Invoke-Docker @('run', '--rm', '--no-deps', 'tests')
    Invoke-Docker @('stop', 'rabbitmq')
    try {
        $taskProbe = @'
import json
import urllib.request
from urllib.error import HTTPError
try:
    urllib.request.urlopen('http://localhost:8000/health/ready', timeout=10)
except HTTPError as error:
    assert error.code == 503
    assert json.load(error)['checks']['rabbitmq'] == 'unavailable'
else:
    raise AssertionError('Readiness must reject a stopped broker')
print('Broker outage correctly reported')
'@
        Invoke-Docker @('exec', '-T', 'api', 'python', '-c', $taskProbe)
    } finally {
        Invoke-Docker @('up', '-d', '--wait', '--wait-timeout', '120', 'rabbitmq')
    }
    Invoke-Docker @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'pytest', '-q', 'tests/test_infrastructure.py', '-k', 'live_dependencies or worker_reachable')
} finally { Pop-Location }
Write-Output 'Infrastructure checks passed, including broker reconnection. Local containers remain running.'
