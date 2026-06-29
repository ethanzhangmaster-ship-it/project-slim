param(
    [string]$TaskName = "Market Ops Weekly Market Group Send",
    [string]$At = "15:00"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $Root "send_market_weekly_all.ps1"

if (-not (Test-Path $ScriptPath)) {
    throw "Missing sender script: $ScriptPath"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Thursday -At $At
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Description "Runs Market Ops source sync, self-check, report audit, pre-send summary, then sends simple market, detailed market, and recovery cards only when all gates pass." `
    -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName every Thursday at $At"
