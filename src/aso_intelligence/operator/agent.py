"""
E16.6.13 — ASO Autonomous Operator.

The final execution layer of E16.6. Closes the entire ASO Agent loop:

  DETECT → ANALYZE → PLAN → APPROVE → EXECUTE → MONITOR → LEARN

This is the AI ASO Growth Operator — equivalent to a 24/7 ASO
operations department for a game company managing 10–50 games.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.aso_intelligence.operator.models import (
    ASOOperationPlan,
    ASOOperationState,
    ASOOperationExperience,
    ASOAutonomousReport,
    ApprovalLevel,
)
from src.aso_intelligence.operator.planner import OperatorPlanner
from src.aso_intelligence.operator.approval import ApprovalGateway
from src.aso_intelligence.operator.executor import ASOExecutor
from src.aso_intelligence.operator.monitor import OperatorMonitor
from src.aso_intelligence.operator.memory import OperatorMemory
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOAutonomousOperator:
    """AI ASO Growth Operator — runs the full ASO lifecycle autonomously.

    Typical usage:

        operator = ASOAutonomousOperator.build(store)
        report = operator.daily_run(
            game_ids=["merge_witch", "puzzle_island"],
            insights=[...detected ASO insights...],
        )
        print(report.to_markdown())
    """

    def __init__(
        self,
        planner: Optional[OperatorPlanner] = None,
        approval: Optional[ApprovalGateway] = None,
        executor: Optional[ASOExecutor] = None,
        monitor: Optional[OperatorMonitor] = None,
        memory: Optional[OperatorMemory] = None,
    ):
        self.planner = planner or OperatorPlanner()
        self.approval = approval or ApprovalGateway()
        self.executor = executor or ASOExecutor()
        self.monitor = monitor or OperatorMonitor()
        self.memory = memory or OperatorMemory()

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOAutonomousOperator":
        return cls(memory=OperatorMemory(store))

    # ------------------------------------------------------------------ #
    def daily_run(
        self,
        game_ids: List[str],
        insights: List[Dict[str, Any]],
        *,
        # Optional: results from completed human tasks
        completed_task_results: List[Dict[str, Any]] = None,
        # Optional: after-measurement data for monitoring
        after_metrics: List[Dict[str, Any]] = None,
    ) -> ASOAutonomousReport:
        """Run the daily ASO autonomous operation cycle.

        Input: list of game_ids + detected insights.
        Output: full ASOAutonomousReport with all operations.
        """
        plans: List[ASOOperationPlan] = []
        auto_count = 0
        pending_count = 0

        # Step 1-2: Plan all detected insights
        for insight in insights:
            game_id = insight.get("game_id", "")
            market = insight.get("market", "US")
            insight_type = insight.get("type", "screenshot_weak")
            reason = insight.get("reason", "Detected by ASO Intelligence")
            confidence = insight.get("confidence", 0.7)
            impact = insight.get("impact", 0.5)
            source = insight.get("source", "aso_intelligence")

            plan = self.planner.plan(
                game_id=game_id,
                market=market,
                insight_type=insight_type,
                reason=reason,
                expected_impact=impact,
                confidence=confidence,
                source_module=source,
            )
            plan.advance(ASOOperationState.ANALYZING)
            plans.append(plan)

        # Step 3: Approval
        for plan in plans:
            plan.advance(ASOOperationState.PLANNED)
            self.approval.apply(plan)

            if plan.approval_level == ApprovalLevel.AUTO:
                plan.advance(ASOOperationState.READY)
            else:
                plan.advance(ASOOperationState.WAITING_APPROVAL)

        # Step 4: Execute (auto only — human tasks wait)
        for plan in plans:
            if plan.approval_level == ApprovalLevel.AUTO:
                self.monitor.start_monitoring(
                    plan.plan_id, plan.game_id, plan.market,
                    plan.action_type,
                )
                self.executor.execute(plan)
                auto_count += 1
            else:
                self.executor.execute(plan)  # creates READY task
                pending_count += 1

        # Step 5: Process completed task results
        completed_today = 0
        if completed_task_results:
            for result in completed_task_results:
                task_id = result.get("task_id", "")
                ok = self.executor.complete_task(
                    task_id, result.get("outcome")
                )
                if ok:
                    completed_today += 1
                    # Start monitoring for this completed plan
                    plan_id = result.get("plan_id", "")
                    if plan_id:
                        self.monitor.start_monitoring(
                            plan_id, result.get("game_id", ""),
                            result.get("market", ""),
                            result.get("action_type", ""),
                            result.get("before_metrics"),
                        )

        # Step 6: Collect monitoring results
        patterns_learned = 0
        if after_metrics:
            for am in after_metrics:
                plan_id = am.get("plan_id", "")
                exp = self.monitor.collect_result(
                    plan_id, am.get("metrics", {})
                )
                if exp:
                    self.memory.record(exp)
                    patterns_learned += 1

        # Build report
        high_priority = [
            p for p in plans
            if p.risk_category.name in ("HIGH", "MEDIUM")
            and p.state != ASOOperationState.COMPLETED
        ]

        report = ASOAutonomousReport(
            date=_today_iso(),
            games_scanned=len(game_ids),
            opportunities_detected=len(insights),
            plans_created=len(plans),
            auto_executed=auto_count,
            pending_approval=pending_count,
            completed_today=completed_today,
            patterns_learned=patterns_learned,
            high_priority_plans=high_priority[:5],
            operations_summary=[p.to_dict() for p in plans],
        )
        return report

    # ------------------------------------------------------------------ #
    def daily_run_full(
        self,
        game_ids: List[str],
        insights: List[Dict[str, Any]],
        portfolio_priorities: Dict[str, int] = None,
        **kwargs,
    ) -> ASOAutonomousReport:
        """Full pipeline with portfolio integration.

        Filters insights to only process games in the portfolio's
        high-priority tier.
        """
        if portfolio_priorities:
            high_priority_games = {
                g for g, rank in portfolio_priorities.items()
                if rank <= 5
            }
            filtered = [
                i for i in insights
                if i.get("game_id") in high_priority_games
            ]
        else:
            filtered = insights

        return self.daily_run(game_ids, filtered, **kwargs)


__all__ = ["ASOAutonomousOperator"]
