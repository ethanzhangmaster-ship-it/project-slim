$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$activeDir = Join-Path $root "output\active"
$runtimeDir = Join-Path $root "output\runtime"
New-Item -ItemType Directory -Force -Path $activeDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$python = "C:\Users\ethan\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$envPath = Join-Path $root ".env"
$envText = ""
if (Test-Path $envPath) {
    $envText = Get-Content $envPath -Raw
}

$allowedChatIds = @()
$allowedLine = ($envText -split "`r?`n") | Where-Object { $_ -match "^FEISHU_DETAIL_ALLOWED_CHAT_IDS=" } | Select-Object -First 1
if ($allowedLine) {
    $value = ($allowedLine -replace "^FEISHU_DETAIL_ALLOWED_CHAT_IDS=", "").Trim()
    if ($value) {
        $allowedChatIds = $value.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
}

$startupDir = [Environment]::GetFolderPath("Startup")
$startupShortcut = Join-Path $startupDir "MarketMeeting-FeishuCallbackStack.lnk"
$shortcutInstalled = Test-Path $startupShortcut

$callbackTxt = Join-Path $activeDir "feishu_callback_live.txt"
$callbackJson = Join-Path $activeDir "feishu_callback_live.json"
$releaseGate = Join-Path $activeDir "weekly_release_gate_latest.md"
$metricsConsistency = Join-Path $activeDir "weekly_metrics_consistency_latest.md"

$callbackHealth = "UNKNOWN"
$callbackUrl = ""
if (Test-Path $callbackJson) {
    try {
        $cfg = Get-Content $callbackJson -Raw -Encoding UTF8 | ConvertFrom-Json
        $callbackUrl = [string]$cfg.callback_url
    } catch {
    }
}

try {
    powershell -ExecutionPolicy Bypass -File ".\check_feishu_callback_stack.ps1" *> $null
    if ($LASTEXITCODE -eq 0) {
        $callbackHealth = "OK"
    } else {
        $callbackHealth = "FAILED"
    }
} catch {
    $callbackHealth = "FAILED"
}

$latestGateStatus = "UNKNOWN"
if (Test-Path $releaseGate) {
    $gateText = Get-Content $releaseGate -Raw -Encoding UTF8
    if ($gateText -match "Status:\s+PASS") {
        $latestGateStatus = "PASS"
    } elseif ($gateText -match "Status:\s+FAIL") {
        $latestGateStatus = "FAIL"
    }
}

$statusPath = Join-Path $activeDir "market_ops_status_latest.md"
$statusJsonPath = Join-Path $activeDir "market_ops_status_latest.json"

$lines = @(
    "# Market Ops Status",
    "",
    "Generated at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "",
    "Core status:",
    "- callback health: $callbackHealth",
    "- callback url: $callbackUrl",
    "- startup shortcut installed: $shortcutInstalled",
    "- allowed group count: $($allowedChatIds.Count)",
    "- weekly release gate: $latestGateStatus",
    "",
    "Artifacts:",
    "- callback text: $callbackTxt",
    "- callback json: $callbackJson",
    "- weekly gate: $releaseGate",
    "- metrics consistency: $metricsConsistency",
    "",
    "Allowed groups:"
)

if ($allowedChatIds.Count) {
    foreach ($chatId in $allowedChatIds) {
        $lines += "- $chatId"
    }
} else {
    $lines += "- none"
}

$payload = @{
    generated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    callback_health = $callbackHealth
    callback_url = $callbackUrl
    startup_shortcut_installed = $shortcutInstalled
    allowed_group_count = $allowedChatIds.Count
    allowed_groups = $allowedChatIds
    weekly_release_gate = $latestGateStatus
    callback_text_path = $callbackTxt
    callback_json_path = $callbackJson
    weekly_gate_path = $releaseGate
    metrics_consistency_path = $metricsConsistency
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($statusPath, $lines, $utf8NoBom)
[System.IO.File]::WriteAllText($statusJsonPath, ($payload | ConvertTo-Json -Depth 4), $utf8NoBom)

Write-Host ""
Write-Host "Market Ops status generated."
Write-Host "Markdown: $statusPath"
Write-Host "JSON: $statusJsonPath"
Write-Host ""
