"""E17.4 — 策略规划器 + 依赖图（StrategyGraph）。

planner：把 GrowthDecision → GrowthStrategyPlan（确定性，无 LLM）
StrategyGraph：管理 task 间 dependencies、拓扑排序、blockers、环检测。
"""
from __future__ import annotations

from collections import deque
from typing import List, Optional

from src.ceo_intelligence.decision_engine.models import GrowthDecision

from .memory import StrategyMemory
from .models import (
    GrowthStrategyPlan,
    StrategyQualityError,
    StrategyTask,
    strategy_type_from_decision,
)
from .templates import build_tasks, get_template
from .validator import StrategyValidator


class StrategyGraph:
    """依赖图：管理 task 间 dependencies、拓扑排序、blockers、环检测。"""

    def __init__(self, tasks: List[StrategyTask]):
        self.tasks = tasks
        self._by_order = {t.order: t for t in tasks}

    def blockers(self, order: int) -> List[int]:
        """返回某任务依赖的前置任务 order 列表。"""
        t = self._by_order.get(order)
        if not t:
            return []
        return [int(d) for d in t.dependency if int(d) in self._by_order]

    def _topo(self) -> List[int]:
        indeg = {t.order: 0 for t in self.tasks}
        adj = {t.order: [] for t in self.tasks}
        for t in self.tasks:
            for d in t.dependency:
                dd = int(d)
                if dd in self._by_order and dd != t.order:
                    adj[dd].append(t.order)
                    indeg[t.order] += 1
        q = deque(sorted(o for o in indeg if indeg[o] == 0))
        out: List[int] = []
        while q:
            n = q.popleft()
            out.append(n)
            for m in sorted(adj[n]):
                indeg[m] -= 1
                if indeg[m] == 0:
                    q.append(m)
        return out

    def has_cycle(self) -> bool:
        return len(self._topo()) != len(self.tasks)

    def is_valid(self) -> bool:
        """依赖图无环且每个被引用前置都存在。"""
        if self.has_cycle():
            return False
        for t in self.tasks:
            for d in t.dependency:
                if int(d) not in self._by_order:
                    return False
        return True

    def execution_order(self) -> List[int]:
        """返回按依赖关系的可执行顺序（同层按 order 升序）。"""
        return self._topo()


class GrowthStrategyPlanner:
    def __init__(
        self,
        memory: Optional[StrategyMemory] = None,
        validator: Optional[StrategyValidator] = None,
    ):
        self.memory = memory
        self.validator = validator or StrategyValidator()

    # ------------------------------------------------------------------ #
    def create_plan(
        self,
        decision: GrowthDecision,
        *,
        segment: str = "global",
        strict: bool = True,
    ) -> GrowthStrategyPlan:
        stype = strategy_type_from_decision(decision)
        template = get_template(stype)

        if template is None:
            # 无模板 → objective / metrics 缺失 → 质量门禁必然拒绝
            plan = GrowthStrategyPlan(
                game_id=decision.game_id,
                decision_id=decision.audit_id,
                objective="",
                strategy_type=stype,
                success_metrics={},
                estimated_duration_days=0,
                confidence=decision.confidence,
                expected_value=decision.expected_value,
                decision_type_value=decision.decision_type.value,
            )
        else:
            conf = decision.confidence
            if self.memory is not None:
                conf = self.memory.confidence_boost(conf, decision.game_id, stype)
            plan = GrowthStrategyPlan(
                game_id=decision.game_id,
                decision_id=decision.audit_id,
                objective=template.objective,
                strategy_type=stype,
                tasks=build_tasks(template),
                success_metrics=dict(template.success_metrics),
                rollback_plan=template.rollback_plan,
                estimated_duration_days=template.estimated_duration_days,
                confidence=round(conf, 4),
                expected_value=decision.expected_value,
                decision_type_value=decision.decision_type.value,
            )

        result = self.validator.validate(plan, decision_risk=decision.risk)
        plan.quality_gate_passed = result.ok
        plan.gate_reasons = result.reasons
        plan.needs_approval = result.needs_approval

        if strict and not result.ok:
            raise StrategyQualityError(
                "; ".join(result.reasons) or "strategy quality gate failed"
            )
        return plan
