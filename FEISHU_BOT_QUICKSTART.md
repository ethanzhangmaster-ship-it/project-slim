# 飞书机器人快速使用说明

## 这套机器人现在能做什么

1. 每周发送市场部周报
2. 在飞书群里通过 `@机器人` 返回简版、详细版、回收版、老板版

当前是固定指令模式，还不是自由问答。

## 先启动回调服务

先运行：

```powershell
.\start_feishu_callback_stack.ps1
```

这条命令会自动完成：

1. 启动本地回调服务
2. 启动公网临时地址
3. 生成最新地址说明文件

生成后的说明文件在：

`output/active/feishu_callback_live.md`

以后如果飞书后台需要重新填写回调地址，就以这份文件里的最新地址为准。

## 飞书后台怎么填

打开飞书开放平台应用后台，进入“事件订阅”，填写：

- 回调请求地址：看 `output/active/feishu_callback_live.md`
- Verification Token：看 `output/active/feishu_callback_live.md`
- Encrypt Key：看 `output/active/feishu_callback_live.md`

只勾选这个事件：

- `im.message.receive_v1`

## 群里怎么用

支持这些固定指令：

1. `@机器人 帮助`
2. `@机器人 简版`
3. `@机器人 详细版`
4. `@机器人 回收版`
5. `@机器人 老板版`
6. `@机器人 摘要`

含义：

- `简版`：返回市场简版周报
- `详细版`：返回发群前结论页 + 市场详细版 + 回收版
- `回收版`：只返回回收倍率增长周报
- `老板版`：返回发群前结论页 + 老板版
- `摘要`：只返回结论页

## 每周怎么发市场部周报

先做本地预览和检查：

```powershell
.\preview_weekly_reports.ps1
```

再正式发送市场群：

```powershell
.\send_market_weekly_all.ps1
```

## 系统默认规则

- 自检不过，不发群
- 审计不过，不发群
- 先生成本地预览，再决定是否发送
- 老板群默认仍然不自动发送

## 常见问题

### 群里 `@机器人` 没反应

优先检查：

1. 是否先运行了 `.\start_feishu_callback_stack.ps1`
2. 飞书后台回调地址是不是最新地址
3. 本地电脑有没有关掉服务
4. 指令是不是固定指令之一

### 飞书后台校验失败

优先检查：

1. 是否先运行了 `.\start_feishu_callback_stack.ps1`
2. 回调地址是否来自 `output/active/feishu_callback_live.md`
3. Token 和 Encrypt Key 是否与说明文件一致

### 周报发不出去

优先看这些文件：

- `output/active/self_check_*.md`
- `output/active/report_audit_*.md`
- `output/active/pre_send_summary_*.md`
- `output/active/weekly_health_check_*.md`

如果这些文件里写的是拦截或失败，就说明系统主动阻止了发群。
