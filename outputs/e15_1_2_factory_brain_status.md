# E15.1.2 — Autonomous Game Factory Brain · 状态报告

_落地日期：2026-07-27 · 全部绿灯 · 2026-07-27 加厚两大核心（Opportunity 预测 + Portfolio 决策）_

## 一句话

**Growth OS → Publishing Factory → Revenue OS 三条线第一次真正闭环**：AI 决定下一批该生产什么游戏、每天对 10–50 款组合下判断、把变现结果反哺回下一代产品。系统从「自动运营工具」升级为「AI 游戏公司操作系统」的大脑层。**确定性规则、不接 LLM、`real_api_called` 永久锁 False、所有决策 requires_manual_apply。**

## 验收结果

| 门 | 结果 |
|---|---|
| E15.1.2 pytest (`tests/e15_1_2/`) | **137 passed**（100 骨架 + 37 加厚）|
| E15.1.2 验收门 (`operation/validate_e15_1_2.py`) | **145 / 0 — FACTORY BRAIN READY** |
| E15.1.1 回归（pytest 120 + 验收门 128/0） | **无回归** |
| 合跑 e15_1_2 + e15_1_1 | **257 passed** |

## 2026-07-27 加厚：两大核心补齐用户 spec

按用户第二版 spec（Product Opportunity + Portfolio Decision 优先），在 flat 结构上新增 3 模块（不改目录、零回归）：

| 新模块 | 能力 | 对应 spec 盒子 |
|---|---|---|
| `opportunity_predictor.py` | 机会 → **CPI / D30_ROAS / D90_ROAS / confidence** 经济预测（确定性公式：竞争↑CPI↑、趋势↑CPI↓；D30 由 eCPM+LTV 驱动被 CPI 惩罚；D90≈D30×1.7 成熟；payback_ok=D90≥1.0）| §1 Product Opportunity Engine（prediction 块）|
| `blueprint_generator.py` | ProductSpec → **GameBlueprint**（core_loop / IAA / IAP / meta / ASO，按 genre 确定性表；hybrid 双端、纯 IAA 加 banner、纯 IAP 加 VIP）→ 可直接交 Unity Agent(E15.4) | §2 Game Blueprint Generator |
| `decision_engine.py` | 吃 **D1/D7 retention + CPI + ROAS + ARPDAU** → **KEEP / SCALE / KILL + 人类理由 + budget_delta% + payback_days**。幂律留存模型算 90 天回本；**实现 ROAS 为准原则**：已证明盈利(ROAS≥1.0)绝不被理论回本模型误杀；不回本(>90d)/漏桶(D1<20%)/流血(ROAS<0.30)才 KILL | §3 Portfolio Manager + §4 自动 Kill/Scale |

BrainReport 新增 `predictions` / `blueprints` / `verdicts` 三字段，`run_daily()` 一次产出。所有新决策同样 `requires_manual_apply=True`。

## 闭环架构（`operation/factory_brain/`，8 个源文件）

```
Growth OS ──(机会 drop-in JSON)──> OpportunityIntake ←──(舰队内生信号)
                                        │ 排名去重
PatternMiner ←──(舰队 revenue_per_dau)──┤
    │ SuccessPattern 权重 (0.5x–1.5x)   ↓
    └────────────────────────> SpecGenerator
                                        │ ProductSpec (product.yaml 形状)
                                        ↓
                               GameRegistry (status=development)
                                        │ → E15.1.1 Publishing Factory
PortfolioManager  每日 ROAS 决策表      │
AsoBandit         商店 listing 胜者→记忆 │
StoreExperimentPlanner  PPO/Play 实验计划│
                                        ↓
                               FactoryBrain.run_daily() → BrainReport
```

## 六大能力（对齐用户 spec）

1. **Opportunity → Factory**：`data/market_opportunities.json` drop-in 契约（与 Adjust DAU 同模式，Growth OS 是独立系统、零耦合）+ 舰队内生机会（自己已证明能变现的品类=市场信号）。评分=0.30·关键词趋势 + 0.25·(1−竞争) + 0.25·eCPM + 0.20·LTV。
2. **Product Spec Generator**：机会 → `ProductSpec`（genre/theme/target_geo/monetization/rewarded_focus/starter_pack/aso keywords，结构对齐 product.yaml 示例）→ `to_game_product()` 直接入舰队。低于 0.35 分不建。
3. **游戏矩阵管理（10–50 款）**：独立 `portfolio_state.json` 状态机 IDEA→PROTOTYPE→SOFT_LAUNCH→UA_TEST→SCALE（KILL 全局可达，不动冻结的 GameProduct 契约）。每日决策表：ROAS>1.0 加预算 / 0.5–1.0 继续优化 / <0.3 停 UA（SCALE 期=kill 候选）/ 广告收入占比≥75% 加强 IAA / IAP≥50% 加强礼包。
4. **Revenue → Publishing 反馈**：`PatternMiner` 按 (genre, monetization) 挖成功率（成功=revenue_per_dau≥$0.03，即全系统北极星 KPI），theme 从 PublishingMemory 截图胜者恢复；权重 0.5x–1.5x 乘入下一代 spec 置信度。**实测：merge+hybrid 两连胜 → 下批 merge spec 权重 1.5x 且自带 prior 注记。**
5. **ASO Bandit**：explore-then-commit（每变体≥500 曝光、胜者需领先≥1pt CVR），胜者写入 PublishingMemory（"Merge Magic Castle 25% > Build Your Kingdom 18%" → 记住 pattern）。JSONL 试验日志，CVR 观测由人工/商店后台导出填入。
6. **商店实验规划**：安装率跌 20%（相对基线）或 <10%（绝对）触发 → 自动生成 5 icon + 3 截图序 + 5 文案变体计划（复用 E15.1.1 asset pipeline），人工贴入 PPO / Play Store listing experiments。

## 安全边界（与全系统一致）

- 所有 PortfolioDecision / StoreExperimentPlan `requires_manual_apply=True`——大脑不花钱、不杀游戏、不碰商店。
- `run_daily(register_specs=False)` 默认只提案；`=True` 才把新品入库为 development（仍需人决定是否真的开发）。
- 舰队硬顶 50 款；已运营的 (genre, theme) 永不重复提案。
- `real_api_called` 恒 False。

## 关键实测行为（烟测 6 款合成舰队）

- 机会排名：growth_os merge/witch 0.71 > fleet_merge 0.695 > word/zen 0.385 > 弱机会 0.1（被 0.35 阈值挡掉）
- 决策：p002 ROAS 1.4→加预算；p004 ROAS 0.22→停 UA；p006 SCALE 期 ROAS 0.25→kill 候选；p001 广告占比 90%→加强 IAA
- 已运营 merge/witch 自动去重，转而提案 merge/fantasy（theme 来自记忆里的截图胜者）

## 还没做（诚实边界）

- Growth OS 真实机会数据尚未流入（drop-in 契约已就绪，等 Growth OS 侧写文件）
- ROAS 数据目前靠 GameProduct.metrics 人工/脚本填充（UA 平台 API 未接）
- ASO CVR 观测人工录入（商店 console API 未接）
- 未接每日 09:30 automation（可与 daily_briefing 并跑，待用户确认再挂）

## 下一步候选

1. 把 FactoryBrain.run_daily 挂进每日 automation + 飞书日报（「今天该建什么/该杀什么」卡片）
2. Growth OS 侧真实机会数据落 drop-in 文件
3. 真实商店 API（第二优先级，省人工不增收）
