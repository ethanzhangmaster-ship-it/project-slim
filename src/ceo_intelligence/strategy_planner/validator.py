"""E17.4 — 策略质量门禁（三道门，确定性，无 LLM）。

Gate 1 — 目标：objective 必须非空且非模糊词（如「优化一下」）。
Gate 2 — 指标：success_metrics 非空，且至少一项可被量化（含 +/- 数字或 %）。
Gate 3 — 风险：决策风险高（>=0.6）或经济/营收类策略 → 标记 needs_approval（不拒绝，仅要求人工审批）。

Gate 1/2 失败 → ok=False（plan 被拒绝 / 标记未通过）；
Gate 3 仅置 needs_approval=True，供 E17.6 Execution Router 走审批流。
"""
from __future__ import annotations

import re
from typing import List, Optional

from .models import GrowthStrategyPlan, StrategyValidationResult

# 模糊目标词（中英文），遇之视为未定义清楚的目标
VAGUE_OBJECTIVES = {
    "优化一下", "调整一下", "改一下", "improve", "optimize", "fix", "do better", "tweak",
}

# 可量化指标：+10% / -5% / 0.1 / +0.2 等
_MEASURABLE = re.compile(r"^[+-]?\d+(\.\d+)?\s*%?$")

# 经济 / 营收修复属高风险动作，默认需人工审批（与 E17.3 Gate 3 的 PAYMENT 域一致）
HIGH_RISK_TYPES = {"monetization", "revenue_recovery"}
HIGH_RISK = 0.6


class StrategyValidator:
    def validate(
        self,
        plan: GrowthStrategyPlan,
        decision_risk: Optional[float] = None,
    ) -> StrategyValidationResult:
        reasons: List[str] = []

        # Gate 1：目标
        obj = (plan.objective or "").strip()
        if not obj or obj.lower() in VAGUE_OBJECTIVES:
            reasons.append("objective missing or vague")

        # Gate 2：指标
        if not plan.success_metrics:
            reasons.append("success metrics missing")
        else:
            measurable = [
                v
                for v in plan.success_metrics.values()
                if isinstance(v, str) and _MEASURABLE.match(v.strip())
            ]
            if not measurable:
                reasons.append("success metric not measurable")

        # Gate 3：风险 → 需审批（不拒绝）
        needs_approval = False
        if decision_risk is not None and decision_risk >= HIGH_RISK:
            needs_approval = True
        elif plan.strategy_type in HIGH_RISK_TYPES:
            needs_approval = True

        return StrategyValidationResult(
            ok=len(reasons) == 0, reasons=reasons, needs_approval=needs_approval
        )
