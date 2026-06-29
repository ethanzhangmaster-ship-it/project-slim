$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "MarketMeeting-FeishuCallbackStack"
$scriptPath = Join-Path $root "refresh_feishu_callback_stack.ps1"

if (-not (Test-Path $scriptPath)) {
    throw "refresh_feishu_callback_stack.ps1 not found"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`""

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Auto refresh Feishu callback stack at Windows logon for Market Meeting bot" `
    -Force | Out-Null

Write-Host ""
Write-Host "Startup task installed."
Write-Host "Task name: $taskName"
Write-Host "It will refresh the Feishu callback stack when you log on to Windows."
Write-Host "If this machine blocks scheduled task registration, use install_feishu_callback_startup_shortcut.ps1 instead."
Write-Host ""
