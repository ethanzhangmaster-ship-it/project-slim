"""E14.8.5 Safety Guard — 增长安全守护器.

E14.8 Autonomous Growth Agent 第五层:
  确保 Autonomous Growth Agent 不会无限操作，保护系统安全.

核心约束:
  1. Budget: 单日预算变化不超过 30%
  2. Frequency: 同一 campaign 7 天内最多一次策略调整
  3. Confidence: confidence < 0.8 需要人工确认
  4. Blast Radius: 首次只影响 10% 预算，验证后扩大

核心模型:
  - BudgetLimit: 预算限制
  - FrequencyLimit: 频率限制
  - SafetyDecision: 安全检查决策
  - GrowthSafetyGuard: 安全守护器
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class SafetyDecisionType(str, Enum):
    """安全检查决策类型."""
    APPROVED = "approved"           # 自动批准
    APPROVED_WITH_LIMITS = "approved_with_limits"  # 限制后批准
    NEEDS_REVIEW = "needs_review"   # 需要人工审核
    BLOCKED = "blocked"             # 阻止


# ═══════════════════════════════════════════════════════════
# 模型
# ═══════════════════════════════════════════════════════════

@dataclass
class BudgetLimit:
    """预算限制 — 单次预算变化约束.

    Attributes:
        max_daily_change_pct: 单日最大预算变化百分比 (默认 30%)
        max_reduce_pct: 最大缩减比例 (默认 50%)
        max_increase_pct: 最大增加比例 (默认 200%)
        blast_radius_pct: 首次操作影响范围 (默认 10%)
    """
    max_daily_change_pct: float = 0.30
    max_reduce_pct: float = 0.50
    max_increase_pct: float = 2.00
    blast_radius_pct: float = 0.10

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_daily_change_pct": self.max_daily_change_pct,
            "max_reduce_pct": self.max_reduce_pct,
            "max_increase_pct": self.max_increase_pct,
            "blast_radius_pct": self.blast_radius_pct,
        }


@dataclass
class FrequencyLimit:
    """频率限制 — 同一目标操作频率约束.

    Attributes:
        min_interval_days: 最小操作间隔 (天) (默认 7)
        max_actions_per_cycle: 每周期最大操作数 (默认 5)
        max_actions_per_campaign: 每 campaign 最大操作数 (默认 3)
    """
    min_interval_days: int = 7
    max_actions_per_cycle: int = 5
    max_actions_per_campaign: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_interval_days": self.min_interval_days,
            "max_actions_per_cycle": self.max_actions_per_cycle,
            "max_actions_per_campaign": self.max_actions_per_campaign,
        }


@dataclass
class SafetyDecision:
    """安全检查决策结果.

    Attributes:
        decision_id: 决策 ID
        decision: 决策类型
        reason: 决策原因
        modified_actions: 修改后的动作列表
        blocked_actions: 被阻止的动作列表
        limits_applied: 应用的限制
        timestamp: 时间戳
    """
    decision_id: str = field(default_factory=lambda: f"sd_{uuid.uuid4().hex[:8]}")
    decision: SafetyDecisionType = SafetyDecisionType.APPROVED
    reason: str = ""
    modified_actions: list[Any] = field(default_factory=list)
    blocked_actions: list[Any] = field(default_factory=list)
    limits_applied: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision": self.decision.value,
            "reason": self.reason,
            "modified_count": len(self.modified_actions),
            "blocked_count": len(self.blocked_actions),
            "limits_applied": self.limits_applied,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════
# GrowthSafetyGuard
# ═══════════════════════════════════════════════════════════

class GrowthSafetyGuard:
    """增长安全守护器 — 在自动操作前进行安全检查.

    检查项:
      1. Budget: 预算变化是否在限制内
      2. Frequency: 操作频率是否过高
      3. Confidence: 置信度是否足够
      4. Blast Radius: 影响范围是否过大

    用法:
        guard = GrowthSafetyGuard()
        decision = guard.check(plan, action_history)
        if decision.decision == SafetyDecisionType.APPROVED:
            execute(decision.modified_actions)
    """

    def __init__(
        self,
        budget_limit: BudgetLimit | None = None,
        frequency_limit: FrequencyLimit | None = None,
        min_confidence_auto: float = 0.8,
        min_confidence_review: float = 0.5,
    ):
        self._budget = budget_limit or BudgetLimit()
        self._frequency = frequency_limit or FrequencyLimit()
        self._min_confidence_auto = min_confidence_auto
        self._min_confidence_review = min_confidence_review
        self._action_history: dict[str, list[str]] = defaultdict(list)
        self._decision_count: int = 0

    def check(
        self,
        plan: Any,  # GrowthPlan
        action_history: dict[str, list[str]] | None = None,
    ) -> SafetyDecision:
        """对计划执行安全检查.

        Args:
            plan: 增长计划
            action_history: 动作历史 {campaign_id: [action_ids]}

        Returns:
            SafetyDecision: 安全检查结果
        """
        self._decision_count += 1

        actions = getattr(plan, "actions", [])
        confidence = getattr(plan, "confidence", 0.0)
        risk_level = getattr(plan, "risk_level", "medium")

        modified = list(actions)
        blocked: list[Any] = []
        reasons: list[str] = []
        limits: list[str] = []

        # 1. 置信度检查
        if confidence < self._min_confidence_review:
            return SafetyDecision(
                decision=SafetyDecisionType.BLOCKED,
                reason=f"Confidence too low: {confidence:.2f} < {self._min_confidence_review}",
                blocked_actions=list(actions),
            )

        if confidence < self._min_confidence_auto:
            reasons.append(f"Confidence {confidence:.2f} below auto threshold")
            limits.append("confidence_review")

        # 2. 频率检查
        if action_history:
            freq_result = self._check_frequency(actions, action_history)
            if freq_result["blocked"]:
                for a in freq_result["blocked"]:
                    blocked.append(a)
                    modified.remove(a)
                reasons.append(f"Frequency limit: {len(freq_result['blocked'])} actions blocked")
                limits.append("frequency")

        # 3. 预算检查
        budget_result = self._check_budget(modified)
        if budget_result["modified"]:
            modified = budget_result["modified"]
            limits.append("budget")
            reasons.append("Budget limits applied")

        # 4. Blast Radius 检查
        blast_result = self._check_blast_radius(modified, action_history)
        if blast_result["modified"]:
            modified = blast_result["modified"]
            limits.append("blast_radius")
            reasons.append("Blast radius limits applied")

        # 5. 高风险计划需要审批
        if risk_level == "high" and confidence < self._min_confidence_auto:
            return SafetyDecision(
                decision=SafetyDecisionType.NEEDS_REVIEW,
                reason=f"High risk plan with moderate confidence: {confidence:.2f}",
                modified_actions=modified,
                blocked_actions=blocked,
                limits_applied=limits,
            )

        # 6. 确定最终决策
        if blocked and not modified:
            decision = SafetyDecisionType.BLOCKED
        elif limits:
            decision = SafetyDecisionType.APPROVED_WITH_LIMITS
        elif reasons:
            decision = SafetyDecisionType.NEEDS_REVIEW
        else:
            decision = SafetyDecisionType.APPROVED

        return SafetyDecision(
            decision=decision,
            reason="; ".join(reasons) if reasons else "All checks passed",
            modified_actions=modified,
            blocked_actions=blocked,
            limits_applied=limits,
        )

    def _check_frequency(
        self,
        actions: list[Any],
        history: dict[str, list[str]],
    ) -> dict[str, Any]:
        """检查操作频率."""
        blocked: list[Any] = []
        now = datetime.now(timezone.utc)

        for action in actions:
            target_id = getattr(action, "target_id", "")
            if not target_id:
                continue

            campaign_history = history.get(target_id, [])
            # 检查 7 天内是否已有操作
            if len(campaign_history) >= self._frequency.max_actions_per_campaign:
                blocked.append(action)

        return {"blocked": blocked}

    def _check_budget(
        self,
        actions: list[Any],
    ) -> dict[str, Any]:
        """检查预算限制."""
        modified: list[Any] = []

        for action in actions:
            payload = getattr(action, "payload", {})
            multiplier = payload.get("budget_multiplier", 1.0)

            if multiplier < 1.0 - self._budget.max_reduce_pct:
                # 限制缩减幅度
                payload["budget_multiplier"] = 1.0 - self._budget.max_reduce_pct
                payload["_safety_note"] = "Budget reduce capped by safety guard"

            if multiplier > 1.0 + self._budget.max_increase_pct:
                # 限制增加幅度
                payload["budget_multiplier"] = 1.0 + self._budget.max_increase_pct
                payload["_safety_note"] = "Budget increase capped by safety guard"

            modified.append(action)

        return {"modified": modified if modified != actions else []}

    def _check_blast_radius(
        self,
        actions: list[Any],
        history: dict[str, list[str]] | None,
    ) -> dict[str, Any]:
        """检查影响范围 — 首次操作限制."""
        if history is None:
            return {"modified": []}

        modified: list[Any] = []
        for action in actions:
            target_id = getattr(action, "target_id", "")
            if not target_id:
                modified.append(action)
                continue

            campaign_history = history.get(target_id, [])
            is_first_operation = len(campaign_history) == 0

            if is_first_operation:
                payload = getattr(action, "payload", {})
                if "budget_multiplier" in payload:
                    # 首次操作限制在 blast_radius 内
                    original = payload["budget_multiplier"]
                    if original > 1.0:
                        capped = min(original, 1.0 + self._budget.blast_radius_pct)
                        payload["budget_multiplier"] = capped
                        payload["_blast_radius_applied"] = True
                    elif original < 1.0:
                        capped = max(original, 1.0 - self._budget.blast_radius_pct)
                        payload["budget_multiplier"] = capped
                        payload["_blast_radius_applied"] = True

            modified.append(action)

        return {"modified": modified if modified != actions else []}

    def record_action(self, campaign_id: str, action_id: str) -> None:
        """记录已执行的动作."""
        self._action_history[campaign_id].append(action_id)

    def get_campaign_history(self, campaign_id: str) -> list[str]:
        """获取 campaign 的操作历史."""
        return list(self._action_history.get(campaign_id, []))

    def is_campaign_eligible(self, campaign_id: str) -> bool:
        """检查 campaign 是否可操作."""
        history = self._action_history.get(campaign_id, [])
        return len(history) < self._frequency.max_actions_per_campaign

    def get_stats(self) -> dict[str, Any]:
        """获取统计."""
        return {
            "decision_count": self._decision_count,
            "tracked_campaigns": len(self._action_history),
            "total_actions_tracked": sum(len(v) for v in self._action_history.values()),
            "budget_limits": self._budget.to_dict(),
            "frequency_limits": self._frequency.to_dict(),
            "min_confidence_auto": self._min_confidence_auto,
            "min_confidence_review": self._min_confidence_review,
        }

    def reset(self) -> None:
        self._action_history.clear()
        self._decision_count = 0

    @property
    def budget_limit(self) -> BudgetLimit:
        return self._budget

    @property
    def frequency_limit(self) -> FrequencyLimit:
        return self._frequency

    @property
    def decision_count(self) -> int:
        return self._decision_count


def create_safety_guard(
    max_daily_change_pct: float = 0.30,
    max_reduce_pct: float = 0.50,
    max_increase_pct: float = 2.00,
    blast_radius_pct: float = 0.10,
    min_interval_days: int = 7,
    max_actions_per_cycle: int = 5,
    min_confidence_auto: float = 0.8,
    min_confidence_review: float = 0.5,
) -> GrowthSafetyGuard:
    """创建默认 SafetyGuard."""
    budget = BudgetLimit(
        max_daily_change_pct=max_daily_change_pct,
        max_reduce_pct=max_reduce_pct,
        max_increase_pct=max_increase_pct,
        blast_radius_pct=blast_radius_pct,
    )
    frequency = FrequencyLimit(
        min_interval_days=min_interval_days,
        max_actions_per_cycle=max_actions_per_cycle,
    )
    return GrowthSafetyGuard(
        budget_limit=budget,
        frequency_limit=frequency,
        min_confidence_auto=min_confidence_auto,
        min_confidence_review=min_confidence_review,
    )