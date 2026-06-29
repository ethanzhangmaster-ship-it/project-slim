# 飞书详细版回复联调清单

目标：

- 周四固定群发：先发市场简版
- 群里有人 `@机器人` 并输入 `详细` / `详细版`
- 机器人在同一个群里回复：
  - 市场部周报详细版
  - 回收倍率增长周报

## 1. 本地配置

先检查这些字段已经存在于 [`.env`](C:/Users/ethan/Documents/市场会议/.env)：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_EVENT_VERIFICATION_TOKEN`
- `FEISHU_EVENT_PATH=/feishu/events`
- `FEISHU_DETAIL_TRIGGER_KEYWORDS=详细,详细版,周报详细版,详版`
- `FEISHU_DETAIL_ALLOWED_CHAT_IDS=`

先不要填 `FEISHU_DETAIL_ALLOWED_CHAT_IDS`。

第一次联调时，先让服务把真实 `chat_id` 打出来。
同时也会自动写入：

```text
output/active/feishu_detail_chat_observations.json
```

后面锁群时可以直接从这个文件复制。

## 2. 本地自检

先跑这两个命令：

```bash
python -m market_ops.cli feishu-event-check
python -m market_ops.cli feishu-event-allowlist-suggest
python -m market_ops.cli feishu-event-allowlist-apply
python -m market_ops.cli feishu-event-simulate --report-date latest --text "@机器人 详细版"
```

预期结果：

- `feishu-event-check` 显示“基本就绪”
- `feishu-event-simulate` 显示会回复两张卡

## 3. 启动服务

本地或服务器启动：

```bash
python -m market_ops.cli feishu-event-server --host 0.0.0.0 --port 8080
```

如果你有公网域名，假设是：

```text
https://your-domain.com
```

那么飞书后台里要填的回调地址就是：

```text
https://your-domain.com/feishu/events
```

## 4. 飞书开放平台配置

进入你的飞书应用后台，按下面配置：

1. 打开“事件订阅”
2. 启用事件订阅
3. 请求地址填：

```text
https://your-domain.com/feishu/events
```

4. Verification Token 填 `.env` 里的 `FEISHU_EVENT_VERIFICATION_TOKEN`
5. Encrypt Key 先留空，不启用加密
6. 订阅事件选择：

```text
im.message.receive_v1
```

7. 保存并通过 URL 校验

## 5. 第一次真实联调

去市场测试群发一条：

```text
@机器人 详细版
```

服务端日志会出现两类信息之一。

如果成功触发但还没锁群，会看到：

```text
Detailed reply trigger matched with no chat allowlist: chat_id=...
Detailed market reply sent: ...
```

这时把日志里的 `chat_id` 复制出来。

## 6. 锁定市场群

把拿到的 `chat_id` 填回 [`.env`](C:/Users/ethan/Documents/市场会议/.env)，或者在拿到真实 `oc_...` 群 ID 后直接运行：

```bash
python -m market_ops.cli feishu-event-allowlist-apply
```

如果你已经拿到了真实 `oc_...` 群 ID，也可以直接手动传入：

```bash
python -m market_ops.cli feishu-event-allowlist-apply --chat-id oc_xxx
```

这个命令会先自动备份 `.env`，再写回 `FEISHU_DETAIL_ALLOWED_CHAT_IDS`。

手动填写方式：

```env
FEISHU_DETAIL_ALLOWED_CHAT_IDS=oc_xxx
```

如果以后要允许多个群，用逗号分隔：

```env
FEISHU_DETAIL_ALLOWED_CHAT_IDS=oc_xxx,oc_yyy
```

然后重启服务。

## 7. 锁群后复测

再在市场测试群发一次：

```text
@机器人 详细版
```

预期：

- 市场测试群继续正常回复详细版
- 其他群即使 `@机器人 详细版`，也不会回复
- 服务端日志会打印：

```text
Detailed reply ignored for non-allowed chat: chat_id=...
```

## 8. 上线后固定规则

当前规则已经是：

- 定时群发只发简版
- `@机器人` 且命中关键词才回详细版
- 回复前先跑自检
- 自检失败只生成预览和自检报告，不发群

## 9. 常见问题

### URL 校验失败

优先检查：

- 回调地址是否能公网访问
- 路径是否是 `/feishu/events`
- `FEISHU_EVENT_VERIFICATION_TOKEN` 是否和飞书后台一致
- 是否错误开启了加密回调

### 群里 @ 了机器人但没回复

优先检查：

- 消息里是否包含 `详细` 或 `详细版`
- 应用是否已订阅 `im.message.receive_v1`
- 机器人是否在该群里
- 是否已经锁了 `FEISHU_DETAIL_ALLOWED_CHAT_IDS`
- 自检是否失败

### 回复了，但回错群

正常情况下不会。

当前实现不是用固定 webhook 二次转发，而是直接回复触发消息所在的群。
