$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Run-Step {
    param(
        [string]$Label,
        [string]$Script
    )

    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host $Label
    Write-Host ("=" * 60)
    powershell -ExecutionPolicy Bypass -File $Script
}

while ($true) {
    Clear-Host
    Write-Host "Market Ops Control Center"
    Write-Host ""
    Write-Host "1. Show system status"
    Write-Host "2. Start callback stack"
    Write-Host "3. Refresh callback stack"
    Write-Host "4. Show callback config"
    Write-Host "5. Check callback health"
    Write-Host "6. Run bot doctor"
    Write-Host "7. Run weekly release gate"
    Write-Host "8. Send market weekly"
    Write-Host "9. Stop callback stack"
    Write-Host "10. Install startup shortcut"
    Write-Host "11. Remove startup shortcut"
    Write-Host "12. Open fixed-domain plan"
    Write-Host "0. Exit"
    Write-Host ""

    $choice = Read-Host "Choose an action"

    switch ($choice) {
        "1" { Run-Step "System status" ".\status_market_ops.ps1" }
        "2" { Run-Step "Start callback stack" ".\start_feishu_callback_stack.ps1" }
        "3" { Run-Step "Refresh callback stack" ".\refresh_feishu_callback_stack.ps1" }
        "4" { Run-Step "Show callback config" ".\show_feishu_callback_config.ps1" }
        "5" { Run-Step "Check callback health" ".\check_feishu_callback_stack.ps1" }
        "6" { Run-Step "Run bot doctor" ".\doctor_feishu_bot.ps1" }
        "7" { Run-Step "Run weekly release gate" ".\gate_weekly_release.ps1" }
        "8" { Run-Step "Send market weekly" ".\send_market_weekly_all.ps1" }
        "9" { Run-Step "Stop callback stack" ".\stop_feishu_callback_stack.ps1" }
        "10" { Run-Step "Install startup shortcut" ".\install_feishu_callback_startup_shortcut.ps1" }
        "11" { Run-Step "Remove startup shortcut" ".\uninstall_feishu_callback_startup_shortcut.ps1" }
        "12" {
            Write-Host ""
            Get-Content ".\FIXED_CALLBACK_DOMAIN_PLAN.md"
        }
        "0" { break }
        default { Write-Host ""; Write-Host "Invalid choice." }
    }

    Write-Host ""
    Pause
}
