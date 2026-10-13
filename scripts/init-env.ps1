$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskEnvPath = Join-Path $taskRoot '.env'
if (Test-Path -LiteralPath $taskEnvPath) {
    Write-Output '.env already exists; preserved without changes.'
    exit 0
}
$taskText = [IO.File]::ReadAllText((Join-Path $taskRoot '.env.example'))
foreach ($taskKey in @('POSTGRES_PASSWORD', 'RABBITMQ_PASSWORD', 'APP_SECRET_KEY', 'OUTBOX_ENCRYPTION_KEY', 'IDEMPOTENCY_ENCRYPTION_KEY')) {
    $taskBytes = New-Object byte[] 32
    $taskRandom = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $taskRandom.GetBytes($taskBytes) } finally { $taskRandom.Dispose() }
    $taskSecret = -join ($taskBytes | ForEach-Object { $_.ToString('x2') })
    $taskText = [regex]::Replace($taskText, "(?m)^$taskKey=.*$", "$taskKey=$taskSecret")
}
[IO.File]::WriteAllText($taskEnvPath, $taskText, [Text.UTF8Encoding]::new($false))
Write-Output 'Created local .env with random secrets. Do not commit this file.'
