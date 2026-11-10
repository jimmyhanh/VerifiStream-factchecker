$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot "../..")
try {
    $env:DEMO_PASSWORD_HASH = "unused-during-shutdown"
    docker compose -p verifistream-online-demo -f docker-compose.yml -f compose.share.yml --profile online down
    if ($LASTEXITCODE -ne 0) { throw "Could not stop demo. Check Docker Desktop." }
} finally {
    Remove-Item Env:DEMO_PASSWORD_HASH -ErrorAction SilentlyContinue
    Pop-Location
}
