param([switch]$LocalOnly)
$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot "../..")
try {
    # Generate a new 128-bit password for each sharing session.
    $bytes = New-Object byte[] 16
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $password = [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
    # Read the password on stdin; do not put it in Docker arguments or a file.
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = "docker"
    $info.Arguments = "run --rm -i caddy:2-alpine caddy hash-password"
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $process = [System.Diagnostics.Process]::Start($info)
    try {
        $process.StandardInput.Write($password)
        $process.StandardInput.Close()
        $hash = $process.StandardOutput.ReadToEnd().Trim()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0 -or $hash -notmatch '^\$2[aby]\$') { throw "Could not generate the demo login. Is Docker Desktop running?" }
    } finally { $process.Dispose() }
    $env:DEMO_PASSWORD_HASH = "$hash".Trim()
    $dc = @("compose", "-p", "verifistream-online-demo", "-f", "docker-compose.yml", "-f", "compose.share.yml")
    & docker @dc up --build -d backend frontend gateway
    if ($LASTEXITCODE -ne 0) { throw "Demo startup failed. Use Docker Compose 2.24.4 or newer." }
    $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("demo:$password"))
    $ready = $false
    for ($i = 0; $i -lt 45; $i++) {
        try {
            $resp = Invoke-RestMethod -TimeoutSec 3 -Headers @{Authorization="Basic $auth"} -Uri "http://127.0.0.1:8787/api/health"
            if ($resp.status -eq "ok") { $ready = $true; break }
        } catch {}
        Start-Sleep 2
    }
    if (-not $ready) { throw "Password-protected API did not become ready. No new tunnel started." }
    Write-Host "Username: demo"
    Write-Host "Session password: $password"
    if ($LocalOnly) {
        & docker @dc --profile online stop tunnel
        if ($LASTEXITCODE -ne 0) { throw "Could not stop an existing tunnel." }
        Write-Host "Local preview: http://127.0.0.1:8787"
        return
    }
    & docker @dc --profile online up -d --force-recreate --no-deps tunnel
    if ($LASTEXITCODE -ne 0) { throw "Tunnel startup failed." }
    for ($i = 0; $i -lt 40; $i++) {
        $logs = (& docker @dc logs --no-color tunnel 2>&1 | Out-String)
        if ($logs -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            Write-Host "Share this HTTPS link: $($Matches[0])"
            return
        }
        Start-Sleep 2
    }
    throw "No public URL was reported. Check Docker Desktop tunnel logs or run the stop script."
} finally {
    Remove-Item Env:DEMO_PASSWORD_HASH -ErrorAction SilentlyContinue
    Pop-Location
}
