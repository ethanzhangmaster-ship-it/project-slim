# P3.1 Daily Operator Scheduler — Contract（先契约后实现）

> 定位：**薄编排层**。把已有能力（E17.9 每日循环 + P1.7 审计 + P2.1–P2.6 执行链）编排成
> 一条命令可重复运行的每日增长经营流程。**不新建重复 orchestrator**：
> E17.2–E17.8 循环直接复用 `DailyGrowthOperatorAgent`；本层只补 4 段胶水
> （audit / approval 显式接线 / monitor / recovery）+ 状态守卫 + 汇总日报。

## 0. 扫描结论（#548，复用清单）

| 阶段 | 复用 | 新写胶水 |
|---|---|---|
| reality_refresh | `GrowthRealityHub.refresh`（经 E17.9 `run_daily`） | 否 |
| audit | `RealityAuditor.audit` + `AuditReport.to_markdown`（P1.7） | **是**（E17.9 未含） |
| opportunities/simulations/decisions | E17.9 `DailyGrowthOperatorAgent._run` 内部（E17.2/17.3/17.8） | 否 |
| approval | `ApprovalService`（P2.3）+ `build_contract`（P2.1） | **是**（E17.9 只进 queue 未走 Service） |
| executions | `build_execution_router` + `build_safe_executor`（P2.2/P2.4） | **是**（把 APPROVAL 类决策转 P2 链，DRY_RUN） |
| monitor | `ExecutionMonitor.observe_batch/report`（P2.5） | **是**（E17.9 未接） |
| recovery | `build_recovery_engine` + `RecoveryEngine.handle`（P2.6） | **是**（E17.9 未接） |
| memory | `JsonlOperatorMemory`（E17.9）+ FeedbackBridge/RecoveryMemoryBridge（P2.5/2.6 内部自动） | 否 |
| report | `MorningReporter`（E17.9）+ `AuditReport.to_markdown` + `ExecutionDailyReport` | **是**（汇总为单一日报） |

## 1. 模块布局（`src/operator/`，6 文件）

```
src/operator/
  __init__.py    # 导出 GrowthOperatorScheduler / OperatorRunResult / build_growth_operator
  models.py      # OperatorRunResult / StageResult / RunStatus（纯 dataclass，str Enum）
  context.py     # OperatorContext：一次装配所有依赖（E17.9 agent、auditor、P2 链、store）
  state.py       # OperatorRunStore：JSONL 防重复运行守卫（模仿 JsonlOperatorMemory 纪律）
  pipeline.py    # DailyOperatorPipeline：14 阶段编排（reality→audit→...→strategy_loop→portfolio→ceo_report→report）
  scheduler.py   # GrowthOperatorScheduler：run_daily_cycle 入口 + 幂等门 + 异常兜底
scripts/run_daily_operator.py   # 唯一命令行入口
tests/p3_1/                     # 契约测试
```

## 2. 核心契约

### 2.1 `OperatorRunResult`（models.py）

```python
@dataclass
class StageResult:
    stage: str                 # 11 阶段名之一
    status: str                # ok / skipped / failed
    detail: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)  # 可序列化摘要

class RunStatus(str, Enum):
    COMPLETED = "completed"    # 全阶段 ok/skipped
    PARTIAL = "partial"        # 有 failed 但未中断（每阶段兜底，不让一段失败毁掉整轮）
    SKIPPED = "skipped"        # 幂等门拦截（当日已跑且未 force）
    FAILED = "failed"          # 不可恢复异常

@dataclass
class OperatorRunResult:
    run_id: str                # f"op-{date}-{seq}" 确定性生成
    date: str                  # business_date (ISO)
    status: RunStatus
    stages: List[StageResult]
    decisions: Dict[str, int]  # {"total","execute","approve","observe","reject"}
    executions: Dict[str, int] # {"auto","approval_pending","blocked","recovered","escalated"}
    errors: List[str]
    report_id: str             # 汇总日报落盘路径（outputs/operator/<date>/daily_report.md）
    real_api_called: bool      # 全链路透传；DRY_RUN 恒 False
    summary: Dict[str, Any]    # E17.9 summary + audit/monitor 摘要
    # to_dict/from_dict 与全库同纪律（str Enum .value 归一化，py3.11 兼容）
```

### 2.2 `GrowthOperatorScheduler`（scheduler.py）

```python
class GrowthOperatorScheduler:
    def __init__(self, context: OperatorContext, run_store: OperatorRunStore = None): ...

    def run_daily_cycle(self, business_date: str, force: bool = False) -> OperatorRunResult:
        """唯一入口。幂等：同日已 COMPLETED/PARTIAL 记录 → 返回 SKIPPED（force=True 重跑）。
        每阶段 try/except 兜底 → StageResult(failed)，绝不半途抛出裸异常。
        运行结束（含失败）必写 run_store。"""
```

责任边界（**不可越界**）：
- 只负责：编排顺序 / 幂等守卫 / 阶段兜底 / 状态落盘 / 汇总日报。
- 不负责：决策（E17.3）、执行动作（P2.4 SafeExecutor 唯一出口）、修改策略（P3.3）、真实定时触发（外部 cron/automation）。

### 2.3 `DailyOperatorPipeline`（pipeline.py）— 14 阶段

```python
def execute(self, business_date: str) -> (List[StageResult], Dict aggregates)
```

| # | 阶段 | 实现 |
|---|---|---|
| 1 | reality_refresh | ctx.agent.run_daily(game_ids, date, force=True)（内部 hub.refresh；无 hub 时 run_daily_for_company） |
| 2 | audit | ctx.auditor.audit(company)（company 从 hub/store 取）；composite<0.5 游戏记 warning |
| 3-5 | opportunities/simulations/decisions | 已含在阶段 1 的 DailyRunResult（dec_report/sim_report），仅提取统计 |
| 6 | approval | 对 DailyRunResult.actions 中 APPROVAL 类决策：build_contract(decision, registry, mode=DRY_RUN) → ctx.approval_service.submit(request)（auto-approve 的拿到令牌） |
| 7 | executions | 对阶段 6 拿到授权 + AUTO 类合同：ctx.safe_executor.execute(request) → SafeExecutionOutcome（默认 DRY_RUN；PRODUCTION 必须已有 P2.3 授权） |
| 8 | monitor | ctx.monitor.observe_batch(paired, date) → ExecutionDailyReport |
| 9 | recovery | 对 outcome.ok=False 且非 BLOCKED 的：ctx.recovery.handle(outcome, request) |
| 10 | memory | E17.9 JsonlOperatorMemory 已在阶段 1 落盘；P2.5/2.6 bridge 已各自回流；本阶段只校验并记数 |
| 11 | report | 汇总 E17.9 CEO 晨报 + AuditReport.to_markdown + ExecutionDailyReport → outputs/operator/<date>/daily_report.md |

### 2.3b `portfolio` 阶段（P3.1 Scheduler Integration — 接 P3.4.5）

> 位置：**紧接 `strategy_loop` 之后、`ceo_report` 之前**（代码常量 `STAGE_PORTFOLIO = "portfolio"`，
> 加入 `ALL_STAGES`，阶段总数现为 **14**）。把 P3.4 Portfolio Optimizer 真正接入每日 CEO Decision Loop。

```python
def _portfolio(self, date, s, run_id) -> StageResult:
    company = s.get("company")
    if company is None or not getattr(company, "per_game", None):
        return StageResult(STAGE_PORTFOLIO, STAGE_SKIPPED, "无公司快照...")
    realities = list(company.per_game.values())           # List[GrowthRealitySnapshot]
    snapshot   = PortfolioAssembler().assemble_fleet(realities, generated_at=company.as_of)
    current_allocation = {g.game_id: g.acquisition.spend or 0.0 for g in realities}  # 仅证据
    constraints = AllocationConstraints(total_budget=company.total_spend or snapshot.total_spend)
    result = PortfolioOptimizer().optimize(PortfolioOptimizationInput(
        snapshots=snapshot, rankings=[], constraints=constraints,
        current_allocation=current_allocation, as_of=company.as_of))
    s["portfolio_result"] = result                         # 挂进共享状态
    return StageResult(STAGE_PORTFOLIO, STAGE_OK, ...)
```

- **输入装配**：`company.per_game`（E17.1 `CompanySnapshot`）→ `PortfolioAssembler.assemble_fleet` 出 `PortfolioSnapshot`；`current_allocation` 取各游戏 `acquisition.spend`（仅作对账证据，绝不覆写 baseline）；`constraints.total_budget = company.total_spend`。
- **编排**：直跑 `PortfolioOptimizer.optimize()`（P3.4.5 已锁，5 步：validate→rank→simulate→propose→assemble），**不重算、不执行、不决策**。
- **结果去向**：`s["portfolio_result"]`（PortfolioOptimizationResult）→ `_ceo_report` 阶段透传给 `build_ceo_report(portfolio_recommendation=...)` → `build_portfolio_recommendation_section(result)`（sections.py，延迟导入纯搬运）→ `CEODailyReport.portfolio_recommendation`（dict）→ renderer "## 七、Portfolio Recommendation（跨游戏资源建议）"。
- **兜底**：company 为空/异常 → `STAGE_SKIPPED`，绝不 raise 毁整轮；`_aggregates` 暴露 `portfolio_status` 与 `summary["portfolio"]`（`to_report_section()`）。
- **纪律红线**：阶段只编排不决策、不执行，`real_api_called` 恒 False；结果只进报告，绝不进执行链。

安全纪律（继承 P1/P2 全部红线）：
- 默认 `ExecutionMode.DRY_RUN`，`real_api_called` 恒 False；PRODUCTION 必经 P2.3 授权 + P2.4 七步。
- 执行唯一出口 = `ctx.safe_executor.execute()`；本层绝不直调 Provider/Router。
- 确定性：无 LLM、无随机；同数据同输出。

### 2.4 `OperatorContext`（context.py）— 一次装配

```python
@dataclass
class OperatorContext:
    agent: DailyGrowthOperatorAgent      # E17.9（含 hub/pipeline/reporter/notifier/memory）
    auditor: RealityAuditor              # P1.7
    registry: CapabilityRegistry         # P2.1（build_default_registry）
    approval_service: ApprovalService    # P2.3（共享 store；router 注入）
    safe_executor: SafeExecutor          # P2.4（build_safe_executor(router)）
    monitor: ExecutionMonitor            # P2.5
    recovery: RecoveryEngine             # P2.6（build_recovery_engine(safe_executor, workflow)）
    game_ids: List[str]                  # 舰队（默认从 GameRegistry 读）
    mode: ExecutionMode = DRY_RUN
    out_dir: str = "outputs/operator"

def build_operator_context(*, game_ids=None, mode=DRY_RUN, data_dir="data",
                           hub=None, company=None, ...) -> OperatorContext
    """工厂：全默认=SIM/DRY_RUN 可离线跑；测试可逐项注入 mock。"""
```

### 2.5 `OperatorRunStore`（state.py）— 防重复运行

模仿 `JsonlOperatorMemory` 纪律：JSONL append-only，`data/operator/runs.jsonl`。
```python
class OperatorRunStore:
    def record(self, result: OperatorRunResult) -> None
    def get(self, date: str) -> Optional[dict]       # 同日取最后一条（latest-wins）
    def has_completed(self, date: str) -> bool       # status in (completed, partial)
    def history(self, limit=30) -> List[dict]
```
注意与 E17.9 `DailyScheduler` 的分工：E17.9 幂等门管"E17 循环当日跑没跑"；
OperatorRunStore 管"P3.1 全 11 阶段当日跑没跑"。阶段 1 调 E17.9 时恒 `force=True`，
由 P3.1 的守卫统一负责幂等（单一幂等源，避免双门打架）。

### 2.6 `scripts/run_daily_operator.py`

```
python scripts/run_daily_operator.py [--date YYYY-MM-DD] [--force] [--demo]
```
- 默认 `--demo`：确定性 SIM 舰队（复用 demo_e17_9 的构造），离线可跑，验收入口。
- prod 模式：GameRegistry 58 游戏 + GrowthRealityHub 四源。
- 退出码：COMPLETED/SKIPPED=0，PARTIAL=1，FAILED=2。
- 产物：`outputs/operator/<date>/daily_report.md` + stdout 摘要。

## 3. 验收标准（P3.1 Definition of Done）

1. `python scripts/run_daily_operator.py` 单命令跑通 14 阶段（含 `portfolio`）并生成结构化日报。
2. 同日重复运行 → SKIPPED（幂等）；`--force` 可重跑。
3. 全程 DRY_RUN：`real_api_called == False` 硬断言。
4. 有 APPROVAL 决策时走 ApprovalService.submit（可见 pending）；无授权的 PRODUCTION 请求被 P2.4 BLOCK。
5. 人为注入失败 outcome → recovery 阶段调 RecoveryEngine.handle 且有记录。
6. tests/p3_1/ 全绿；双版本串行回归 ≥1983 passed ×2 零回归。
