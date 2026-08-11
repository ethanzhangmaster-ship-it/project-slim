"""E15.2.3 Explainability Layer — 可解释性层.

每次选择必须输出:
  - 为什么选择此动作
  - 为什么拒绝其他动作
  - 决策追踪信息

连接:
  - E15.0.11 Observability
  - Dashboard
  - Human Approval System
"""

from __future__ import annotations

from typing import Any

from .models import (
    ActionCandidate,
    ScoredCandidate,
    SelectedAction,
    SelectionResult,
    SelectionStatus,
)


class DecisionExplainer:
    """E15.2.3 决策解释器 — 生成选择理由和决策追踪.

    用法:
        explainer = DecisionExplainer()
        selected = explainer.explain(result)
    """

    def explain(self, result: SelectionResult) -> SelectedAction:
        """为选择结果生成解释.

        Args:
            result: SelectionResult (含所有候选)

        Returns:
            SelectedAction: 含 reasoning 和 alternatives
        """
        if result.selected is None:
            return SelectedAction(
                reasoning="No action selected — no eligible candidates",
                trace={"total_candidates": len(result.candidates)},
            )

        selected = result.selected

        # 构建选中的理由
        reasoning = self._build_reasoning(selected, result.candidates)

        # 构建备选方案
        alternatives = self._build_alternatives(result.candidates)

        # 构建决策追踪
        trace = self._build_trace(selected, result.candidates)

        return SelectedAction(
            action_id=selected.action_id,
            action_type=selected.action_type,
            score=selected.score,
            confidence=selected.confidence,
            reasoning=reasoning,
            alternatives=alternatives,
            trace=trace,
        )

    def _build_reasoning(
        self,
        selected: SelectedAction,
        all_candidates: list[ScoredCandidate],
    ) -> str:
        """构建选择理由."""
        selected_scored = None
        for c in all_candidates:
            if c.candidate.action_id == selected.action_id:
                selected_scored = c
                break

        if selected_scored is None:
            return f"Selected {selected.action_type} with score {selected.score:.4f}"

        parts = [f"Selected '{selected.action_type}' " f"(score: {selected.score:.4f})"]

        candidate = selected_scored.candidate

        if candidate.expected_reward > 0.5:
            parts.append(f"high expected reward ({candidate.expected_reward:.2f})")
        if candidate.confidence > 0.7:
            parts.append(f"strong confidence ({candidate.confidence:.2f})")
        if candidate.memory_boost > 0.3:
            parts.append(f"strong historical pattern (boost: {candidate.memory_boost:.2f})")
        if candidate.risk_score < 0.3:
            parts.append(f"low risk ({candidate.risk_score:.2f})")

        # 与第二名对比
        ranked = [c for c in all_candidates if c.status != SelectionStatus.BLOCKED]
        ranked.sort(key=lambda c: c.total_score, reverse=True)
        if len(ranked) >= 2:
            runner_up = ranked[1]
            margin = selected_scored.total_score - runner_up.total_score
            parts.append(f"margin over runner-up: {margin:.4f}")

        return "; ".join(parts)

    def _build_alternatives(
        self,
        all_candidates: list[ScoredCandidate],
    ) -> list[dict[str, Any]]:
        """构建备选方案列表."""
        alternatives: list[dict[str, Any]] = []
        for c in all_candidates:
            if c.status == SelectionStatus.SELECTED:
                continue
            alt = {
                "action_id": c.candidate.action_id,
                "action_type": c.candidate.action_type,
                "score": c.total_score,
                "status": c.status.value,
                "reason": self._rejection_reason(c),
            }
            if c.block_reason:
                alt["block_reason"] = c.block_reason
            alternatives.append(alt)
        return alternatives

    def _rejection_reason(self, candidate: ScoredCandidate) -> str:
        """生成拒绝原因."""
        if candidate.status == SelectionStatus.BLOCKED:
            return f"Blocked: {candidate.block_reason}"

        reasons: list[str] = []

        c = candidate.candidate
        if c.expected_reward < 0.5:
            reasons.append("lower expected reward")
        if c.confidence < 0.6:
            reasons.append("low confidence")
        if c.risk_score > 0.5:
            reasons.append("high risk")
        if c.execution_cost > 0.3:
            reasons.append("high execution cost")

        if reasons:
            return "; ".join(reasons)
        return "lower overall score"

    def _build_trace(
        self,
        selected: SelectedAction,
        all_candidates: list[ScoredCandidate],
    ) -> dict[str, Any]:
        """构建决策追踪."""
        return {
            "selection_timestamp": "",
            "total_candidates": len(all_candidates),
            "blocked_count": sum(
                1 for c in all_candidates if c.status == SelectionStatus.BLOCKED
            ),
            "rejected_count": sum(
                1 for c in all_candidates if c.status == SelectionStatus.REJECTED
            ),
            "selected_action": selected.action_type,
            "selected_score": selected.score,
            "score_breakdown": {
                "reward": selected.score,
                "confidence": selected.confidence,
            },
        }


__all__ = ["DecisionExplainer"]