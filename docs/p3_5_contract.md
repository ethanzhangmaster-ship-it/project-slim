# P3.5 — Growth Knowledge Graph / CEO Memory Consolidation Contract

> 状态：底座优先里程碑（Closed，2026-07-30）。只读、不写回、不接消费端。
> 复用面审计：复用 E17.7 `GrowthMemoryGraph`，扩展其 schema，不新建 store。

---

## 1. 定位（跨源 consolidated 知识图谱，只读底座）

P3.5 **不是** 新的分析引擎，也**不是** 决策/执行层。它是把当前分散在 5 个 memory 源的「经验」沉淀成一张可跨源查询的图谱，让 AI CEO 从「规则执行器」升级为「有经验的操盘手」。

```
5 个分散 memory 源（只读消费）
  E17.7 Graph (extract_patterns)  ─┐
  P3.3 Strategy Memory            ├─► GrowthKnowledgeGraph.consolidate()
  E17.6 Execution Memory          │     (只读吃 5 源 -> 往 E17.7 图加高层节点)
  E16 Recovery Experience         │            │ 幂等
  P3.4.5 Portfolio 结果           ─┘            ↓
                                  扩展后的 E17.7 图（新增 7 NodeType / 8 EdgeType）
                                            │
                                            ↓  (只读查询)
                                  why_game_succeeded / similar_games /
                                  strategy_results_by_success / strategy_for_lifecycle
```

职责一句话：**在只读前提下，回答 P3.5 三个核心问题**——（1）为什么这个游戏过去成功？（2）类似情况以前怎么处理？（3）哪个策略在什么生命周期有效？

纪律红线（比 P3.4 更严——只读）：
- **❌ 不写回任何 5 个源**（`strategy_memory.save` / `execution_memory.record` / `recovery_store.add` / `graph.record_outcome` 一律不调）。`consolidate` 只「读」源、只往 E17.7 图「加」高层节点。
- **❌ 不决策、不执行、不调 Provider**；**❌ 不重算 ROAS / revenue / LTV**。
- **✅ `real_api_called` 恒 `False`**（纯分析层）。
- **✅ 幂等**：重复 `consolidate` 不产生重复节点/边（E17.7 图键去重）。
- 复用不重写；确定性规则，不接 LLM。

---

## 2. 文件布局（复用 `src/ceo_intelligence/growth_memory_graph/`）

```
src/ceo_intelligence/growth_memory_graph/
├── models.py          # 已扩 7 NodeType + 8 EdgeType（见 §3）
├── store.py           # GrowthMemoryGraph（复用，落盘 data/ceo/...jsonl）
├── patterns.py        # extract_patterns（复用，产出 GraphPattern）
├── ingest.py          # event_from_*（复用）
├── agent.py           # GrowthMemoryGraph Agent / run_pipeline（复用）
├── knowledge_models.py # 【P3.5.1】5 个 consolidated 实体 dataclass
│                      #   GrowthPattern / StrategyResult / ExecutionOutcome
│                      #   / RecoveryHistory / PortfolioDecision
│                      #   （包 GraphNode via to_node()/from_node()）
├── knowledge.py       # 【P3.5.2】GrowthKnowledgeGraph：
│                      #   consolidate() 只读吃 5 源 + 查询 API
├── signals.py         # 【P3.5.1】KnowledgeSignal（经验信号 dataclass）+ 修正函数
├── advisor.py         # 【P3.5.1】GrowthKnowledgeAdvisor：
│                      #   advise_portfolio / advise_strategy（只读消费图）
├── feedback.py        # 【P3.5.2】DecisionKnowledgeRecord + KnowledgeFeedbackRecorder
│                      #   （唯一 Graph 写入口，只写图不碰 5 源）
└── quality.py         # 【P3.5.3】MemoryQualityGovernor（只读质量门：score/decay/conflict/filter）
```

测试：`tests/p3_5/`（18 项）；`tests/p3_5_1/`（15 项）；`tests/p3_5_2/`（24 项）；`tests/p3_5_3/`（29 项）。

---

## 3. Schema 扩展（在 E17.7 之上）

`models.py` `NodeType` 新增：

| NodeType | 含义 |
|---|---|
| `CREATIVE_PATTERN` | 创意模式（domain=creative） |
| `UA_PATTERN` | 买量模式（domain=ua） |
| `MONETIZATION_PATTERN` | 变现模式（domain=monetization） |
| `STRATEGY_RESULT` | 策略结果（来自 P3.3 Strategy Memory） |
| `EXECUTION_OUTCOME` | 执行结果（来自 E17.6 Execution Memory） |
| `RECOVERY_HISTORY` | 恢复经验（来自 E16 Recovery） |
| `PORTFOLIO_DECISION` | 组合决策（来自 P3.4.5 结果） |

`EdgeType` 新增：

| EdgeType | 含义 |
|---|---|
| `HAS_CREATIVE_PATTERN` / `HAS_UA_PATTERN` / `HAS_MONETIZATION_PATTERN` | 游戏 → 模式节点 |
| `HAS_STRATEGY_RESULT` | 游戏 → 策略结果节点 |
| `HAS_EXECUTION_OUTCOME` | 游戏 → 执行结果节点 |
| `HAS_RECOVERY_HISTORY` | 游戏 → 恢复经验节点 |
| `HAS_PORTFOLIO_DECISION` | 游戏 → 组合决策节点 |
| `PATTERN_SIMILAR_TO` | 模式间（共享 strategy_type）互连，跨动作/跨游戏学习 |

不新建图存储模型——高层节点与边均复用 `GraphNode` / `GraphEdge`，仅扩展类型枚举。

---

## 4. 5 源 → 高层节点映射

| 源 | 消费入口 | 高层节点 |
|---|---|---|
| E17.7 `extract_patterns(graph)` | `_consolidate_patterns` | CreativePattern / UAPattern / MonetizationPattern |
| P3.3 Strategy Memory（`src/operator/strategy/memory.py::StrategyMemoryAdapter`） | `.build_insights(graph)` + `.all_states()` | StrategyResult |
| E17.6 Execution Memory（`src/ceo_intelligence/execution_router/memory.py::ExecutionMemory`） | `.all()` | ExecutionOutcome |
| E16 Recovery（`src/execution/recovery/__init__.py::JsonlRecoveryExperienceStore`） | `.all()` | RecoveryHistory |
| P3.4.5 `PortfolioOptimizationResult` | `.proposal.items` | PortfolioDecision |

> **导入陷阱**：P3.3 Strategy Memory 在 `src/operator/strategy/memory.py`，**不在** `src/ceo_intelligence/strategy/`。`knowledge.py` 内须 `from ...operator.strategy.memory import StrategyMemoryAdapter`（三跳：`growth_memory_graph` → `ceo_intelligence` → `src` → `src.operator.strategy`）。

源适配 `_coerce_*` 均惰性导入、接受实例或 JSONL 路径；传 `None` 则跳过该源 consolidate（源可不齐）。

---

## 5. `GrowthKnowledgeGraph` API

### 5.1 主入口
- `consolidate(*, strategy_memory, execution_memory, recovery_store, portfolio_results=None, include_patterns=True) -> {"nodes_added", "edges_added"}`
  - 只读吃 5 源，只往 E17.7 图加高层节点；幂等（重复 consolidate 加 0）。
  - Recovery 用 E17.7 图 `execution_id → game_id` 映射把恢复经验挂到具体游戏。
  - Pattern 间按共享 `strategy_type` 连 `PATTERN_SIMILAR_TO`。

### 5.2 查询 API（回答 P3.5 三核心问题）
- `why_game_succeeded(game_id) -> {...}`：**问题 1**——汇聚该游戏在 5 类高层节点上的全部经验证据 + 可解释摘要（`summary`）。
- `similar_games(game_id) -> [...]`：**问题 2**——基于「游戏 → 经验信号」重叠度找相似游戏，按 `shared_count` 降序。
- `strategy_results_by_success(descending=True) -> [...]`：**问题 3（基础）**——哪些策略有效，按历史成功率排序。
- `strategy_for_lifecycle(stage) -> [...]`：**问题 3（进阶）**——哪策略在哪个生命周期有效。当前用启发式 `_LIFECYCLE_DIMENSION`：`launch→creative / growth→ua / maturity,decline→monetization`。真实生命周期源接入是后续里程碑扩展点。
- 辅助：`portfolio_decisions(game_id=None)` / `recovery_history(game_id=None)` / `creative_patterns()` / `ua_patterns()` / `monetization_patterns()` / `game_knowledge(game_id)`（= `why_game_succeeded`）/ `summary()` / `to_markdown()`。

---

## 6. 边界锁（`tests/p3_5/test_contract_boundary.py`，4 项）

AST 静态扫描（剥 docstring/注释后）：
- 禁 `src.execution.providers` / `src.execution.contracts` / `src.execution.safe_executor` 符号与 import；
- 禁 `ExecutionContract` / `Provider` / `SafeExecutor`；
- 禁越界方法名/函数：`calculate_roas` / `predict_revenue` / `estimate_ltv` / `record_outcome` / `allocate` / `decide` / `predict` / `forecast` / `safe_executor`；
- 禁收入预测式（`new_revenue` / `revenue *` 等）。

（注：P3.5 较 P3.4 无「模拟/预算」语义，故不常见 `sorted(`/`/` 锁；锁聚焦「不写回、不预测、不碰执行层」三件事。）

---

## 7. P3.5.1 — Knowledge-Augmented Decision Loop（消费端接入，只读）

> 状态：Closed（2026-07-30）。把 P3.5 的「被动知识库」接进两个既有决策入口，让 AI CEO **用记忆改变行为**：
> 不是再堆一个 Memory Layer，而是让已有 Ranker / Strategy Loop 「借用历史经验」而非冷启动。
> 新增 `src/ceo_intelligence/growth_memory_graph/{advisor,signals}.py`；接线 P3.4 Ranker + P3.3 Strategy Loop。
> **15 tests** `tests/p3_5_1/` 全绿（test_advisor 11 + test_contract_boundary 4）。

### 7.1 设计原则

- **只读、fail-open**：Advisor 只读 P3.5 图；图不可用 / 查询异常 → 返回空 `KnowledgeSignal`（confidence=0），**绝不中断主链**。
- **不做决策、不重算 ROAS**：只给决策入口「经验修正」信号。Rank 公式 = `base + 经验分 − 风险惩罚`；Strategy 置信 `压低` 而非直接否决。
- **中性信号**：无历史经验的游戏 → 修正 (0, 0)，不被不当降权。
- `real_api_called` 恒 `False`。

### 7.2 新文件

**`signals.py`** — `KnowledgeSignal` dataclass（与 P3.5.1 契约一致）：

| 字段 | 含义 |
|---|---|
| `confidence` | 信号自身可信度（经验越多越可信，0..1 = case_count/(case_count+3)） |
| `historical_success_rate` | 相似历史经验成功率（0..1） |
| `similar_case_count` | 命中相似经验条数 |
| `risk_flags` | 风险标记（空=无风险） |
| `evidence` | 人可读证据行 |

辅助：`to_dict/from_dict`（序列化，含 `has_risk()/is_empty()`）；`PortfolioExperienceSignal = KnowledgeSignal`（命名别名）。
函数：`experience_adjustment(sig)->(exp,pen)`（无历史→(0,0)；`exp=clamp((sr-0.5)*2,-1,1)`；`pen=min(0.5, 0.15*len(risk_flags))`）、`augmented_score(base,sig)`、`knowledge_adjusted_confidence(base,sig)`（风险时 `factor=max(0.4, 1-0.18*len(risk_flags))`）、`knowledge_requires_approval(sig)`（= `bool(risk_flags)`）。

**`advisor.py`** — `GrowthKnowledgeAdvisor(graph: Optional[GrowthKnowledgeGraph]=None)`：

- `advise_portfolio(game) -> KnowledgeSignal`（喂 P3.4 Ranker）：
  - graph None 或无 game_id → 空信号（fail-open）；否则 `_advise_portfolio(gid)` 包 try/except→空。
  - 收集相似游戏的 `strategy_results / execution_outcomes / portfolio_decisions`；算 `hist_sr`、`case_count`、`confidence=count/(count+3)`。
  - `risk_flags`：`low_historical_success`（sr<0.4 且 count≥3）、`high_rollback_rate`（avg>0.3）、`historical_scale_failure`（存在 negative 组合决策）。
- `advise_strategy(proposal, game_id=None) -> KnowledgeSignal`（喂 P3.3 Strategy Loop）：
  - 提案文本（current_strategy/proposed_change/expected_impact）与历史策略结果（strategy_id/dimension/rationale/recommendation）做 **≥4 字符 token 子串匹配**（不依赖分词库）。
  - `risk_flags`：`historical_failure_pattern`（sr<0.4 且 count≥3），若文本含 "retention" 叠加 `retention_drop_risk`。

### 7.3 两个接入点（接线，均默认 off 保证零回归）

1. **P3.4 Portfolio Ranker**（`src/operator/portfolio/ranker.py`）：
   - `rank(snapshots, knowledge_signals: Optional[Dict[str, KnowledgeSignal]]=None)`——缺省 None = P3.4.2 完全一致行为。
   - 有信号时：`aug = base + exp - pen` 用于排序/`priority=round(aug*100,2)`；候选挂 `knowledge_signal`（dict）+ `knowledge_adjustment`（float，round-trip 安全）；reason 追加 `[experience] ...` 与 risk。
   - `AllocationCandidate` 新增可选字段 `knowledge_signal: Optional[Dict]=None`、`knowledge_adjustment: float=0.0`（纳入 `to_dict/from_dict`，往返安全）。
   - **P3.4.5 Optimizer**（`optimizer.py`）：`__init__`/`build_portfolio_optimizer` 新增 `advisor` 参数；`optimize` 注入 advisor 时先 `knowledge_signals = {snap.game_id: advisor.advise_portfolio(snap)}`，再传给 `ranker.rank(...)`。

2. **P3.3 Strategy Loop**（`src/operator/strategy/loop.py`）：
   - `__init__` 新增 `advisor` 参数；gating 提案后若 advisor 存在，对每个 proposal 调 `advise_strategy(p)` 挂 `p.knowledge_signal`；有 risk_flags 时设 `p.knowledge_confidence = knowledge_adjusted_confidence(p.confidence, sig)` 且**强制 `p.requires_simulation=True`**（历史失败模式 → 自动放行转审批）。
   - Emit 段追加 `[经验降权→x]` 与 `[知识增强] ...` 行。
   - `StrategyProposal` 新增 `knowledge_signal: Optional[Dict]=None`、`knowledge_confidence: Optional[float]=None`（纳入 `to_dict/from_dict`）。

### 7.4 测试重点（`tests/p3_5_1/`，15 项）

- `test_advisor.py`（11）：Case1 无历史 `confidence=0`；Case2 成功模式 `success_rate>0.8` 无风险；Case3 失败模式 `risk_flags` 命中；Case4 图 None + 图抛异常 → fail-open；advisor `real_api_called`=False；strategy 失败/无匹配；ranker 集成（负历史游戏被压到正历史游戏之下，knowledge_adjustment<0）；ranker 无信号行为不变（零回归）；strategy loop 集成（`aggressive_scale` 被禁用 → proposal 带 knowledge_signal、`knowledge_confidence<confidence`、`requires_simulation=True`、"知识增强" 入 patterns）。
- `test_contract_boundary.py`（4）：AST 扫描仅 `advisor.py`+`signals.py`：禁 `src.execution`/`SafeExecutor`/`Provider`/`DecisionEngine`/`write(`/`append(`/`consolidate(`/`record_outcome`/`save(`/`calculate_roas` 等 token 与 import；禁收入预测式。

### 7.5 业务价值验证点

系统从「自动化」走向「智能化」的关键节点：P3.5 的 Graph 不再是被动知识库——

- Portfolio Ranker 借历史经验做 **经验修正排序**（同一份现状数据，因历史成败而改变优先级）；
- Strategy Loop 借历史失败模式做 **置信降权 + 强制审批**（曾经翻车的策略，新一轮提案自动降权并改走 Simulation/Approval，不再 AUTO 放行）。

---

## 8. P3.5.2 — Knowledge Feedback Loop（Graph 成为可增长学习层）

> 状态：Closed（2026-07-31）。P3.5.2 首次引入 **Graph write path**——把每次 CEO Decision
> 收敛成 `CEO_DECISION` 节点 + 3 边，让 Knowledge Graph 从「查询系统」变成「学习系统」；
> 同时给 Advisor 加入 **confidence weighting（防自我强化）**，杜绝「AI 自己相信自己」。
> **24 tests** `tests/p3_5_2/` 全绿（test_feedback 10 + test_consume 6 + test_contract_boundary 8）。

### 8.1 契约冻结点（用户拍板，P3.6 将依赖）

1. **Graph Writer 唯一入口**：所有新增图写入必须经 `KnowledgeFeedbackRecorder.record()` /
   `attach_outcome()`；其他组件一律只读 Graph（AST 锁死）。
2. **命名**：`NodeType.CEO_DECISION`（不叫 DECISION，避免与 E17.3 Decision Engine 混淆）。
3. **Edge 语义**：`HAS_CEO_DECISION`（GAME→决策归属）/ `USED_KNOWLEDGE_SIGNAL`（决策使用了什么知识）/
   `PRODUCED_OUTCOME`（决策产出什么结果）。
4. **字段冻结**：`DecisionKnowledgeRecord{record_id, game_id, decision_type, decision_payload,
   knowledge_signal, outcome, source, created_at}`——`created_at` 保留不参与排序（未来做经验衰减/时间窗口/策略版本）。
5. **confidence weighting（防自我强化）**：外部事实（Execution/Strategy）w=1.0；CEO 决策实际结果 w=0.5；
   CEO 决策模拟结果 w=0.2。`historical_success_rate` 用加权平均，`confidence` 用加权有效样本。
6. **Recorder 接 Optimizer 的位置**：不在 `PortfolioOptimizer.optimize()` 内写 Graph（业务计算层纯净）——
   由 Operator Layer（`src/operator/feedback.py` + pipeline 阶段）消费 `PortfolioOptimizationResult` 后写入。
7. **StrategyLoop 同理**：不在 `StrategyLoop.run()` 内写 Graph——Operator Layer 消费 `StrategyLoopResult` 后写入。

### 8.2 新文件 / 改动

- **`src/ceo_intelligence/growth_memory_graph/feedback.py`**（新）：`DecisionKnowledgeRecord`（8 字段冻结，
  to_node/from_node/to_dict/from_dict）+ `KnowledgeFeedbackRecorder(graph=None)`——`record()` 写
  `CEO_DECISION` 节点 + 3 边（幂等）；`attach_outcome()` 结果回流（走 store 公开 `add_node` 合并，不直接 append）；
  `real_api_called` 恒 False；fail-open（图不可用/异常 → 空计数，不中断主链）。
- **`models.py`**：NodeType 加 `CEO_DECISION`；EdgeType 加 `HAS_CEO_DECISION` / `USED_KNOWLEDGE_SIGNAL` /
  `PRODUCED_OUTCOME`。
- **`knowledge.py`**：`why_game_succeeded` 返回值加 `ceo_decisions`（本游戏历史 CEO 决策，只读，additive 不破坏旧键）。
- **`advisor.py`**：`advise_portfolio` / `advise_strategy` 消费 `ceo_decisions` 时按来源带权并入
  `weighted_success_rate`（`_WEIGHT_EXTERNAL=1.0` / `_WEIGHT_CEO_REALIZED=0.5` / `_WEIGHT_CEO_SIMULATED=0.2`），
  `confidence` 用加权有效样本；知识建议被证伪（knowledge_signal 有 risk_flags + outcome 失败）→
  追加 `knowledge_advice_failed` 风险标记。无 CEO_DECISION 时行为与 P3.5.1 完全一致（零回归）。
- **`src/operator/feedback.py`**（新，Operator Layer 反馈适配器）：`record_portfolio_feedback(recorder, result)` /
  `record_strategy_feedback(recorder, result, game_id="")`——消费 Result 的 `ranked_games` / `proposals`，
  映射成 `DecisionKnowledgeRecord` 交 recorder 写入；fail-open。
- **`pipeline.py`**：`DailyOperatorPipeline(context, feedback_recorder=None)`——portfolio 阶段产出结果后
  调 `record_portfolio_feedback`；strategy_loop 阶段产出结果后调 `record_strategy_feedback`；None → 不记录（零回归）。

### 8.3 验收 Case（`tests/p3_5_2/`，24 项）

- **Record**：写节点 + 3 边 / 同 record_id 幂等 / fail-open（graph None + graph 抛异常）/ real_api_called=False /
  attach_outcome 回流（幂等）/ 只加 `ceo_decision` 节点类型（不污染其他类型）。
- **Operator 适配器**：portfolio 每个候选 1 条（含 source/action/knowledge_signal/outcome 空）；
  strategy 每个提案 1 条（含 simulated outcome=知识降权后置信）；recorder None / result None → 0。
- **Consume（加权）**：无 CEO 记录行为不变；CEO 自报（w=0.5）置信 < 等量外部执行（w=1.0）；
  **Knowledge Source Isolation**——10 执行失败 + 10 CEO 自报成功 → `weighted_sr ≈ 5.5/16 ≈ 0.344`
  （绝不 1.0 / 朴素 0.5）且触发 `low_historical_success`；模拟成功（w=0.2）最弱 → `sr ≈ 2.5/13`；
  知识建议被证伪 → `knowledge_advice_failed`。
- **AST Boundary Lock（8 项）**：feedback.py 正向含 `def record`+`add_node`，禁 5 源写回
  （record_outcome/consolidate(/strategy_memory/execution_memory/recovery_store）+ 执行链
  （src.execution/SafeExecutor/Provider/DecisionEngine）；advisor.py+signals.py 禁 `add_node(`/`add_edge(`/`feedback`
  （只读保持）；optimizer.py+loop.py 禁 `add_node(`/`add_edge(`/`growth_memory_graph.feedback`/`KnowledgeFeedbackRecorder`
  （不感知存储）；operator/feedback.py 正向含 `DecisionKnowledgeRecord` 但禁 `add_node(`/`add_edge(`（只调 recorder）。

### 8.4 业务价值验证点

Graph 从「查询系统」升级为「学习系统」的第一次闭环：策略侧（Operator Layer）把
决策 + 所用知识 + 模拟结果写入图 → 下一轮 Advisor 按权重消费 → 历史翻车的知识
建议触发 `knowledge_advice_failed` → 未来同类提案自动降权 + 强制审批；
同时加权规则保证外部事实不被自生成记录淹没（10 条外部失败 + 10 条自报成功 ≠ 100% 成功率）。

---

## 9. P3.5.3 — Memory Quality Governance（知识质量管理层，只读）

> 状态：Closed（2026-07-31）。「会记忆」已完成，本里程碑保证「记住的是正确的东西」——
> 在 P3.5.2 经验闭环之上加三道闸（KnowledgeScore / Decay / Contradiction / Advisor
> KnowledgeQualityFilter），防止 **Memory Drift**（bad memory → bad advice → bad decision
> → more bad memory）。**29 tests** `tests/p3_5_3/` 全绿（test_quality 12 + test_conflict 6 +
> test_advisor_filter 5 + test_contract_boundary 6）。

### 9.1 设计（用户拍板）

1. **KnowledgeScore**：每条知识（按 `decision_type:action` 聚合）质量分
   `quality = success_rate × recency_factor × source_weight`：
   - recency：今天 **1.0** 线性衰减到一年前 **0.2**（`max(0.2, 1 - 0.8*age/365)`）；
   - source_weight：realized=**1.0** / simulated=**0.5**（模拟可信度减半）；
   - 未验证（无 outcome.success_rate）→ **0 分**（不参与 Advisor）。
2. **Knowledge Decay**：时间戳取 `outcome.last_validated_at` 优先、其次 `record.created_at`；
   `attach_outcome` 结果回流时自动盖 `last_validated_at`（幂等）。
3. **Contradiction Detection**：同键同时存在成功与失败结果 → `KnowledgeConflict`，
   **双记录保留不覆盖**（图本就 append-only，不删除）。
4. **Advisor 输入升级**：注入 `MemoryQualityGovernor` 后，Advisor 折叠 CEO_DECISION 经验前
   先 `filter_records`（只消费 `quality >= min_quality`，默认 0.3）；未注入 → 零回归。

### 9.2 落地

- **`src/ceo_intelligence/growth_memory_graph/quality.py`**（新，只读）：
  - `KnowledgeScore{key, confidence, usage_count, success_count, failure_count,
    last_validated_at, quality}`（+ `success_rate` / `validated_count` 派生）；
  - `KnowledgeConflict{key, successes, failures, evidence}`；
  - `MemoryQualityGovernor(graph=None, as_of=None, min_quality=0.3)`：`quality_of(record)` /
    `score_records(records)`（按 key 聚合）/ `filter_records(records)`（quality≥min）/ 
    `detect_conflicts(records=None)`（None→从图读 CEO_DECISION）/ `ceo_decision_records()`（fail-open）；
    `real_api_called` 恒 False；❌ 禁写 Graph / 5 源 / 执行链（AST 锁）。
  - 公共别名 `recency_factor` / `age_days`（供测试直接使用）。
- **`feedback.py`**：`attach_outcome` 落 `last_validated_at`（幂等）；`DecisionKnowledgeRecord.created_at`
  保留可选显式赋值（供老化/时间窗口）。
- **`advisor.py`**：`__init__` 加 `quality: Optional[MemoryQualityGovernor]=None`；
  `advise_portfolio` / `advise_strategy` 折叠 ceo_decisions 前先 `self.quality.filter_records(...)`；
  清掉 P3.5.2 遗留的死变量（ceo_count/ceo_eff）。

### 9.3 验收 Case（`tests/p3_5_3/`，29 项）

- **Scoring/Decay（12）**：decay 曲线 0→1.0 / 182.5→0.6 / 365→0.2 / 730→0.2 封底；
  `quality_of`（近期成功 1.0 / 模拟减半 0.5 / 未验证 0 / 一年前 0.2 / last_validated_at 优先于 created_at）；
  `score_records` 聚合（usage/success/failure/confidence 均值/last_validated_at max）；
  `filter_records` 只留 quality≥threshold；real_api_called=False；fail-open。
- **Conflict（6）**：同键正反结果 → KnowledgeConflict（successes/failures/evidence 双列）；
  全同结果不冲突；**不覆盖**（双记录原样保留）；未验证记录不参与；按键隔离；to_dict 往返。
- **Advisor Filter（5）**：未注入 quality=零回归（P3.5.2 公式 10.5/11）；一年前旧败绩被滤
  （with 10.5/11 > without 10.5/11.5，旧败绩不污染信号）；近期高质量成功照常应用（11/11.5）；
  全部过闸时质量门不改变结果；real_api_called=False。
- **Boundary（6）**：quality.py 正向含 KnowledgeScore/KnowledgeConflict/filter_records/detect_conflicts，
  禁 add_node(/add_edge(（只读）、禁 5 源写回 + 执行链、禁 import feedback；
  advisor.py 仍只读（无 add_node/add_edge/feedback）。

### 9.4 业务价值验证点

防止 Memory Drift 的第一道闸：旧败绩不会永久污染建议（decay + filter）；同一策略出现
相反结果时双记录保留待仲裁（conflict 不覆盖）；模拟结果质量分减半、未验证经验完全不参与
（quality=0）——「记住的是正确的东西」才让 P3.6 有意义。

---

## 10. 后续里程碑（未做，用户未要求）

- **write-back 里程碑**：把 `why_game_succeeded` / 经验降权结论反哺 Strategy Memory（闭环学习）。
- **真实生命周期源注入**：替换 `_LIFECYCLE_DIMENSION` 启发式，接 E15.1.2 真实阶段。
- **realized outcome 回流钩子**：把 portfolio 侧 `attach_outcome` 接到真实 Monitor/Execution 结果。
- **冲突仲裁**：KnowledgeConflict 的人工/自动仲裁入口（当前只检测不裁决）。

下一步建议路线：**P3.5.3（本里程碑）→ P3.6 Autonomous CEO Memory → P4 Autonomous Growth Agent**。

---

## 11. 回归

- managed 3.13 全量 **2499 passed / 0 failed**（2470 + P3.5.3 +29）；ci311 全量异常属环境问题，不计入。
- 基线 2499。
