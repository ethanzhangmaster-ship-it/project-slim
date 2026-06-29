$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$txtPath = Join-Path $root "output\active\feishu_callback_live.txt"

if (-not (Test-Path $txtPath)) {
    Write-Host ""
    Write-Host "No callback config found."
    Write-Host "Run .\\start_feishu_callback_stack.ps1 first."
    Write-Host ""
    exit 1
}

Write-Host ""
Get-Content $txtPath -Encoding UTF8
Write-Host ""
