# Full Closed Loop — 上线 Checklist (v2.0)

> 最后更新: 2026-06-29
> 统一闭环脚本: `scripts/run_full_closed_loop.py`

---

## 前置条件

- [x] 有网络环境可访问 `graph.facebook.com`
- [x] `.env` 中 `META_ACCESS_TOKEN` 已配置
- [x] `.env` 中 `META_AD_ACCOUNT_ID` 已配置
- [x] Lovart API 凭证有效（`LOVART_ACCESS_KEY` + `LOVART_SECRET_KEY`）
- [x] DuckDB 数据库可读写
- [x] 统一闭环脚本 `scripts/run_full_closed_loop.py` 已创建
- [ ] `.env` 中 `CLOSED_LOOP_ADSET_ID` 已配置 (可选, 用于自动上传)
- [ ] `.env` 中 `CLOSED_LOOP_PAGE_ID` 已配置 (可选, 用于自动上传)

---

## Phase 1: 验证链路连通性

```bash
# Dry-run 检查所有模块是否正常
python scripts/run_full_closed_loop.py --dry-run
```

**验证**:
- [x] 所有核心模块可导入 (Pipeline, Lovart, Facebook Publisher, P04CreativeLoop)
- [x] 环境变量齐全 (META_*, LOVART_*)
- [x] 数据库存在

---

## Phase 2: 运行完整闭环 (Pipeline + 出图)

```bash
# 完整闭环 (不出图时跳过上传)
python scripts/run_full_closed_loop.py --project P04 --days 7

# 或分步执行:
# 仅 Pipeline
python scripts/run_full_closed_loop.py --pipeline-only
# 仅出图 (基于已有 pipeline 结果)
python scripts/run_full_closed_loop.py --generate-only
```

**输出文件**:
| 文件 | 说明 |
|------|------|
| `output/pipeline_strategy.md` | Bandit 投放策略报告 |
| `output/pipeline_prompts.md` | AI 裂变 prompt |
| `output/monitor/current_state.json` | Dashboard 数据 |
| `output/closed_loop/<run_id>/run_*.json` | 出图+评分结果 |
| `output/closed_loop/<run_id>/filter_result.json` | 过滤结果 |
| `output/closed_loop/<run_id>/images/` | 生成的图片 |

**验证**:
- [ ] Pipeline 完成 (Step 1-5 全部通过)
- [ ] 策略报告中有明确的 winner 特征
- [ ] 出图 10-20 张
- [ ] 评分 ≥6.0 的图片 ≥3 张

---

## Phase 3: 配置 Facebook 上传

在 `.env` 中添加:
```env
CLOSED_LOOP_ADSET_ID=<你的 adset ID>
CLOSED_LOOP_PAGE_ID=<你的 page ID>
```

**获取 adset_id**:
1. 打开 Facebook Ads Manager
2. 找到或创建一个 adset (建议 daily budget $20-50)
3. adset ID 在 URL 中: `.../adset/238XXXXXXXXXX`

**获取 page_id**:
1. 打开 Facebook Page Settings
2. Page ID 在 "Page Info" 中

---

## Phase 4: 完整闭环 (含上传)

```bash
# 完整闭环 + 上传 (PAUSED 状态)
python scripts/run_full_closed_loop.py --project P04 --days 7

# 自动激活 (谨慎使用!)
python scripts/run_full_closed_loop.py --project P04 --days 7 --auto-activate
```

**验证**:
- [ ] Facebook Ads Manager 中可见新广告 (状态: PAUSED 或 In Review)
- [ ] 图片与 prompt 描述一致
- [ ] 人工审核通过后手动激活广告

---

## Phase 5: 安装定时任务

```powershell
# 安装每日凌晨 2:00 自动运行的定时任务
.\install_closed_loop_task.ps1 -Project "P04" -Days 7

# 自定义时间
.\install_closed_loop_task.ps1 -ScheduleTime "03:00" -Project "P04"
```

**管理命令**:
```powershell
taskschd.msc                                           # 打开任务计划程序
Get-ScheduledTask -TaskName "MarketOps_FullClosedLoop"  # 查看任务
Start-ScheduledTask -TaskName "MarketOps_FullClosedLoop" # 手动触发
Unregister-ScheduledTask -TaskName "MarketOps_FullClosedLoop" # 删除
```

**验证**:
- [ ] 定时任务已安装
- [ ] 日志文件生成正常 (`output/logs/`)
- [ ] Monitor Dashboard 显示每日更新的 theta/sigma
- [ ] entropy 不崩塌
- [ ] 去重计数正常

---

## Phase 6: 7 天后评估

```bash
# 查看 Monitor Dashboard 数据
cat output/monitor/current_state.json

# 查看最新闭环结果
ls output/closed_loop/
```

**判定标准**:

| 指标 | PASS 条件 |
|------|-----------|
| theta 排序 | 与真实 ROAS 排序一致 |
| sigma 下降 | decline_ratio < 0.9 |
| entropy | 不崩塌 (> early × 0.3) |
| 图片评分 | avg ≥ 6.0 |
| 上传成功率 | ≥ 80% |
| 去重 | duplicate_reject 稳定 |

**如果全部 PASS** → 扩大维度，加入更多 gene_type，开启 P02/P07
**如果有 FAIL** → 检查数据质量，考虑调参

---

## 快速命令参考

```bash
# 验证链路
python scripts/run_full_closed_loop.py --dry-run

# 完整闭环 (不出图时不上传)
python scripts/run_full_closed_loop.py --project P04 --days 7

# 仅 Pipeline
python scripts/run_full_closed_loop.py --pipeline-only

# 仅出图
python scripts/run_full_closed_loop.py --generate-only

# 仅上传
python scripts/run_full_closed_loop.py --publish-only

# P07 项目
python scripts/run_full_closed_loop.py --project P07 --days 14

# 查看帮助
python scripts/run_full_closed_loop.py --help
```

---

## 风险提示

| 风险 | 缓解 |
|------|------|
| Token 过期 | 提前 7 天检查 token 有效期 |
| API rate limit | 每天只跑 1 次闭环 |
| Budget 超支 | campaign 设 daily budget cap, auto_activate=false |
| 图片审核不通过 | 人工预审 + 避免敏感内容 |
| 数据延迟回流 | rolling 7 天窗口覆盖 T+7 |
| Lovart SSL 异常 | 已降级修复 (verify=False fallback) |
