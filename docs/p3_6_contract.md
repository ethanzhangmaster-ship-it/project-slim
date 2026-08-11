# P3.6 — Autonomous Memory Controller / Memory Intelligence Layer Contract

> 状态：**Contract Audit（2026-07-31，未写代码）**。P3.5 三层（Storage / Understanding /
> Evolution）已完整闭环，P3.6 重新定义：不再"建更强的 Memory"，而是 **Memory Intelligence
> Layer**——AI CEO 什么时候调用什么记忆、如何组织成战略认知。
> 本里程碑先做 **Memory Retrieval Contract Audit**（Part A/B），再冻结
> **MemoryController Contract**（Part C），P3.6.1 实现方案见 Part D（待批准后实施）。

---

## Part A — Memory Retrieval Contract Audit（现状盘点）

### A.1 E17.7 Graph 查询 API（`src/ceo_intelligence/growth_memory_graph/store.py`）
`GrowthMemoryGraph`（node/edge/jsonl/traversal 存储层）暴露：

| API | 能力 | 消费方 |
|---|---|---|
| `query(node_type, game_id=None, **payload_filters)` | 按类型/游戏/payload 过滤节点（确定性排序） | GrowthKnowledgeGraph 全部查询 |
| `neighbors(nid, edge_type, direction)` | 邻接遍历（in/out） | trace_execution / game_subgraph |
| `trace_execution(execution_id)` | 执行因果链回溯 | E17.7 报告 |
| `game_subgraph(game_id)` | 游戏 BFS 子图 | 报告/调试 |
| `success_rate_by(...)` | RESULT 节点成功率聚合 | E17.7 pattern |
| `stats()` | 图谱规模 | summary |

### A.2 P3.5 GrowthKnowledgeGraph 查询 API（`knowledge.py`，只读底座）
- `why_game_succeeded(game_id)` → 5 类节点经验证据 + `ceo_decisions` + 可解释 `summary`
- `similar_games(game_id)` → 基于「游戏→经验信号」重叠度找相似游戏（shared_count 降序）
- `strategy_results_by_success(descending=True)` / `strategy_for_lifecycle(stage)`
- `portfolio_decisions(game_id)` / `recovery_history(game_id)`
- `creative_patterns()` / `ua_patterns()` / `monetization_patterns()`
- `summary()` / `to_markdown()`

### A.3 P3.5.1 Advisor（`advisor.py`，只读消费端）
- `advise_portfolio(game)` → `KnowledgeSignal`：相似游戏 strategy/execution/portfolio/CEO 经验
  带权聚合（外部 w=1.0 / CEO 实际 0.5 / 模拟 0.2），risk_flags + confidence
- `advise_strategy(proposal, game_id=None)` → `KnowledgeSignal`：关键词匹配历史策略 + 相似游戏经验
- `__init__(graph, quality=None)`：P3.5.3 质量门可选注入

### A.4 P3.5.3 QualityGovernor（`quality.py`，只读质量门）
- `quality_of(record)` = `success_rate × recency × source_weight`（未验证=0）
- `score_records(records)` 按 key 聚合 / `filter_records(records)`（quality≥min）
- `detect_conflicts(records=None)` 同键正反结果 → KnowledgeConflict（不覆盖）
- `ceo_decision_records()` 从图读 CEO_DECISION（fail-open）

### A.5 四个消费侧接线（审计重点）

| 消费侧 | 当前接线 | 状态 |
|---|---|---|
| P3.4 Ranker | `rank(snapshots, knowledge_signals: Dict[gid, KnowledgeSignal]=None)` | ✅ 参数就绪，缺省 None=零回归 |
| P3.4.5 Optimizer | `__init__/build(advisor=None)`，`optimize` 注入时先 `advise_portfolio` 再喂 Ranker | ⚠️ **仅测试注入，pipeline 未注入** |
| P3.3 Strategy Loop | `__init__(advisor=None)`，gating 后 `advise_strategy` 挂 knowledge_signal/knowledge_confidence | ⚠️ **仅测试注入，pipeline 未注入** |
| CEO Report | `build_portfolio_recommendation_section(result)` 只搬 confidence/status/items | ❌ **不消费任何知识 evidence/source_chain** |

**关键审计结论（P3.6.1 的核心缺口）**：
1. **读侧在生产链路是断的**——`DailyOperatorPipeline` 只接了写侧（`feedback_recorder`，
   P3.5.2），**没有注入 advisor/quality**；知识增强目前只在测试里生效。
2. **检索是被动、按入口写死的**——`advise_portfolio` / `advise_strategy` 两条硬编码路径，
   无统一 `MemoryContext`，无多路召回（相似游戏/策略史/失败史/组合经验/创意模式 五路）。
3. **CEO Report 无法回答"为什么推荐这个动作"**——knowledge evidence 不上报告。
4. **无 source_chain 追溯**——KnowledgeSignal 有 `evidence` 文本行，但非结构化可追溯链。
5. **"为什么拒绝过去成功的方法"无出口**——`detect_conflicts` 只检测，不进入解释/决策理由。

---

## Part B — Gap Analysis（与 P3.6.1 目标对照）

用户目标：`Decision Context → Memory Controller → 五路召回 → Relevant Knowledge Bundle`。

| # | 缺口 | 现状 → 目标 |
|---|---|---|
| G1 | 无 `MemoryContext` | 各入口各自传参（game/strategy 上下文散落）→ 统一 `MemoryContext{query_reason, game_id, lifecycle, decision_type, required_confidence}` |
| G2 | 无 `KnowledgeBundle` 输出 | 只回聚合 `KnowledgeSignal`（丢逐条记忆）→ `KnowledgeBundle{memories[], confidence, explanation, source_chain}` |
| G3 | 读侧未接入生产 pipeline | advisor/quality 仅测试注入 → pipeline 注入 `MemoryController`（读侧闭环） |
| G4 | 无五路召回 | 单一 similar_games 路径 → 按 query_reason 路由到 Similar Game / Strategy History / Failure Memory / Portfolio Experience / Creative Pattern |
| G5 | Report 无知识解释 | portfolio 段无 evidence → 新增 "Knowledge Reasoning" 段（explain 输出：为什么推荐/为什么拒绝） |
| G6 | 拒绝理由无出口 | conflict 只检测 → explain("why_reject") 引用 detect_conflicts + failure memory |

---

## Part C — MemoryController Contract（冻结）

### C.1 MemoryContext（请求）

```python
@dataclass
class MemoryContext:
    query_reason: str            # "portfolio_rank" | "strategy_check" | "report_explain" | "why_reject"
    game_id: str = ""
    lifecycle: str = ""          # launch / growth / maturity / decline（启发式映射复用 _LIFECYCLE_DIMENSION）
    decision_type: str = ""      # "portfolio" | "strategy"
    required_confidence: float = 0.3   # 对齐 MemoryQualityGovernor.min_quality
    as_of: str = ""              # 可注入（decay 时间基准），默认 now
```

### C.2 KnowledgeBundle（输出）

```python
@dataclass
class MemoryItem:                # 逐条召回记忆（结构化可追溯）
    memory_type: str             # "similar_game" | "strategy_history" | "failure_memory"
                                 # | "portfolio_experience" | "creative_pattern"
    key: str                     # 稳定键（如 game_id / strategy_id / decision_type:action）
    success_rate: float
    weight: float                # 外部1.0 / CEO实际0.5 / 模拟0.2（对齐 P3.5.2）
    quality: float               # P3.5.3 质量分（decay 后）
    evidence: List[str] = ...
    source_ref: str = ""         # 可追溯：graph node id / record_id

@dataclass
class KnowledgeBundle:
    memories: List[MemoryItem]
    confidence: float            # 加权聚合置信（对齐 P3.5.2 加权有效样本）
    explanation: List[str]       # 人可读理由（喂报告）
    source_chain: List[str]      # 追溯链：每条的 source_ref 汇总
```

### C.3 MemoryController（编排层，复用不重造）

```python
class MemoryController:
    """Memory Brain 检索编排层（只读，fail-open）。

    组装既有部件，不重写 Advisor 的聚合/加权逻辑：
      GrowthKnowledgeGraph（底层查询）+ GrowthKnowledgeAdvisor（聚合/加权）
      + MemoryQualityGovernor（过滤/评分/冲突）+ 五路召回组合。
    """

    def __init__(self, graph, advisor=None, quality=None, as_of=""):
        # advisor 缺省内部构造 GrowthKnowledgeAdvisor(graph, quality)
        ...

    def retrieve(self, ctx: MemoryContext) -> KnowledgeBundle:
        """按 query_reason 路由五路召回 → 逐条 MemoryItem → 聚合 confidence/explanation/source_chain。"""

    def explain(self, ctx: MemoryContext) -> str:
        """报告段落：为什么推荐 / 为什么拒绝（引用 conflict + failure memory）。"""
```

### C.4 契约铁律（继承 P3.5 纪律）

- ❌ **只读**：controller 禁 `add_node(`/`add_edge(`（禁 import feedback——不借 recorder 之外写路径）；
- ❌ 不写回 5 源、不调 consolidate、不调 Provider / SafeExecutor / DecisionEngine、不替代 E17.3；
- ✅ `real_api_called` 恒 False；✅ fail-open（图异常 → 空 bundle，不中断主链）；
- ✅ **零回归**：controller 是新增可选层；advisor/ranker/loop 原样保留（注入与否行为不变）；
- ✅ 确定性：无 LLM、无随机性（与全库一致）。

### C.5 验收能力映射（用户三问 → P3.6.1 范围）

| 能力 | P3.6.1 范围 |
|---|---|
| ① 为什么推荐这个动作 | ✅ `explain(ctx)`：输出 similar cases 数 / 成功率 / 最新验证时间 / 加权置信（MemoryItem 逐条可引） |
| ② 为什么拒绝过去成功的方法 | ✅ `explain(why_reject)`：路由 failure_memory + `detect_conflicts`（recent contradiction / conversion dropped 等 evidence） |
| ③ 形成长期战略规则 | ⏭ **P3.6.2 Strategic Summary Memory**（本里程碑只埋 MemoryItem 结构化基础，供 Pattern Mining 消费） |

---

## Part D — P3.6.1 实现（Closed，2026-07-31，用户批准后实施）

### D.1 落地（与 Part C 契约一致）

- **`src/ceo_intelligence/growth_memory_graph/controller.py`**（新，只读）：
  - `MemoryContext{query_reason, game_id, lifecycle, decision_type, required_confidence, as_of}`
  - `MemoryItem{memory_type, key, success_rate, weight, quality, evidence, source_ref, validated_at}`（to_dict/from_dict）
  - `RetrievalTrace{query, sources}`（供 P3.6.3 Reflection 复盘"AI 当时看过什么"）
  - `KnowledgeBundle{memories, confidence, explanation(str), source_chain, conflicts(list[str]), retrieval_trace, real_api_called}`（用户冻结形状 + retrieval_trace）
  - `MemoryController(graph=None, quality=None, as_of="")`：`retrieve(ctx)` 按 query_reason 路由五路召回
    （similar_game / strategy_effectiveness(+lifecycle 维度启发式) / failure_reason / execution_outcome /
    portfolio_context / contradiction / report_explain 全量）+ `MemoryQualityGovernor` 质量门
    （`quality >= required_confidence`，含 decay）+ 加权置信（Laplace `eff/(eff+3)`，eff=Σweight）
    + `explanation`（相似游戏/历史成功率/最近验证/冲突）+ `source_chain` + `retrieval_trace`；fail-open。
  - `bundle_to_signal(bundle) -> KnowledgeSignal`（薄映射：置信/加权 sr/条数/`knowledge_conflict` 风险标记）
  - `MemoryControllerAdvisor(controller, role)`：复用 P3.5.1 既有 advisor 注入点（**不新增构造参数**）。
- **`context.py`**：`OperatorContext` 加 `memory_controller` 字段；`build_operator_context(memory_controller=...)`。
- **`pipeline.py`**：`_portfolio` 注入 `MemoryControllerAdvisor`（经既有 `build_portfolio_optimizer(advisor=...)`）；
  `_strategy_loop` 注入 advisor；`_ceo_report` 先 `controller.retrieve(report_explain)` 挂 `s["memory_bundle"]`，
  再传 `build_ceo_report(memory_reasoning=...)`。None → 零回归（纯规则路径）。
- **Report**：`CEODailyReport.memory_reasoning`（round-trip）；`sections.build_memory_reasoning_section(bundle)`；
  renderer 新增 **"## 八、Memory Reasoning（本次建议的知识依据）"**（Similar games / 召回记忆数 /
  Historical success / Recent validation / Conflict / Confidence；空 bundle 优雅显示）。

### D.2 测试（`tests/p3_6_1/`，35 项全绿）

- Controller（16）：空图 fail-open / 五路召回（similar_game 需 game_id；strategy_effectiveness 含 lifecycle 过滤；
  failure_reason / execution_outcome / portfolio_context / contradiction / report_explain）/ 质量门
  （一年前 sr=1.0 → quality 0.2 被滤；required_confidence=0 全保留）/ Laplace 置信（2 条 → 0.4）/
  round-trip / bundle_to_signal（含 knowledge_conflict 风险标记）。
- Adapter（4）：advise_portfolio / advise_strategy 返回 controller 驱动的 KnowledgeSignal；空图信号 0；real_api_called False。
- Pipeline（3）：**MemoryController 缺省（None）→ 候选无 knowledge_signal（零回归）**；注入 →
  候选携带 knowledge_signal（confidence>0）；注入后 portfolio 阶段仍不触发执行链（real_api_called False）。
- Report（6）：section 构建 / dict 兼容 / renderer 八段 / **空 bundle 优雅**（召回 0 条 + Conflict none）/
  无 section 时省略 / CEODailyReport round-trip。
- Boundary（6）：controller.py 禁 add_node(/add_edge(/feedback/5 源写回/执行链；advisor 保持只读。

### D.3 验收能力映射（P3.6.1 已交付）

| 能力 | 状态 |
|---|---|
| ① 为什么推荐这个动作 | ✅ `MemoryController.explain` + CEO 报告"八、Memory Reasoning"（相似游戏/历史成功率/最近验证/置信） |
| ② 为什么拒绝过去成功的方法 | ✅ `contradiction` 路由 + `bundle.conflicts`（recent contradiction 进 explanation 与风险标记） |
| ③ 形成长期战略规则 | ⏭ P3.6.2 Strategic Summary Memory（MemoryItem 结构化基础已埋） |

### D.4 纪律验收

- 零回归：全量 **2534 passed / 0 failed**（2499 + P3.6.1 +35）；p3_3 / p3_4 / p3_5.x / p3_1 全绿；
- controller 只读锁：AST 禁 `add_node(`/`add_edge(`/`growth_memory_graph.feedback`/5 源/执行链；
- `real_api_called` 恒 False；fail-open 空 bundle 不中断主链；
- **不提前做**：❌ embedding/vector DB、❌ LLM summarization、❌ StrategicInsight、❌ autonomous reflection、❌ memory pruning（属 P3.6.2/3.6.3/3.6.4）。

### D.5 路线
**P3.6.1（本里程碑 Closed）→ P3.6.2 Strategic Summary Memory（StrategicInsight 节点 + Pattern Mining）→ P3.6.3 Memory Reflection Loop（CEO Reflection：wins/mistakes/changed_beliefs/new_rules）→ P3.6.4 Memory Governance（duplicate merge / obsolete archive / contradiction resolution / knowledge lifecycle）→ P4 Autonomous Growth Agent。**

---

## Part E — P3.6.2 Strategic Summary Memory Contract Audit（2026-07-31，未写代码）

> 定位：**Retrieval → Understanding**。P3.6.1 给 CEO 找证据；P3.6.2 从大量证据中总结规律
> （Strategic Insight）。仍保持边界：❌ 不修改 StrategyLoop / Ranker、不产生 Action、不执行优化、
> 不写回 Strategy Memory、不做 LLM——第一阶段是**规则归纳器**。

### E.1 四形状核实（审计结论）

| # | 形状 | 核实结果 | 对 StrategicInsight 的支撑 |
|---|---|---|---|
| S1 | **Strategy Memory（P3.3）** | `StrategyMemoryAdapter.build_insights()` → `StrategyInsight{strategy_id, dimension, historical_success_rate, samples, avg_reward, recommendation, rationale}`；`all_states()` → `StrategyState.performance{wins, losses, reward_sum}`（**精确计数**） | ✅ **Strategy Insight 直接支撑**。⚠️ 计数应取 `all_states().performance`（wins/losses 整数），**不要**从 graph 节点的 6dp `success_rate` 反推（有损） |
| S2 | **Recovery Memory（E16）** | 记录 `{failure, action, recovery, result, reward, success, metadata{execution_id}}`；图节点 `RecoveryHistory{failure_type, recovery_strategy, success_rate, n, avg_reward, game_id, games}` | ✅ **Failure Insight 支撑**（failure 聚类 + 恢复成功率）。⚠️ **`common_causes` 字段不存在**（用户例：CPI increase / creative fatigue）——需确定性 keyword 规则从 failure_type 派生（如含 "cpi"→CPI increase、含 "fatigue"→creative fatigue），或本里程碑省略 |
| S3 | **Lifecycle** | ⚠️ **图内无 lifecycle 字段**。真实源 `E15.1.2 PortfolioManager.stage_of(game_id)` → `GamePortfolioSnapshot.lifecycle_stage`（**portfolio 层，不在图**）。图内仅有 `STRATEGY_RESULT.dimension`（creative/ua/monetization） | **Lifecycle Insight 需注入 `game→lifecycle` 映射**（builder 参数 `lifecycle_map`，来自 E15.1.2），否则用 dimension 作弱代理或跳过 |
| S4 | **MemoryController 输入** | `MemoryItem{memory_type, key, success_rate, weight, quality, evidence, source_ref, validated_at}`（5 路，**不含 CEO_DECISION**） | Action 级规则归纳（用户例 `scale_budget` 失败 2/3）最佳来源是 **CEO_DECISION.decision_payload.action + outcome**（P3.5.2 已冻结）——需 builder 可选接收 `ceo_records` |

### E.2 关键契约决策点（需用户拍板）

- **D1（写入口）**：P3.5.2 冻结「Graph Writer 唯一入口 = `KnowledgeFeedbackRecorder`」。用户要求新增 `strategic_store.py` 负责写入——若它直接 `add_node` 会破坏该冻结点。
  **推荐：strategic_store 内部走 KnowledgeFeedbackRecorder 的写路径**（在 recorder 上新增 `record_insight(insight)`，仍唯一写入口）；若用户希望 strategic_store 独立写，需显式放宽 P3.5.2 冻结点 1。
- **D2（Lifecycle 数据源）**：① 注入 `lifecycle_map`（推荐，接 E15.1.2 真实源） ② dimension 代理 ③ 本里程碑不做 Lifecycle Insight。
- **D3（builder 输入）**：冻结接口 `build(memories, as_of, *, lifecycle_map=None, ceo_records=None)`——后两者可空（fail-open），保持用户冻结的 `build(memories, as_of)` 兼容。

### E.3 StrategicInsight Schema（用户冻结，字段齐备）

```python
@dataclass
class StrategicInsight:
    insight_id: str
    category: str            # lifecycle | ua | monetization | creative | portfolio
    statement: str           # 人可读规律（确定性模板生成）
    evidence_count: int      # = len(supporting_memories)
    success_rate: float
    confidence: float        # 样本 × 质量（加权有效样本 Laplace，对齐全库）
    supporting_memories: List[str]   # source_ref 列表（可追溯）
    counter_examples: List[str]      # 反例 source_ref（contradiction 侧）
    created_at: str
    last_validated_at: str
    real_api_called: bool = False
    # to_dict / from_dict
```

### E.4 Graph 扩展（append-only，不覆盖旧 Memory）

- `NodeType.STRATEGIC_INSIGHT`
- `EdgeType.INSIGHT_DERIVED_FROM_MEMORY`（insight → 支撑记忆节点，source_ref 可追溯）
- 纪律：只加节点/边，**不删除/不覆盖**任何既有 memory 节点。

### E.5 模块分工（用户冻结 + D1 修正）

| 模块 | 职责 | 写权限 |
|---|---|---|
| `strategic_builder.py`（新） | `MemoryItem[] + ceo_records → StrategicInsight[]`（纯规则归纳，无 IO） | ❌ 禁 `add_node(`/`add_edge(`（AST 锁） |
| `strategic_store.py`（新） | 写入 StrategicInsight 节点/边 | ✅ 经 `KnowledgeFeedbackRecorder.record_insight()`（D1 推荐） |
| `controller.py`（升级） | `KnowledgeBundle` 加 `strategic_insights: List[dict]`；`retrieve` 加 `query_reason="strategic"` 路由；explanation 含战略规律 | 只读（不变） |
| Report | 新增 **"## 九、Strategic Memory"**（长期规律列表） | — |

### E.6 第一批 Insight 类型（确定性规则归纳器）

1. **Lifecycle Insight**（需 lifecycle_map，见 D2）：桶 early(0-7d)/mid(7-30d)/late(30+) → 每桶按策略聚类 `sr`；
   例：`late 生命周期游戏：creative_refresh sr=0.68、ua_scale sr=0.31`。
2. **Strategy Insight**：按 strategy_id 取 `all_states().performance{wins,losses}` → `sr`；`confidence = 样本×质量`；
   `category` 由 dimension 映射（ua→ua / creative→creative / monetization→monetization）。
3. **Failure Insight**：按 failure_type 聚类恢复成功率（RecoveryHistory）；`common_causes` 由 failure_type
   keyword 规则确定性派生（见 S2）或省略；`category` 由 failure_type 关键字映射到 ua/creative/monetization。

### E.7 测试规划（`tests/p3_6_2/`，约 25 项）

- Builder（6）：基础 insight 生成 / success_rate 计算 / confidence 计算 / **样本不足过滤**（min_samples 阈值）/ contradiction 反例收集 / 确定性（无随机）。
- Lifecycle（3）：生命周期聚类 / 生命周期隔离（不同桶不串） / 无 lifecycle_map 时优雅跳过。
- Graph（4）：insight node 写入 / `INSIGHT_DERIVED_FROM_MEMORY` 边正确 / round-trip / append-only 不覆盖旧节点。
- Controller（5）：`retrieve("strategic")` 召回 insight / explanation 含战略规律 / bundle.strategic_insights 空缺省零回归 / fail-open / real_api_called False。
- Report（3）："## 九、Strategic Memory" 渲染 / 空 insight 优雅 / round-trip。
- Boundary（4）：`strategic_builder.py` 禁 `add_node(`/`add_edge(`/feedback/执行链；controller 只读保持。

### E.8 边界（不提前做）

❌ 不修改 StrategyLoop / Ranker、不产生 Action、不执行优化、不写回 Strategy Memory、
❌ 不做 LLM summarization / embedding——StrategicInsight 全部由**确定性规则归纳器**产出。
❌ 本里程碑不做 trend detection / reflection（属 P3.6.3）。

---

## Part F — P3.6.2 实现（Closed，2026-07-31，用户拍板 D1/D2/D3 后实施）

### F.1 决策落地（用户拍板）

- **D1（写入口）✅**：保持 P3.5.2 冻结「Graph Writer 唯一入口 = `KnowledgeFeedbackRecorder`」。
  `strategic_store.py` **禁直接 graph.add_node/add_edge**（Writer Lineage，AST 锁死）——
  链路为 `StrategicBuilder → StrategicInsight → StrategicStore → recorder.record_insight() → Graph`。
- **D2（Lifecycle）✅**：注入 `lifecycle_map`（E15.1.2 真实源，**不把 lifecycle 冗余复制进 Graph**）；
  无 lifecycle_map/ceo_records → 跳过 Lifecycle Insight（fail-open）。
- **D3（builder 输入）✅**：`build(memories, as_of, *, lifecycle_map=None, ceo_records=None)`。
- **额外冻结点 ✅**：**StrategicInsight 不复用 DecisionKnowledgeRecord**（一次具体决策反馈 vs
  跨决策规律；CEO_DECISION → StrategicInsight 是派生关系，不是等价）。

### F.2 落地（2 新文件 + 4 处扩展）

- **`strategic_builder.py`**（新，纯计算）：`StrategicInsight`（用户冻结 schema + to_node/from_node/
  to_dict/from_dict，**非 DecisionKnowledgeRecord**）+ `StrategicMemoryBuilder.build(...)`（规则归纳器）：
  - **Strategy Insight**（strategy_history 按 key 聚类）：sr=加权平均（weight×quality），
    conf=`eff/(eff+3)`（eff=Σweight×quality，样本×质量）；`_MIN_SAMPLES=3` 过滤；counter_examples=相反结果。
  - **Failure Insight**（recovery_experience 按 failure_type 聚类）+ **common_causes keyword 规则**
    （cpi→CPI increase / fatigue→creative fatigue / retention→retention drop / roas / cvr / crash）。
  - **Action Pattern Insight**（ceo_records 按 decision_payload.action 聚类，P3.5.2 权重 realized=0.5/simulated=0.2）。
  - **Lifecycle Insight**（ceo_records + lifecycle_map[game_id]→stage 聚类；无输入 → 跳过）。
  - category 确定性映射（lifecycle / ua / monetization / creative / portfolio）。
- **`strategic_store.py`**（新，写适配）：`StrategicStore(recorder).save/save_all`——**只调
  `recorder.record_insight()`**，不直接碰 Graph；real_api_called 恒 False；fail-open。
- **`feedback.py`**：`KnowledgeFeedbackRecorder.record_insight(insight)`（唯一写入口扩展：
  写 STRATEGIC_INSIGHT 节点 + INSIGHT_DERIVED_FROM_MEMORY 边；幂等/fail-open）。
- **`models.py`**：NodeType `STRATEGIC_INSIGHT`；EdgeType `INSIGHT_DERIVED_FROM_MEMORY`（append-only）。
- **`controller.py`**：`KnowledgeBundle.strategic_insights: List[dict]`（默认空，零回归）+
  `retrieve(query_reason="strategic")` 召回 STRATEGIC_INSIGHT + explanation 含「战略规律：N 条」。
- **Report**：`CEODailyReport.strategic_memory`（round-trip）+ `build_strategic_memory_section` +
  renderer **"## 九、Strategic Memory（长期战略规律）"**（按 category 分组展示；空 → 优雅省略）。
- **`pipeline.py`**：`_ceo_report` 额外 `retrieve("strategic")` 挂 strategic_bundle → `build_ceo_report(strategic_memory=...)`。

### F.3 测试（`tests/p3_6_2/`，43 项全绿）

- Builder（16）：strategy/failure/action-pattern/lifecycle 生成、sr/conf 精确计算、样本不足过滤、
  counter_examples、common_causes keyword、缺输入 fail-open、确定性（排除 id/时间戳）、round-trip。
- Store（10）：**Writer Lineage（save 调用 recorder.record_insight，Spy 验证，不直接 add_node）**、
  save_all、fail-open、real_api_called=False、record_insight 写节点+边/幂等（固定时间戳保证 payload 一致）/
  fail-open/错误类型 fail-open、store→recorder→graph 全链路、from_node round-trip。
- Controller+Report（9）：retrieve("strategic") 召回/explanation/其他 reason 空缺省/空图/
  bundle round-trip、section 构建/九章渲染/空 insight 优雅/无 section 省略/CEODailyReport round-trip。
- Boundary（8）：builder 禁 add_node/add_edge/feedback/strategic_store/5 源/执行链；
  store 禁 add_node/add_edge/**graph.**（Writer Lineage 锁）；controller 只读保持；recorder 含 record_insight。

### F.4 验收能力映射（P3.6.2 已交付）

| 能力 | 状态 |
|---|---|
| ③ 形成长期战略规则 | ✅ StrategicInsight（Lifecycle / Strategy / Failure / ActionPattern 四类，确定性规则归纳）+ CEO 报告"九、Strategic Memory" |
| Writer Lineage | ✅ StrategicStore → recorder.record_insight（唯一写入口，AST + Spy 双验证） |
| append-only | ✅ 只加 STRATEGIC_INSIGHT 节点/边，不覆盖任何旧 Memory |

### F.5 纪律验收

- 零回归：全量 **2577 passed / 0 failed**（2534 + P3.6.2 +43）；p3_3 / p3_4 / p3_5.x / p3_6_1 / p3_1 / p3_2 全绿；
- builder/store 只读锁：AST 禁 add_node/add_edge；store 禁 `graph.`；controller 只读保持；
- `real_api_called` 恒 False；fail-open 空输入不中断；**不提前做**：❌ LLM/embedding/trend/reflection（P3.6.3）。

### F.6 路线
**P3.6.2（本里程碑 Closed）→ P3.6.3 Memory Reflection Loop（CEO Reflection：wins/mistakes/changed_beliefs/new_rules）→ P3.6.4 Memory Governance（duplicate merge / obsolete archive / contradiction resolution / knowledge lifecycle）→ P4 Autonomous Growth Agent。**

---

## Part G — P3.6.3 Memory Reflection Loop Contract Audit + 契约冻结（2026-07-31）

> 定位：**Understanding → Self-Correction**。P3.6.1 给 CEO 找证据、P3.6.2 总结规律；
> P3.6.3 让 AI CEO **修改自己的认知模型**——每天对昨日决策复盘：
> What was right? What was wrong? What changed? What should we believe now?
> 全部**确定性规则**（无 LLM/embedding），输出 `CEOReflection`（wins / mistakes /
> changed_beliefs / new_rules），供 CEO 报告"十、Memory Reflection"展示。

### G.1 六形状核实（审计结论）

| # | 形状 | 核实结果 | 对 Reflection 的支撑 |
|---|---|---|---|
| R1 | **CEO_DECISION / outcome** | `DecisionKnowledgeRecord{record_id, game_id, decision_type, decision_payload{action,...}, knowledge_signal, outcome{success,reward,metrics,success_rate,simulated,last_validated_at}, source, created_at}`；图节点 payload 全字段；`created_at` 为 ISO UTC 字符串 | ✅ 复盘原料（wins/mistakes）。窗口过滤可用 `created_at.startswith(period)` 确定性实现 |
| R2 | **RetrievalTrace** | `{query, sources}`（P3.6.1 已为 P3.6.3 预埋"AI 当时看了什么"） | ✅ `ReflectionItem.knowledge_signal` 即「当时认知」，证据链可追溯 |
| R3 | **StrategicInsight** | `{insight_id, category, statement, evidence_count, success_rate, confidence, supporting_memories(ceo_decision:{id}), counter_examples, created_at, last_validated_at}` | ✅ changed_beliefs 基础：窗口证据与既有规律方向冲突 → 信念被修正 |
| R4 | **QualityGovernor** | `ceo_decision_records()`（fail-open 读图）/ `_record_is_success`（显式 success 优先，否则 sr≥0.5）/ `detect_conflicts`（同键正反 → KnowledgeConflict 双记录保留） | ✅ wins/mistakes 判定对齐；conflicts 并入 changed_beliefs |
| R5 | **报告消费链** | `CEODailyReport` 已有 memory_reasoning(八)/strategic_memory(九) 字段 + round-trip；sections 纯搬运函数；renderer 段；builder 参数；pipeline `_ceo_report` 挂 bundle | ✅ 新增"十、Memory Reflection"对称接入 |
| R6 | **写入口** | 唯一写入口 = `KnowledgeFeedbackRecorder`（record / attach_outcome / record_insight） | ✅ P3.6.3 对称扩展 `record_reflection`，不破坏唯一 mutation owner |

### G.2 契约冻结（自主拍板，理由写入）

- **D1（Reflection 是否写图）✅ 写**：Reflection 写图（`CEO_REFLECTION` 节点 + `REFLECTION_DERIVED_FROM_DECISION` 边，
  指向 `ceo_decision:{record_id}`）——① P3.6.4 要求"保持 append-only 审计证据；任何合并/归档必须可追溯"，
  Reflection 写图提供审计基础；② 与 P3.6.2 D1 精神一致（唯一写入口 = recorder，`reflection_store` 只调
  `record_reflection`，AST 禁 `graph.`）；③ 未来 P3.6.4 / 复盘可查询。幂等键 = `reflection:{period}`（每天一条）。
- **D2（时间窗口）**：`period` = ISO 日期（`"2026-07-31"`，UTC 日语义）；`created_at.startswith(period)` 确定性过滤；
  空 `created_at` 不属任何窗口。
- **D3（wins/mistakes 判定）**：对齐 quality 层——显式 `outcome.success` 优先；否则 `success_rate ≥ 0.5` → win、
  `< 0.5` → mistake；无 outcome / 无法判定 → 计入 `unresolved_count`（不参与 wins/mistakes）。
- **D4（changed_beliefs）**：① 每条 StrategicInsight 关联窗口记录（supporting_memories ∩ 窗口 record_id），
  窗口加权 sr 方向（≥0.5 / <0.5）与 insight.success_rate 方向冲突 → 信念修正；
  ② 窗口内 `detect_conflicts` 产生的 KnowledgeConflict → 并入（同键正反并存 = 认知冲突）。
- **D5（new_rules）**：按 action 聚类窗口记录——失败 ≥ `_RULE_MIN_FAILURES(2)` → `caution` 规则
  （未来同类决策建议强制审批/降权）；成功 ≥ `_RULE_MIN_WINS(3)` 且失败 0 → `reinforce` 规则（可维持置信）。
  规则是**认知声明**（进报告），不自动改 StrategyLoop/Ranker 权重（本里程碑不改消费端）。
- **D6（幂等）**：`build()` 纯函数；period 过滤确定性；排序按 record_id/insight_id/action；`generated_at` 由
  `as_of` 注入（不注入 = now，测试必须注入固定值）；同输入同输出。
- **D7（边界）**：`reflection_builder.py` 纯计算（AST 禁 `add_node(`/`add_edge(`/feedback/执行链）；
  `reflection_store.py` 禁 `graph.` 只调 `record_reflection`（Writer Lineage）；controller 只读保持。

### G.3 数据契约（冻结）

```python
@dataclass
class ReflectionItem:            # wins / mistakes 的条目（证据链完整）
    record_id: str               # ceo_decision 幂等键
    game_id: str
    decision_type: str
    action: str                  # decision_payload.action
    verdict: bool                # True=win / False=mistake
    success_rate: float
    knowledge_signal: dict       # 当时看了什么（RetrievalTrace 关联）
    source_ref: str              # ceo_decision:{record_id}

@dataclass
class BeliefChange:              # changed_beliefs 条目
    belief_id: str               # insight_id 或 conflict:{key}
    belief: str                  # 人可读（insight.statement 或 key）
    previous_success_rate: float # insight.success_rate
    window_success_rate: float   # 窗口内同关联记录加权 sr
    reason: str
    evidence: List[str]          # record_id 列表

@dataclass
class NewRule:                   # new_rules 条目
    rule_id: str                 # rule:{action}
    action: str
    rule_type: str               # "caution" | "reinforce"
    failures: int
    successes: int
    statement: str               # 确定性模板
    evidence: List[str]          # record_id 列表

@dataclass
class CEOReflection:             # 主产物（用户冻结四段 + 审计字段）
    period: str
    wins: List[ReflectionItem]
    mistakes: List[ReflectionItem]
    unresolved_count: int        # 无 outcome 记录数（不算 win/mistake）
    changed_beliefs: List[BeliefChange]
    new_rules: List[NewRule]
    evidence_count: int
    generated_at: str            # as_of 注入（幂等）
    real_api_called: bool = False
    # to_dict / from_dict（纯序列化，非 DecisionKnowledgeRecord）
```

### G.4 模块分工（对齐 P3.6.2 模式）

| 模块 | 职责 | 写权限 |
|---|---|---|
| `reflection_builder.py`（新） | `MemoryReflectionBuilder.build(period, ceo_records, strategic_insights=None, conflicts=None, as_of="") -> CEOReflection`（纯计算，window 过滤/判定/聚类/信念对比） | ❌ 禁 add_node/add_edge（AST 锁） |
| `feedback.py`（扩展） | `KnowledgeFeedbackRecorder.record_reflection(reflection)`（唯一写入口扩展，period 幂等） | ✅ 唯一 mutation owner |
| `reflection_store.py`（新） | `ReflectionStore(recorder).save`——只调 `record_reflection` | ✅ 经 recorder（禁 graph.） |
| `controller.py`（升级） | 只读方法 `reflection_inputs(period) -> Dict{ceo_records, strategic_insights, conflicts}`（fail-open） | 只读（不变） |
| `models.py` | `NodeType.CEO_REFLECTION` + `EdgeType.REFLECTION_DERIVED_FROM_DECISION`（append-only） | — |
| Report | **"## 十、Memory Reflection（昨日复盘）"**（period/wins/mistakes/changed_beliefs/new_rules；空 → 优雅省略） | — |

### G.5 测试规划（`tests/p3_6_3/`，约 30 项）

- Builder（~14）：window 过滤（跨日不串/空 created_at 排除）/ wins / mistakes / unresolved /
  判定阈值（显式 success 优先、sr 边界 0.5）/ changed_beliefs（方向冲突 + conflicts 并入）/
  new_rules（caution ≥2 失败、reinforce ≥3 全胜、阈值下不生成）/ 空窗口 fail-open / 确定性（排除 generated_at）/
  幂等（固定 as_of）/ round-trip。
- Store（~3）：**Writer Lineage（Spy：save → recorder.record_reflection，非 graph.add_node）** / save fail-open / real_api_called False。
- Recorder（~5）：record_reflection 写节点+边 / **period 幂等**（固定 generated_at 保证 payload 一致）/
  round-trip / fail-open（graph None / 异常）/ 节点类型校验。
- Controller（~2）：reflection_inputs 返回三件套 / 空图 fail-open。
- Report（~4）：十段渲染 / 空 reflection 优雅 / CEODailyReport round-trip / build_reflection_section 纯搬运。
- Boundary（~5）：builder 禁 add_node/add_edge/feedback/执行链；store 禁 `graph.`；controller 只读保持。

### G.6 边界（不提前做）

❌ 不修改 StrategyLoop / Ranker / Optimizer（new_rules 只进报告，不改消费端权重）；
❌ 不产生 Action、不执行优化、不写回 5 源；❌ 无 LLM/embedding；
❌ 不做 duplicate merge / obsolete archive / contradiction resolution / knowledge lifecycle（属 P3.6.4）。

---

## Part H — P3.6.4 Memory Governance Contract Audit + 契约冻结（2026-07-31）

> 定位：**Self-Correction → Governance**。P3.6.1 检索、P3.6.2 总结规律、P3.6.3 每日复盘；
> P3.6.4 让记忆系统**自我治理**——随着时间推移，知识图谱会膨胀、矛盾、老化，
> 需要一组确定性治理规则保证 Memory 长期健康。四个治理维度：
> Duplicate Merge（重复归并）、Obsolete Archive（陈旧归档）、
> Contradiction Resolution（矛盾裁决）、Knowledge Lifecycle（知识生命周期）。
>
> 全部**确定性规则**（无 LLM/embedding）。本里程碑**只做 Contract Audit 与契约冻结，
> 不写实现代码**。Part H 仅记录审计结论和冻结点，实施留在后续 P3.6.4 实现里程碑。

### H.1 四现状核实（审计结论）

#### H.1.1 Duplicate Merge（重复归并）

| 维度 | 现状 | 缺口 |
|---|---|---|
| **幂等去重** | `KnowledgeFeedbackRecorder.record()` 按 `record_id` 幂等（同 ID 重复入图自动去重） | ✅ 这是单条记录级去重，不是语义级归并 |
| **语义重复** | 两个不同 `game_id` 的 portfolio 决策，相同 `action="scale_budget"`、相同 outcome 方向，会生成两个独立的 `CEO_DECISION` 节点 | ❌ 无归并逻辑。两条等价经验散落，未合并成一条证据更强的聚合记录 |
| **同键聚合** | `MemoryQualityGovernor.score_records()` 按 `decision_type:action` 聚合 `KnowledgeScore`（读时聚合，不写回） | ⚠️ 只在读侧临时聚合，下次查询需重新计算 |
| **STRATEGIC_INSIGHT 重复** | `StrategicMemoryBuilder.build()` 每次重新归纳，旧 insight 与新 insight 可能表达相同规律但 `insight_id` 不同 | ❌ 无 insight 去重/合并机制。可能产生大量语义重复的 StrategicInsight |
| **图存储去重** | `GrowthMemoryGraph.add_node()` 按 `id` 幂等（last-write-wins）；`add_edge()` 按 `(src,tgt,type)` 三元组去重 | ✅ 存储层基础去重已在 |

**审计结论**：图存储层的幂等去重充分（节点 id、边三元组），但**语义级的记录归并、insight 去重完全空缺**——这是 P3.6.4 要补齐的核心能力。

#### H.1.2 Obsolete Archive（陈旧归档）

| 维度 | 现状 | 缺口 |
|---|---|---|
| **质量衰减** | `MemoryQualityGovernor.quality_of()` 提供线性时间衰减（今天 1.0→一年前 0.2）；`filter_records(records, min_quality=0.3)` 在读时过滤低质记录 | ✅ 这是在读侧实现的"软废弃"——过期经验自动降权，不影响图本身 |
| **显式废弃标记** | 无——没有 `obsolete`/`archived` 字段在 `CEO_DECISION` 或任何记录上 | ❌ 无法显式标记"这个经验不再适用"（手动覆盖） |
| **自动归档策略** | 无——记录在图中永久驻留，永不自动归档 | ❌ 无时间/质量驱动的归档触发器 |
| **归档后可见性** | N/A——无归档概念 | ❌ 归档记录的读取可见性未定义 |
| **图膨胀** | JSONL append-only，记录只增不减——随着运行天数增加，图文件持续增长 | ⚠️ 虽当前无性能问题（纯内存 Map），但长期需归档策略防止无限增长 |

**审计结论**：质量衰减在读侧实现了"软过滤"，但缺少**显式废弃标记**与**归档概念**。P3.6.4 需要定义：什么是"obsolete"（质量低于阈值 + 时间窗口）、什么是"archived"（从活跃检索中移除但保留审计链）、以及两者之间的转换规则。

#### H.1.3 Contradiction Resolution（矛盾裁决）

| 维度 | 现状 | 缺口 |
|---|---|---|
| **矛盾检测** | `MemoryQualityGovernor.detect_conflicts()` 检测同键正反结果 → `KnowledgeConflict{key, successes[], failures[]}`。**双记录保留不覆盖**。 | ✅ 检测已就绪 |
| **矛盾上报** | P3.6.1 `KnowledgeBundle.conflicts`（list[str]）→ 进 CEO 报告"八、Memory Reasoning"；P3.6.3 `BetChange`（conflicts 并入 changed_beliefs）→ 进"十、Memory Reflection" | ✅ 矛盾已在两级报告可见 |
| **矛盾裁决** | **无**——detect_conflicts 只检测不解决 | ❌ 核心缺口：谁来裁决？如何裁决？裁决后图如何更新？ |
| **冲突优先级** | N/A——无裁决逻辑，自然无优先级 | ❌ 当多组矛盾并存时，无优先级排序 |
| **时间维度** | N/A——"最近的矛盾比 6 个月前的矛盾更重要"没有体现 | ❌ 无矛盾年龄概念 |

**审计结论**：矛盾**检测**完整闭环（detect → report → reflection），但**裁决**完全空缺。P3.6.4 需要定义：裁决策略（自动/半自动/手动）、证据质量权重（更多证据 > 更旧证据）、裁决后图的更新方式（append-only 审计边）。

#### H.1.4 Knowledge Lifecycle（知识生命周期）

| 维度 | 现状 | 缺口 |
|---|---|---|
| **创建** | `KnowledgeFeedbackRecorder.record()` → `CEO_DECISION` 节点（幂等键 = record_id） | ✅ |
| **验证** | `KnowledgeFeedbackRecorder.attach_outcome()` → 合并 outcome 到已有节点（幂等） | ✅ |
| **使用** | 读侧消费：`MemoryQualityGovernor.filter_records()`（质量门）+ `MemoryController.retrieve()`（五路召回） | ✅ |
| **复盘** | P3.6.3 `CEOReflection`（wins/mistakes/changed_beliefs/new_rules）→ 认知修正声明 | ✅ |
| **老化** | 质量衰减（quality_of recency factor）+ 读时过滤 | ⚠️ 只在读侧 |
| **废弃** | 无显式废弃机制 | ❌ 缺口 |
| **归档** | 无归档概念 | ❌ 缺口 |
| **删除** | 全库禁止物理删除（符合纪律） | ✅ 保持 |

**审计结论**：知识生命周期链中"创建→验证→使用→复盘"已完整闭环（P3.5.2→P3.5.3→P3.6.1→P3.6.2→P3.6.3），但"老化→废弃→归档"完全空缺——P3.6.4 要补齐后半段。**全文禁止物理删除**是铁律，所有生命周期终点必须是归档而非删除。

### H.2 审计发现汇总（关键缺口）

| # | 缺口 | 严重程度 | 说明 |
|---|---|---|---|
| G-1 | **无语义重复归并** | 高 | 相同 action+outcome 的多条记录独立存在，证据被稀释（分散而未被合并） |
| G-2 | **无显式废弃标记** | 高 | 无法手动覆盖"这个经验不再适用"，只能靠自然衰减 |
| G-3 | **无矛盾裁决机制** | 高 | 检测闭环完整，但缺乏自动裁决策略和裁决后图更新 |
| G-4 | **无生命周期状态** | 中 | 记录无显式状态（ACTIVE/OBSOLETE/ARCHIVED），治理决策无法持久化 |
| G-5 | **StrategicInsight 去重缺失** | 中 | 每次 `build()` 生成新 insight_id，语义重复的规律无法合并 |
| G-6 | **图膨胀无治理** | 低 | 附录-only JSONL 只增不减，长期需归档策略 |
| G-7 | **CEOReflection 历史不清洁** | 低 | 同一 period 的 reflection 只有 latest-wins，旧版被覆盖而非版本化 |

### H.3 契约冻结（自主拍板，理由写入）

#### H.3.1 数据模型

**冻结：GovernanceRecord 与状态枚举**

```python
class GovernanceAction(str, Enum):     # 治理动作类型
    MARK_OBSOLETE = "mark_obsolete"    # 标记废弃
    MARK_ARCHIVED = "mark_archived"    # 标记归档
    RESOLVE_CONFLICT = "resolve_conflict"  # 裁决矛盾
    MERGE_DUPLICATES = "merge_duplicates"  # 归并重复

class RecordState(str, Enum):          # 记录治理状态
    ACTIVE = "active"                   # 正常（默认）
    CONFLICTED = "conflicted"           # 存在矛盾
    OBSOLETE = "obsolete"               # 已废弃
    ARCHIVED = "archived"               # 已归档

@dataclass
class GovernanceRecord:                 # 一次治理行动的审计记录
    governance_id: str                  # 幂等键：gov_{uuid}
    target_node_id: str                 # 目标节点 ID（ceo_decision:{id} / strategic_insight:{id}）
    action: GovernanceAction
    reason: str                         # 人可读理由
    evidence: List[str]                 # 支撑 evidence（source_ref 列表）
    previous_state: RecordState         # 动作前状态
    new_state: RecordState              # 动作后状态
    merged_from: List[str] = ...        # MERGE_DUPLICATES 时：归并来源节点列表
    created_at: str                     # ISO UTC
    real_api_called: bool = False
```

**理由**：治理动作本身需要审计链（谁在什么时候做了什么），不应直接改写目标记录 payload（那样丢失治理历史）。`GovernanceRecord` 既是治理决策的记录，也是状态的声明——通过 `previous_state → new_state` 变迁可追溯完整生命周期。

**冻结点 H1**：治理动作不影响被治理记录的原始 payload。治理状态通过 GovernanceRecord 节点 + 审计边 (`GOVERNANCE_APPLIED_TO`) 声明，不修改 `CEO_DECISION`/`STRATEGIC_INSIGHT` 节点的原有 payload。

**冻结点 H2**：`NodeType.GOVERNANCE_RECORD`（治理记录节点）+ `EdgeType.GOVERNANCE_APPLIED_TO`（治理→目标节点审计边）。图扩展 append-only，不覆盖任何旧节点。

#### H.3.2 状态机

**冻结：记录生命周期状态机**

```
              record()/record_insight()
                      │
                      ▼
    ┌────────────────────────────────────┐
    │              ACTIVE                │ ◀── 默认初始状态
    │  (质量分正常, 参与检索与建议)        │
    └───────┬────────────┬───────────────┘
            │            │
    detect_conflicts      quality < OBSOLETE_THRESHOLD
    发现同键相反结果       且持续时间 > GRACE_PERIOD
            │            │
            ▼            ▼
    ┌──────────────┐  ┌──────────────────┐
    │  CONFLICTED  │  │    OBSOLETE      │
    │ (存在矛盾,    │  │ (质量过低/过时,   │
    │  带警告可见)  │  │  默认不参与检索)  │
    └──────┬───────┘  └────────┬─────────┘
           │                   │
    resolve_conflict    显式归档 / 超 ARCHIVE_AFTER
    裁决后矛盾消除        │
           │                   │
           ▼                   ▼
    ┌──────────────┐  ┌──────────────────┐
    │   ACTIVE     │  │    ARCHIVED      │
    │ (重返正常)    │  │ (仅审计可见,      │
    └──────────────┘  │  不参与日常检索)   │
                      └──────────────────┘
```

**状态转换规则**：

| 转换 | 触发器 | 条件 |
|---|---|---|
| → ACTIVE | record/record_insight 创建 | 默认初始状态 |
| ACTIVE → CONFLICTED | detect_conflicts | 同键存在 ≥1 成功 + ≥1 失败记录 |
| ACTIVE → OBSOLETE | quality decay | quality < `OBSOLETE_THRESHOLD(0.1)` 持续 ≥ `GRACE_PERIOD_DAYS(30)` |
| CONFLICTED → ACTIVE | resolve_conflict | 矛盾被裁决消除 |
| CONFLICTED → OBSOLETE | quality decay | 同 ACTIVE→OBSOLETE |
| OBSOLETE → ARCHIVED | 显式归档或自动策略 | 显式 `mark_archived` 或距上次激活 > `ARCHIVE_AFTER_DAYS(365)` |
| OBSOLETE → ACTIVE | 新证据注入 | 新 outcome 注入后 quality 回升超过 `REACTIVATE_THRESHOLD(0.3)` |
| ARCHIVED → (终态) | — | 不可逆（归档后永久保留审计，不复活） |

**冻结点 H3**：状态标签不存储在目标节点 payload 中（避免破坏原始记录），而是由 GovernanceRecord 节点 + 最新治理边的 `new_state` 字段推导。读取时：取目标节点上最新的 `GOVERNANCE_APPLIED_TO` 边，读取其 `new_state` 作为当前状态；无边 → 默认 ACTIVE。

#### H.3.3 唯一写入口

**冻结：GovernanceStore → KnowledgeFeedbackRecorder.govern_record()**

对齐 P3.6.2 StrategicStore / P3.6.3 ReflectionStore 的 Writer Lineage 模式：

```
GovernanceEngine ── GovernanceRecord ──▶ GovernanceStore ──▶ recorder.govern_record() ──▶ GrowthMemoryGraph
```

- **`governance_engine.py`**（新，纯计算）：`GovernanceEngine`——读图 + 计算治理动作，产出 `List[GovernanceRecord]`。禁 `add_node/add_edge/feedback/graph.`。
- **`governance_store.py`**（新，写适配）：`GovernanceStore(recorder).save/save_all`——只调 `recorder.govern_record()`，禁 `add_node/add_edge/graph.`。
- **`feedback.py`**（扩展）：`KnowledgeFeedbackRecorder.govern_record(gov: GovernanceRecord)`——唯一写入口扩展：写 `GOVERNANCE_RECORD` 节点 + `GOVERNANCE_APPLIED_TO` 审计边；幂等键 = `governance_id`；fail-open。

**冻结点 H4**：`KnowledgeFeedbackRecorder` 保持唯一 mutation owner。GovernanceStore 禁直接 `graph.`（AST 锁死），读写路径全经 recorder。

#### H.3.4 Append-Only 审计

**冻结：治理逻辑不修改任何被治理节点的 payload**

所有治理动作通过**新节点 + 新边**表达：

- `GOVERNANCE_RECORD` 节点：记录治理决策全文（governance_id / target / action / reason / evidence / previous_state / new_state / merged_from / created_at）
- `GOVERNANCE_APPLIED_TO` 边：治理节点 → 目标节点（`ceo_decision:{id}` / `strategic_insight:{id}`）
- `MERGE_SOURCE` 边（仅 MERGE_DUPLICATES）：治理节点 → 被归并源节点（归并来源链可追溯）

**冻结点 H5**：禁止修改被治理节点的 payload（不修改 `CEO_DECISION.outcome`/`STRATEGIC_INSIGHT.statement` 等）。治理权威完全在 GovernanceRecord 节点 + 关联边中表达。

#### H.3.5 幂等键

| 操作 | 幂等键 | 说明 |
|---|---|---|
| `govern_record` 写节点 | `governance_id`（`gov_{uuid}`） | 每生成一条 GovernanceRecord 都带唯一 id |
| 重复检测（语义归并） | `{decision_type}:{action}` + 同一 outcome 方向 | 归并只能执行一次——已归并的组不能再二次归并 |
| 废弃标记 | `{target_node_id}:mark_obsolete`（只一次） | 同一记录不会重复废弃 |
| 归档标记 | `{target_node_id}:mark_archived`（只一次） | 同一记录不会重复归档 |
| 矛盾裁决 | `{conflict_key}:{resolution_period}` | 按周期可重新裁决（矛盾可能随时间演變） |

**冻结点 H6**：治理动作的幂等性由 GovernanceRecord.governance_id（写节点）+ 重复治理检测（目标节点+动作类型已有记录则跳过）保证。

#### H.3.6 冲突优先级

当多组矛盾并存时，按以下优先级排序：

1. **证据量差异最大**：`|successes| - |failures||` 最大 → 先解决证据量悬殊的矛盾
2. **最新验证时间最新**：同一证据量差异下，`last_validated_at` 最新优先
3. **质量分最高**：同一证据量 + 同一新鲜度下，quality 最高优先

不可自动裁决的情况（需 CEO 关注）：证据量差异 ≤ 2:1 且双方质量均 > 0.5 → 标记为 `requires_ceo_review` 而非自动裁决。

**冻结点 H7**：自动裁决条件 = 优势侧 evidence 数量 ≥ 3×劣势侧 evidence 数量。不满足 → 标记 `requires_ceo_review` 由报告上报。

#### H.3.7 归档而非删除

- ❌ **绝对禁止物理删除**：禁止 `remove_node/remove_edge` 或 JSONL 行删除——与全库 append-only 纪律一致
- 归档 = 软移除：`RecordState.ARCHIVED` → `GovernanceRecord(new_state=ARCHIVED, reason="...")`
- 归档记录：默认不参与 `retrieve()` 五路召回、不参与 `ceo_decision_records()`、不参与 `similar_games()`；但在审计/调试接口可见
- **归档触发**：
  - 自动：`OBSOLETE` 状态持续 ≥ `ARCHIVE_AFTER_DAYS(365)` → 自动归档
  - 手动：显式调用 `mark_archived(reason="...")` 时

**冻结点 H8**：禁止物理删除任何记录。归档 = 治理状态标记（ARCHIVED），审计链可追溯，默认隐藏但可查。

#### H.3.8 读取可见性

| 状态 | `retrieve()` | `ceo_decision_records()` | `filter_records()` | `reflection_inputs()` | 报告 | 审计接口 |
|---|---|---|---|---|---|---|
| ACTIVE | ✅ 正常 | ✅ 正常 | 按质量过滤 | ✅ 属于窗口 | 正常展示 | ✅ |
| CONFLICTED | ✅ 带警告 | ✅ 带标记 | 按质量过滤（不减权） | ✅ 带冲突标记 | 报告含 "Conflict" 行 | ✅ |
| OBSOLETE | ❌ 默认排除 | ❌ 默认排除 | ❌ quality < threshold 已过滤 | ❌ 不属于活跃窗口 | 不展示 | ✅ |
| ARCHIVED | ❌ 排除 | ❌ 排除 | ❌ 排除 | ❌ 排除 | 不展示 | ✅ |

**冻结点 H9**：OBSOLETE 和 ARCHIVED 记录在**所有正常读路径**上默认不可见。`ceo_decision_records()` 加 `include_obsolete`/`include_archived` 布尔参数（默认 False）供审计/调试使用。

#### H.3.9 Fail-Open/Fail-Closed 边界

| 操作 | 策略 | 说明 |
|---|---|---|
| 治理引擎计算失败 | **Fail-Open** | 返回空 GovernanceRecord 列表，不中断 pipeline |
| governance_store.write 失败 | **Fail-Open** | 静默跳过，日志记录，不中断 pipeline |
| 治理状态读取失败 | **Fail-Open** | 默认所有记录为 ACTIVE（无边 = 未治理） |
| 归档/废弃后无法恢复 | **Fail-Closed** | ARCHIVED = 终态，不可逆（保护审计完整性） |
| 矛盾自动裁决（证据不足） | **Fail-Open** | 不裁决，标记 `requires_ceo_review`，不上报为错误 |
| recorder.govern_record graph None | **Fail-Open** | 返回空计数，不中断 pipeline |

**冻结点 H10**：治理全线 fail-open（与全库一致），但归档/废弃操作本身不可逆（ARCHIVED = 终态）。唯一 mutation owner = KnowledgeFeedbackRecorder，所有写经 recorder → fail-open 返回空计数。

#### H.3.10 报告与 Pipeline 消费

- **Pipeline 位置**：`_governance` 阶段，位于 `ceo_reflection` 之后、`ceo_report` 之前
  ```
  ... → strategy_loop → portfolio → ceo_reflection → **_governance** → ceo_report
  ```
- **报告段落**：CEODailyReport 新增 `governance` 字段（round-trip）+ `build_governance_section` + renderer **"## 十一、Memory Governance（记忆治理）"**
  - 本期重复归并：N 组（归并后 node 数 / 归并前 node 数）
  - 本期废弃标记：N 条（按废弃理由分组）
  - 本期矛盾裁决：N 组（其中自动裁决 X 组，待 CEO 关注 Y 组）
  - 本期归档：N 条（归档理由）
  - 知识图谱健康度：活跃记录数 / 废弃记录数 / 归档记录数 / 矛盾记录数
- 空 → 优雅省略

**冻结点 H11**：Governance 阶段位于 Reflection 之后、Report 之前（治理必须在复盘完成后才能执行——需要矛盾检测的最新结果）。空结果（无治理动作）→ pipeline 正常继续，不产生额外 output。

#### H.3.11 测试矩阵

**`tests/p3_6_4/` 约 30 项：**

| 类别 | 数量 | 覆盖点 |
|---|---|---|
| **Governance Engine**（~12） | 12 | 重复检测（同键同方向→归并候选 / 同键不同方向→不归并）/ 废弃判定（quality 持续低于阈值 / 不足 grace period / 质量恢复不废弃）/ 矛盾裁决（证据量比≥3:1→自动裁决 / <3:1→标记 requires_ceo_review）/ 自动归档（OBSOLETE 超期）/ 空图 fail-open / 确定性（排除 governance_id+created_at）/ 幂等 |
| **Governance Store**（~3） | 3 | **Writer Lineage（Spy: save→recorder.govern_record，非 graph.add_node）** / save fail-open / real_api_called False |
| **Recorder**（~5） | 5 | govern_record 写节点+边 / **governance_id 幂等** / target_node 不存在→fail-open / graph None→fail-open / 节点类型校验 |
| **Controller（扩展）**（~2） | 2 | governance_inputs 返回需要治理的记录列表（OBSOLETE 候选 / 重复组 / 矛盾组） / 空图 fail-open |
| **Report**（~4） | 4 | "## 十一、Memory Governance" 渲染 / 空治理优雅省略 / CEODailyReport round-trip / build_governance_section 纯搬运 |
| **Boundary**（~6） | 6 | governance_engine.py 禁 add_node/add_edge/feedback/governance_store/5 源/执行链；governance_store.py 禁 add_node/add_edge/graph./5 源/执行链；recorder 含 govern_record；controller 只读保持 |

**冻结点 H12**：测试矩阵不包含实现代码——本里程碑只冻结测试范围。引擎纯计算 AST 锁（禁 add_node/add_edge/feedback/governance_store/5源/执行链）；store 禁 graph.（Writer Lineage 锁）。

#### H.3.12 AST 边界锁

**P3.6.4 新增模块的 AST 锁：**

| 模块 | 禁止 | 必须包含 |
|---|---|---|
| `governance_engine.py` | `add_node(`, `add_edge(`, `feedback`, `governance_store`, `graph.`, 5 源写回, 执行链 | `GovernanceRecord`, `GovernanceEngine`, `def run` |
| `governance_store.py` | `add_node(`, `add_edge(`, `graph.`, 5 源写回, 执行链 | `GovernanceStore`, `def save`, `govern_record` |
| `feedback.py`（扩展） | （现有锁保持） | `govern_record` |
| `controller.py`（扩展） | （现有只读锁保持：禁 add_node/add_edge/feedback） | `governance_inputs` |

**冻结点 H13**：governance_engine 纯计算（禁所有 mutation）；governance_store 只调 recorder.govern_record（禁 graph. 禁 add_node/add_edge）；recorder 扩展 govern_record（唯一写入口保持）；controller 扩展 governance_inputs（只读）。

### H.4 需要用户拍板的重大契约分歧

以下决策点存在多种合理方案，需用户决定方向后冻结为 P3.6.4 正式契约：

#### D-GOV-1：归并策略（Duplicate Merge 后）——被归并的原始记录如何处理？

| 选项 | 描述 | 推荐 |
|---|---|---|
| **A. 标记 OBSOLETE** | 归并后原始记录标记 OBSOLETE，后续检索只看到归并后的聚合记录 | ⭐ 推荐 |
| B. 保持 ACTIVE | 原始记录保持 ACTIVE，归并只产生一个 Advisory 引用，不改变可见性 |
| C. 标记 ARCHIVED | 原始记录直接归档，最激进方案 |

**推荐 A**：标记 OBSOLETE 而非 ARCHIVED（保留恢复空间），且 OBSOLETE 默认不参与检索（与 H.3.8 可见性一致）。归并后的聚合表达通过 GovernanceRecord 的 `merged_from` 字段追溯。

#### D-GOV-2：重复检测范围——归并是跨游戏还是同游戏内？

| 选项 | 描述 | 推荐 |
|---|---|---|
| A. **跨游戏** | 相同 action+outcome 方向的记录，无论 game_id 是否相同，都视为重复 | 
| **B. 仅同游戏** | 只有同 game_id 的记录才归并，跨游戏经验保持独立 | ⭐ 推荐 |

**推荐 B**：跨游戏的相同 action 可能在不同生命周期/市场中表现完全不同——归并会丢失上下文。同游戏内归并需求更明确（例如同一游戏的多次 portfolio review 得出相同结论）。跨游戏的经验聚合在 StrategicInsight 层（P3.6.2）通过 Strategy/Failure Insights 实现。

#### D-GOV-3：废弃判定方式——全自动还是允许手动？

| 选项 | 描述 | 推荐 |
|---|---|---|
| A. **仅自动** | 只通过 quality < OBSOLETE_THRESHOLD + GRACE_PERIOD 自动判定 | ⭐ 推荐 |
| B. 自动 + 手动 | 支持显式 `mark_obsolete(reason)` 手动覆盖 |
| C. 全手动 | 不做自动判定，所有废弃由 pipeline 传参显式触发 |

**推荐 A**：仅自动判定最简洁，且与 "无 LLM/无人类介入" 的确定性原则一致。手动废弃可通过 GovernanceStore 的 `mark_obsolete` 接口预留（API 存在但不强制 pipeline 调用），支持未来扩展。

#### D-GOV-4：矛盾裁决——自动 vs 半自动 vs 手动？

| 选项 | 描述 | 推荐 |
|---|---|---|
| A. **混合（推荐）** | 证据量比 ≥3:1 → 自动裁决（优势侧胜）；<3:1 → 标记 requires_ceo_review | ⭐ 推荐 |
| B. 全自动 | 一律优势侧胜出，无论证据量比率 |
| C. 全手动 | 只检测矛盾，一律标记 requires_ceo_review，不自动裁决 |

**推荐 A**：混合方案平衡了自动化与谨慎——证据悬殊时自动裁决有意义（减少人工负担），证据接近时上报警告（避免误判）。3:1 比率可按需调整参数。

#### D-GOV-5：知识生命周期阈值

以下阈值可参数化，建议初始值如下：

| 参数 | 推荐初始值 | 说明 |
|---|---|---|
| `OBSOLETE_THRESHOLD` | `0.1` | quality < 此值标记 OBSOLETE（当前 decay 一年前 sr=1.0 的 quality=0.2，约 2 年后 sr=1.0 的 quality 会到 0.1 以下） |
| `GRACE_PERIOD_DAYS` | `30` | 连续低于阈值 30 天才执行废弃（防止单日数据抖动） |
| `ARCHIVE_AFTER_DAYS` | `365` | OBSOLETE 状态持续 365 天后自动归档 |
| `REACTIVATE_THRESHOLD` | `0.3` | OBSOLETE 记录因新证据注入回升到此 quality 以上 → 重返 ACTIVE |
| `AUTO_RESOLVE_RATIO` | `3.0` | 优势侧 evidence ≥ 3×劣势侧 → 自动裁决 |
| `DUPLICATE_SIMILARITY_THRESHOLD` | 同 `decision_type:action` + 同 outcome 方向 | 归并候选条件 |

**用户需确认**：以上阈值是否合适，或者需要调整任意值。

### H.5 纪律红线（铁律）

- ❌ **禁止物理删除任何旧 Memory**（node/edge/JSONL 行）——对齐 H.3.7 "归档而非删除"；
- ❌ **KnowledgeFeedbackRecorder 为唯一 mutation owner**——governance_store 禁 `graph.`（AST 锁死），所有写经 `recorder.govern_record()`；
- ❌ **禁止直接 graph 写入**——任何新增模块禁 `add_node(`/`add_edge(` 调用；
- ❌ **禁止 LLM / embedding**——全部确定性规则，不调用任何外部模型；
- ❌ **禁止产生 Action 或调用执行层**——治理是声明性动作，不触发 Provider/SafeExecutor/ExecutionContract；
- ❌ **不修改 StrategyLoop / Ranker / Optimizer**——Governance 是独立阶段，不改消费端权重/行为；
- ❌ **不提前做 P4**——治理上限为"保持 Memory 健康"，不涉及 Autonomous Growth Agent 的决策自主性；
- ✅ **`real_api_called` 恒 False**；
- ✅ **fail-open**（治理异常 → 空结果，不中断 pipeline 主链）；
- ✅ **append-only 审计**（所有治理决策通过新节点/边记录，不覆盖原始记录 payload）；
- ✅ **确定性**（同输入同输出）。

### H.6 模块分工（冻结）

| 模块 | 职责 | 写权限 |
|---|---|---|
| `governance_engine.py`（新） | `GovernanceEngine.run(ceo_records, strategic_insights, conflicts, as_of) -> List[GovernanceRecord]`——重复检测/废弃判定/矛盾裁决/归档候选，纯计算 | ❌ 禁 add_node/add_edge/feedback/governance_store/graph./5源/执行链（AST 锁死） |
| `governance_store.py`（新） | `GovernanceStore(recorder).save/save_all`——只调 `recorder.govern_record()` | ✅ 经 recorder（禁 graph.） |
| `feedback.py`（扩展） | `KnowledgeFeedbackRecorder.govern_record(gov: GovernanceRecord)`——唯一写入口扩展 | ✅ 唯一 mutation owner |
| `models.py`（扩展） | `NodeType.GOVERNANCE_RECORD` + `EdgeType.GOVERNANCE_APPLIED_TO` + `EdgeType.MERGE_SOURCE` | — |
| `controller.py`（扩展） | `governance_inputs(as_of) -> Dict`——返回需要治理的记录集（OBSOLETE 候选/重复组/矛盾组） | 只读 |
| `quality.py`（扩展） | `ceo_decision_records(include_obsolete=False, include_archived=False)`——可见性参数 | 只读 |
| Report | "## 十一、Memory Governance（记忆治理）"（归并/废弃/矛盾裁决/归档/健康度） | — |

### H.7 图扩展（append-only，不覆盖旧 Memory）

```python
# models.py 新增
class NodeType(str, Enum):
    # ... 现有所有类型保持不变 ...
    GOVERNANCE_RECORD = "governance_record"  # P3.6.4

class EdgeType(str, Enum):
    # ... 现有所有类型保持不变 ...
    GOVERNANCE_APPLIED_TO = "governance_applied_to"  # GOVERNANCE_RECORD → 目标节点
    MERGE_SOURCE = "merge_source"                     # GOVERNANCE_RECORD → 被归并源节点
```

### H.8 路线

**P3.6.4 Implementation 已于 2026-08-03 完成（Closed）→ 下一阶段 P4 Autonomous Growth Agent。**

实施采用 H.4 推荐默认值：归并源标记 OBSOLETE、仅同游戏内语义归并、
自动质量废弃并预留显式 Store API、3:1 混合矛盾裁决，以及 H.4/D-GOV-5
列出的生命周期阈值。生产链顺序已冻结为 Reflection 写回 → Governance →
CEO Report；治理为空时报告优雅省略。

验收基线：`tests/p3_6_4/` 30 passed；P3.6.3 + P3.6.4 77 passed；
全量 2654 passed / 0 failed（Python 3.11.15，UTF-8 模式）。

### H.9 不提前做的 P4 能力

❌ Autonomous Learning Rate adjustment（Governance 提供证据但 P4 决定"学到多少"）；
❌ Agent-initiated knowledge pruning（Governance 标记废弃但 P4 决定是否删除）；
❌ Cross-agent knowledge sharing（多 Agent 记忆合并属 P4 多实例协调）；
❌ Trend prediction from lifecycle patterns（Governance 管理状态但 P4 做趋势预测）；
❌ Auto-retrain strategy weights（new_rules 早已进报告，P4 才自动写入 StrategyLoop 权重）。
