# 🌅 LaunchForge 每日全量晨报

_生成 2026-07-27 · 数据窗口 2026-07-17 ~ 2026-07-26_
_亮灯：1 账户正常 / 0 异常 · 舰队 1 款 · 新游机会 8 条_

## 1️⃣ 营收诊断 · Revenue OS

| 账户 | 健康 | 机会 | 风险 | 营收$ | 混合eCPM | 动作 |
|---|---|---|---|---|---|---|
| ACCT_TEST | 80 | 7 | 92 | 77.0 | 24.44 | 3 |

---

## 2️⃣ 真实舰队判决 · Fleet Verdicts

| SCALE | Winner Game | replicate pattern |

---

## 3️⃣ 新游机会 · Growth

_生成 2026-07-27 · 数据源：Growth OS（mock 信号（真实市场源未配置；接入后自动替换，流程不变））_

共发现 **8** 条去重机会，按综合分排序，Top 5：

| # | 机会 | 来源 | 综合分 | 目标市场 | 信号 |
|---|---|---|---|---|---|
| 1 | merge × vampire | [MOCK] | 0.792 | US,DE,JP | [MOCK] proven in our fleet (Merge Monster) + ... |
| 2 | word × zen | [MOCK] | 0.755 | US | [MOCK] word + relax niche trending on TikTok ... |
| 3 | sort × color | [MOCK] | 0.732 | US | [MOCK] sort/color emerging hypercasual->casua... |
| 4 | idle × tycoon | [MOCK] | 0.655 | US,BR | [MOCK] idle-tycoon CPI softening, eCPM holding |
| 5 | puzzle × block | [MOCK] | 0.655 | US,KR | [MOCK] block-puzzle evergreen; stable top-50 ... |

---

- 🟢 已落盘 `data/market_opportunities.json`，Factory Brain 自动进入 spec 流水线
- 🔧 真市场源（App Store 排名 / TikTok 话题 / Sensor Tower 等）接入后，
  仅需注册一个 adapter + 配 endpoint，整条链路不动
- 📌 本卡为只读发现，未对任一外部系统执行写操作

---

📎 完整明细见 outputs/daily_briefing/ 与 outputs/monetization_reports/