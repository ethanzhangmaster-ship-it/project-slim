"""P3.2 — Action Formatter（三态收敛 + WHY 解释）。

把 E17.9 的 `DailyActionItem`（已是 E17.3 + E17.8 + P2.3 三方协调后的最终三态）
收敛成 CEO 可读的 `CEOAction`，并补上「责任来源 + 为什么」。

纪律：
- 纯函数，无 IO、无 Provider、无 LLM
- 零重算：只读 ActionKind / GrowthDecision / DecisionSimulation 既有字段
- 三态唯一权威 = ActionKind（AUTO / APPROVAL / BLOCK）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.ceo_intelligence.daily_operator.models import ActionKind, DailyActionItem

from .models import ActionState, CEOAction, CEOActionStatus


# 责任来源（审计可追溯：这一行行动是谁、哪一关产生的）
_SOURCE_BY_KIND = {
    ActionKind.AUTO: "e17.3_decision+e17.8_sim+p2.4_execution",
    ActionKind.APPROVAL: "e17.3_decision+p2.3_approval",
    ActionKind.BLOCK: "e17.8_simulation_gate",
}

_STATE_BY_KIND = {
    ActionKind.AUTO: ActionState.AUTO,
    ActionKind.APPROVAL: ActionState.APPROVAL,
    ActionKind.BLOCK: ActionState.BLOCKED,
}

_STATUS_BY_KIND = {
    ActionKind.AUTO: CEOActionStatus.EXECUTED,
    ActionKind.APPROVAL: CEOActionStatus.AWAITING_APPROVAL,
    ActionKind.BLOCK: CEOActionStatus.PREVENTED,
}


class ActionFormatter:
    """DailyActionItem(+decision+sim) -> CEOAction。"""

    def __init__(
        self,
        decisions_by_id: Optional[Dict[str, Any]] = None,
        sims_by_id: Optional[Dict[str, Any]] = None,
        priorities_by_game: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.decisions_by_id = decisions_by_id or {}
        self.sims_by_id = sims_by_id or {}
        self.priorities_by_game = priorities_by_game or {}

    # ------------------------------------------------------------------ #
    def _priority(self, action: DailyActionItem) -> float:
        """优先级取 E17.9 已算好的 GamePriority；缺则退化用 |EV|×置信。"""
        pri = self.priorities_by_game.get(action.game_id)
        if pri is not None:
            return float(getattr(pri, "priority_score_value", 0.0) or 0.0)
        dec = self.decisions_by_id.get(action.decision_audit_id)
        if dec is not None:
            ev = float(getattr(dec, "expected_value", 0.0) or 0.0)
            conf = float(getattr(dec, "confidence", 0.0) or 0.0)
            return round(abs(ev) * conf, 6)
        return 0.0

    def _explain(
        self,
        action: DailyActionItem,
        decision: Optional[Any],
        sim: Optional[Any],
    ) -> str:
        kind = action.kind
        conf = float(getattr(decision, "confidence", 0.0) or 0.0)
        risk = float(getattr(decision, "risk", 0.0) or 0.0)
        ev = float(getattr(decision, "expected_value", 0.0) or 0.0)
        label = action.action or action.opportunity_type or "动作"

        if kind == ActionKind.AUTO:
            return (
                f"已自动执行：{label} ｜ 预期收益 {ev:+.1%}，"
                f"置信 {conf:.0%}，风险 {risk:.0%}。"
            )
        if kind == ActionKind.APPROVAL:
            note = f" 备注：{action.detail}" if action.detail else ""
            return (
                f"等待 CEO 审批：{label} ｜ 风险 {risk:.0%}，"
                f"置信 {conf:.0%}，预期收益 {ev:+.1%}。{note}"
            )
        # BLOCK
        reason = ""
        if sim is not None:
            flag = getattr(sim, "flag", None)
            if flag is not None:
                reason = getattr(flag, "reason", "") or ""
        reason = reason or action.detail or (
            getattr(decision, "reason", "") if decision else ""
        ) or "未通过模拟闸门"
        return f"已被模拟闸门阻断：{label} ｜ {reason}"

    def format_one(
        self, action: DailyActionItem, action_id: str
    ) -> CEOAction:
        decision = self.decisions_by_id.get(action.decision_audit_id)
        sim = self.sims_by_id.get(action.decision_audit_id)
        return CEOAction(
            action_id=action_id,
            game_id=action.game_id,
            action_type=action.action or action.opportunity_type,
            source=_SOURCE_BY_KIND.get(action.kind, "unknown"),
            priority=self._priority(action),
            execution_mode=_STATE_BY_KIND[action.kind],
            status=_STATUS_BY_KIND[action.kind],
            explanation=self._explain(action, decision, sim),
        )

    def format(self, actions: List[DailyActionItem]) -> List[CEOAction]:
        """稳定按优先级降序，确定性分配 cea-{idx:03d} id。"""
        ordered = sorted(
            actions, key=lambda a: self._priority(a), reverse=True
        )
        return [
            self.format_one(a, action_id=f"cea-{idx:03d}")
            for idx, a in enumerate(ordered)
        ]


def format_actions(
    actions: List[DailyActionItem],
    decisions_by_id: Optional[Dict[str, Any]] = None,
    sims_by_id: Optional[Dict[str, Any]] = None,
    priorities_by_game: Optional[Dict[str, Any]] = None,
) -> List[CEOAction]:
    """模块级便捷入口。"""
    return ActionFormatter(
        decisions_by_id=decisions_by_id,
        sims_by_id=sims_by_id,
        priorities_by_game=priorities_by_game,
    ).format(actions)


__all__ = ["ActionFormatter", "format_actions"]
