# P3.3.3 — Adaptive Strategy Contract（自适应策略落地契约）

> 状态：定义中（实现前锁定）
> 依赖扫描：#559 E17.8 Simulation / #560 P2.3 ApprovalService + P2.4 SafeExecutor / #561 P3.3 StrategyProposal —— 均已完成，签名已逐项核对。

---

## 1. 定位（不重新发明轮子）

P3.3.3 **不是** 一个新的 Decision Engine。它是 P3.3 `StrategyProposal` 的「生产级落地器」：

```
StrategyProposal  ──┐
                    ├─► AdaptiveStrategyController ──► Simulation(E17.8)
(strategy-level)  ──┘          │                         → Approval(P2.3)
                               ├─ re-merge provider params
                               ├─► SafeExecutor(P2.4) ──► Provider(P2.2)
                               └─► Feedback(P3.3 evaluator+memory)
```

职责一句话：**把「策略层的一条建议」真正走完 `Simulation → Approval → Execution → Outcome → Memory` 闭环，且全程复用既有三层执行门，绝不新建执行链。**

纪律红线（继承全库 + P3.3）：
- 只读 E17.7 / P3.3 经验；**不**重算业务指标；
- **禁止** Controller 直接 import 或调用任何 Provider（`MaxExecutionProvider` / `MetaExecutionProvider` / `PlayExecutionProvider`）。Controller 只认 `ApprovalService.submit/approve/authorize/execute` 和 `SafeExecutor.execute`，二者背后统一走 `ProviderRouter`；
- `real_api_called` 纪律由 Provider 自身保证（DRY_RUN=`False`，PRODUCTION=`True`），Controller 只**观测并断言**它，不篡改。

---

## 2. 文件布局（新增 6 文件，薄层）

```
src/operator/adaptive_strategy/
├── __init__.py        # 导出 Controller / Request / Result / Stage / FinalStatus / TEMPLATES
├── models.py          # AdaptiveStrategyRequest / AdaptiveStrategyResult / Stage / FinalStatus
│                      #   / AdaptiveAction(enum) / AdaptiveStrategyTemplate(dataclass)
├── planner.py         # AdaptiveStrategyPlanner + TEMPLATES 注册表（2 首批 + budget_scale 暂缓）
│                      #   StrategyProposal → ceo_intelligence.GrowthDecision + provider 参数
├── simulator.py       # AdaptiveStrategySimulator：封装 DeterministicSimulator.simulate_decision
│                      #   + get_prior（prior_provider 可注入，测试可强制 FAIL）
├── controller.py      # AdaptiveStrategyController.run()：状态机编排（闭环核心）
└── feedback.py        # build_feedback() + record_feedback()：薄封装 OutcomeEvaluator + memory
```

复用入口（已核对签名）：

| 复用对象 | 精确签名 | 用途 |
|---|---|---|
| E17.3 `GrowthDecision` | `GrowthDecision(game_id, opportunity_id, action, decision_type, expected_value, confidence, risk, reason, urgency=0.5, simulation=None, audit_id="", executed=False, queued=False)` | Controller 构造决策 |
| E17.8 `DeterministicSimulator.simulate_decision(decision, prior, scenarios=None) -> DecisionSimulation` | 单决策模拟 + 预飞闸门 | 仿真 |
| E17.8 `PreFlightStatus` | `PASS / REVIEW / BLOCK`（`.flag.status`） | 闸门判定 |
| E17.8 `get_prior(opportunity_type, graph=None, *, domain, action_type, simulator) -> SimulationPrior` | 先验（opportunity_type 由 `opportunity_id.rsplit(":",1)[-1]` 解析） | 喂 simulate_decision |
| P2.1 `build_contract(decision, registry=None, validator=None, mode=DRY_RUN, audit_trail=None) -> ExecutionContract` | 决策→合同（`.blocked/.needs_approval/.approved_auto/.request`） | 出 ExecutionRequest |
| P2.1 `DecisionToIntentMapper` | `MAX_OPTIMIZE→DISABLE_NETWORK(AD_MONETIZATION)` / `UA_STOP→PAUSE_CAMPAIGN(UA)` | 动作映射 |
| P2.3 `ApprovalService(store, policy, router)` | `.submit(req, requested_by) -> SubmitResult` / `.approve(id, approver, role) -> ExecutionAuthorization` / `.reject(...)` / `.authorize(req, auth) -> req` / `.execute(req)` | 审批 + 执行编排 |
| P2.4 `build_safe_executor(router, *, idempotency_store, snapshot_store, rollback_engine, audit, sandbox, strict_snapshot) -> SafeExecutor` | `SafeExecutor.execute(req) -> SafeExecutionOutcome`；`ok = verdict in (EXECUTED, RETURN_EXISTING)` | 安全执行 |
| P2.2 `build_execution_router(*, registry, providers, approval_store, reality_gate, audit_trail, authorization_gate, max_client, meta_kwargs, play_kwargs) -> ProviderRouter` | 一键装配；`authorization_gate` 注入 `AuthorizationGate` | 路由（唯一出口） |
| P3.3 `OutcomeEvaluator.evaluate(action, execution_result=None, business_outcome=None, *, strategy_id, action_id) -> StrategyFeedback` | 零重算反馈 | 反馈 |
| P3.3 `StrategyMemoryAdapter.apply_feedback(fb) -> StrategyState` + `.save()` | 经验折入 + 落盘 | 记忆 |

---

## 3. 核心契约（models.py）

### 3.1 `AdaptiveAction`（首批仅 2 个）

```python
class AdaptiveAction(str, Enum):
    DISABLE_NETWORK = "disable_network"   # 对应 E17.3 MAX_OPTIMIZE
    PAUSE_CAMPAIGN  = "pause_campaign"    # 对应 E17.3 UA_STOP
    # SCALE_BUDGET = "scale_budget"      # 暂缓：预算扩量风险高，本阶段门控拒绝
```

### 3.2 `AdaptiveStrategyTemplate`（planner 注册表项）

```python
@dataclass
class AdaptiveStrategyTemplate:
    strategy_id: str            # 如 "adaptive.network_cleanup"
    decision_action: str        # E17.3 动作：MAX_OPTIMIZE / UA_STOP
    opportunity_type: str       # 喂 get_prior：monetization / ua_stop_loss
    execution_domain: str       # AD_MONETIZATION / UA（对应 ExecutionDomain）
    provider_params_keys: Tuple[str, ...]  # 须 re-merge 进 expected_impact 的键
    description: str
```

### 3.3 `AdaptiveStrategyRequest`（控制器入参）

```python
@dataclass
class AdaptiveStrategyRequest:
    proposal_id: str            # 来源 StrategyProposal 标识
    strategy_id: str            # 模板/策略 id（如 "adaptive.network_cleanup"）
    target: str                 # game_id（也是 intent.target_id 回退）
    expected_change: Dict[str, Any]   # 预期影响（看板可读）
    parameters: Dict[str, Any] = field(default_factory=dict)  # provider 专属参数
    requires_simulation: bool = True
    source: str = "strategy_loop"
    mode: str = "dry_run"       # 透传给 ExecutionMode（测试可切 production）
    approver: Optional[str] = None     # 人工审批人（MANUAL 路径必填）
    approver_role: str = "operator"   # OPERATOR 可批两类动作
```

### 3.4 `Stage` / `FinalStatus`（状态机枚举）

```python
class Stage(str, Enum):
    CREATED = "created"
    SIMULATION_PENDING = "simulation_pending"
    SIMULATION_PASS = "simulation_pass"
    SIMULATION_FAIL = "simulation_fail"
    APPROVAL_PENDING = "approval_pending"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    APPROVAL_REJECTED = "approval_rejected"
    EXECUTION_FAILED = "execution_failed"
    RECOVERY_REQUIRED = "recovery_required"   # ESCALATED / ROLLED_BACK / 未知策略

class FinalStatus(str, Enum):
    COMPLETED = "completed"
    SIMULATION_FAIL = "simulation_fail"
    APPROVAL_REJECTED = "approval_rejected"
    EXECUTION_FAILED = "execution_failed"
    BLOCKED_UNSUPPORTED = "blocked_unsupported"   # 预算扩量等暂缓项
```

### 3.5 `AdaptiveStrategyResult`（控制器出参）

```python
@dataclass
class AdaptiveStrategyResult:
    proposal_id: str
    strategy_id: str
    target: str
    action: str                       # 实际执行的 E17.3 动作
    stage: Stage                      # 最终到达状态
    final_status: FinalStatus
    simulation_flag: Optional[str]    # PreFlightStatus.value（PASS/REVIEW/BLOCK）
    simulation_detail: Dict[str, Any]
    approval_status: Optional[str]    # "auto" / "approved" / "rejected" / "pending"
    execution_verdict: Optional[str]  # SafeExecutionOutcome.verdict
    execution_result: Optional[Dict]  # ExecutionResult.to_dict()（含 real_api_called）
    real_api_called: Optional[bool]   # 来自 ExecutionResult.real_api_called
    feedback: Optional[Dict]          # StrategyFeedback.to_dict()
    errors: List[str] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)  # 状态跃迁审计
```

---

## 4. 状态机（controller.run 编排）

```
CREATED
  └─► SIMULATION_PENDING
        ├─ (flag=BLOCK) ─────────────► SIMULATION_FAIL            [停止，不进审批/执行]
        ├─ (flag=REVIEW) ────────────► 仍进入 APPROVAL（带 REVIEW 标记继续；本阶段视为可继续）
        └─ (flag=PASS) ──► SIMULATION_PASS
                                └─► APPROVAL_PENDING
                                      ├─ (AUTO 批准) ───────────► AUTHORIZED
                                      ├─ (MANUAL + 有 approver) ─► approve ─► AUTHORIZED
                                      ├─ (MANUAL + 无 approver) ─► RECOVERY_REQUIRED（待人工，停止）
                                      └─ (reject) ──────────────► APPROVAL_REJECTED [停止]
                                                                └─► EXECUTING
                                                                      ├─ (EXECUTED/RETURN_EXISTING) ─► COMPLETED ─► feedback→memory
                                                                      ├─ (BLOCKED) ─────────────────► EXECUTION_FAILED
                                                                      └─ (FAILED/ROLLED_BACK/ESCALATED) ─► EXECUTION_FAILED（ESCALATED/ROLLED_BACK 记 RECOVERY_REQUIRED）
```

**关键过渡纪律**
- SIMULATION_FAIL / APPROVAL_REJECTED / EXECUTION_FAILED / RECOVERY_REQUIRED 为终态，绝不回环触发 Provider。
- `real_api_called` 仅在 `EXECUTED` 且 `execution_result.real_api_called=True` 时为 True；其余终态若为 BLOCKED 则恒 False（Provider 从未被调用）。

---

## 5. 安全边界（不可违背）

✅ **允许路径**：`StrategyProposal/Request → Simulator → build_contract → ApprovalService → SafeExecutor → ProviderRouter → Provider`

❌ **禁止**：
- Controller / planner / simulator **不得** `from ...providers.max.provider import MaxExecutionProvider` 或实例化/调用它们；
- Controller **不得** 自己拼 `ExecutionResult` 或假造 `real_api_called`；
- Controller **不得** 修改 E17.3 `GrowthDecision` 的语义或绕过 `build_contract`；
- Provider 专属参数（`network` / `ad_unit_id` / `campaign_id`）**不得**写进 `GrowthDecision.expected_value`，只能在 `build_contract` 之后 **re-merge** 进 `request.intent.expected_impact`（见 §6）；
- 任何 `AdaptiveAction` 不在 `TEMPLATES` 注册表（如 `SCALE_BUDGET`）→ 直接 `BLOCKED_UNSUPPORTED`，不触任何执行。

---

## 6. re-merge 规则（绕开 P2.1 mapper 丢弃 provider 参数）

`DecisionToIntentMapper.map()` 重建 `expected_impact = {"expected_value": decision.expected_value, [+simulation 字段]}`，**丢弃** provider 专属键。因此 Controller 在 `build_contract` 之后、submit/execute 之前，必须把参数塞回：

```python
request.intent.expected_impact.update(provider_params)   # 同一 intent 对象，router 后续可见
```

键映射（已核对 provider 源码）：

| 动作 | provider | 读取键 | re-merge 来源（AdaptiveStrategyRequest.parameters） |
|---|---|---|---|
| DISABLE_NETWORK | Max | `expected_impact["network"]`（必填）、`["ad_unit_id"]`（缺省回退 `target_id`） | `parameters["network"]`、`parameters.get("ad_unit_id")` |
| PAUSE_CAMPAIGN | Meta | `expected_impact["campaign_id"]`（缺省回退 `target_id`） | `parameters["campaign_id"]` |

`AdaptiveStrategyTemplate.provider_params_keys` 声明该模板需要哪些键，planner 据此从 `request.parameters` 抽取并回填。

---

## 7. 首批策略（TEMPLATES 注册）

```python
TEMPLATES = {
    "adaptive.network_cleanup": AdaptiveStrategyTemplate(
        strategy_id="adaptive.network_cleanup",
        decision_action="MAX_OPTIMIZE",          # → DISABLE_NETWORK
        opportunity_type="monetization",          # 先验 +0.18/+0.15/0.70/0.50 → PASS
        execution_domain="AD_MONETIZATION",
        provider_params_keys=("network", "ad_unit_id"),
        description="关停低 eCPM 僵尸广告网络",
    ),
    "adaptive.campaign_pause": AdaptiveStrategyTemplate(
        strategy_id="adaptive.campaign_pause",
        decision_action="UA_STOP",               # → PAUSE_CAMPAIGN
        opportunity_type="ua_stop_loss",          # 先验 +0.08/+0.20/0.85/0.25 → PASS
        execution_domain="UA",
        provider_params_keys=("campaign_id",),
        description="暂停亏损买量系列止损",
    ),
    # "adaptive.budget_scale": 暂缓（SCALE_BUDGET 高熔断风险）→ 门控拒绝
}
```

两条首批策略经 `ApprovalPolicy` 判定均走 **MANUAL**（DISABLE_NETWORK 先验 risk 0.50/conf 0.70 不达标 AUTO 阈值 risk<0.3&conf>0.9；PAUSE_CAMPAIGN 恒 MANUAL），因此闭环必经 `submit → approve → authorize → execute` 完整路径 —— 正好满足「真实反馈闭环」诉求。

---

## 8. 测试 Case（目标 70–100 tests，覆盖 #565）

| # | 场景 | 关键断言 |
|---|---|---|
| 1 | Proposal 自动进 Simulation，不执行 | `simulation_flag` 存在；`approval_status`/`execution_result` 在 SIM_FAIL 时为 None；DRY_RUN 路径下不触网即 `real_api_called=False` |
| 2 | SIM_FAIL（注入负先验）→ BLOCKED | `final_status==SIMULATION_FAIL`；`ApprovalService`/`SafeExecutor` **从未**被调用（mock 计数 0） |
| 3 | APPROVAL_REJECT → STOP | 拒绝后 `final_status==APPROVAL_REJECTED`；`execution_result is None`；Provider 未被调用 |
| 4 | APPROVAL_PASS → SafeExecutor 验证 `real_api_called` 纪律 | DRY_RUN：`real_api_called is False`；PRODUCTION + fake transport（返回 success 且标记 `real_api_called=True`）：`real_api_called is True`；verdict==EXECUTED |
| 5 | 执行成功 → 反馈 → Monitor/StrategyMemory | `feedback.outcome=="SUCCESS"`；`StrategyMemoryAdapter` 对应 `strategy_id` 的 `samples` +1、`reward_sum` 累加；`memory.save()` 落盘 |
| 6 | 状态机完整跃迁 | `trace` 顺序 `CREATED→SIMULATION_PENDING→SIMULATION_PASS→APPROVAL_PENDING→AUTHORIZED→EXECUTING→COMPLETED` |
| 7 | 安全边界：Strategy→Provider 直连被禁止 | Controller 模块 import 图中**不含** `providers.max/meta/play` 的具体 Provider 类（用 AST/import 检查）；唯一出口是 router |
| 8 | Budget Scale 门控 | `strategy_id=="adaptive.budget_scale"` → `final_status==BLOCKED_UNSUPPORTED`；不触 Provider |
| 9 | 无 approver 的 MANUAL 请求 | → `RECOVERY_REQUIRED`（待人工），不执行 |
| 10 | re-merge 正确性 | execution 时 `request.intent.expected_impact` 含 `network`/`campaign_id`，且 Provider 回显 after_state 引用该参数 |

> 测试纪律：所有 PRODUCTION 路径必须注入 **fake Provider**（`MaxExecutionProvider(client=fake)` / `MetaExecutionProvider(transport=fake)`），**绝不**默认构造真实 `MaxClient`/`MetaClient` 触网。DRY_RUN 路径默认 Provider 即可（`real_api_called=False`）。双版本串行回归：managed 3.13 + ci311 3.11。

---

## 9. Do / Don't

**Do**
- 复用 `build_contract` / `ApprovalService` / `build_safe_executor` / `build_execution_router` 整条链；
- 把 provider 参数通过 re-merge 注入 `expected_impact`，而非伪造 `GrowthDecision`；
- 把 `simulator`（`DeterministicSimulator`）与 `prior_provider`（`get_prior`）做成可注入，便于测试强制 FAIL；
- 闭环末端调用 `OutcomeEvaluator.evaluate` + `StrategyMemoryAdapter.apply_feedback` + `save()`；
- `mode` 默认 `DRY_RUN`，显式切 `PRODUCTION` 才允许真实出口。

**Don't**
- ❌ 不新建 Decision Engine / 新的执行门；
- ❌ 不 import / 调用任何具体 Provider；
- ❌ 不篡改 `real_api_called`；
- ❌ 不把 provider 参数塞进 `expected_value`；
- ❌ 不在 DRY_RUN 下触网；不在测试里默认构造真实 `MaxClient`/`MetaClient`；
- ❌ 不为 `SCALE_BUDGET` 等暂缓项开后门。

---

## 10. Definition of Done（#563+#564+#565 验收）

- [ ] `src/operator/adaptive_strategy/` 6 文件就位，namespace import 正常；
- [ ] `AdaptiveStrategyController.run(request)` 实现 §4 状态机，全部终态安全不回环；
- [ ] re-merge 规则落地，Case 10 通过；
- [ ] `StrategyLoop` 集成：过闸的 `StrategyProposal` 经 keyword 适配 → `AdaptiveStrategyRequest` → 闭环（保留 P3.3 非变异路径，互不破坏）；
- [ ] 70–100 测试覆盖 Case 1–10，双版本串行回归零回归，新基线记录；
- [ ] 安全边界 Case 7（import 图检查）通过 —— Controller 不直连 Provider；
- [ ] 记忆更新：MEMORY.md 标记 P3.3.3 Closed + 新基线数字。
