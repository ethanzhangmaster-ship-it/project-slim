$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$runtimeDir = Join-Path $root "output\runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$tempPy = Join-Path $runtimeDir "doctor_feishu_bot_tmp.py"

Write-Host ""
Write-Host "Step 1/3: callback health check"
powershell -ExecutionPolicy Bypass -File ".\check_feishu_callback_stack.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "callback health check failed"
}

Write-Host "Step 2/3: current callback config"
powershell -ExecutionPolicy Bypass -File ".\show_feishu_callback_config.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "show callback config failed"
}

$script = @'
from pathlib import Path
import os
import subprocess
import sys

root = Path.cwd()
env_path = root / ".env"
if not env_path.exists():
    raise SystemExit(".env not found")

allowed = []
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("FEISHU_DETAIL_ALLOWED_CHAT_IDS="):
        value = line.split("=", 1)[1].strip()
        if value:
            allowed = [item.strip() for item in value.split(",") if item.strip()]
        break

print("")
print("Step 3/3: group reply simulation")
if not allowed:
    print("No allowed chat ids configured.")
    raise SystemExit(0)

help_text = "@" + chr(0x673A) + chr(0x5668) + chr(0x4EBA) + " " + chr(0x5E2E) + chr(0x52A9)
detail_text = "@" + chr(0x673A) + chr(0x5668) + chr(0x4EBA) + " " + chr(0x8BE6) + chr(0x7EC6) + chr(0x7248)

for chat_id in allowed:
    print("")
    print(f"Testing group: {chat_id}")
    cmd_help = [sys.executable, "-m", "market_ops.cli", "feishu-event-simulate", "--report-date", "latest", "--chat-id", chat_id, "--text", help_text]
    result_help = subprocess.run(cmd_help, cwd=root)
    if result_help.returncode != 0:
        raise SystemExit(f"simulate help failed for {chat_id}")
    cmd_detail = [sys.executable, "-m", "market_ops.cli", "feishu-event-simulate", "--report-date", "latest", "--chat-id", chat_id, "--text", detail_text]
    result_detail = subprocess.run(cmd_detail, cwd=root)
    if result_detail.returncode != 0:
        raise SystemExit(f"simulate detail failed for {chat_id}")

print("")
print("Feishu bot doctor finished.")
'@

[System.IO.File]::WriteAllText($tempPy, $script, (New-Object System.Text.UTF8Encoding($false)))
& $python $tempPy
if ($LASTEXITCODE -ne 0) {
    throw "doctor_feishu_bot failed"
}

Write-Host ""
