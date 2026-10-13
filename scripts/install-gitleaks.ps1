$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$toolsDirectory = Join-Path $root ".tmp/tools"
New-Item -ItemType Directory -Force $toolsDirectory | Out-Null
$version = "8.30.1"
if ($env:OS -eq "Windows_NT") {
    $asset = "gitleaks_" + $version + "_windows_x64.zip"
    $digest = "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"
} else {
    $asset = "gitleaks_" + $version + "_linux_x64.tar.gz"
    $digest = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
}
$archive = Join-Path $toolsDirectory $asset
Invoke-WebRequest "https://github.com/gitleaks/gitleaks/releases/download/v$version/$asset" -OutFile $archive
if ((Get-FileHash -Algorithm SHA256 $archive).Hash.ToLowerInvariant() -ne $digest) {
    throw "Gitleaks archive checksum mismatch"
}
if ($env:OS -eq "Windows_NT") {
    Expand-Archive -LiteralPath $archive -DestinationPath $toolsDirectory -Force
} else {
    tar -xzf $archive -C $toolsDirectory gitleaks
    if ($LASTEXITCODE -ne 0) { throw "Gitleaks extraction failed" }
}
Write-Host "Gitleaks $version installed; pinned SHA-256 verified."
