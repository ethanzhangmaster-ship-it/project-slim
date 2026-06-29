$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$OutputDir = Join-Path $Root "output\runtime"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $OutputDir "weekly_preview_$Timestamp.log"
$Python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

Start-Transcript -Path $LogPath -Append | Out-Null
try {
    Write-Host "Step 1/2: syncing Feishu and Adjust source data..."
    & $Python -m market_ops.cli sync-feishu-sources --print-summary
    $SyncExitCode = $LASTEXITCODE
    if ($SyncExitCode -ne 0) {
        throw "source sync failed with exit code $SyncExitCode; preview aborted"
    }

    Write-Host "Step 2/2: generating previews, self-check report, audit report, and health check..."
    & $Python -m market_ops.cli card-preview --report-date latest
    $PreviewExitCode = $LASTEXITCODE
    if ($PreviewExitCode -ne 0) {
        throw "card-preview failed with exit code $PreviewExitCode"
    }
}
finally {
    Stop-Transcript | Out-Null
}

Write-Host "Weekly preview finished. Log: $LogPath"
