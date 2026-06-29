param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$OutputDir = Join-Path $Root "output\runtime"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $OutputDir "boss_manual_send_$Timestamp.log"
$Python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

if (-not $Force) {
    Write-Host "This will send the boss executive card and recovery card to the boss Feishu group."
    Write-Host "Type SEND to continue. Anything else will cancel."
    $Answer = Read-Host "Confirm"
    if ($Answer -ne "SEND") {
        Write-Host "Canceled. Nothing was sent."
        exit 0
    }
}

Start-Transcript -Path $LogPath -Append | Out-Null
try {
    Write-Host "Step 1/3: syncing Feishu and Adjust source data..."
    & $Python -m market_ops.cli sync-feishu-sources --print-summary
    $SyncExitCode = $LASTEXITCODE
    if ($SyncExitCode -ne 0) {
        throw "source sync failed with exit code $SyncExitCode; send aborted"
    }

    Write-Host "Step 2/4: running report audit gate..."
    & $Python -m market_ops.cli report-audit --report-date latest
    $AuditExitCode = $LASTEXITCODE
    if ($AuditExitCode -ne 0) {
        throw "report-audit failed with exit code $AuditExitCode; send intercepted, preview only"
    }

    Write-Host "Step 3/4: generating pre-send summary..."
    & $Python -m market_ops.cli pre-send-summary --report-date latest
    $SummaryExitCode = $LASTEXITCODE
    if ($SummaryExitCode -ne 0) {
        throw "pre-send-summary failed with exit code $SummaryExitCode; send aborted"
    }
    Write-Host "Pre-send summary generated. Check output\\active\\pre_send_summary_<date>.md or this log summary line."

    Write-Host "Step 4/4: sending boss cards..."
    & $Python -m market_ops.cli card-send --report-date latest --boss
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "boss card-send failed with exit code $ExitCode"
    }
}
finally {
    Stop-Transcript | Out-Null
}

Write-Host "Boss manual send finished. Log: $LogPath"
