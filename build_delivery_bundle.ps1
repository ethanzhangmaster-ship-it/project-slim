$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$bundleRoot = Join-Path $root "output\delivery_bundle"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bundleDir = Join-Path $bundleRoot $timestamp
New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null

$items = @(
    "output\active\market_ops_status_latest.md",
    "output\active\market_ops_status_latest.json",
    "output\active\feishu_callback_live.txt",
    "output\active\feishu_callback_live.json",
    "output\active\weekly_release_gate_latest.md",
    "output\active\weekly_metrics_consistency_latest.md",
    "output\active\pre_send_summary_20260603.md",
    "output\active\card_preview_summary_20260603.md",
    "output\active\card_preview_market_20260603.md",
    "output\active\card_preview_market_detail_20260603.md",
    "output\active\card_preview_recovery_20260603.md",
    "output\active\card_preview_boss_20260603.md",
    "output\active\group_execution_checklist_latest.md",
    "output\active\group_task_packet_latest.md",
    "output\active\group_approval_packet_latest.md",
    "output\active\group_approved_tasks_latest.md",
    "output\active\group_approved_execution_latest.md",
    "output\active\group_approved_execution_latest.json",
    "output\active\group_requirements_queue.json",
    "output\active\group_send_log_latest.md",
    "output\active\group_send_log_latest.json",
    "FEISHU_CALLBACK_USE.txt",
    "FEISHU_BOT_TROUBLESHOOTING.txt",
    "WEEKLY_RELEASE_USE.txt",
    "MARKET_OPS_STATUS_USE.txt",
    "CONTROL_CENTER_USE.txt",
    "GROUP_QA_BOT_USE.md",
    "GROUP_QA_BOT_MINIMUM_PLAN.md",
    "STABLE_STARTUP_FLOW.md",
    "FIXED_CALLBACK_DOMAIN_PLAN.md",
    "FIXED_CALLBACK_DOMAIN_INTAKE.txt",
    "FIXED_CALLBACK_DOMAIN_CHECKLIST.md"
)

$copied = @()
foreach ($item in $items) {
    $source = Join-Path $root $item
    if (Test-Path $source) {
        $target = Join-Path $bundleDir ([System.IO.Path]::GetFileName($source))
        Copy-Item $source $target -Force
        $copied += $target
    }
}

$readme = Join-Path $bundleDir "DELIVERY_BUNDLE_README.txt"
$lines = @(
    "Market Ops delivery bundle",
    "",
    "Generated at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Bundle folder: $bundleDir",
    "",
    "Main entry files:",
    "- market_ops_status_latest.md",
    "- feishu_callback_live.txt",
    "- weekly_release_gate_latest.md",
    "- group_execution_checklist_latest.md",
    "- group_requirements_queue.json",
    "- FEISHU_CALLBACK_USE.txt",
    "- GROUP_QA_BOT_USE.md",
    "- WEEKLY_RELEASE_USE.txt",
    "- FIXED_CALLBACK_DOMAIN_PLAN.md",
    "",
    "Copied files:"
)
foreach ($path in $copied) {
    $lines += "- $([System.IO.Path]::GetFileName($path))"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($readme, $lines, $utf8NoBom)

Write-Host ""
Write-Host "Delivery bundle built."
Write-Host "Bundle folder: $bundleDir"
Write-Host ""
