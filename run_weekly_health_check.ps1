$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$OutputDir = Join-Path $Root "output\runtime"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $OutputDir "weekly_health_check_$Timestamp.log"
$Python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

Start-Transcript -Path $LogPath -Append | Out-Null
try {
    Write-Host "Step 1/3: syncing Feishu and Adjust source data..."
    & $Python -m market_ops.cli sync-feishu-sources --print-summary
    $SyncExitCode = $LASTEXITCODE
    if ($SyncExitCode -ne 0) {
        throw "source sync failed with exit code $SyncExitCode; health check aborted"
    }

    Write-Host "Step 2/3: running preview, self-check, audit, pre-send summary, and health check..."
    & $Python -m market_ops.cli card-preview --report-date latest
    $PreviewExitCode = $LASTEXITCODE
    if ($PreviewExitCode -ne 0) {
        throw "card-preview failed with exit code $PreviewExitCode"
    }

    Write-Host "Step 3/3: simulating Feishu detailed reply..."
    & $Python -m market_ops.cli feishu-event-simulate --report-date latest --text "@机器人 详细版"
    $SimExitCode = $LASTEXITCODE
    if ($SimExitCode -ne 0) {
        throw "feishu-event-simulate failed with exit code $SimExitCode"
    }
}
finally {
    Stop-Transcript | Out-Null
}

Write-Host "Weekly health check finished. Log: $LogPath"
