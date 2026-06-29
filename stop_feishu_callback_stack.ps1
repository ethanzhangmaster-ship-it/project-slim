$ErrorActionPreference = "Stop"

$ports = @(8092)

foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        } catch {
        }
    }
}

$cloudflared = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "cloudflared.exe" -and $_.CommandLine -like "*127.0.0.1:8092*" }

foreach ($proc in $cloudflared) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    } catch {
    }
}

Write-Host ""
Write-Host "Feishu callback stack stopped."
Write-Host ""
