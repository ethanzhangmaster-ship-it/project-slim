$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "Step 1/4: stop old callback stack..."
powershell -ExecutionPolicy Bypass -File ".\stop_feishu_callback_stack.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "stop_feishu_callback_stack.ps1 failed"
}

Write-Host "Step 2/4: start fresh callback stack..."
powershell -ExecutionPolicy Bypass -File ".\start_feishu_callback_stack.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "start_feishu_callback_stack.ps1 failed"
}

Write-Host "Step 3/4: check callback health..."
powershell -ExecutionPolicy Bypass -File ".\check_feishu_callback_stack.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "check_feishu_callback_stack.ps1 failed"
}

Write-Host "Step 4/4: show current callback config..."
powershell -ExecutionPolicy Bypass -File ".\show_feishu_callback_config.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "show_feishu_callback_config.ps1 failed"
}

Write-Host ""
Write-Host "Feishu callback stack refresh finished."
Write-Host "If Feishu backend needs a new address, copy it from output\\active\\feishu_callback_live.txt"
Write-Host ""
