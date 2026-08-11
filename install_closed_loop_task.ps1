# Full Closed Loop 定时任务 — Windows Task Scheduler

<#
.SYNOPSIS
  安装每日自动运行 Full Closed Loop 的 Windows 定时任务

.DESCRIPTION
  每天凌晨 2:00 自动执行完整闭环:
    ① 拉取 Facebook 数据
    ② FinalBandit 学习
    ③ Lovart 出图 + 自评
    ④ Facebook 上传 (如已配置 adset_id)

.PARAMETER ScheduleTime
  每天执行时间 (默认 02:00)

.PARAMETER Project
  目标项目 (默认 P04)

.PARAMETER Days
  Bandit 学习天数 (默认 7)

.EXAMPLE
  .\install_closed_loop_task.ps1
  .\install_closed_loop_task.ps1 -ScheduleTime "03:00" -Project "P04"
  .\install_closed_loop_task.ps1 -Project "P04" -Days 14
#>

param(
    [string]$ScheduleTime = "02:00",
    [string]$Project = "P04",
    [int]$Days = 7
)

$ErrorActionPreference = "Stop"

$TaskName = "MarketOps_FullClosedLoop"
$ProjectRoot = $PSScriptRoot
$PythonPath = (Get-Command python).Source
$ScriptPath = Join-Path $ProjectRoot "scripts\run_full_closed_loop.py"
$LogDir = Join-Path $ProjectRoot "output\logs"
$LogFile = Join-Path $LogDir "closed_loop_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# 确保日志目录存在
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# 构建命令
$Action = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --project $Project --days $Days 2>&1 | Out-File -FilePath `"$LogFile`" -Append"

$Trigger = New-ScheduledTaskTrigger -Daily -At $ScheduleTime

$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Write-Host "=" * 70
Write-Host "  安装 Full Closed Loop 定时任务"
Write-Host "=" * 70
Write-Host ""
Write-Host "  任务名:     $TaskName"
Write-Host "  执行时间:   $ScheduleTime (每天)"
Write-Host "  项目:       $Project"
Write-Host "  Python:     $PythonPath"
Write-Host "  脚本:       $ScriptPath"
Write-Host "  日志:       $LogDir"
Write-Host ""

# 先删除旧任务 (如果存在)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  删除旧任务..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 创建新任务
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Market Ops Full Closed Loop - 每日自动执行图片素材闭环"

Write-Host "  ✅ 定时任务已安装!"
Write-Host ""
Write-Host "  管理命令:"
Write-Host "    taskschd.msc                            # 打开任务计划程序"
Write-Host "    Get-ScheduledTask -TaskName '$TaskName' # 查看任务"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName' # 手动触发"
Write-Host "    Unregister-ScheduledTask -TaskName '$TaskName' # 删除任务"
Write-Host ""
Write-Host "  日志位置: $LogDir"
