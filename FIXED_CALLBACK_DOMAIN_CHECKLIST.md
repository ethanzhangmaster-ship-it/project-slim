# 固定回调地址落地检查清单

## 目标

把飞书回调地址从临时 `trycloudflare` 改成固定地址。

## 一、前置资源

至少满足下面一类：

### A. Cloudflare 固定 Tunnel

- Cloudflare 账号
- 已接入 Cloudflare 的域名
- 一个固定子域名

### B. 云服务器反向代理

- 一台公网服务器
- 一个固定域名或子域名
- 可登录服务器

## 二、我会做的改造

拿到资源后，我会继续改这些：

1. `start_feishu_callback_stack.ps1`
2. `refresh_feishu_callback_stack.ps1`
3. `check_feishu_callback_stack.ps1`
4. `show_feishu_callback_config.ps1`
5. `status_market_ops.ps1`
6. `doctor_feishu_bot.ps1`
7. `gate_weekly_release.ps1`

## 三、落地完成后要验证的点

1. 飞书后台回调地址不再变化
2. 重启电脑后机器人仍可恢复
3. 不需要重复改飞书后台
4. `check_feishu_callback_stack.ps1` 返回 OK
5. `doctor_feishu_bot.ps1` 返回 OK
6. `status_market_ops.ps1` 显示 callback health=OK

## 四、当前仍未完成的唯一外部项

固定公网回调地址。

除此之外，当前系统内部闭环已经基本完成。
