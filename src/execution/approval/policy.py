"""P2.3.3 Permission Policy (V2 — 见 docs/p0_approval_gate_v2_spec.md).

ApprovalPolicy answers: "For this ExecutionIntent, WHAT kind of approval is
required?" It maps an intent to one of four outcomes:

- AUTO      : policy auto-approves (SYSTEM role), no human needed.
- MANUAL    : requires a human at OPERATOR/MANAGER level (per roles.py).
- ADMIN     : requires an ADMIN-level human.
- DENY      : the action is never approvable by policy.

V2 升级（Spec §6）：
- 引入 Level 0/1/2 三级分级（与 scripts/action_planner.py approval_level 对齐）
- Level 0：小额 + 低风险 + 高置信 + allowlist → AUTO（受 level0_enabled / shadow_mode 开关控制）
- Level 1：中额或中风险 → MANUAL + dry_run_required（受 dry_run_verify_enabled 开关）
- Level 2：大额 / 超日累计 / ADMIN 动作 → MANUAL/ADMIN
- 新增 budget_amount_usd 维度（从 intent 读取，缺失默认 0）
- 新增 (game_id, action_type, day) 累计窗口检查

向后兼容（V1）：
- ApprovalPolicy() 无参构造仍工作（默认 config + 无 window_tracker）
- 默认 level0_enabled=false / dry_run_verify_enabled=false 时，行为与 V1 一致
- ApprovalDecision 新增 level / dry_run_required 字段（默认值不破坏 V1 读取）

Deterministic rules only — no LLM, no I/O（BudgetWindowTracker 查询是只读 IO）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from src.execution.approval.config import ApprovalConfig
from src.execution.approval.budget_window import BudgetWindowTracker
from src.execution.approval.roles import (
    ApprovalRole,
    minimum_role_for,
    role_can,
)
from src.execution.models import ExecutionAction, ExecutionIntent

# Outcome constants
OUTCOME_AUTO = "AUTO"
OUTCOME_MANUAL = "MANUAL"
OUTCOME_ADMIN = "ADMIN"
OUTCOME_DENY = "DENY"

VALID_OUTCOMES = (OUTCOME_AUTO, OUTCOME_MANUAL, OUTCOME_ADMIN, OUTCOME_DENY)

# ──────────────────────────────────────────────
# V1 阈值常量（保留，向后兼容 ApprovalPolicy(auto_max_risk=...) 调用）
# ──────────────────────────────────────────────

# Auto-approval thresholds (conservative by design)
AUTO_MAX_RISK = 0.3
AUTO_MIN_CONFIDENCE = 0.9

# Budget impact above this magnitude escalates to ADMIN even for MANAGER
# actions (expected_impact is treated as absolute magnitude).
ADMIN_BUDGET_IMPACT_THRESHOLD = 0.5

# Actions the policy may auto-approve when thresholds are met.
# V1 保留：用于无 config 构造时的 fallback
AUTO_ELIGIBLE_ACTIONS = (
    ExecutionAction.DISABLE_NETWORK,
    ExecutionAction.CREATE_INVESTIGATION,
)

# Actions that ALWAYS require a human (never auto), at their minimum role.
# V1 保留：V2 在 level0_enabled=false 时仍走此清单
MANUAL_ACTIONS = (
    ExecutionAction.PAUSE_CAMPAIGN,
    ExecutionAction.SCALE_BUDGET,
    ExecutionAction.UPDATE_WATERFALL,
    ExecutionAction.CREATE_ASO_UPDATE,
)

# Actions that ALWAYS require ADMIN.
ADMIN_ACTIONS = (ExecutionAction.CREATE_RELEASE,)

# ──────────────────────────────────────────────
# V2 Level 0 白名单（Spec §6）
# ──────────────────────────────────────────────

# Level 0 白名单：默认 level0_enabled=false 时不生效；
# 启用后，小额 + 低风险 + 高置信的这些动作可走 AUTO
LEVEL0_ALLOWLIST = (
    ExecutionAction.DISABLE_NETWORK,
    ExecutionAction.CREATE_INVESTIGATION,
    ExecutionAction.PAUSE_CAMPAIGN,   # V2 新增：暂停是无损动作
    ExecutionAction.SCALE_BUDGET,     # V2 新增：小额 scale 走 Level 0
)


@dataclass
class ApprovalDecision:
    """Result of evaluating an intent against the policy.

    V2 新增字段：
        level: 0/1/2，与 action_planner.approval_level 对齐（默认 2 兜底）
        dry_run_required: Level 1 是否需要 dry_run 验证后才升 AUTO
    """

    outcome: str
    required_role: str
    reason: str
    auto_approved: bool = False
    # V2 新增（默认值保证 V1 读取不破）
    level: int = 2
    dry_run_required: bool = False

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "required_role": self.required_role,
            "reason": self.reason,
            "auto_approved": self.auto_approved,
            "level": self.level,
            "dry_run_required": self.dry_run_required,
        }


class ApprovalPolicy:
    """Deterministic mapping: ExecutionIntent -> ApprovalDecision.

    V2 支持两种构造方式：
    1. V1 兼容：ApprovalPolicy() 或 ApprovalPolicy(auto_max_risk=..., ...)
       — 使用 V1 阈值常量，无 config / window_tracker
       — 行为与 V1 完全一致（level0_enabled=false）
    2. V2 完整：ApprovalPolicy(config=ApprovalConfig.from_env(),
                                window_tracker=BudgetWindowTracker(...))
       — 启用 Level 0/1/2 三级分级 + 累计窗口
    """

    def __init__(
        self,
        # V1 兼容参数（优先级低于 config）
        auto_max_risk: float = AUTO_MAX_RISK,
        auto_min_confidence: float = AUTO_MIN_CONFIDENCE,
        admin_budget_impact_threshold: float = ADMIN_BUDGET_IMPACT_THRESHOLD,
        # V2 完整参数（优先级高于 V1 参数）
        config: Optional[ApprovalConfig] = None,
        window_tracker: Optional[BudgetWindowTracker] = None,
    ) -> None:
        self._config = config
        self._window = window_tracker
        # V1 参数保留（用于无 config 时的 fallback）
        self.auto_max_risk = auto_max_risk
        self.auto_min_confidence = auto_min_confidence
        self.admin_budget_impact_threshold = admin_budget_impact_threshold

    # ------------------------------------------------------------------
    # 配置访问器（统一 V1/V2）
    # ------------------------------------------------------------------

    @property
    def _cfg(self) -> ApprovalConfig:
        """获取有效配置：有 config 用 config，否则用 V1 参数构造临时 config。"""
        if self._config is not None:
            return self._config
        # V1 兼容：用 V1 参数 + 默认 V2 开关（全关）
        # auto_budget_threshold_usd=inf 使 amount 维度不参与分级（V1 无金额维度）
        return ApprovalConfig(
            auto_budget_threshold_usd=float("inf"),
            auto_daily_cumulative_usd=float("inf"),  # V1 无累计检查
            level1_budget_threshold_usd=float("inf"),
            auto_max_risk=self.auto_max_risk,
            auto_min_confidence=self.auto_min_confidence,
            level1_max_risk=1.0,
            level0_enabled=False,  # V1 默认关 Level 0
            shadow_mode=False,
            dry_run_verify_enabled=False,
        )

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def evaluate(self, intent: ExecutionIntent) -> ApprovalDecision:
        """评估 intent，返回 ApprovalDecision。

        V2 流程（Spec §6）：
        0. 未知动作 → DENY
        1. ADMIN 强制动作 → Level 2 ADMIN
        2. 超日累计 → Level 2 MANUAL
        3. 大额 → Level 2 MANUAL
        4. 中额或中风险 → Level 1 MANUAL + dry_run_required
        5. 小额 + 低风险 + 高置信 + allowlist → Level 0 AUTO
        6. 兜底 → Level 1 MANUAL

        V1 兼容：无 config 时走纯 V1 逻辑（行为与 V1 完全一致）。
        """
        action = getattr(intent, "action", "")
        risk = self._float(getattr(intent, "risk_level", 1.0), default=1.0)
        confidence = self._float(getattr(intent, "confidence", 0.0), default=0.0)
        impact = self._impact_magnitude(getattr(intent, "expected_impact", 0.0))

        # V1 兼容路径：无 config 时走纯 V1 逻辑
        if self._config is None:
            return self._evaluate_v1(intent, action, risk, confidence, impact)

        # V2 路径
        return self._evaluate_v2(intent, action, risk, confidence, impact)

    # ------------------------------------------------------------------
    # V1 评估（纯 V1 逻辑，向后兼容）
    # ------------------------------------------------------------------

    def _evaluate_v1(
        self,
        intent: ExecutionIntent,
        action: Any,
        risk: float,
        confidence: float,
        impact: float,
    ) -> ApprovalDecision:
        """V1 逻辑：与改造前完全一致。"""
        # 0) 未知动作 → DENY
        if not minimum_role_for(action):
            return ApprovalDecision(
                outcome=OUTCOME_DENY,
                required_role="",
                reason=f"action '{action}' is not approvable by any role",
                level=2,
            )

        # 1) ADMIN-only actions
        if action in ADMIN_ACTIONS:
            return ApprovalDecision(
                outcome=OUTCOME_ADMIN,
                required_role=ApprovalRole.ADMIN,
                reason=f"{action} always requires ADMIN approval",
                level=2,
            )

        # 2) SCALE_BUDGET 大额归一化 impact 升级 ADMIN
        if (
            action == ExecutionAction.SCALE_BUDGET
            and impact > self.admin_budget_impact_threshold
        ):
            return ApprovalDecision(
                outcome=OUTCOME_ADMIN,
                required_role=ApprovalRole.ADMIN,
                reason=(
                    f"SCALE_BUDGET impact {impact:.2f} exceeds admin threshold "
                    f"{self.admin_budget_impact_threshold:.2f}"
                ),
                level=2,
            )

        # 3) AUTO_ELIGIBLE_ACTIONS 自动批准
        if (
            action in AUTO_ELIGIBLE_ACTIONS
            and risk < self.auto_max_risk
            and confidence > self.auto_min_confidence
        ):
            return ApprovalDecision(
                outcome=OUTCOME_AUTO,
                required_role=ApprovalRole.SYSTEM,
                reason=(
                    f"auto-approved: {action} risk={risk:.2f}<"
                    f"{self.auto_max_risk} conf={confidence:.2f}>"
                    f"{self.auto_min_confidence}"
                ),
                level=0,
                auto_approved=True,
            )

        # 4) 兜底 → MANUAL
        return self._v1_fallback_manual(action, intent)

    # ------------------------------------------------------------------
    # V2 评估（Level 0/1/2 分级）
    # ------------------------------------------------------------------

    def _evaluate_v2(
        self,
        intent: ExecutionIntent,
        action: Any,
        risk: float,
        confidence: float,
        impact: float,
    ) -> ApprovalDecision:
        """V2 逻辑：Spec §6 Level 0/1/2 三级分级。"""
        cfg = self._config  # type: ignore[assignment]
        # V2 新增：金额维度（缺失默认 0）
        amount_usd = abs(self._float(
            getattr(intent, "budget_amount_usd", 0.0), default=0.0
        ))
        # V2 新增：game_id（从 target_id 取，缺失默认 "default"）
        game_id = getattr(intent, "target_id", "") or "default"

        # 0) 未知动作 → DENY（fail-closed）
        if not minimum_role_for(action):
            return ApprovalDecision(
                outcome=OUTCOME_DENY,
                required_role="",
                reason=f"action '{action}' is not approvable by any role",
                level=2,
            )

        # 1) ADMIN-only actions
        if action in ADMIN_ACTIONS:
            return ApprovalDecision(
                outcome=OUTCOME_ADMIN,
                required_role=ApprovalRole.ADMIN,
                reason=f"{action} always requires ADMIN approval",
                level=2,
            )

        # 2) V1 兼容：SCALE_BUDGET 大额归一化 impact 升级 ADMIN
        #    （V2 优先用 amount_usd，但 V1 intent 可能无 budget_amount_usd，
        #     仍需保留 impact 升级逻辑）
        if (
            action == ExecutionAction.SCALE_BUDGET
            and impact > self.admin_budget_impact_threshold
        ):
            return ApprovalDecision(
                outcome=OUTCOME_ADMIN,
                required_role=ApprovalRole.ADMIN,
                reason=(
                    f"SCALE_BUDGET impact {impact:.2f} exceeds admin threshold "
                    f"{self.admin_budget_impact_threshold:.2f}"
                ),
                level=2,
            )

        # 3) V2 累计窗口检查（仅当 window_tracker 存在）
        if self._window is not None:
            # 用 str(action) 作 key，与 V2ActionExecutor.record 保持一致
            cumulative = self._window.get_cumulative(
                game_id, str(action), date.today()
            )
            if cumulative + amount_usd > cfg.auto_daily_cumulative_usd:
                return ApprovalDecision(
                    outcome=OUTCOME_MANUAL,
                    required_role=ApprovalRole.MANAGER,
                    reason=(
                        f"daily cumulative overflow: {cumulative:.2f}+"
                        f"{amount_usd:.2f} > "
                        f"{cfg.auto_daily_cumulative_usd:.2f}"
                    ),
                    level=2,
                )

        # 4) V2 大额 → Level 2 MANUAL
        if amount_usd >= cfg.level1_budget_threshold_usd:
            return ApprovalDecision(
                outcome=OUTCOME_MANUAL,
                required_role=ApprovalRole.MANAGER,
                reason=f"large budget impact: {amount_usd:.2f} >= "
                       f"{cfg.level1_budget_threshold_usd:.2f}",
                level=2,
            )

        # 5) V2 中额或中风险 → Level 1
        is_medium_amount = amount_usd >= cfg.auto_budget_threshold_usd
        is_medium_risk = risk >= cfg.auto_max_risk
        is_high_risk = risk >= cfg.level1_max_risk
        if is_high_risk:
            # risk 过高 → Level 2
            return ApprovalDecision(
                outcome=OUTCOME_MANUAL,
                required_role=ApprovalRole.MANAGER,
                reason=f"risk {risk:.2f} >= level1_max_risk "
                       f"{cfg.level1_max_risk:.2f}",
                level=2,
            )
        if is_medium_amount or is_medium_risk:
            # Level 1
            if not cfg.dry_run_verify_enabled:
                return ApprovalDecision(
                    outcome=OUTCOME_MANUAL,
                    required_role=ApprovalRole.MANAGER,
                    reason="Level 1: dry_run verify disabled",
                    level=1,
                    dry_run_required=False,
                )
            return ApprovalDecision(
                outcome=OUTCOME_MANUAL,
                required_role=ApprovalRole.MANAGER,
                reason="Level 1: dry_run required",
                level=1,
                dry_run_required=True,
            )

        # 6) V2 Level 0：小额 + 低风险 + 高置信 + allowlist
        if (
            action in LEVEL0_ALLOWLIST
            and risk < cfg.auto_max_risk
            and confidence > cfg.auto_min_confidence
        ):
            if cfg.level0_enabled:
                if cfg.shadow_mode:
                    return ApprovalDecision(
                        outcome=OUTCOME_MANUAL,
                        required_role=ApprovalRole.OPERATOR,
                        reason="Level 0 shadow mode: log only",
                        level=0,
                        dry_run_required=False,
                    )
                return ApprovalDecision(
                    outcome=OUTCOME_AUTO,
                    required_role=ApprovalRole.SYSTEM,
                    reason=(
                        f"Level 0 auto: amount={amount_usd:.2f} "
                        f"risk={risk:.2f} conf={confidence:.2f}"
                    ),
                    level=0,
                    auto_approved=True,
                )
            # Level 0 关闭：V1 AUTO_ELIGIBLE_ACTIONS 仍走 AUTO，其它走 manual
            if action in AUTO_ELIGIBLE_ACTIONS:
                return ApprovalDecision(
                    outcome=OUTCOME_AUTO,
                    required_role=ApprovalRole.SYSTEM,
                    reason=(
                        f"auto-approved: {action} risk={risk:.2f}<"
                        f"{cfg.auto_max_risk} conf={confidence:.2f}>"
                        f"{cfg.auto_min_confidence}"
                    ),
                    level=0,
                    auto_approved=True,
                )
            return self._v1_fallback_manual(action, intent)

        # 7) 兜底 → Level 1 MANUAL
        return self._v1_fallback_manual(action, intent)

    # ------------------------------------------------------------------
    # V1 兼容辅助
    # ------------------------------------------------------------------

    def _v1_fallback_manual(
        self, action: ExecutionAction, intent: ExecutionIntent
    ) -> ApprovalDecision:
        """V1 行为：除 ADMIN/AUTO 外的动作走 MANUAL，按 minimum_role_for 定角色。"""
        required = minimum_role_for(action)
        if required == ApprovalRole.SYSTEM:
            required = ApprovalRole.OPERATOR
        return ApprovalDecision(
            outcome=OUTCOME_MANUAL,
            required_role=required,
            reason=f"{action} requires human approval at {required} or above",
            level=1,
        )

    # ------------------------------------------------------------------
    # 角色批准组合检查（V1 保留）
    # ------------------------------------------------------------------

    def can_role_approve(self, role: str, intent: ExecutionIntent) -> bool:
        """Combined check: policy + role permission for this intent's action."""
        decision = self.evaluate(intent)
        if decision.outcome == OUTCOME_DENY:
            return False
        if decision.outcome == OUTCOME_ADMIN and role != ApprovalRole.ADMIN:
            return False
        return role_can(role, getattr(intent, "action", ""))

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _impact_magnitude(cls, value: Any) -> float:
        """expected_impact 可能是数值或 P2.1 的 Dict；取最大数值幅度。"""
        if isinstance(value, dict):
            magnitudes = [
                abs(cls._float(v))
                for v in value.values()
                if isinstance(v, (int, float))
            ]
            return max(magnitudes) if magnitudes else 0.0
        return abs(cls._float(value))
