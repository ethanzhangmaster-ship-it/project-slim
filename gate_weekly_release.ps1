$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$reportDate = "latest"
$reportDateLabel = "latest"
$outPath = Join-Path $root "output\active\weekly_release_gate_latest.md"

Write-Host ""
Write-Host "Step 1/6: preview"
& $python -m market_ops.cli card-preview --report-date $reportDate
if ($LASTEXITCODE -ne 0) {
    throw "card-preview failed"
}

Write-Host "Step 2/6: self-check and audit"
& $python -m market_ops.cli report-audit --report-date $reportDate
if ($LASTEXITCODE -ne 0) {
    throw "report-audit failed"
}

Write-Host "Step 3/7: pre-send summary"
& $python -m market_ops.cli pre-send-summary --report-date $reportDate
if ($LASTEXITCODE -ne 0) {
    throw "pre-send-summary failed"
}

Write-Host "Step 4/7: metrics consistency"
powershell -ExecutionPolicy Bypass -File ".\verify_weekly_metrics_consistency.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "weekly metrics consistency check failed"
}

Write-Host "Step 5/7: callback health"
powershell -ExecutionPolicy Bypass -File ".\check_feishu_callback_stack.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "callback health check failed"
}

Write-Host "Step 6/7: bot route doctor"
powershell -ExecutionPolicy Bypass -File ".\doctor_feishu_bot.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "doctor_feishu_bot failed"
}

Write-Host "Step 7/7: build release gate summary"

$selfCheck = Get-ChildItem "output\active\self_check_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$reportAudit = Get-ChildItem "output\active\report_audit_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$preSend = Get-ChildItem "output\active\pre_send_summary_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$marketPreview = Get-ChildItem "output\active\card_preview_market_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$marketDetail = Get-ChildItem "output\active\card_preview_market_detail_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$bossPreview = Get-ChildItem "output\active\card_preview_boss_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$recoveryPreview = Get-ChildItem "output\active\card_preview_recovery_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$summaryPreview = Get-ChildItem "output\active\card_preview_summary_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$metricsConsistency = Join-Path $root "output\active\weekly_metrics_consistency_latest.md"
$callbackTxt = Join-Path $root "output\active\feishu_callback_live.txt"

$lines = @(
    "# Weekly Release Gate",
    "",
    "Status: PASS",
    "Report date: $reportDateLabel",
    "Generated at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "",
    "Checks completed:",
    "- preview generated",
    "- self-check and audit passed",
    "- pre-send summary generated",
    "- weekly metrics consistency passed",
    "- callback health passed",
    "- bot route doctor passed",
    "",
    "Artifacts:",
    "- summary preview: $($summaryPreview.FullName)",
    "- market preview: $($marketPreview.FullName)",
    "- market detail preview: $($marketDetail.FullName)",
    "- boss preview: $($bossPreview.FullName)",
    "- recovery preview: $($recoveryPreview.FullName)",
    "- self-check: $($selfCheck.FullName)",
    "- report audit: $($reportAudit.FullName)",
    "- pre-send summary: $($preSend.FullName)",
    "- metrics consistency: $metricsConsistency",
    "- callback config: $callbackTxt",
    "",
    "Next action:",
    "- if this is a send day, run .\\send_market_weekly_all.ps1",
    "- if the bot is not replying in group, run .\\refresh_feishu_callback_stack.ps1",
    ""
)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($outPath, $lines, $utf8NoBom)

Write-Host ""
Write-Host "Weekly release gate passed."
Write-Host "Summary file: $outPath"
Write-Host ""
