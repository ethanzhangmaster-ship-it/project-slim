# P3.4 — Portfolio Optimization Contract（组合层资源配置器契约）

> 状态：定义中（实现前锁定）
> 依赖扫描：复用面审计已在 #567 完成（Explore agent 全量扫描 + 签名核对）。本契约所有数据字段均有明确上游来源，未新增任何指标计算。

---

## 1. 定位（组合层资源配置器，不是单游戏策略优化器）

P3.4 **不是** Decision Engine，也**不是** Strategy Engine。它是跨游戏「有限预算 / 有限运营资源」下的**排序 + 分配模拟器**：

```
上游已算好的产物（只读消费）
  E17 Reality Snapshot  ─┐
  P1.7 Reality Confidence┤
  P2.5 Execution Monitor ├─► PortfolioOptimizer ─► PortfolioRecommendation
  P2.6 Recovery 经验流   │     (rank → simulate → guard)
  P3.3 Strategy Memory   │            │
  E15.1.2 Lifecycle      ─┘            ↓
                         PortfolioRecommendation
                                │
                                ↓  (只产出建议，不执行)
                          P3.2 CEO Report（新增 Section）
                                │
                                ↓  下游
                          E17.3 Decision Engine → ExecutionContract → ...
```

职责一句话：**在有限资源下，回答「多游戏之间如何排序、预算如何分配」，并只产出 `PortfolioRecommendation`（三态：AUTO / APPROVAL / BLOCKED），由 E17.3 与执行链落地。**

纪律红线（继承全库 + P3.3.3）：
- **❌ 不重新计算 ROAS / spend / revenue / retention**。这些全部来自 `GrowthRealitySnapshot`（E17.1/P1.6.4），P3.4 只读。
- **❌ 不替代 E17.3 Decision Engine**。P3.4 产出 `PortfolioVerdict`（SCALE/MAINTAIN/REDUCE/SUNSET/NO_SCALE）级别的**组合建议**，绝不直接生成 `PAUSE_CAMPAIGN` / `DISABLE_NETWORK` 等执行动作。
- **❌ 不直连 Provider、不调 `SafeExecutor`**。保持 `Recommendation → Simulation → Approval → Execution` 链路，P3.4 停在 Recommendation。
- 复用不重写；确定性规则，不接 LLM。

---

## 2. 文件布局（新增 `src/operator/portfolio/`，薄层 + 消费者）

```
src/operator/portfolio/
├── __init__.py        # 统一出口（兼容用）；新代码按阶段从子模块导入
├── models.py          # 【P3.4.1】纯快照模型层：GamePortfolioSnapshot / PortfolioSnapshot
│                      #   / PortfolioSignal + StrategySource/ExecutionSource
│                      #   /RecoverySource/LifecycleSource
│                      #   ❗不含评分/判决/推荐模型（见 ranking_models.py）
├── assembler.py       # 【P3.4.1】PortfolioAssembler：多源读取→字段映射→PortfolioSnapshot
├── ranking_models.py  # 【P3.4.2+】PortfolioScore / PortfolioVerdict(enum)
│                      #   / AllocationCandidate / PortfolioRecommendation
├── ranker.py          # 【P3.4.2】PortfolioRanker：多游戏排序
├── allocation_models.py # 【P3.4.3】模拟结果模型（AllocationSimulationResult / GameAllocation
│                      #   / AllocationDelta / ConstraintCheck / 枚举 / REAL_API_CALLED）
├── constraints.py    # 【P3.4.3】AllocationConstraints + validate()（预算守恒 / 挪动上限 / 储备下限）
├── simulator.py      # 【P3.4.3】AllocationSimulator：what-if 资源迁移**模拟器**（只模拟不执行）
├── proposal.py        # 【P3.4.4】Portfolio Decision Proposal（内嵌 Rule0~3 安全闸门；
│                      #   SimulationResult → PortfolioProposal，只建议不执行）
├── optimizer_models.py # 【P3.4.5】编排 I/O 壳：OptimizationStatus /
│                      #   PortfolioOptimizationInput / PortfolioOptimizationResult
│                      #   （含 to_report_section() 供 CEO 报告消费）
└── optimizer.py       # 【P3.4.5】PortfolioOptimizer 编排：validate→rank→simulate→
│                      #   propose→assemble + build_portfolio_optimizer()
│                      #   （消费侧）src/operator/report/sections.py::
│                      #   build_portfolio_recommendation_section(result) 把结果
│                      #   收敛成 CEO 报告「Portfolio Recommendation」段
```

> **命名澄清**：§1/§4.5 的 `PortfolioRecommendation`（位于 `ranking_models.py`）
> 是早期契约名。P3.4.5 实际顶层出参为 `PortfolioOptimizationResult`
> （`optimizer_models.py`），概念上即「组合推荐（只建议不执行）」；
> CEO 报告段标题沿用 `Portfolio Recommendation`。`PortfolioRecommendation`
> 旧类保留为兼容导出，不再作为编排顶层。

> **§2 修订（P3.4.1 落地时）**：原设计把 `PortfolioScore` / `PortfolioVerdict` /
> `AllocationCandidate` / `PortfolioRecommendation` 放在 `models.py`。但 P3.4.1 的边界是
> **「只建模型、不计算、不排序、不产生 Action」**——`PortfolioScore.compute()` 含评分计算、
> `PortfolioRecommendation` 属 Action 语义，留在 `models.py` 会污染模型层。
> 故拆出 `ranking_models.py` 由 P3.4.2+ 拥有；`models.py` 保持纯快照层，
> 并由 `tests/p3_4_1/test_contract_boundary.py` 静态锁定（越界即失败）。

复用入口（已核对签名，详见 §3 审计表）：

| 复用对象 | 精确签名 | 用途 |
|---|---|---|
| E17.1 `GrowthRealitySnapshot` | `revenue.daily_revenue`, `acquisition.spend/roas`, `product.dau/retention/release_status`, `creative.fatigue_score`, `confidence/real_confidence/real_domains` | 收入/花费/ROAS/留存/疲劳/置信原始读数 |
| P1.6.4 `DailyRealityStore` | `data/reality/<gid>/<date>.json` 读取 → `GrowthRealitySnapshot` | assembler 拉单游戏当日快照 |
| P1.7 `ConfidenceScorer` | `score_game(game_id, coverage, freshness, consistency) -> RealityScore`；`RealityScore.composite`（=coverage×freshness×consistency, 0-1） | 每游戏现实置信分（Confidence 因子） |
| E15.1.2 `PortfolioManager` | `stage_of(game_id) -> LifecycleStage`（IDEA/PROTOTYPE/SOFT_LAUNCH/UA_TEST/SCALE/KILL） | 生命周期阶段（GrowthPotential 因子） |
| E17.7 `GrowthMemoryGraph` | `success_rate_by(strategy_type=None, domain=None, action_type=None, game_id=None) -> float` | 每游戏策略成功率（策略证据） |
| E17.7 `extract_patterns(graph)` | `-> List[GraphPattern]`（`success_rate`, `samples`, `avg_revenue_delta`, `confidence_boost`） | 学到的模式证据 |
| P3.3 `StrategyMemoryAdapter` | `build_insights(graph=None) -> List[StrategyInsight]`（`historical_success_rate`, `samples`, `avg_reward`, `recommendation`） | 策略经验证据 |
| P2.5 `ExecutionMonitor` | `compute_health_score(outcomes) -> ExecutionHealthScore`（`.score`, `.level`, `.success_rate`） | 执行健康分（ExecutionHealth 因子） |
| P2.6 `RecoveryEngine` | `JsonlRecoveryExperienceStore.stats(failure, recovery="") -> {n, success_rate, avg_reward}`；`RecoveryIncident.target`（game_id） | 恢复率证据（可选因子） |
| P3.2 `CEODailyReport` | `report_id, date, health_summary, opportunities, actions, risks, learning_summary, execution_summary, real_api_called`；便捷 `auto_actions/approval_actions/blocked_actions` | 报告挂载体 |
| P3.2 `ActionState` / `CEOActionStatus` | `ActionState.AUTO/APPROVAL/BLOCKED`；`CEOActionStatus.EXECUTED/AWAITING_APPROVAL/PREVENTED` | 三态收敛（沿用，不新造） |
| E16.6.12 `ASOResourceAllocator` | `allocate(ranked_scores, games, total_creative_budget, total_localization_budget, total_experiment_budget)`（Top20%→50% / Mid40%→30% / Bot40%→20%） | **只借鉴分配范式形状**，不复用类 |
| E16.1.4 `PortfolioIntelligence` | `evaluate(entries: List[GamePortfolioEntry]) -> PortfolioReport`（`PortfolioDecision.verdict`=SCALE/MAINTAIN/REDUCE/SUNSET/REPLICATE, `score`, `confidence`） | 可选：作为 SCALE/MAINTAIN 判定的补充信号 |

---

## 3. 复用资产审计结论

| 现有资产 | 路径 | 复用决策 |
|---|---|---|
| E16.1.4 组合智能 | `src/revenue_intelligence/portfolio.py` | 复用其 `PortfolioDecision.verdict` 语义作 P3.4 `PortfolioVerdict` 参考；不依赖其实现 |
| E16.6.12 ASO 资源分配 | `src/aso_intelligence/portfolio/resource_allocator.py` | **只借鉴「按排名比例切预算」形状**（Top20%→50%…），不复用类；P3.4 是单一预算池 |
| E15.1.2 生命周期 | `operation/factory_brain/portfolio_manager.py` | 复用 `PortfolioManager.stage_of(game_id)` 取 lifecycle_stage |
| E17.10 组合仪表盘 | `src/ceo_intelligence/portfolio_dashboard/aggregator.py` | 下游消费者，P3.4 结果可并行喂入，本阶段不耦合 |
| E17.1 现实快照 | `src/growth_reality/models.py` | 核心数据来源（只读） |
| P1.7 现实置信 | `src/growth_reality/validation/confidence.py` | Confidence 因子来源 |
| P2.5 执行监控 | `src/execution/monitor/` | ExecutionHealth 因子来源 |
| P2.6 自动恢复 | `src/execution/recovery/` | RecoveryRate 证据来源 |
| P3.3 策略记忆 | `src/operator/strategy/memory.py` | 策略成功率证据来源 |
| P3.3.3 自适应策略 | `src/operator/adaptive_strategy/` | 不依赖；P3.4 在其下游消费策略成功信号 |
| P3.2 CEO 报告 | `src/operator/report/` | 报告集成目标（新增 Section） |

**结论**：现成「跨游戏预算/优先级分配器」不存在，P3.4 分配器是新代码；但应复用 `ASOResourceAllocator` 的分配范式、消费 `GrowthRealitySnapshot`/`ConfidenceScorer`/`PortfolioManager`/`GrowthMemoryGraph` 的既有读数，并沿用 P3.2 三态呈现。

---

## 4. 核心契约

> **归属提示**：§4.1 / §4.3 / §4.4 / §4.5 的模型位于 **`ranking_models.py`（P3.4.2+）**；
> 只有 §4.2 `GamePortfolioSnapshot` 及 `PortfolioSnapshot` / `PortfolioSignal`
> 位于 **`models.py`（P3.4.1 纯快照层）**。详见 §2 修订说明。

### 4.1 `PortfolioVerdict`（组合层动作，非执行动作）— `ranking_models.py`

```python
class PortfolioVerdict(str, Enum):
    SCALE     = "scale"      # 扩量（申请增量预算）
    MAINTAIN  = "maintain"   # 维持现状（小幅维系预算）
    REDUCE    = "reduce"    # 收缩（减量预算）
    SUNSET    = "sunset"    #  sunset（大幅减量/止损）
    NO_SCALE  = "no_scale"  # 观察期，不扩量（新游戏 <7d）
```

### 4.2 `GamePortfolioSnapshot`（只读上游产物组装，绝不重算）

```python
@dataclass
class GamePortfolioSnapshot:
    game_id: str
    revenue: float                       # ← GrowthRealitySnapshot.revenue.daily_revenue
    spend: float                        # ← GrowthRealitySnapshot.acquisition.spend
    roas: float                         # ← GrowthRealitySnapshot.acquisition.roas
    confidence: float                   # ← ConfidenceScorer.RealityScore.composite (0-1)
    lifecycle_stage: str                # ← PortfolioManager.stage_of(game_id).value
    strategy_score: float               # ← GrowthMemoryGraph.success_rate_by(game_id=) (0-1)
    execution_health: float            # ← ExecutionMonitor.compute_health_score(...).score (0-1)
    retention: float = 0.0              # ← GrowthRealitySnapshot.product.retention
    creative_fatigue: float = 0.0      # ← GrowthRealitySnapshot.creative.fatigue_score
    recovery_rate: float = 1.0         # ← RecoveryEngine 经验流 per-game（可选，缺省中立 1.0）
    data_age_days: int = 0              # ← P3.4 自跟踪 first_seen（见 §6，非重算）
    has_reality: bool = True            # ← 是否有当日快照（False → Rule0 BLOCK）
```

> **data_age_days 来源说明**：上游 registry / reality 均不含 `first_seen`。P3.4 维护自有 `data/portfolio_memory.jsonl`（append-only），记录每 `game_id` 首次观测日期。这是 P3.4 的**观察元数据**，不计算任何经济指标，符合「只消费」纪律。`data_age_days = (as_of - first_seen).days`。

### 4.3 `PortfolioScore`（4 因子乘积，不是收入排序）

```python
@dataclass
class PortfolioScore:
    game_id: str
    revenue_quality: float     # clamp(roas / 1.5, 0, 1)
    growth_potential: float    # 0.5*lifecycle + 0.3*retention_factor + 0.2*(1-fatigue)
    confidence: float          # = snapshot.confidence
    execution_health: float    # = snapshot.execution_health
    score: float               # = product of above (0-1)
    # 支持证据（不进入乘积，仅用于 reason 文本与排序 tie-break）
    strategy_score: float      # = snapshot.strategy_score
```

因子归一（确定性）：
- `revenue_quality = clamp(roas / 1.5, 0.0, 1.0)`（roas≥1.5 → 1.0）
- `lifecycle_factor`: SCALE=1.0, UA_TEST=0.85, SOFT_LAUNCH=0.70, PROTOTYPE=0.45, IDEA=0.25, KILL=0.0
- `retention_factor = clamp(retention / 0.4, 0.0, 1.0)`（40% D1 留存视为强）
- `fatigue_factor = clamp(creative_fatigue, 0.0, 1.0)`；`(1 - fatigue_factor)` 即低疲劳=高潜力
- `growth_potential = 0.5*lifecycle_factor + 0.3*retention_factor + 0.2*(1 - fatigue_factor)`
- `score = revenue_quality * growth_potential * confidence * execution_health`

### 4.4 `AllocationCandidate`（分配器 + 闸门出参）

```python
@dataclass
class AllocationCandidate:
    game_id: str
    rank: int                           # 排序后的名次（1-based）
    portfolio_score: float             # §4.3 score
    recommended_action: PortfolioVerdict
    recommended_budget_delta: float    # 模拟增量（可为负）；第一阶段不执行
    priority: float                    # = round(portfolio_score * 100, 2)，展示用
    confidence: float                  # = snapshot.confidence
    action_state: ActionState          # AUTO / APPROVAL / BLOCKED（闸门后）
    reason: str                        # WHY：引用 roas/conf/lifecycle/strategy/fatigue 证据
    strategy_score: float = 0.0       # 支持证据
```

### 4.5 `PortfolioRecommendation`（顶层出参，挂 P3.2 报告）

```python
@dataclass
class PortfolioRecommendation:
    as_of: str
    candidates: List[AllocationCandidate]
    total_recommended: float          # Σ 正向 delta
    auto_count: int
    approval_count: int
    blocked_count: int
    notes: List[str] = field(default_factory=list)
```

---

## 5. 评分与排序（ranker.py）

**输入**：`List[GamePortfolioSnapshot]`
**输出**：`List[AllocationCandidate]`（含 `portfolio_score`，`rank` 已填，但 `action_state` 留待 guard 填）

排序规则（确定性）：
1. 计算每游戏 `PortfolioScore.score`；
2. 按 `score` 降序；同分按 `revenue` 降序；再同分按 `game_id` 升序；
3. `rank = 1..N`；
4. `recommended_action` 初判（未经闸门）：
   - `score >= 0.6` 且 lifecycle ∈ {SCALE, UA_TEST} → `SCALE`
   - `score >= 0.4` → `MAINTAIN`
   - `score < 0.25` → `REDUCE`
   - lifecycle == KILL → `SUNSET`
   - 其余 → `MAINTAIN`

> 排序因子表（来自用户规格，已锚定上游来源）：

| 因子 | 来源 |
|---|---|
| Revenue trend / ROAS | E17.1 Reality Snapshot |
| Strategy success | P3.3 / E17.7 |
| Execution health | P2.5 Monitor |
| Recovery rate | P2.6 Recovery |
| Confidence | P1.7 Confidence |

---

## 6. 预算分配模拟器（P3.4.3 — simulator.py，只模拟不执行）

> **§6 修订（P3.4.3 落地时）**：原设计把分配器命名为 `allocator.py`、直接把 `recommended_budget_delta`
> 填回 `AllocationCandidate`。实际落地改为「what-if 资源迁移模拟器」独立成层，输出
> `AllocationSimulationResult`（baseline / proposed / delta / 约束检查 / verdict / risk / confidence），
> 不动 `AllocationCandidate` 字段、不产生执行动作。故拆为三文件：`allocation_models.py`
> （结果模型）+ `constraints.py`（约束与校验）+ `simulator.py`（模拟算法）。

**输入**：
```python
AllocationSimulator.simulate(
    snapshot:  PortfolioSnapshot | List[PortfolioSnapshot],  # baseline 取各游戏 spend
    ranking:   List[AllocationCandidate],                    # 提供 recommended_action 与 portfolio_score
    constraints: AllocationConstraints(total_budget, max_shift_ratio=0.2, min_reserve_ratio=0.1),
) -> AllocationSimulationResult
```

**输出**（`AllocationSimulationResult`，详见 `allocation_models.py`）：

- `baseline_allocation: List[GameAllocation]` / `proposed_allocation: List[GameAllocation]` / `delta: List[AllocationDelta]`
- `constraints_checked: List[ConstraintCheck]`（non_empty / budget_conservation / per_game_shift_cap / reserve_floor / non_negative / total_shift_warn）
- `verdict: SimulationVerdict(PASS | BLOCKED)`、`risk: RiskLevel(LOW | MEDIUM | HIGH)`、`confidence: float`、`explanation: str`
- `real_api_called` **恒 `False`**（由 `REAL_API_CALLED` 常量锁死）

**模拟算法（确定性、纯资源约束）**：

1. `baseline_i = snapshot.spend`（`None` → 0，`known=False`）；
2. 按 `recommended_action` 给方向权重：`SCALE=+1.0` `MAINTAIN=+0.2` `NO_SCALE=0` `REDUCE=-0.5` `SUNSET=-1.0`；
3. 负向权重游戏释放资金（`freed = Σ|负向delta|`），正向权重游戏按 `portfolio_score` 占池比例吸收；
4. **缩放正向 delta 使 `Σdelta == 0`**（预算守恒，绝不生/灭预算）；
5. `proposed_i = baseline_i + delta_i`（设计保证 `proposed ≥ 0`）；
6. 跑 `AllocationConstraints.validate(...)` 收敛 `verdict`；`risk` 由挪动比例定（非收入预测）；`confidence` = `(已知比例 + 排名覆盖率) / 2`（模拟可信度，**不是** E17.3 / P1.7 confidence）。

**约束语义**：

- `max_shift_ratio`：单游戏 `|delta| / total_budget` 上限；超限 → `per_game_shift_cap` **BLOCKED**；
- `min_reserve_ratio`：战略储备下限，`reserve = total_budget - Σproposed` 必须 ≥ 此比例（等价任一游戏占比 ≤ `1 - min_reserve_ratio`）；不足 → `reserve_floor` **BLOCKED**；
- 预算守恒失败 / 负分配 / 空组合 → 对应规则 **BLOCKED**；总挪动超软阈值（0.35）仅 **WARN**。

**纪律（硬）**：

- ❌ **不预测收入**（无 `new_revenue = old_revenue * multiplier`）；只挪钱，不推断 revenue。
- ❌ 不重算 ROAS / spend / revenue；只读 `snapshot.spend` 作 baseline。
- ❌ 不修改 E17.3 Decision；不替代 StrategyMutation；不调 Provider / `SafeExecutor`。
- ❌ 不产生 `ExecutionRequest` / `ExecutionContract` / `ExecutionIntent`；不绕过 P2.3 Approval；不自动调预算。
- ✅ `real_api_called` 恒 `False`。

---

## 7. 安全边界（内嵌于 proposal.py 的 PortfolioGuard）

> **§7 修订（P3.4.4 落地时）**：原契约把 P3.4.4 设计为独立 `guard.py`。实际落地改为
> 「Portfolio Decision Proposal」——`proposal.py` 内嵌 `PortfolioGuard`（Rule0~3 闸门），
> 由 `ProposalGenerator.propose(simulation, ranking, snapshot, constraints, data_age_days=None)`
> 把 `AllocationSimulationResult` 转换成 `PortfolioProposal`（recommendation-only）。
> 闸门仍是 Rule0~3，三态仍复用 P3.2 `ActionState.AUTO / APPROVAL / BLOCKED`，不新造枚举。
> `data_age_days` 由上游可选注入（来自 P3.4 自跟踪 registry，未注入则跳过 Rule3）。

`PortfolioGuard.evaluate(game, delta, current_spend, data_age_days=None) -> GuardOutcome(action_state, triggered_rules, evidence)`：

| 规则 | 条件 | 结果 |
|---|---|---|
| Rule0 | `not snapshot.has_reality` | `BLOCKED`（无现实数据不决策） |
| Rule2 | `snapshot.confidence < 0.5` | `BLOCKED`（Reality Confidence 不足） |
| Rule3 | `snapshot.data_age_days < 7` | `recommended_action = NO_SCALE` + `BLOCKED`（观察窗口不足） |
| Rule1 | `|delta| / max(current_spend, eps) > 0.30` | `APPROVAL`（需人工审批，不阻断，保留 delta） |
| 默认 | 其余 | `AUTO` |

- Rule2 / Rule3 为硬阻断；Rule1 为升级审批（仍给 delta，但标 `APPROVAL`）；
- 三态严格落在 `ActionState.AUTO / APPROVAL / BLOCKED`，不新造枚举；
- `reason` 必须含触发规则编号与证据值（如 `confidence=0.32<0.5 → BLOCKED`）。

---

## 8. 报告集成（P3.4.5，接 P3.2）

> **§8 状态（P3.4.5 落地时）**：本阶段完成「消费侧」最小闭环——`PortfolioOptimizationResult`
> 已可被 CEO 报告段读取，满足 Case6（「PortfolioRecommendation section 可消费
> PortfolioOptimizationResult」）。具体落地：

- ✅ `src/operator/report/sections.py`：新增 `build_portfolio_recommendation_section(result) -> dict`
  （纯函数、延迟导入避免耦合、不重算不决策）；`result.to_report_section()` 提供
  `{title, status, summary, recommendation, guard_verdict, confidence, items, real_api_called}`；
- ⏳（后续，非 P3.4.5 强制）：`CEODailyReport.portfolio_reco` 字段、`renderer` 段落、
  `builder` kwarg、`P3.1` 调度器插入 `portfolio` 阶段、`AllocationCandidate → CEOAction`
  收敛。这些属于「报告渲染 + 调度接入」，Case6 只要求消费能力已具备。

`PortfolioOptimizationResult` 经 `to_report_section()` 后即可并入 CEO 报告正文；最终路径
严格为：`PortfolioProposal → CEO Daily Report → Human / E17.3 Review → Approval → Execution`。

---

## 9. 门面与装配（optimizer.py）

> **§9 修订（P3.4.5 落地时）**：原契约设想 `build_portfolio_optimizer(...)` 注入
> registry / reality_store / confidence_scorer 等并暴露 `run(daily, ...)`。实际落地
> 遵循「编排器只接收已就绪的 `PortfolioOptimizationInput`」原则（快照/排名/约束由上游
> 组装好再传入），编排器内部用默认 `build_*` 工厂驱动 ranker/simulator/proposer。
> 这更贴合「只编排不重算」纪律，也避免编排器反向依赖数据层。

**实际签名**：

```python
@dataclass
class PortfolioOptimizationInput:
    snapshots: PortfolioSnapshot | List[PortfolioSnapshot]
    rankings: List[AllocationCandidate] = []          # 非空则跳过内部重排
    constraints: AllocationConstraints
    current_allocation: Dict[str, float] = {}          # 仅作证据/对账，不覆写 baseline
    data_age_days: Optional[Dict[str, int]] = None     # 注入 Rule3 闸门
    as_of: str = ""

class PortfolioOptimizer:
    def __init__(self, ranker=None, simulator=None, proposer=None): ...
    def optimize(self, input: PortfolioOptimizationInput) -> PortfolioOptimizationResult: ...

def build_portfolio_optimizer(ranker=None, simulator=None, proposer=None) -> PortfolioOptimizer
```

`PortfolioOptimizer.optimize(input)` 编排顺序（严格）：

1. **validate**：合并 snapshot；无游戏 → `INSUFFICIENT_DATA`；
2. **rank**：`rankings` 非空则采用，否则 `ranker.rank(games)`；空候选 → `INSUFFICIENT_DATA`；
3. **simulate**：`simulator.simulate(snapshot, ranked, constraints)`；
4. **propose**：`proposer.propose(simulation, ranked, snapshot, constraints, data_age_days)`；
5. **assemble**：`status` = BLOCKED（模拟或提案被阻断）/ 否则 COMPLETED；产出
   `PortfolioOptimizationResult`（含 `proposal` / `simulation` / `ranked_games` /
   `evidence` / `real_api_called=False`）。

**纪律（硬）**：编排器**不覆盖**下层 BLOCKED 标记（模拟/提案说 BLOCKED，编排就如实
BLOCKED）；不重算 ROAS/spend/revenue/LTV；不调 `src.execution` / `ProviderRouter` /
`SafeExecutor`；不产生 `ExecutionRequest` / `Action`；不 mutate 入参；`real_api_called`
恒 `False`。

---

## 10. 测试 Case（目标 60–80 tests，覆盖 #573）

| # | 文件 | 场景 | 关键断言 |
|---|---|---|---|
| 1 | test_models | GamePortfolioSnapshot / PortfolioScore 构造 | score = 四因子乘积；clamp 边界（roas=3.0→rq=1.0） |
| 2 | test_ranker | 多游戏排序（用户 Case1） | 按 score 降序、tie-break revenue→game_id 确定性；rank 连续 |
| 3 | test_ranker | 生命周期因子 | SCALE 比 PROTOTYPE growth_potential 高；KILL→SUNSET |
| 4 | test_allocator | 预算模拟（用户 Case2） | SCALE 池按 score 比例切 available_budget；MAINTAIN/REDUCE/SUNSET delta 符号正确；不执行（无 Provider 调用） |
| 5 | test_guard | 低 confidence 阻断（用户 Case3） | confidence<0.5 → BLOCKED |
| 6 | test_guard | 大额变化进审批（用户 Case4） | delta/spend>0.30 → APPROVAL |
| 7 | test_guard | 数据不足 | data_age<7 → NO_SCALE + BLOCKED |
| 8 | test_guard | 无现实数据 | has_reality=False → Rule0 BLOCKED |
| 9 | test_report | 三态收敛 | PortfolioRecommendation → CEOAction 三态分组正确 |
| 10 | test_integration | 完整链（用户 Case5） | Reality→Strategy Feedback→Portfolio→CEO Report 串联产出 PortfolioRecommendation 段；`real_api_called=False` |
| 11 | test_integration | 边界 | available_budget=0 / 空游戏列表 / 全部 BLOCKED 不抛错 |

> 测试纪律：所有路径纯内存对象 + fake/mock 上游（snapshot / confidence / graph / monitor）；**绝不**构造真实 `MaxClient`/`MetaClient`；**绝不**调用 `SafeExecutor`。双版本串行回归：managed 3.13 + ci311 3.11。

**P3.4.3 验收 Case（实际落地，`tests/p3_4_3/`）**：

| # | 文件 | 场景 | 关键断言 |
|---|---|---|---|
| 1 | test_simulator | 正常模拟（Case1） | PASS；SCALE 吸收 REDUCE 释放；预算守恒；confidence=1.0；risk=MEDIUM |
| 2 | test_simulator | 超挪动上限（Case2） | `per_game_shift_cap` BLOCKED；risk=HIGH |
| 3 | test_simulator | 预算守恒（Case3） | `Σproposed == Σbaseline`；`Σdelta ≈ 0` |
| 4 | test_simulator | 空组合（Case4） | `non_empty` BLOCKED；`real_api_called=False` |
| 5 | test_simulator | real_api_called（Case5） | 结果 `real_api_called` 恒 `False`；常量锁死 |
| 6 | test_simulator | 无执行请求（Case6） | 结果是 `AllocationSimulationResult`；源码不引用 `ExecutionRequest` |
| 7 | test_simulator | risk 等级 | LOW（微挪）/ HIGH（超 max_shift_ratio） |
| 8 | test_simulator | confidence 公式 | 已知比例 / 排名覆盖率 各降 → 0.75 |
| 9 | test_simulator | 软告警 WARN | gross>0.35 仅 WARN，不阻断 |
| 10 | test_simulator | 无迁移边界 | 全 REDUCE / 缺排名 → delta=0 |
| 11 | test_simulator | 序列化 + 输入兼容 | result/constraints roundtrip；接受 `List[PortfolioSnapshot]` |
| 12 | test_contract_boundary | 边界锁（AST） | simulator/allocation_models/constraints 不引用执行层 / 不预测收入；变异测试确认锁会触发 |

**P3.4.4 验收 Case（实际落地，`tests/p3_4_4/`）**：

| # | 文件 | 场景 | 关键断言 |
|---|---|---|---|
| 1 | test_proposal | 正常提案（全 AUTO） | `guard_verdict=PROPOSABLE`；confidence=1.0；`real_api_called=False` |
| 2 | test_proposal | Rule0 无现实数据 | 无 revenue/spend/roas → BLOCKED，`rule0_no_reality` |
| 3 | test_proposal | Rule2 低置信 | `confidence=0.30<0.5` → BLOCKED，`rule2_low_confidence` |
| 4 | test_proposal | Rule3 观察不足 | `data_age_days=3<7` → NO_SCALE + BLOCKED，`rule3_insufficient_data_age` |
| 5 | test_proposal | Rule1 大额挪动 | `\|delta\|/spend>0.30` → APPROVAL（保留 delta），`guard_verdict=PARTIAL` |
| 6 | test_proposal | 默认 AUTO | 小挪动 → AUTO，无触发规则 |
| 7 | test_proposal | 置信公式 | AUTO 全权 / APPROVAL 折半；模拟阻断再折损 0.5 |
| 8 | test_proposal | 证据链 / 人可读 | `evidence_chain` 含预算守恒 + 不发出执行请求；`recommendation` 含游戏/动作/三态 |
| 9 | test_proposal | 空模拟 | SimulationResult 空 → BLOCKED，items 空，`real_api_called=False` |
| 10 | test_proposal | 序列化 / 输入兼容 / 不可变 | roundtrip；接受 `List[PortfolioSnapshot]`；不改动入参 |
| 11 | test_proposal | 真实链路 | `AllocationSimulator`→`ProposalGenerator` 条目数==游戏数，计数守恒 |
| 12 | test_contract_boundary | 边界锁（AST） | proposal.py 不引用执行层 / 不预测收入 / 不定义越界方法；复用 `ActionState`；变异测试确认锁会触发 |

**P3.4.5 验收 Case（实际落地，`tests/p3_4_5/`）**：

| # | 文件 | 场景 | 关键断言 |
|---|---|---|---|
| 1 | test_optimizer | 完整链路（Case1） | Snapshot→Rank→Simulation→Proposal→Result；`status=COMPLETED`；`real_api_called=False`；排名确定（高分在前）；含 AUTO 项 |
| 2 | test_optimizer | 空 Portfolio（Case2） | 无游戏 → `INSUFFICIENT_DATA`；`proposal=None`/`simulation=None`/`ranked_games=[]` |
| 3 | test_optimizer | 模拟 BLOCKED（Case3） | `reserve_floor` 阻断 → `status=BLOCKED`；**不覆盖**下层标记（`proposal.is_blocked=True`） |
| 4 | test_optimizer | 输入不可变（Case4） | 优化后 `snapshot.games` / `rankings` 未被 mutate；编排器无状态（二次调用一致） |
| 5 | test_optimizer | real_api_called（Case5） | 结果 / 提案 / 模拟 `real_api_called` 均 `False`；常量 `REAL_API_CALLED is False` |
| 6 | test_optimizer | CEO 报告集成（Case6） | `build_portfolio_recommendation_section(result)` 返回 `{title,status,items,...}`；`real_api_called=False`；不携带执行请求字段；`INSUFFICIENT_DATA` 段不崩；错类型抛 `TypeError` |
| 7 | test_optimizer | 状态枚举 / 序列化 / 兼容 | `OptimizationStatus` 三值；COMPLETED/INSUFFICIENT roundtrip 一致；接受 `List[PortfolioSnapshot]`；`rankings` 提供则跳过重排；`current_allocation` 进 evidence |
| 8 | test_contract_boundary | 边界锁（AST，Case7） | optimizer.py / optimizer_models.py 不引用执行层（`src.execution`/`Provider`/`Meta`/`MAX`/`DecisionEngine`/`calculate_roas`/`predict_revenue`/`estimate_ltv`）；不预测收入；不定义越界方法；变异测试确认锁会触发 |

> P3.4.5 共 **33 测试**（test_optimizer 21 + test_contract_boundary 14）。

---

## 11. Do / Don't

**Do**
- 只读 `GrowthRealitySnapshot` / `ConfidenceScorer` / `PortfolioManager` / `GrowthMemoryGraph` / `ExecutionMonitor` / `RecoveryEngine` 既有读数；
- 复用 `ASOResourceAllocator` 的「按排名比例切预算」范式；
- 沿用 P3.2 `ActionState` 三态做建议级别；
- 把可选上游（graph / monitor / recovery）做成可注入，便于测试；
- `real_api_called` 恒 `False`（纯分析层）。

**Don't**
- ❌ 不重算 ROAS / spend / revenue / retention；
- ❌ 不替代 E17.3 Decision Engine，不直接生成执行动作；
- ❌ 不 import / 调用任何具体 Provider，不调 `SafeExecutor`；
- ❌ 不新造三态枚举（复用 `ActionState`）；
- ❌ 不在第一阶段执行预算变更（allocator 只模拟）。

---

## 12. Definition of Done（#568~#573 验收）

- [x] `src/operator/portfolio/` 10 源文件就位（models / assembler / ranking_models / ranker / allocation_models / constraints / simulator / proposal / optimizer / optimizer_models）+ `__init__.py`，namespace import 正常；
- [x] `GamePortfolioSnapshot` 全部字段有上游来源，无重算；data_age 自跟踪不触经济指标；
- [x] `PortfolioRanker` 排序确定性通过（Case1/3）；
- [x] `AllocationSimulator` 只模拟不执行（Case2/11）；
- [x] `PortfolioGuard`（内嵌于 proposal.py）Rule0~3 正确（Case rule0/1/2/3）；
- [x] `PortfolioProposal` 由 `AllocationSimulationResult` 生成，含 evidence chain / 人可读建议 / 三态（Case1/8）；
- [x] `PortfolioOptimizer`（P3.4.5）编排 validate→rank→simulate→propose→assemble，只编排不决策，`status` 不覆盖下层 BLOCKED（Case1~5）；
- [x] P3.2 报告消费侧闭环：`build_portfolio_recommendation_section(result)` 可消费 `PortfolioOptimizationResult`（Case6；CEODailyReport 字段/renderer 段落/调度接入为后续）；
- [x] 双版本串行回归零回归（managed 3.13 全绿 2406 passed；ci311 3.11 P3.4.5 自身 33 passed），新基线记录（2339 → 2406）；
- [x] 记忆更新：MEMORY.md 标记 P3.4.5 Closed + 新基线数字。
