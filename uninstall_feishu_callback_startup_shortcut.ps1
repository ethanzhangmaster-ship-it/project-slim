$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupDir "MarketMeeting-FeishuCallbackStack.lnk"

if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host ""
    Write-Host "Startup shortcut removed."
    Write-Host "Shortcut: $shortcutPath"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Startup shortcut not found."
    Write-Host "Shortcut: $shortcutPath"
    Write-Host ""
}
