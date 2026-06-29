$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$jsonPath = Join-Path $root "output\active\feishu_callback_live.json"

if (-not (Test-Path $jsonPath)) {
    Write-Host ""
    Write-Host "No callback config found."
    Write-Host "Run .\\start_feishu_callback_stack.ps1 first."
    Write-Host ""
    exit 1
}

$python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$script = @'
import json
from pathlib import Path
import requests

cfg = json.loads(Path("output/active/feishu_callback_live.json").read_text(encoding="utf-8"))
resp = requests.post(
    cfg["callback_url"],
    json={
        "type": "url_verification",
        "challenge": "health_check",
        "token": cfg["verification_token"],
    },
    timeout=20,
)
print(resp.status_code)
print(resp.text)
if resp.status_code != 200:
    raise SystemExit(1)
if "health_check" not in resp.text:
    raise SystemExit(1)
'@

try {
    $responseText = $script | & $python -
    if ($LASTEXITCODE -ne 0) {
        throw "python callback check failed"
    }
    $parts = $responseText -split "`r?`n"
    $statusCode = $parts[0]
    $bodyText = ($parts | Select-Object -Skip 1) -join "`n"
    $raw = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ""
    Write-Host "Callback status: OK"
    Write-Host "Callback URL: $($raw.callback_url)"
    Write-Host "HTTP status: $statusCode"
    Write-Host "Response: $bodyText"
    Write-Host ""
} catch {
    $raw = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ""
    Write-Host "Callback status: FAILED"
    Write-Host "Callback URL: $($raw.callback_url)"
    Write-Host "Error: $($_.Exception.Message)"
    Write-Host ""
    exit 1
}
