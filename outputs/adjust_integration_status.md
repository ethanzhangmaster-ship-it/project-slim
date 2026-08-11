# Adjust DAU 自动接入 — 覆盖进度（E15.2.6.5）

> 更新于 2026-07-24 18:07。**关键更正**：ACCT_1（Bible/Trivia）经用户确认**根本不使用 Adjust**——其 DAU 手动兜底（`cli.py dau`）是**永久路径**，不是待替换的临时状态。因此"等 ACCT_1 独立 token"一项已消解。

## 账号覆盖矩阵

| 账号 | MAX 真实 app 数 | 已映射 Adjust token | 自动 DAU | mean DAU（07-14..07-23） | 状态 |
|------|----------------|---------------------|---------|--------------------------|------|
| **ACCT_2** | 6 | 6/6 | ✅ | ~6,067 | 全自动（含 Hospital Fever→Hospital Frenzy Amazon） |
| **ACCT_3** | 4 | 4/4 | ✅ | ~34 | 全自动；Drama Hospital→老 Drama Hospital 为**低置信**（待校准） |
| **ACCT_1** | — | 0/0 | ⚠️ 手动（设计如此） | — | **不使用 Adjust**（用户 2026-07-24 确认）→ 永久 `cli.py dau` 手动 |

## ACCT_3 映射明细（已落 credentials/live_accounts.json）

| MAX app | Adjust app | token | 置信 |
|---------|-----------|-------|------|
| Be A Master Chef | P15 Chef | `qmwlp0c43u9s` | 高 |
| Stella's Salon: Drama Makeover | P14 Salon | `p6fdx0g4j474` | 高 |
| Be a Super Model: Merge & Slay | P17 Super Model | `f1iig9pqo6ww` | 高 |
| Drama Hospital: Doctor ASMR | 老 Drama Hospital | `pa520bj5zw1s` | **低**（候选 P12 31-Drama DAU=0） |

## 本次顺带修复的健壮性

- **`pull_rows` 加 3 次退避重试**（1.5s×attempt）：修掉 MAX Report API 偶发 `SSL: UNEXPECTED_EOF_WHILE_READING` 直接 FAIL 的问题（历史与主拉取全覆盖）。
- **播种 `data/ACCT_3_report.json`（6290 行真实报表）** 作缓存基线：ACCT_3 首次自动化跑批若抖动，可经 `_replay_cache` 兜底（此前无缓存→兜底返 None→FAIL）。

## 验收

- `validate_e15_2_5.py` **259/0**、`validate_e15_2_4_v2.py` **73/0**，无回归。
- ACCT_3 端到端 `daily_briefing.py --no-notify`：OK 153.5s，H83/O18/R26，rev $58.17，2 actions，ARPDAU 护栏激活。
- 每日 09:30 自动化（automation-1784885330915）现已自动覆盖 **ACCT_2 + ACCT_3（Adjust 自动 DAU）+ ACCT_1（手动，设计如此）**。

## 仍需你拍板/提供的项

1. **ACCT_3 Drama Hospital 低置信映射**：若 ARPDAU 看起来明显偏低，改映射到 `P12 31-Drama`（DAU=0）或告诉我正确 Adjust app。
2. **Unity SDK 事件流** → 解锁 E15.2.7 Player Monetization Intelligence（Agent 2：Placement/Frequency A/B）。
3. （可选）ARPDAU 改真日均（除以窗口天数）：会改 manual 历史基线，待你定。

> 注：ACCT_1 不使用 Adjust 已记入金库 `_mapping_notes`，系统逻辑已天然支持（无映射→回落 ManualDropInProvider，不会空等 token）。无需代码改动。
