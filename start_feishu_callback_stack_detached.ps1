$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$runner = Join-Path $root "refresh_feishu_callback_stack.ps1"
$outLog = Join-Path $root "output\runtime\refresh_callback_detached.out.log"
$errLog = Join-Path $root "output\runtime\refresh_callback_detached.err.log"

if (-not (Test-Path $runner)) {
    throw "refresh_feishu_callback_stack.ps1 not found"
}

Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-File", $runner `
    -WorkingDirectory $root `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden

Write-Host ""
Write-Host "Detached refresh started."
Write-Host "Wait about 10 to 20 seconds, then run:"
Write-Host ".\\show_feishu_callback_config.ps1"
Write-Host ""
