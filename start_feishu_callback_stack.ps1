$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$runtimeDir = Join-Path $root "output\runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$activeDir = Join-Path $root "output\active"
New-Item -ItemType Directory -Force -Path $activeDir | Out-Null

$python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$serverPort = 8092
$serverLog = Join-Path $runtimeDir "feishu_event_server_8092.log"
$serverErr = Join-Path $runtimeDir "feishu_event_server_8092.err.log"
$tunnelLog = Join-Path $runtimeDir "cloudflared_8092.log"
$callbackInfo = Join-Path $activeDir "feishu_callback_live.md"
$callbackInfoTxt = Join-Path $activeDir "feishu_callback_live.txt"
$callbackInfoJson = Join-Path $activeDir "feishu_callback_live.json"

function Stop-PortProcess {
    param([int]$Port)

    $connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        } catch {
        }
    }
}

function Wait-ForFile {
    param(
        [string]$Path,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Path) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Find-Cloudflared {
    $candidates = @(
        (Join-Path $HOME "AppData\Local\Microsoft\WinGet\Links\cloudflared.exe"),
        (Join-Path $HOME "AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe"),
        "C:\ProgramData\chocolatey\bin\cloudflared.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    throw "cloudflared not found"
}

Stop-PortProcess -Port $serverPort

if (Test-Path $serverLog) { Remove-Item $serverLog -Force }
if (Test-Path $serverErr) { Remove-Item $serverErr -Force }

Start-Process -FilePath $python `
    -ArgumentList @("-m", "market_ops.cli", "feishu-event-server", "--host", "127.0.0.1", "--port", "$serverPort") `
    -WorkingDirectory $root `
    -RedirectStandardOutput $serverLog `
    -RedirectStandardError $serverErr `
    -WindowStyle Hidden

Start-Sleep -Seconds 3

$listener = Get-NetTCPConnection -State Listen -LocalPort $serverPort -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) {
    throw "local callback server did not start on port $serverPort"
}

$cloudflaredPath = Find-Cloudflared

$existingTunnel = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "cloudflared.exe" -and $_.CommandLine -like "*127.0.0.1:$serverPort*" }
foreach ($proc in $existingTunnel) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    } catch {
    }
}

if (Test-Path $tunnelLog) { Remove-Item $tunnelLog -Force }

Start-Process -FilePath $cloudflaredPath `
    -ArgumentList @("tunnel", "--url", "http://127.0.0.1:$serverPort", "--no-autoupdate", "--logfile", $tunnelLog, "--loglevel", "info") `
    -WorkingDirectory $root `
    -WindowStyle Hidden

if (-not (Wait-ForFile -Path $tunnelLog -TimeoutSeconds 20)) {
    throw "tunnel log was not created"
}

$publicUrl = $null
$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
    $content = Get-Content $tunnelLog -ErrorAction SilentlyContinue
    $match = $content | Select-String -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
    if ($match) {
        $publicUrl = $match.Matches[0].Value
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $publicUrl) {
    throw "could not parse public callback url from tunnel log"
}

$callbackUrl = "$publicUrl/feishu/events"
$verificationToken = ""
$encryptKey = ""

Get-Content ".env" | ForEach-Object {
    if ($_ -match "^FEISHU_EVENT_VERIFICATION_TOKEN=(.*)$") {
        $verificationToken = $Matches[1]
    }
    if ($_ -match "^FEISHU_EVENT_ENCRYPT_KEY=(.*)$") {
        $encryptKey = $Matches[1]
    }
}

$lines = @(
    "# Feishu callback live info",
    "",
    "Generated at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Local port: $serverPort",
    "Callback URL: $callbackUrl",
    "Verification Token: $verificationToken",
    "Encrypt Key: $encryptKey",
    "",
    "Enable only this event subscription in Feishu:",
    "- im.message.receive_v1",
    "",
    "Validation step:",
    "After saving this callback in Feishu, send @robot help in the allowed group.",
    "",
    "Notes:",
    "- this trycloudflare url is temporary",
    "- restart this script if the tunnel or local service stops",
    "- always use the latest callback url written in this file"
)

$txtLines = @(
    "Callback URL: $callbackUrl",
    "Verification Token: $verificationToken",
    "Encrypt Key: $encryptKey",
    "Event: im.message.receive_v1"
)

$jsonPayload = @{
    generated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    local_port = $serverPort
    callback_url = $callbackUrl
    verification_token = $verificationToken
    encrypt_key = $encryptKey
    event = "im.message.receive_v1"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($callbackInfo, $lines, $utf8NoBom)
[System.IO.File]::WriteAllLines($callbackInfoTxt, $txtLines, $utf8NoBom)
[System.IO.File]::WriteAllText($callbackInfoJson, ($jsonPayload | ConvertTo-Json -Depth 3), $utf8NoBom)

Write-Host ""
Write-Host "Feishu callback stack is live."
Write-Host "Callback URL: $callbackUrl"
Write-Host "Callback info file: $callbackInfo"
Write-Host "Callback copy file: $callbackInfoTxt"
Write-Host "Server log: $serverLog"
Write-Host "Tunnel log: $tunnelLog"
Write-Host ""
