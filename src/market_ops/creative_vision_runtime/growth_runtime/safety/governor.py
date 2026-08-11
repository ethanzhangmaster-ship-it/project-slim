"""E15.0.3 Safety Governor — 安全策略执行.

防止 Agent 误操作的安全控制层。

核心规则:
  - Budget Change: 单次预算变化 ≤ 20%
  - New Campaign: 必须 Human Approval
  - Auto Pause: 允许低 ROAS / 高风险
  - Cooldown: 同一 Campaign 7 天内最多调整一次

所有自动执行必须经过 Safety Governor:
  Action → Safety Check → Execute
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    """风险等级."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SafetyDecision:
    """安全决策 — 安全评估后的结果.

    Attributes:
        approved:    是否批准
        risk_level:  风险等级
        reason:      决策原因
        decision_id: 决策唯一标识
        timestamp:   决策时间
        constraints: 附加约束 (如最大预算变化比例)
        requires_manual: 是否需要人工审批
    """

    approved: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    reason: str = ""
    decision_id: str = field(default_factory=lambda: f"safety_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    constraints: dict[str, Any] = field(default_factory=dict)
    requires_manual: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "approved": self.approved,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "constraints": self.constraints,
            "requires_manual": self.requires_manual,
        }


class ActionType(str, Enum):
    """动作类型."""
    BUDGET_CHANGE = "budget_change"
    CREATE_CAMPAIGN = "create_campaign"
    PAUSE_CAMPAIGN = "pause_campaign"
    RESUME_CAMPAIGN = "resume_campaign"
    UPLOAD_CREATIVE = "upload_creative"
    MUTATE_CREATIVE = "mutate_creative"
    ROLLBACK = "rollback"


# ═══════════════════════════════════════════════════════════════
# Safety Policies
# ═══════════════════════════════════════════════════════════════


@dataclass
class BudgetChangePolicy:
    """预算变化策略 — 单次预算变化 ≤ 20%."""

    max_change_pct: float = 0.20
    require_approval_above_pct: float = 0.15

    def evaluate(
        self,
        current_budget: float,
        new_budget: float,
    ) -> SafetyDecision:
        """评估预算变化.

        Args:
            current_budget: 当前预算
            new_budget: 新预算

        Returns:
            SafetyDecision
        """
        if current_budget <= 0:
            return SafetyDecision(
                approved=False,
                risk_level=RiskLevel.HIGH,
                reason="Cannot evaluate budget change: current budget is zero",
            )

        change_pct = abs(new_budget - current_budget) / current_budget

        if change_pct > self.max_change_pct:
            return SafetyDecision(
                approved=False,
                risk_level=RiskLevel.HIGH,
                reason=f"Budget change {change_pct:.1%} exceeds max {self.max_change_pct:.0%}",
                constraints={"max_allowed_change": self.max_change_pct},
            )

        if change_pct > self.require_approval_above_pct:
            return SafetyDecision(
                approved=True,
                risk_level=RiskLevel.MEDIUM,
                reason=f"Budget change {change_pct:.1%} requires approval",
                requires_manual=True,
                constraints={"change_pct": change_pct},
            )

        return SafetyDecision(
            approved=True,
            risk_level=RiskLevel.LOW,
            reason=f"Budget change {change_pct:.1%} within safe range",
            constraints={"change_pct": change_pct},
        )


@dataclass
class NewCampaignPolicy:
    """新 Campaign 策略 — 必须 Human Approval."""

    require_approval: bool = True

    def evaluate(self) -> SafetyDecision:
        if self.require_approval:
            return SafetyDecision(
                approved=True,
                risk_level=RiskLevel.MEDIUM,
                reason="New campaign creation requires human approval",
                requires_manual=True,
            )
        return SafetyDecision(
            approved=True,
            risk_level=RiskLevel.LOW,
            reason="New campaign creation auto-approved",
        )


@dataclass
class AutoPausePolicy:
    """自动暂停策略 — 允许低 ROAS / 高风险."""

    roas_threshold: float = 0.5
    risk_threshold: RiskLevel = RiskLevel.HIGH

    def evaluate(
        self,
        roas: float,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> SafetyDecision:
        """评估是否允许自动暂停.

        Args:
            roas: 当前 ROAS
            risk_level: 风险等级

        Returns:
            SafetyDecision
        """
        reasons: list[str] = []

        if roas < self.roas_threshold:
            reasons.append(f"ROAS {roas:.2f} below threshold {self.roas_threshold}")

        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            reasons.append(f"Risk level is {risk_level.value}")

        if reasons:
            return SafetyDecision(
                approved=True,
                risk_level=RiskLevel.MEDIUM,
                reason="Auto-pause allowed: " + "; ".join(reasons),
            )

        return SafetyDecision(
            approved=False,
            risk_level=RiskLevel.LOW,
            reason="Auto-pause not justified: ROAS and risk within acceptable range",
        )


@dataclass
class CooldownPolicy:
    """冷却时间策略 — 同一 Campaign 7 天内最多调整一次."""

    cooldown_days: int = 7

    def evaluate(
        self,
        campaign_id: str,
        last_action_time: str | None,
    ) -> SafetyDecision:
        """评估冷却时间.

        Args:
            campaign_id: 广告系列 ID
            last_action_time: 上次操作时间 (ISO 8601)

        Returns:
            SafetyDecision
        """
        if not last_action_time:
            return SafetyDecision(
                approved=True,
                risk_level=RiskLevel.LOW,
                reason="No previous action on this campaign",
            )

        try:
            last_time = datetime.fromisoformat(last_action_time)
            cooldown_end = last_time + timedelta(days=self.cooldown_days)
            now = datetime.now(timezone.utc)

            if now < cooldown_end:
                remaining = cooldown_end - now
                return SafetyDecision(
                    approved=False,
                    risk_level=RiskLevel.MEDIUM,
                    reason=f"Campaign {campaign_id} in cooldown: "
                           f"{remaining.days}d {remaining.seconds // 3600}h remaining "
                           f"(cooldown: {self.cooldown_days} days)",
                    constraints={"cooldown_end": cooldown_end.isoformat()},
                )
        except (ValueError, TypeError):
            pass

        return SafetyDecision(
            approved=True,
            risk_level=RiskLevel.LOW,
            reason=f"Cooldown passed for campaign {campaign_id}",
        )


# ═══════════════════════════════════════════════════════════════
# Safety Governor
# ═══════════════════════════════════════════════════════════════


class SafetyGovernor:
    """安全治理器 — E15.0.3 核心.

    所有自动执行必须经过 Safety Governor:
      Action → Safety Check → Execute

    用法:
        governor = SafetyGovernor()
        decision = governor.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 100, "new_budget": 115},
            campaign_id="camp_001",
        )
        if decision.approved:
            execute(action)
    """

    def __init__(
        self,
        budget_policy: BudgetChangePolicy | None = None,
        campaign_policy: NewCampaignPolicy | None = None,
        pause_policy: AutoPausePolicy | None = None,
        cooldown_policy: CooldownPolicy | None = None,
    ):
        self._budget_policy = budget_policy or BudgetChangePolicy()
        self._campaign_policy = campaign_policy or NewCampaignPolicy()
        self._pause_policy = pause_policy or AutoPausePolicy()
        self._cooldown_policy = cooldown_policy or CooldownPolicy()
        self._action_history: dict[str, str] = {}  # campaign_id → last_action_time

    # ── Main Entry ───────────────────────────────────────────

    def evaluate(
        self,
        action_type: ActionType,
        params: dict[str, Any] | None = None,
        campaign_id: str = "",
        game_id: str = "",
    ) -> SafetyDecision:
        """评估动作安全性.

        Args:
            action_type: 动作类型
            params:      动作参数
            campaign_id: 广告系列 ID
            game_id:     游戏 ID

        Returns:
            SafetyDecision
        """
        params = params or {}

        if action_type == ActionType.BUDGET_CHANGE:
            return self._evaluate_budget(params, campaign_id)

        if action_type == ActionType.CREATE_CAMPAIGN:
            return self._evaluate_campaign(campaign_id)

        if action_type == ActionType.PAUSE_CAMPAIGN:
            return self._evaluate_pause(params, campaign_id)

        if action_type == ActionType.RESUME_CAMPAIGN:
            return self._evaluate_cooldown(campaign_id)

        if action_type in (ActionType.UPLOAD_CREATIVE, ActionType.MUTATE_CREATIVE):
            return SafetyDecision(
                approved=True,
                risk_level=RiskLevel.LOW,
                reason=f"Creative action {action_type.value} is low risk",
            )

        if action_type == ActionType.ROLLBACK:
            return SafetyDecision(
                approved=True,
                risk_level=RiskLevel.MEDIUM,
                reason="Rollback is always allowed for safety",
            )

        return SafetyDecision(
            approved=False,
            risk_level=RiskLevel.HIGH,
            reason=f"Unknown action type: {action_type}",
        )

    def _evaluate_budget(
        self,
        params: dict[str, Any],
        campaign_id: str,
    ) -> SafetyDecision:
        """评估预算变化 (先检查冷却时间, 再检查预算变化)."""
        # 1. 冷却时间检查
        if campaign_id:
            cooldown = self._cooldown_policy.evaluate(
                campaign_id,
                self._action_history.get(campaign_id),
            )
            if not cooldown.approved:
                return cooldown

        # 2. 预算变化检查
        current_budget = params.get("current_budget", 0)
        new_budget = params.get("new_budget", 0)
        decision = self._budget_policy.evaluate(current_budget, new_budget)

        # 3. 记录操作时间
        if decision.approved and campaign_id:
            self._action_history[campaign_id] = datetime.now(timezone.utc).isoformat()

        return decision

    def _evaluate_campaign(self, campaign_id: str) -> SafetyDecision:
        """评估新 Campaign 创建."""
        return self._campaign_policy.evaluate()

    def _evaluate_pause(
        self,
        params: dict[str, Any],
        campaign_id: str,
    ) -> SafetyDecision:
        """评估自动暂停."""
        roas = params.get("roas", 1.0)
        risk = params.get("risk_level", RiskLevel.LOW)
        if isinstance(risk, str):
            try:
                risk = RiskLevel(risk)
            except ValueError:
                risk = RiskLevel.LOW

        pause_decision = self._pause_policy.evaluate(roas, risk)
        if not pause_decision.approved:
            return pause_decision

        # 冷却时间检查
        if campaign_id:
            return self._cooldown_policy.evaluate(
                campaign_id,
                self._action_history.get(campaign_id),
            )

        return pause_decision

    def _evaluate_cooldown(self, campaign_id: str) -> SafetyDecision:
        """仅检查冷却时间."""
        if campaign_id:
            return self._cooldown_policy.evaluate(
                campaign_id,
                self._action_history.get(campaign_id),
            )
        return SafetyDecision(
            approved=True,
            risk_level=RiskLevel.LOW,
            reason="No campaign specified, cooldown not applicable",
        )

    # ── Action History ───────────────────────────────────────

    def record_action(self, campaign_id: str) -> None:
        """记录一次操作."""
        self._action_history[campaign_id] = datetime.now(timezone.utc).isoformat()

    def get_last_action(self, campaign_id: str) -> str | None:
        """获取上次操作时间."""
        return self._action_history.get(campaign_id)

    def reset_cooldown(self, campaign_id: str) -> None:
        """重置冷却时间."""
        self._action_history.pop(campaign_id, None)

    # ── Statistics ───────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "budget_max_change_pct": self._budget_policy.max_change_pct,
            "campaign_require_approval": self._campaign_policy.require_approval,
            "pause_roas_threshold": self._pause_policy.roas_threshold,
            "cooldown_days": self._cooldown_policy.cooldown_days,
            "tracked_campaigns": len(self._action_history),
        }


__all__ = [
    "SafetyGovernor",
    "SafetyDecision",
    "RiskLevel",
    "ActionType",
    "BudgetChangePolicy",
    "NewCampaignPolicy",
    "AutoPausePolicy",
    "CooldownPolicy",
]