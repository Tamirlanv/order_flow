$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$since = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$marker = "security-probe-" + [Guid]::NewGuid().ToString("N")
Push-Location $root
try {
    Invoke-WebRequest "http://localhost:8080/api/v1/system?token=$marker" -UseBasicParsing -Headers @{ "Authorization" = "Bearer $marker"; "Cookie" = "probe=$marker" } | Out-Null
    try {
        Invoke-WebRequest "http://localhost:8080/api/v1/auth/login?token=$marker" -UseBasicParsing -Method Post -Body ($marker + ('x' * 17000)) | Out-Null
    } catch {
        if ([int]$_.Exception.Response.StatusCode -ne 413) { throw }
    }
    $lines = docker compose logs --since $since --no-log-prefix frontend api 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Cannot read logs" }
    if (($lines -join "`n").Contains($marker)) { throw "Sensitive probe leaked into container logs" }
    $jsonLines = @($lines | Where-Object { "$_" -match '^\{"request_id":' })
    if ($jsonLines.Count -lt 2) { throw "Expected safe access records for both requests" }
    foreach ($line in $jsonLines) {
        $record = "$line" | ConvertFrom-Json
        $keys = @($record.PSObject.Properties.Name | Sort-Object)
        if (($keys -join ',') -ne 'bytes,duration,request_id,status') { throw "Unexpected access log fields" }
    }
    Write-Host "Nginx/API logs PASS: query, authorization, cookie and rejected request body absent; safe JSON records present."
} finally { Pop-Location }
