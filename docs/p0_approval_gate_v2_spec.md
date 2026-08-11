# P0 — ApprovalGate V2 Spec（无人值守审批门控规范）

> 状态：定义中（实现前锁定）
> 优先级：P0（影响"1 款游戏无人值守增长闭环"30 天目标）
> 审计依据：[AI_Game_Studio_OS_审计报告.md](file:///d:/project_slim/project_slim/AI_Game_Studio_OS_审计报告.md) §6 P2-1、§8 30 天路线
> 依赖扫描（已逐项核对签名）：
>   - [scripts/action_planner.py](file:///d:/project_slim/project_slim/scripts/action_planner.py) `ExecutionAction.approval_level: int = 0  # 0=自动, 1=确认, 2=审批`（已存在）
>   - [scripts/action_planner.py](file:///d:/project_slim/project_slim/scripts/action_planner.py#L419-L435) `_compute_approval(budget_impact, risk_level) -> (bool, int)`
>   - [src/execution/approval/policy.py](file:///d:/project_slim/project_slim/src/execution/approval/policy.py) `ApprovalPolicy.evaluate(intent) -> ApprovalDecision{outcome: AUTO/MANUAL/ADMIN/DENY}`
>   - [src/execution/approval/roles.py](file:///d:/project_slim/project_slim/src/execution/approval/roles.py) `ApprovalRole.{SYSTEM,OPERATOR,MANAGER,ADMIN}`
>   - [scripts/action_executor.py](file:///d:/project_slim/project_slim/scripts/action_executor.py#L354-L362) `if action.approval_level > self._auto_max: ... requires manual approval`

---

## 1. 定位（不重新发明轮子）

ApprovalGate V2 **不是** 一个新的审批引擎，也不是新的算法层或新版本。它是对**两套已存在但割裂的审批机制**的统一与升级：

```
当前割裂现状（必须解决）：
┌─────────────────────────────────┐    ┌──────────────────────────────────┐
│ scripts/action_planner.py       │    │ src/execution/approval/policy.py │
│ ─────────────────────────       │    │ ──────────────────────────────── │
│ approval_level: 0/1/2           │    │ outcome: AUTO/MANUAL/ADMIN/DENY  │
│   基于 budget_impact 金额阈值   │    │   基于 allowlist + risk/conf     │
│   _BUDGET_IMPACT_WARN/APPROVAL  │    │   AUTO_MAX_RISK=0.3              │
│   /BLOCK                        │    │   AUTO_MIN_CONFIDENCE=0.9        │
│   (无金额维度)                  │    │   (无金额维度)                   │
└─────────────────────────────────┘    └──────────────────────────────────┘
            │                                          │
            └──────────── 未对齐 ─────────────────────┘
```

V2 职责一句话：**在 `ApprovalPolicy` 中引入"金额阈值 + dry_run 升级 + 累计窗口"三维门控，与 `action_planner.approval_level` 完成对齐，使 Level 0 动作真正可自动执行，Level 1 可通过 dry_run 验证后升 AUTO，Level 2 保持人工。**

纪律红线（继承全库 + memory 约束）：
- **禁止**新增算法层或新版本（v7/v8/v9 不动），只修改 `policy.py` / `roles.py` / `action_executor.py` / `action_planner.py` 现有文件
- **禁止**硬编码阈值，所有阈值走配置（环境变量 + 配置文件）
- **必须**保留 rollback 能力，Level 0 自动批准的动作同样可回滚
- **必须**保留 `ApprovalGate` fail-closed 语义：未知动作 DENY，凭证缺失 DENY
- **禁止**直接调用 Provider，Policy 只输出 `ApprovalDecision`，执行仍走 `SafeExecutor`

---

## 2. 三级分级定义（Level 0/1/2）

> 命名对齐 [action_planner.py](file:///d:/project_slim/project_slim/scripts/action_planner.py#L112) 已有字段 `approval_level: int = 0  # 0=自动, 1=确认, 2=审批`，**不引入新枚举**。

| Level | 名称 | 执行路径 | 适用动作 | 触发条件 |
|-------|------|---------|---------|---------|
| **0** | 全自动 | Policy → AUTO → SafeExecutor 真实执行 | `PAUSE_CAMPAIGN` + 小额 `SCALE_BUDGET` + `DISABLE_NETWORK` + `CREATE_INVESTIGATION` | 单次金额 < `AUTO_BUDGET_THRESHOLD_USD` **且** 日累计 < `AUTO_DAILY_CUMULATIVE_USD` **且** risk<`AUTO_MAX_RISK` **且** conf>`AUTO_MIN_CONFIDENCE` |
| **1** | dry_run 验证后自动 | Policy → MANUAL → `DryRunVerifier` 执行 dry_run → 通过升 AUTO → SafeExecutor 真实执行 | 中额 `SCALE_BUDGET` + `UPDATE_WATERFALL` | 单次金额 ∈ [`AUTO_BUDGET_THRESHOLD_USD`, `LEVEL1_BUDGET_THRESHOLD_USD`) **或** risk ∈ [`AUTO_MAX_RISK`, `LEVEL1_MAX_RISK`) |
| **2** | 强制人工 | Policy → MANUAL/ADMIN → 等待 human approve | `CREATE_RELEASE` + 大额 `SCALE_BUDGET` (impact > `ADMIN_BUDGET_IMPACT_THRESHOLD`) + 任何超日累计的动作 | 单次金额 ≥ `LEVEL1_BUDGET_THRESHOLD_USD` **或** 日累计 ≥ `AUTO_DAILY_CUMULATIVE_USD` **或** action ∈ `ADMIN_ACTIONS` |

**关键升级**（相对当前 [policy.py](file:///d:/project_slim/project_slim/src/execution/approval/policy.py)）：
1. `PAUSE_CAMPAIGN` 从 `MANUAL_ACTIONS` 移除，加入 Level 0 白名单（暂停是无损动作，不该阻塞无人值守）
2. `SCALE_BUDGET` 不再一刀切 MANUAL，按金额分级（当前 [policy.py#L49-L54](file:///d:/project_slim/project_slim/src/execution/approval/policy.py#L49-L54) 把所有 SCALE_BUDGET 都归为 MANUAL）
3. 新增"日累计窗口"维度，防止小额高频绕过单次阈值

---

## 3. 配置参数（环境变量优先）

所有阈值通过环境变量注入，无环境变量时使用默认值。**禁止在代码中硬编码数值**。

| 参数名 | 默认值 | 含义 | 来源文件 |
|--------|--------|------|---------|
| `APPROVAL_AUTO_BUDGET_THRESHOLD_USD` | `50.0` | Level 0 单次金额上限（USD） | 新增 |
| `APPROVAL_AUTO_DAILY_CUMULATIVE_USD` | `200.0` | Level 0 日累计上限（USD，按 game_id+action_type 聚合） | 新增 |
| `APPROVAL_LEVEL1_BUDGET_THRESHOLD_USD` | `500.0` | Level 1 单次金额上限，超过即 Level 2 | 新增 |
| `APPROVAL_AUTO_MAX_RISK` | `0.3` | Level 0 风险上限（沿用 [policy.py#L35](file:///d:/project_slim/project_slim/src/execution/approval/policy.py#L35) `AUTO_MAX_RISK`） | 复用 |
| `APPROVAL_AUTO_MIN_CONFIDENCE` | `0.9` | Level 0 置信度下限（沿用 [policy.py#L36](file:///d:/project_slim/project_slim/src/execution/approval/policy.py#L36) `AUTO_MIN_CONFIDENCE`） | 复用 |
| `APPROVAL_LEVEL1_MAX_RISK` | `0.6` | Level 1 风险上限，超过即 Level 2 | 新增 |
| `APPROVAL_LEVEL0_ENABLED` | `false` | Level 0 自动执行总开关（默认关，灰度切换） | 新增 |
| `APPROVAL_SHADOW_MODE` | `false` | Shadow 模式：Level 0 决策只记录不执行 | 新增 |
| `APPROVAL_DRY_RUN_VERIFY_ENABLED` | `false` | Level 1 dry_run 升级开关（默认关） | 新增 |
| `APPROVAL_AUDIT_LOG_DIR` | `outputs/approval_audit` | audit log 目录 | 新增 |

**读取约定**：所有参数通过新增 `ApprovalConfig` dataclass 统一加载（见 §5），Policy 构造时注入，不直接 `os.getenv` 散落在业务逻辑中。

---

## 4. 数据模型变更（最小侵入）

### 4.1 `ExecutionAction` 字段补充

在 [scripts/action_planner.py](file:///d:/project_slim/project_slim/scripts/action_planner.py#L80-L119) `ExecutionAction` 中新增 1 个字段（不删旧字段，向后兼容）：

```python
# ── 安全元数据（V2 补充）──
budget_impact_usd: float = 0.0  # V2: 绝对金额（USD），用于 Level 分级
                                  # 旧 budget_impact 保留（归一化值），两者并存
```

`ActionPlanner._compute_approval` 改造：基于 `budget_impact_usd`（绝对金额）而非 `budget_impact`（归一化）做分级，解决当前"无金额维度"问题。

### 4.2 `ApprovalDecision` 字段补充

在 [src/execution/approval/policy.py](file:///d:/project_slim/project_slim/src/execution/approval/policy.py#L60-L75) `ApprovalDecision` 中新增 2 个字段：

```python
@dataclass
class ApprovalDecision:
    outcome: str           # AUTO / MANUAL / ADMIN / DENY（不变）
    required_role: str     # 不变
    reason: str            # 不变
    auto_approved: bool = False  # 不变
    # V2 新增：
    level: int = 2         # 0/1/2，与 action_planner.approval_level 对齐
    dry_run_required: bool = False  # Level 1 是否需要 dry_run 验证后才升 AUTO
```

### 4.3 `ExecutionIntent` 字段补充

[src/execution/models.py](file:///d:/project_slim/project_slim/src/execution/models.py) `ExecutionIntent` 需暴露 `budget_amount_usd` 字段，供 Policy 读取。若 `ExecutionIntent` 无此字段，通过 mapper 从 `ExecutionAction.budget_impact_usd` 映射。

---

## 5. 文件布局（修改 5 文件，新增 2 文件，薄层）

```
src/execution/approval/
├── config.py          # 【新增】ApprovalConfig dataclass + 从环境变量加载
├── policy.py          # 【修改】evaluate() 引入 level / dry_run_required / 累计窗口查询
├── roles.py           # 【修改】ROLE_ALLOWED.SYSTEM 扩展 PAUSE_CAMPAIGN
├── budget_window.py   # 【新增】BudgetWindowTracker: 日累计追踪 + JSONL 持久化
└── dry_run_verifier.py # 【新增】DryRunVerifier: Level 1 dry_run → 对比 → 升级

scripts/
├── action_planner.py  # 【修改】_compute_approval 基于 budget_impact_usd 重写
└── action_executor.py # 【修改】approval_level > self._auto_max 分支对接 level/dry_run_required
```

**不新增**：算法层、版本号、Provider、Decision Engine。所有改动都在既有审批/执行链内。

### 5.1 关键签名契约

| 文件 | 函数/类 | 精确签名 | 用途 |
|------|--------|---------|------|
| `config.py` | `ApprovalConfig` | `ApprovalConfig.from_env() -> ApprovalConfig` | 环境变量加载 |
| `config.py` | `ApprovalConfig` | `ApprovalConfig(auto_budget_threshold_usd, auto_daily_cumulative_usd, level1_budget_threshold_usd, auto_max_risk, auto_min_confidence, level1_max_risk, level0_enabled, shadow_mode, dry_run_verify_enabled, audit_log_dir)` | dataclass |
| `budget_window.py` | `BudgetWindowTracker` | `BudgetWindowTracker(audit_log_dir: str)` | 构造 |
| `budget_window.py` | `BudgetWindowTracker.get_cumulative` | `get_cumulative(game_id: str, action_type: str, day: date) -> float` | 查询日累计 |
| `budget_window.py` | `BudgetWindowTracker.record` | `record(game_id: str, action_type: str, amount_usd: float, action_id: str) -> None` | 记录执行 |
| `dry_run_verifier.py` | `DryRunVerifier` | `DryRunVerifier(executor: SafeExecutor)` | 构造 |
| `dry_run_verifier.py` | `DryRunVerifier.verify_and_promote` | `verify_and_promote(action: ExecutionAction) -> tuple[bool, str]` | 返回 (是否通过, 原因) |
| `policy.py` | `ApprovalPolicy.evaluate` | `evaluate(intent: ExecutionIntent) -> ApprovalDecision`（签名不变，实现升级） | 主入口 |
| `policy.py` | `ApprovalPolicy.__init__` | `__init__(config: ApprovalConfig, window_tracker: BudgetWindowTracker)` | 依赖注入 |

---

## 6. 核心算法：`evaluate()` 升级伪代码

```python
def evaluate(self, intent: ExecutionIntent) -> ApprovalDecision:
    action = intent.action
    risk = float(intent.risk_level if numeric else _risk_to_float(intent.risk_level))
    conf = float(intent.confidence)
    amount_usd = abs(float(intent.budget_amount_usd))
    game_id = intent.game_id
    today = date.today()
    cumulative = self._window.get_cumulative(game_id, action, today)

    # 0) 未知动作 → DENY（fail-closed，不变）
    if not minimum_role_for(action):
        return ApprovalDecision(outcome=DENY, level=2, reason="unknown action")

    # 1) ADMIN 强制动作 → Level 2
    if action in ADMIN_ACTIONS:  # CREATE_RELEASE
        return ApprovalDecision(outcome=ADMIN, required_role=ADMIN,
                                level=2, reason="admin action")

    # 2) 超日累计 → 强制 Level 2（防小额高频绕过）
    if cumulative + amount_usd > self._config.auto_daily_cumulative_usd:
        return ApprovalDecision(outcome=MANUAL, required_role=MANAGER,
                                level=2, reason=f"daily cumulative overflow: "
                                f"{cumulative}+{amount_usd} > "
                                f"{self._config.auto_daily_cumulative_usd}")

    # 3) 大额 → Level 2
    if amount_usd >= self._config.level1_budget_threshold_usd:
        return ApprovalDecision(outcome=MANUAL, required_role=MANAGER,
                                level=2, reason="large budget impact")

    # 4) 中额 → Level 1（dry_run 验证后可升 AUTO）
    if amount_usd >= self._config.auto_budget_threshold_usd \
            or risk >= self._config.auto_max_risk:
        if not self._config.dry_run_verify_enabled:
            return ApprovalDecision(outcome=MANUAL, required_role=MANAGER,
                                    level=1, dry_run_required=False,
                                    reason="dry_run verify disabled")
        return ApprovalDecision(outcome=MANUAL, required_role=MANAGER,
                                level=1, dry_run_required=True,
                                reason="Level 1: dry_run required")

    # 5) 小额 + 低风险 + 高置信 + allowlist → Level 0
    if action in LEVEL0_ALLOWLIST \
            and risk < self._config.auto_max_risk \
            and conf > self._config.auto_min_confidence:
        if not self._config.level0_enabled:
            return ApprovalDecision(outcome=MANUAL, required_role=OPERATOR,
                                    level=0, reason="Level 0 disabled by config")
        if self._config.shadow_mode:
            return ApprovalDecision(outcome=MANUAL, required_role=OPERATOR,
                                    level=0, reason="shadow mode: log only")
        return ApprovalDecision(outcome=AUTO, required_role=SYSTEM,
                                level=0, auto_approved=True,
                                reason=f"Level 0: amount={amount_usd} "
                                f"risk={risk} conf={conf}")

    # 6) 兜底 → Level 1
    return ApprovalDecision(outcome=MANUAL, required_role=OPERATOR,
                            level=1, reason="default to manual")
```

**Level 0 白名单**（新增常量，替代当前 [policy.py#L43-L46](file:///d:/project_slim/project_slim/src/execution/approval/policy.py#L43-L46) `AUTO_ELIGIBLE_ACTIONS`）：

```python
LEVEL0_ALLOWLIST = (
    ExecutionAction.DISABLE_NETWORK,
    ExecutionAction.CREATE_INVESTIGATION,
    ExecutionAction.PAUSE_CAMPAIGN,           # V2 新增：暂停是无损动作
    ExecutionAction.SCALE_BUDGET,             # V2 新增：小额 scale 走 Level 0
)
```

---

## 7. `action_executor.py` 集成改造

当前 [action_executor.py#L354-L362](file:///d:/project_slim/project_slim/scripts/action_executor.py#L354-L362) 的检查：

```python
# 当前（过于简单）：
if action.approval_level > self._auto_max:
    return (False, f"Approval level {action.approval_level} > auto-approve "
                   f"max {self._auto_max} — requires manual approval")
```

V2 改造（伪代码）：

```python
decision = self._policy.evaluate(intent)

# Level 0: 直接执行（或 shadow 模式跳过）
if decision.level == 0 and decision.auto_approved:
    if self._config.shadow_mode:
        self._audit_log(action, decision, executed=False, reason="shadow")
        return (False, "shadow mode: decision logged, execution skipped")
    self._window.record(game_id, action_type, amount_usd, action_id)
    self._audit_log(action, decision, executed=True)
    return self._safe_executor.execute(action, dry_run=False)

# Level 1: dry_run 验证后升 AUTO
if decision.level == 1 and decision.dry_run_required:
    ok, reason = self._dry_run_verifier.verify_and_promote(action)
    if not ok:
        self._audit_log(action, decision, executed=False, reason=f"dry_run fail: {reason}")
        return (False, f"dry_run verification failed: {reason}")
    self._window.record(...)
    self._audit_log(action, decision, executed=True, reason="dry_run passed")
    return self._safe_executor.execute(action, dry_run=False)

# Level 1 (dry_run disabled) 或 Level 2: 阻塞，等人工
return (False, f"requires manual approval: level={decision.level} reason={decision.reason}")
```

---

## 8. Audit Log 格式

每次 `evaluate()` 决策落盘 JSONL，路径 `{APPROVAL_AUDIT_LOG_DIR}/YYYY-MM-DD.jsonl`：

```json
{
  "ts": "2026-08-06T14:30:00Z",
  "action_id": "exec_abc123",
  "game_id": "p04_witch_merge",
  "action_type": "SCALE_BUDGET",
  "amount_usd": 35.0,
  "cumulative_before": 120.0,
  "risk": 0.2,
  "confidence": 0.92,
  "level": 0,
  "outcome": "AUTO",
  "shadow": false,
  "executed": true,
  "dry_run_required": false,
  "dry_run_result": null,
  "reason": "Level 0: amount=35.0 risk=0.2 conf=0.92"
}
```

**不可变**：audit log 只追加，不修改不删除。ShadowMode 下 `executed=false`，用于 7 天对比一致性。

---

## 9. ShadowMode 灰度策略

目标：在不真实执行的前提下，验证 Level 0 决策与人类决策的一致性。

```
Day 1-7:  APPROVAL_LEVEL0_ENABLED=true, APPROVAL_SHADOW_MODE=true
          → Policy 输出 Level 0 AUTO，但 executor 跳过真实执行，只记 audit
          → 人工仍按原流程审批+执行
          → 每日对比 audit log 与人工决策，统计一致率

Day 8:    一致率 ≥ 95% → 切 APPROVAL_SHADOW_MODE=false（真实执行）
          一致率 < 95% → 暂停，分析分歧，调整阈值，重跑 7 天

Day 14:   累计 14 天无重大分歧 → Level 0 正式启用
```

**回滚机制**：任何时刻设 `APPROVAL_LEVEL0_ENABLED=false` 即回退到 V1 行为（全部 MANUAL），audit log 保留可追溯。

---

## 10. 测试矩阵

### 10.1 单元测试（Week 1 Day 7）

新增 `tests/p2_3/test_approval_level_v2.py`，覆盖 12 个场景：

| # | 场景 | 输入 | 期望 level | 期望 outcome |
|---|------|------|-----------|-------------|
| 1 | 小额 PAUSE + 低风险 + 高置信 | amount=0, risk=0.1, conf=0.95, action=PAUSE | 0 | AUTO |
| 2 | 小额 SCALE + 低风险 + 高置信 | amount=30, risk=0.2, conf=0.92, action=SCALE | 0 | AUTO |
| 3 | 中额 SCALE | amount=100, risk=0.3, conf=0.9, action=SCALE | 1 | MANUAL + dry_run_required |
| 4 | 大额 SCALE | amount=600, risk=0.4, action=SCALE | 2 | MANUAL |
| 5 | 超日累计 | cumulative=180, amount=30, action=SCALE | 2 | MANUAL |
| 6 | CREATE_RELEASE | action=CREATE_RELEASE | 2 | ADMIN |
| 7 | 未知动作 | action=UNKNOWN | 2 | DENY |
| 8 | Level 0 关闭 | level0_enabled=false, 同场景 1 | 0 | MANUAL |
| 9 | Shadow 模式 | shadow=true, 同场景 1 | 0 | MANUAL (log only) |
| 10 | dry_run 验证通过 | level=1, dry_run_ok=true | 1 | AUTO (promoted) |
| 11 | dry_run 验证失败 | level=1, dry_run_ok=false | 1 | MANUAL (blocked) |
| 12 | risk 过高 | risk=0.7, amount=30 | 2 | MANUAL |

### 10.2 集成测试（Week 2 Day 13）

新增 `tests/integration/test_growth_loop_unattended.py`：
- 模拟 24h growth loop 循环
- 注入 20 个动作（含 5 个 Level 0、10 个 Level 1、5 个 Level 2）
- 验证 Level 0 自动执行 + Level 2 阻塞 + audit log 完整性

### 10.3 回归门控（Week 2 Day 14）

- 现有 `tests/p2_3/` 全绿（不破坏 V1 行为）
- 现有 `tests/test_action_executor.py` 全绿
- 全量回归 ≥ 120+/120 PASS（符合发布门控）

---

## 11. 实施顺序（Week 1 排期）

| Day | 产出 | 验收 |
|-----|------|------|
| D1 | 本 Spec 文档（本文档） | 评审通过 |
| D2 | `config.py` 新增 `ApprovalConfig` + 环境变量加载 | 单元测试 `test_config.py` 通过 |
| D3 | `budget_window.py` 新增 `BudgetWindowTracker` + JSONL 持久化 | 单元测试 `test_budget_window.py` 通过 |
| D4 | `policy.py` 改造 `evaluate()` + `LEVEL0_ALLOWLIST` | 单元测试覆盖场景 1-7 |
| D5 | `roles.py` 同步 `LEVEL0_ALLOWLIST`；`action_planner.py` 改造 `_compute_approval` | 单元测试覆盖场景 8-12 |
| D6 | `dry_run_verifier.py` 新增；`action_executor.py` 集成 | 集成测试通过 |
| D7 | `test_approval_level_v2.py` 完整 12 场景 + 回归 | 12/12 PASS + 现有 p2_3 全绿 |

---

## 12. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Level 0 误批准导致预算损失 | 单次 $50 + 日累计 $200 双硬上限 + ShadowMode 7 天验证 + audit log 可追溯 |
| `budget_impact_usd` 与 `budget_impact` 双字段并存引发混淆 | Spec §4.1 明确：V2 分级只看 `budget_impact_usd`；`budget_impact` 保留仅用于日志，不参与决策 |
| dry_run 验证与真实执行结果不一致 | DryRunVerifier 对比 `expected_impact` 与 dry_run 实际返回，差异 > 20% 拒绝升级 |
| ShadowMode 7 天不够 | 可配置延长，默认 7 天，一致率 < 95% 强制重跑 |
| 累计窗口跨重启丢失 | `BudgetWindowTracker` JSONL 持久化，启动时从 `{audit_log_dir}/YYYY-MM-DD.jsonl` 重载当日累计 |
| 凭证缺失时误放行 | fail-closed 保留：凭证缺失 → DENY（不变） |

---

## 13. 不做的事（Out of Scope）

明确排除以下内容，避免范围蔓延：

- ❌ 不修改 `CREATE_RELEASE` 的 ADMIN 强制语义（iOS 上架走另一条 P0 计划）
- ❌ 不接入 Slack/飞书 webhook 告警（P2，30 天后）
- ❌ 不实现 `OPTIMIZE_AD_PLACEMENT` 等未实现动作
- ❌ 不修改 `growth_loop_orchestrator.py` 的编排逻辑（Week 2 D11 才集成）
- ❌ 不引入新算法层或新版本号

---

## 14. 验收标准（Week 1 出口）

1. ✅ 本 Spec 评审通过（本文档）
2. ✅ `config.py` / `budget_window.py` / `dry_run_verifier.py` 三个新文件实现 + 单元测试通过
3. ✅ `policy.py` / `roles.py` / `action_planner.py` / `action_executor.py` 四个修改完成
4. ✅ `test_approval_level_v2.py` 12/12 PASS
5. ✅ `tests/p2_3/` 现有测试全绿（V1 兼容）
6. ✅ `tests/test_action_executor.py` 全绿
7. ✅ 全量回归 ≥ 120+/120 PASS

---

## 变更记录

| 日期 | 版本 | 作者 | 变更 |
|------|------|------|------|
| 2026-08-06 | v0.1 | TRAE Agent | 初始草案，基于 [审计报告](file:///d:/project_slim/project_slim/AI_Game_Studio_OS_审计报告.md) P0 缺口与真实代码现状起草 |
