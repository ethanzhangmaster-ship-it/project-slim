$ErrorActionPreference = "Stop"

$taskName = "MarketMeeting-FeishuCallbackStack"

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host ""
    Write-Host "Startup task removed."
    Write-Host "Task name: $taskName"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Startup task not found."
    Write-Host "Task name: $taskName"
    Write-Host ""
}
