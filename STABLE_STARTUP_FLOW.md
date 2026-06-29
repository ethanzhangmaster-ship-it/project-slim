# 稳定启动流程

## 1. 启动机器人回调

先运行：

```powershell
.\refresh_feishu_callback_stack.ps1
```

这一步会自动完成：

1. 停掉旧服务
2. 重启本地回调服务
3. 重启临时公网地址
4. 输出最新地址

然后查看当前地址：

```powershell
.\show_feishu_callback_config.ps1
```

最新地址会同时写到：

- `output/active/feishu_callback_live.txt`
- `output/active/feishu_callback_live.md`
- `output/active/feishu_callback_live.json`

## 2. 做周报健康检查

先运行：

```powershell
python -m market_ops.cli health-check --report-date latest
```

重点看：

- `output/active/weekly_health_check_20260603.md`
- `output/active/self_check_20260603.md`
- `output/active/report_audit_20260603.md`
- `output/active/pre_send_summary_20260603.md`

只要这里显示“通过”或“可发送”，才进入正式发送。

## 3. 正式发送

市场群发送简版：

```powershell
python -m market_ops.cli market-send --report-date latest
```

市场群发送详细版：

```powershell
python -m market_ops.cli market-send --report-date latest --detailed
```

市场群一次发全套：

```powershell
python -m market_ops.cli market-send --report-date latest --all
```

老板版仍然默认锁住，不自动恢复。

## 4. 群里可直接用的指令

- `@机器人 帮助`
- `@机器人 简版`
- `@机器人 详细版`
- `@机器人 回收版`
- `@机器人 老板版`
- `@机器人 摘要`
- `@机器人 最新待办`
- `@机器人 最近待办`
- `@机器人 已批准任务`
- `@机器人 执行已批准任务`
- `@机器人 最近发送记录`

## 5. 如果群里没回复

按这个顺序检查：

1. `output/active/feishu_callback_live.txt`
2. `output/active/market_ops_status_latest.md`
3. `output/active/weekly_health_check_20260603.md`
4. `output/runtime/start_callback_run.log`
5. `output/runtime/feishu_event_server_8092.log`
6. `output/runtime/cloudflared_8092.log`

## 6. 清理测试发送记录

如果本地发送记录里混入了测试样本，运行：

```powershell
python -m market_ops.cli group-send-log-cleanup
```

清理后保留真实发送记录，移除测试群和测试消息样本。

## 7. 刷新状态台账

如需刷新当前回调状态、允许群数量、门禁状态，运行：

```powershell
.\status_market_ops.ps1
```

输出文件：

- `output/active/market_ops_status_latest.md`
- `output/active/market_ops_status_latest.json`
