$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startupDir = [Environment]::GetFolderPath("Startup")
$launcherPath = Join-Path $root "start_feishu_callback_stack_detached.ps1"
$shortcutPath = Join-Path $startupDir "MarketMeeting-FeishuCallbackStack.lnk"

if (-not (Test-Path $launcherPath)) {
    throw "start_feishu_callback_stack_detached.ps1 not found"
}

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$launcherPath`""
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 7
$shortcut.Description = "Auto start Feishu callback stack for Market Meeting bot"
$shortcut.Save()

Write-Host ""
Write-Host "Startup shortcut installed."
Write-Host "Shortcut: $shortcutPath"
Write-Host ""
