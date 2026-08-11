# P3.3 Autonomous Strategy Loop — Contract

> 阶段定位：**Strategy Feedback Controller**（策略反馈控制器）。
> 连接 `P3.2 CEO Report → P2.5 Monitor → P2.6 Recovery → E17.7 Pattern Memory → Strategy Mutation → 下一轮 E17 Decision`，
> 形成 `Observe → Evaluate → Learn → Adjust → Execute(经闸门) → Measure ↺` 的自进化闭环。
>
> 它**不是**「自动决策 Agent」，也**不替代** E17.3 Decision Engine。它只调整*长期策略参数*，单次决策仍由 E17.3 负责。

---

## 1. 职责分离（不可违背）

| 模块 | 职责 | 是否由 P3.3 改动 |
|------|------|------------------|
| E17.2 Opportunity | 发现问题 | 否 |
| E17.3 Decision | 单次决策 | **否（绝不修改）** |
| P2 Execution | 执行动作 | 否（P3.3 不调 Provider） |
| P2.5 Monitor | 观察结果 | 否（只读） |
| E17.7 Memory | 存储经验（action-level） | 否（复用，不重造） |
| **P3.3 Strategy Loop** | **调整长期策略参数** | **是（本层唯一新增）** |

P3.3 只做四件事：**读**历史结果、**聚**成策略级经验、**提**策略调整建议、**标**责任状态。
它**不**重新计算 ROAS、**不**调用 Provider、**不**绕过 Approval、**不**修改 E17.3 Decision、**不**直改生产。

---

## 2. 复用地图（来自 P3.3.0 扫描，零重造）

| 来源 | 复用方式 | 具体接口 |
|------|----------|----------|
| E17.7 Pattern Memory | **READ + CALL** | `extract_patterns(graph)` → `List[GraphPattern]`（含 strategy_type/domain/action_type/success_rate/avg_revenue_delta/confidence_boost）；`record_outcome(graph, execution_id, revenue_delta)` 回写收入 |
| E17.7 Graph | **READ** | `self.ctx.agent.pipeline.memory_graph`（`GrowthMemoryGraph`，与 E17.9 同实例）；默认 `data/ceo/memory_graph.jsonl` |
| P2.5 FeedbackBridge | **READ** | `ExecutionExperienceRecord`（action/reward/success/execution_id）；`observe_batch` 已自动回流 |
| P2.6 RecoveryMemoryBridge | **READ** | `RecoveryResult.status`、`RecoveryExperienceRecord`（failure/recovery/reward） |
| E17.4 StrategyType | **READ** | 8 值策略分类（creative_refresh/ua_scale/ua_stop_loss/aso_optimization/monetization/revenue_recovery/retention/release_health），作为 strategy 维度 |
| E17.9 DailyRunResult | **READ** | `daily.actions`（`DailyActionItem`：kind/game_id/action/decision_audit_id/opportunity_type）；`dec_report` 提供 confidence/risk（经 `decision_audit_id` 关联） |
| P3.2 build_ceo_report | **CALL** | `build_ceo_report(..., patterns=...)` 已支持把策略学习点写入决策单「今日学习」段 |

**关键纪律**：E17.7 是 action-level 经验；P3.3 在其上新增一层 **strategy-level 经验**（`StrategyState` 持久化于 `strategy_memory.jsonl`，不复用图谱存储），二者职责清晰、不混用。

---

## 3. 目录布局（薄层，6 文件）

```
src/operator/strategy/
├── models.py        # StrategyState / StrategyFeedback / StrategyProposal / StrategyInsight / StrategyLoopResult / BusinessOutcome / StrategyStatus
├── evaluator.py     # OutcomeEvaluator：Action + ExecutionResult + BusinessOutcome → StrategyFeedback（零重算）
├── memory.py        # StrategyMemoryAdapter：连 E17.7（READ patterns）+ 维护 strategy-level 经验（boost/penalize/disable）
├── mutation.py      # StrategyMutationEngine：历史绩效 → StrategyProposal（requires_simulation=True）
├── guard.py         # StrategyGuard：Mutation → Simulation → Approval → Execution 链路门禁；禁止直改生产
├── loop.py          # StrategyLoop：Observe→Evaluate→Learn→Adjust→Emit（不执行）
└── __init__.py
```

---

## 4. 核心 Contract

### StrategyState（策略长期状态，P3.3 新增的经验单元）
```python
class StrategyStatus(str, Enum):
    ACTIVE = "active"
    LEARNING = "learning"
    DISABLED = "disabled"

@dataclass
class StrategyState:
    strategy_id: str          # e.g. "network_cleanup" / StrategyType.value
    dimension: str            # "monetization" / "ua" / "creative" / "aso"
    parameters: Dict[str, Any]
    confidence: float
    performance: Dict[str, Any]   # wins, losses, reward_sum, samples, last_outcome, consecutive_failures
    status: StrategyStatus = ACTIVE
```

### StrategyFeedback（单次动作→策略反馈，P3.3.1 核心产物）
```python
@dataclass
class StrategyFeedback:
    action_id: str
    strategy_id: str
    reward: float             # [-1, 1]，由业务结果衍生
    outcome: str              # "SUCCESS" / "FAILURE" / "NEUTRAL"
    evidence: str
    timestamp: str = ""       # 空串（确定性）
```

### StrategyProposal（建议修改策略，非 Decision）
```python
@dataclass
class StrategyProposal:
    current_strategy: str
    proposed_change: str      # 人类可读的变更描述
    expected_impact: str
    confidence: float
    requires_simulation: bool # 恒 True（guard 强制）
```

### StrategyInsight（P3.3.1 交付物：过去执行结果→策略洞察）
```python
@dataclass
class StrategyInsight:
    strategy_id: str
    dimension: str
    historical_success_rate: float
    samples: int
    avg_reward: float
    recommendation: str       # "boost" / "reduce" / "disable" / "hold"
    rationale: str
```

### StrategyLoopResult（一轮循环交付物）
```python
@dataclass
class StrategyLoopResult:
    insights: List[StrategyInsight]
    proposals: List[StrategyProposal]      # 已过 guard（gated）的建议
    states: Dict[str, StrategyState]       # 更新后的策略状态
    feedbacks: List[StrategyFeedback]
```

---

## 5. Pipeline 插入点

当前 12 阶段：`reality → audit → opportunities → simulations → decisions → approval → executions → monitor → recovery → memory → ceo_report → report`

P3.3 在 **`memory` 与 `ceo_report` 之间**插入 `strategy_loop`：

```
monitor → recovery → memory → strategy_loop → ceo_report → report
```

理由：CEO Report 展示「今天发生了什么」；Strategy Loop 产出「未来应该怎么变」，应先算好再喂给决策单的「今日学习」段（`build_ceo_report(patterns=...)`）。

最小改动：
- `src/operator/models.py`：新增 `STAGE_STRATEGY = "strategy_loop"`，插入 `ALL_STAGES` 的 `memory` 之后、`ceo_report` 之前，并加入 `__all__`。
- `src/operator/pipeline.py`：`runner` 元组插入 `(STAGE_STRATEGY, self._strategy_loop)`；新增 `_strategy_loop(date, s, run_id)` 方法，从 `s["daily"]` / `s["exec_report"]` / `s["recoveries"]` 读取，从 `self.ctx.agent.pipeline.memory_graph` 读取图谱，调用 `StrategyLoop.run(...)`，把 `insights/proposals/states` 存入 `s`，并把 `insight_lines` 透传给 `_ceo_report` 的 `build_ceo_report(patterns=...)`。
- 落盘：`outputs/operator/<date>/{strategy_insights.json, strategy_proposals.json, strategy_states.json}`。

---

## 6. 分阶段 Scope

### ✅ 本阶段实现（P3.3.1 + P3.3.2 脚手架）
- **P3.3.1 Strategy Feedback Loop**：读过去执行结果（E17.7 patterns + 当日 actions 三态）→ 生成 `StrategyInsight`。
- **经验更新**：success → confidence↑（Case1）；5 次连续失败 → `DISABLED`（Case2）。
- **P3.3.2 Mutation Proposal**：突变引擎产出 `StrategyProposal`（`requires_simulation=True`），经 `StrategyGuard` 校验后进入 *Simulation Queue*（仅产出，**不执行**）。

### ⏸ 本阶段不做（P3.3.3 Adaptive Strategy，后续）
- **不**把 Proposal 自动灌入真实 Simulation Engine 并 Approval→Execution。
- **不**调用 Provider、不修改 Decision、不直改 `meta`/生产参数。
- 链路 `Proposal → Simulation → Approval → Execution` 的*执行出口*留待 P3.3.3，本阶段只把 Proposal 作为「建议」落到文件与决策单。

---

## 7. 测试重点（预计 60~100 tests）

- **Case1 成功经验增强**：10 次成功 + 高 reward → `StrategyState.confidence` 提升。
- **Case2 连续失败降权**：5 次失败 → `status == DISABLED`。
- **Case3 不越权**：`StrategyLoop.run` 不调用 Provider、不修改 `dec_report`、不触发任何执行；可注入「执行即抛」的 spy 验证。
- **Case4 Simulation Gate**：任意 `StrategyProposal.requires_simulation == True`；`StrategyGuard` 拦截 `requires_simulation=False` 的生产变更。
- **集成 Case**：P3.1 Run → Strategy Loop → 决策单含策略学习点；双版本串行回归零回归。

---

## 8. Do / Don't 纪律

**Do**
- 只读 E17.7 / P2.5 / P2.6 / DailyRunResult；复用 `extract_patterns`、`build_ceo_report`。
- 策略经验持久化到独立 `strategy_memory.jsonl`（不污染图谱）。
- 所有建议一律 `requires_simulation=True` 进 Simulation Queue。

**Don't**
- 不重算 ROAS / 不重新判断机会 / 不调 Provider。
- 不绕过 P2.3 Approval / 不修改 E17.3 Decision。
- 不直改生产参数（meta）—— 任何变更都必须先过 Simulation 闸门。

---

## 9. Definition of Done

- `python scripts/run_daily_operator.py --date 2026-07-31` 在既有三文件外，新增 `outputs/operator/2026-07-31/{strategy_insights.json, strategy_proposals.json, strategy_states.json}`，且 `daily_report.md` 的「今日学习」段包含策略洞察/建议。
- `tests/p3_3/` 5+ 文件、60~100 tests 全过，含 Case1–Case4。
- 双版本串行回归（managed 3.13.12 + ci311 3.11.15）零回归。
- 标记 P3.3.1 Closed（P3.3.3 留作后续）。
