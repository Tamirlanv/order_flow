$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $certDirectory = Join-Path $root ".tmp/tls"
    New-Item -ItemType Directory -Force $certDirectory | Out-Null
    if ((Test-Path "$certDirectory/cert.pem") -or (Test-Path "$certDirectory/key.pem")) {
        throw "Local certificate already exists; refusing to overwrite it."
    }
    # OpenSSL ships in the project's Python Debian image. No host installation.
    docker compose --profile app run --rm --no-deps --user 0 --entrypoint openssl `
        --volume "${certDirectory}:/certs" api req -x509 -newkey rsa:3072 -nodes `
        -keyout /certs/key.pem -out /certs/cert.pem -days 30 `
        -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,DNS:frontend,IP:127.0.0.1"
    if ($LASTEXITCODE -ne 0) { throw "OpenSSL failed" }
    Write-Host "Local TLS certificate created in .tmp/tls (ignored by Git; not added to OS trust)."
} finally {
    Pop-Location
}
