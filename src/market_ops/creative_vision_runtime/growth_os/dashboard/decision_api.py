"""E12.7.7 Decision API — 查看 AI 决策和推理过程."""

from __future__ import annotations

from typing import Any

from ..agent.agent_controller import AutonomousGrowthAgent
from ..agent.models import AgentDecision, GrowthHypothesis

from .models import DecisionView


class DecisionAPI:
    """决策 API — 查看 AI 决策和推理过程.

    提供:
      - get_decisions():        获取所有决策
      - get_decisions_by_product(): 按产品筛选
      - get_top_decisions():    获取最高优先级决策
      - get_decision_detail():  决策详情
    """

    def __init__(self, agent: AutonomousGrowthAgent | None = None):
        self._agent = agent or AutonomousGrowthAgent()
        self._query_count: int = 0

    @property
    def query_count(self) -> int:
        return self._query_count

    # ── Get Decisions ─────────────────────────────────────────

    def get_decisions(self, product_id: str = "") -> list[DecisionView]:
        """获取所有决策."""
        self._query_count += 1

        decisions = self._agent.get_last_decisions()
        result: list[DecisionView] = []

        for d in decisions:
            dv = self._decision_to_view(d)
            if not product_id or dv.product_id == product_id:
                result.append(dv)

        return result

    def get_decisions_by_product(self, product_id: str) -> list[DecisionView]:
        """按产品获取决策."""
        return self.get_decisions(product_id=product_id)

    def get_top_decisions(self, limit: int = 5) -> list[DecisionView]:
        """获取最高优先级决策."""
        self._query_count += 1

        decisions = self._agent.get_last_decisions()
        sorted_decisions = sorted(decisions, key=lambda d: d.priority, reverse=True)
        return [self._decision_to_view(d) for d in sorted_decisions[:limit]]

    def get_decision_detail(self, decision_id: str) -> dict[str, Any] | None:
        """获取决策详情."""
        self._query_count += 1

        decisions = self._agent.get_last_decisions()
        for d in decisions:
            if d.decision_id == decision_id:
                return self._build_decision_detail(d)
        return None

    def get_pending_decisions(self) -> list[DecisionView]:
        """获取待处理决策."""
        self._query_count += 1

        decisions = self._agent.get_last_decisions()
        return [
            self._decision_to_view(d)
            for d in decisions
            if getattr(d, "status", "pending") == "pending"
        ]

    # ── Helpers ───────────────────────────────────────────────

    def _decision_to_view(self, d: AgentDecision) -> DecisionView:
        """将 AgentDecision 转换为 DecisionView."""
        return DecisionView(
            decision_id=d.decision_id,
            product_id=d.product_id,
            action=d.action_type.value if d.action_type else "",
            reason=d.reason,
            confidence=d.confidence,
            priority=d.priority,
            impact=d.expected_impact,
            source_module="Agent Decision Engine",
            status="pending" if d.priority > 0 else "done",
            created_at=d.created_at.isoformat() if d.created_at else "",
        )

    def _build_decision_detail(self, d: AgentDecision) -> dict[str, Any]:
        """构建决策详情."""
        view = self._decision_to_view(d)
        return {
            **view.to_dict(),
            "hypothesis_id": d.hypothesis_id,
            "risk_level": getattr(d, "risk_level", ""),
            "metadata": getattr(d, "metadata", {}),
        }

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        decisions = self._agent.get_last_decisions()
        return {
            "total_decisions": len(decisions),
            "pending_count": len(self.get_pending_decisions()),
            "top_priority": self._agent.get_top_decision().priority if self._agent.get_top_decision() else 0,
            "query_count": self._query_count,
        }