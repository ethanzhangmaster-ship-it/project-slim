"""E17.4 — 策略规划器主入口（Agent）。

输入：E17.3 的 GrowthDecision / DecisionReport
输出：GrowthStrategyPlan / PortfolioStrategyPlan（CEO 周作战计划）

并提供 run_pipeline() 串联 E17.1 → E17.2 → E17.3 → E17.4（供端到端测试与每日自动运行）。

SIM 纪律：本层纯确定性生成，不触发任何真实 API；future 接 E17.6 Execution Router 才落地执行。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.ceo_intelligence.decision_engine.agent import run_pipeline as _decision_pipeline
from src.ceo_intelligence.decision_engine.models import DecisionReport, GrowthDecision

from .memory import StrategyMemory
from .models import (
    GrowthStrategyPlan,
    PortfolioStrategyPlan,
    StrategyQualityError,
)
from .planner import GrowthStrategyPlanner


class GrowthStrategyPlannerAgent:
    """对外 API（与 spec 命名一致：GrowthStrategyPlanner 入口类）。"""

    def __init__(
        self,
        memory: Optional[StrategyMemory] = None,
        validator=None,
    ):
        self.memory = memory
        self.planner = GrowthStrategyPlanner(memory=memory, validator=validator)

    # ------------------------------------------------------------------ #
    def create_plan(
        self,
        decision: GrowthDecision,
        *,
        segment: str = "global",
        strict: bool = True,
    ) -> GrowthStrategyPlan:
        return self.planner.create_plan(decision, segment=segment, strict=strict)

    def create_portfolio_plan(
        self,
        report: DecisionReport,
        *,
        segment: str = "global",
        strict: bool = False,
    ) -> PortfolioStrategyPlan:
        """把一批决策转成 CEO 周作战计划。

        strict=False（默认）：单条被质量门禁拒绝不影响其余，进 rejected 列表。
        strict=True：任意一条拒绝则整体抛异常。
        """
        plans: List[GrowthStrategyPlan] = []
        rejected: List[Dict[str, Any]] = []
        total_expected = 0.0
        needs_approval = 0

        for d in report.decisions:
            try:
                plan = self.planner.create_plan(d, segment=segment, strict=strict)
            except StrategyQualityError as e:
                rejected.append(
                    {
                        "game_id": d.game_id,
                        "strategy_type": d.opportunity_id.rsplit(":", 1)[-1],
                        "reason": str(e),
                    }
                )
                continue
            if not plan.quality_gate_passed:
                rejected.append(
                    {
                        "game_id": d.game_id,
                        "strategy_type": plan.strategy_type,
                        "reason": "; ".join(plan.gate_reasons) or "quality gate failed",
                    }
                )
                continue
            plans.append(plan)
            if plan.needs_approval:
                needs_approval += 1
            if d.decision_type.value in ("execute", "approve"):
                total_expected += d.expected_value

        summary = {
            "planned": len(plans),
            "rejected": len(rejected),
            "needs_approval": needs_approval,
            "total_expected_uplift": round(total_expected, 4),
        }
        return PortfolioStrategyPlan(plans=plans, rejected=rejected, summary=summary)

    def to_markdown(self, portfolio: PortfolioStrategyPlan) -> str:
        return portfolio.to_markdown()


# --------------------------------------------------------------------------- #
# 端到端流水线：Reality Hub → Opportunity Engine → Decision Engine → Strategy Plan
# --------------------------------------------------------------------------- #
def run_pipeline(
    company,
    *,
    store=None,
    opportunity_memory=None,
    decision_memory=None,
    strategy_memory: Optional[StrategyMemory] = None,
    action_sink=None,
    segment: str = "global",
    top_n: int = 10,
    approval_queue_path: str = "data/ceo/approval_queue.jsonl",
    audit_dir: str = "data/ceo/audit",
    created_at: str = "",
) -> Tuple[DecisionReport, PortfolioStrategyPlan]:
    """串联 E17.1 → E17.2 → E17.3 → E17.4，产出决策报告 + 作战计划组合。"""
    opp_report, dec_report = _decision_pipeline(
        company,
        store=store,
        opportunity_memory=opportunity_memory,
        decision_memory=decision_memory,
        action_sink=action_sink,
        segment=segment,
        top_n=top_n,
        approval_queue_path=approval_queue_path,
        audit_dir=audit_dir,
        created_at=created_at,
    )
    agent = GrowthStrategyPlannerAgent(memory=strategy_memory)
    portfolio = agent.create_portfolio_plan(dec_report, segment=segment)
    return dec_report, portfolio
