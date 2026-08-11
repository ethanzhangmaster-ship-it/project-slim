# P3.2 — CEO Daily Report（运营决策单）

> 状态：**规划 / 待实现**
> 前置：P3.1 Daily Operator Scheduler（Closed ✅）、E17（决策脑）、P1.7（真实审计）、P2（执行链）、E17.7（记忆图谱）
> 定位：**Presentation + Action Orchestration Layer**——只聚合、转换、编排，不重算、不决策、不调 Provider、不绕 Approval、不改 Decision。

---

## 0. 一句话定位

P3.1 解决了「系统每天能自动跑一次」。P3.2 解决「跑完之后，CEO / 运营人员能不能直接拿结果做决策」。

这一层**不重新做数据分析、不侵入 E17 / P2**。所有数字都来自既有链路的最终产物，P3.2 只是把它们收敛成一张「运营决策单」+ 一份「行动队列」。

---

## 1. 设计原则（纪律）

### 不做（Do NOT）
- ❌ 不重新计算 ROAS / 预期收益 / 风险分（只读 `DailyRunResult` 已定结论）
- ❌ 不重新判断机会（不调 E17.2 / E17.3 / E17.8）
- ❌ 不调用任何 Provider / 平台 API（P2.4 是唯一执行出口，P3.2 无副作用）
- ❌ 不绕过 P2.3 Approval（三态来自 `ActionKind`，已含审批结论）
- ❌ 不修改任何 `Decision` / `Audit` / `Execution` 对象（只读）
- ❌ 不引入 LLM / 不确定逻辑（确定性，同数据同输出，可复现到 1e-6）

### 只做（DO）
- ✅ 聚合既有结果（health / opportunities / actions / risks / learning / execution）
- ✅ 转成 CEO 可读语言（中文 Markdown 决策单）
- ✅ 生成行动队列（AUTO / APPROVAL / BLOCKED 三态）
- ✅ 标记责任状态与「为什么」（source + explanation）
- ✅ 输出风险说明（warnings / 闸门 / 升级）

---

## 2. 复用结论（扫描 P3.1 既有产物）

| 来源 | 数据 | P3.2 用法 | 纪律 |
|---|---|---|---|
| E17.9 `DailyRunResult.actions` | `List[DailyActionItem]`（kind=AUTO/APPROVAL/BLOCK） | **三态唯一权威源**，直接读 | 零重算 |
| E17.9 `DailyRunResult.priorities` | `List[GamePriority]` | 机会 Top N | 零重算 |
| E17.3 `dec_report.decisions` | `List[GrowthDecision]` | 取 confidence/risk/expected_value/reason 解释 WHY | 只读 |
| E17.8 `sim_report.simulations` | `List[DecisionSimulation]` | 取 `flag.status/reason` 解释 BLOCK | 只读 |
| P2.5 `ExecutionDailyReport` | counts/warnings/learnings/health | 执行小结 + 风险 + 学习 | 零重算 |
| P2.6 `recoveries` | `List[RecoveryResult]` | 恢复/升级统计 | 只读 |
| P1.7 `AuditReport` | green/yellow/red/decision_ready | 健康补充 | 只读 |
| E17.7 `extract_patterns(graph)` | 学习模式 | **可选** learning 增强 | READ，非必须 |

**三态收敛点**：`ActionKind`（E17.9）是 AUTO/APPROVAL/BLOCK 唯一权威枚举。代码库另有 `DecisionType`(E17.3)、`RealityGate` 等级、`PreFlightStatus`(E17.8) 等冲突枚举，**P3.2 一律收敛到 `ActionKind`**，不复用其它。

**现成渲染器可 CALL（不重写）**：`AuditReport.to_markdown()`、`DecisionReport.to_markdown()`、`PortfolioSimulationReport.to_markdown()`、`ExecutionDailyReport.to_markdown()`、`MorningReporter.build_ceo(...)`。P3.2 的 `Renderer` 仅在「决策单」层面组合，不直接重写这些。

---

## 3. 文件布局（新增 `src/operator/report/` 6 文件，namespace package）

```
src/operator/report/
  __init__.py          # 导出 CEODailyReport / CEOAction / ActionState / build_ceo_report
  models.py            # CEODailyReport + CEOAction + ActionState + 各 section 模型
  action_formatter.py  # DailyActionItem(+decision+sim) -> CEOAction（三态收敛 + WHY）
  sections.py          # 各 section 数据装配（health/opportunities/risks/learning/exec）
  builder.py           # CEOReportBuilder：聚合全部输入 -> CEODailyReport + 落盘
  renderer.py          # CEODailyReport -> Markdown 决策单 / JSON
```

---

## 4. 契约（Contract）

### 4.1 模型：`CEODailyReport`

```python
@dataclass
class CEODailyReport:
    report_id: str                       # 确定性：f"ceo-{date}"
    date: str
    health_summary: HealthSummary
    opportunities: List[OpportunityItem]
    actions: List[CEOAction]             # 行动队列（三态）
    risks: List[RiskItem]
    learning_summary: List[str]
    execution_summary: ExecutionSummary
    real_api_called: bool = False
```

- `to_dict()` / `from_dict()`：纯 dataclass，可 JSON 序列化（str-Enum 用 `.value`）。
- `HealthSummary`: company_status, status_label, game_count, total_revenue, total_dau, total_spend, avg_confidence, at_risk[], auto/approval/blocked/observed 计数。
- `OpportunityItem`: rank, game_id, action, opportunity_type, priority_score, expected_value, confidence, urgency, sim_gate。
- `RiskItem`: level("info"|"warn"|"critical"), title, detail。
- `ExecutionSummary`: total_executions, success, failed, rollback, blocked, health_level, warnings[], recovery{recovered,escalated}, real_api_called。

### 4.2 模型：`CEOAction`（行动三态）

```python
class ActionState(str, Enum):
    AUTO = "auto"          # ✅ AUTO EXECUTE
    APPROVAL = "approval"  # 🖐 APPROVAL REQUIRED
    BLOCKED = "blocked"    # ⛔ BLOCKED

class CEOActionStatus(str, Enum):
    EXECUTED = "executed"               # AUTO 已落地（经 P2.4）
    AWAITING_APPROVAL = "awaiting"      # APPROVAL 等 CEO
    PREVENTED = "prevented"             # BLOCK 被闸门拦下

@dataclass
class CEOAction:
    action_id: str          # 确定性：f"cea-{idx:03d}"
    game_id: str
    action_type: str       # 动作标签（如 ua_scale）
    source: str            # 责任来源（e17.3_decision+p2.4 / +p2.3 / e17.8_gate）
    priority: float
    execution_mode: ActionState
    status: CEOActionStatus
    explanation: str       # WHY：来自 confidence/risk/expected_value/闸门 reason
```

### 4.3 输入契约（Builder.build）

```python
build_ceo_report(
    daily: DailyRunResult,
    company: Optional[CompanySnapshot] = None,
    exec_report: Optional[ExecutionDailyReport] = None,
    audit_report: Optional[AuditReport] = None,
    recoveries: Optional[List[RecoveryResult]] = None,
    patterns: Optional[List[str]] = None,   # E17.7 可选学习增强
) -> CEODailyReport
```

### 4.4 输出契约（落盘）

`outputs/operator/<date>/`：
- `daily_report.md` — **运营决策单**（CEO 直接拿做决策，非日志）
- `daily_report.json` — `CEODailyReport.to_dict()`
- `actions.json` — `[a.to_dict() for a in actions]`（行动队列，供自动化/看板消费）

工程日志（保留可追溯）改名 `engineering_report.md`（P3.1 `_report` 阶段产物）。

---

## 5. 与 P3.1 集成点（不改 Pipeline 数据流，只新增 Stage）

在 `src/operator/pipeline.py` 的 `runner` 元组里，**Memory 之后插入** `STAGE_CEO_REPORT`：

```
... -> STAGE_RECOVERY -> STAGE_MEMORY -> STAGE_CEO_REPORT -> STAGE_REPORT
```

- `_ceo_report` 阶段：读 `s["daily"] / s["company"] / s["exec_report"] / s["audit_report"] / s["recoveries"]`，调用 `build_ceo_report(...)`，写三文件，回填 `s["ceo_report_path"/"ceo_report_json"/"actions_path"]`。
- `_aggregates` 新增 `ceo_report_path / ceo_report_json / actions_path / engineering_report_path`，`report_path` 指向 `daily_report.md`（交付物）。
- `ALL_STAGES` 增加 `STAGE_CEO_REPORT = "ceo_report"`（StageResult 校验用）。
- `scripts/run_daily_operator.py` 复跑即天然产出三文件（无需改入口逻辑，仅补一行打印）。

---

## 6. 测试设计（`tests/p3_2/` 5 文件，~40–60 tests）

- `test_models.py`：模型 round-trip（to_dict/from_dict）、ActionState 枚举、默认值。
- `test_action_formatter.py`：三态收敛 + WHY 解释。
  - **Case1 AUTO**：`ActionKind.AUTO` + 低险高置信决策 → `execution_mode=AUTO, status=EXECUTED, explanation` 含「已自动执行」。
  - **Case2 APPROVAL**：`ActionKind.APPROVAL` + `risk=0.6` → `execution_mode=APPROVAL, status=AWAITING_APPROVAL, explanation` 含「审批」。
  - **Case3 BLOCK**：`ActionKind.BLOCK` + `confidence=0.3` → `execution_mode=BLOCKED, status=PREVENTED, explanation` 含闸门 reason。
- `test_sections.py`：health/opportunities/risks/learning/execution 各 section 装配正确。
- `test_renderer.py`：Markdown 决策单结构（六段标题、三态分组表）、JSON 键齐全、actions.json 形状。
- `test_integration.py`：**Case4 完整链路**——`build_growth_operator(demo)` → `run_daily_cycle` → 断言三文件存在且 `daily_report.md` 为决策单（含 AUTO/APPROVAL/BLOCKED 三态标题、行动队列、风险与执行小结）。

---

## 7. 完成标准（DoD）

- [ ] `python scripts/run_daily_operator.py --date 2026-07-31` 生成 `outputs/operator/2026-07-31/{daily_report.json, daily_report.md, actions.json}`。
- [ ] `daily_report.md` 是「运营决策单」而非日志：含今日健康概览、机会 Top N、今日行动队列（AUTO/APPROVAL/BLOCKED 三态 + 责任来源 + WHY）、风险、执行小结、学习。
- [ ] `actions.json` 含每个 action 的 `execution_mode` / `status` / `explanation`，可被自动化消费。
- [ ] 全链路 `real_api_called` 恒 False（DRY_RUN 纪律不被破坏）。
- [ ] 双版本串行回归全绿（managed 3.13.12 + ci311 3.11.15），无新增回归。
- [ ] P3.2 标记为 Closed ✅。

---

## 8. P3 后续路线

- **P3.3 Strategy Loop**：读决策单 → 调策略（P3.3，真正做决策优化）。
- **P3.4 Portfolio Optimization**：组合层优化（跨游戏预算再分配）。
- P3.2 是 P3 链条里「人能消费」的关键一环；上游越自动化，下游越要「可读、可决策、可追责」。
