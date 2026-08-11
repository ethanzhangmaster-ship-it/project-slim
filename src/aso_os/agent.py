"""
E16.6.14 — ASO Growth OS Agent.

The main entry point. Runs the daily ASO OS cycle:

  Kernel → Event Bus → Opportunity Engine → Priority Engine
  → Workflow → Execution → Knowledge → Dashboard Report
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.aso_os.kernel.models import (
    ASOEvent,
    ASOEventType,
    ASOGrowthScore,
    ASOOSDashboardReport,
)
from src.aso_os.kernel.state import ASOOSKernel, DailyScheduler
from src.aso_os.intelligence.opportunity_engine import (
    OpportunityEngine,
    PriorityEngine,
)
from src.aso_os.operation.workflow import WorkflowEngine, SystemExecutor
from src.aso_os.governance.policy import GovernancePolicy, SystemApproval
from src.aso_os.memory.knowledge_graph import KnowledgeGraph, PatternStore
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOOSAgent:
    """ASO Growth Operating System — unified entry point.

    Usage:
        os = ASOOSAgent.build(store)
        report = os.daily_run(
            events=[...all ASO events from all modules...],
            game_count=50,
        )
        print(report.to_markdown())
    """

    def __init__(
        self,
        kernel: Optional[ASOOSKernel] = None,
        scheduler: Optional[DailyScheduler] = None,
        opportunity: Optional[OpportunityEngine] = None,
        priority: Optional[PriorityEngine] = None,
        workflow: Optional[WorkflowEngine] = None,
        executor: Optional[SystemExecutor] = None,
        policy: Optional[GovernancePolicy] = None,
        approval: Optional[SystemApproval] = None,
        knowledge: Optional[KnowledgeGraph] = None,
        pattern_store: Optional[PatternStore] = None,
    ):
        self.kernel = kernel or ASOOSKernel()
        self.scheduler = scheduler or DailyScheduler()
        self.opportunity = opportunity or OpportunityEngine()
        self.priority = priority or PriorityEngine()
        self.workflow = workflow or WorkflowEngine()
        self.executor = executor or SystemExecutor()
        self.policy = policy or GovernancePolicy()
        self.approval = approval or SystemApproval()
        self.knowledge = knowledge or KnowledgeGraph()
        self.pattern_store = pattern_store or PatternStore()

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOOSAgent":
        return cls(pattern_store=PatternStore(store))

    # ------------------------------------------------------------------ #
    def daily_run(
        self,
        events: List[ASOEvent],
        game_count: int = 0,
        market_count: int = 0,
        portfolio_priorities: Dict[str, int] = None,
        revenue_feedback: Dict[str, float] = None,
    ) -> ASOOSDashboardReport:
        """Run the full ASO OS daily cycle.

        1. Update kernel state
        2. Process events → opportunities
        3. Rank by priority
        4. Check governance policies
        5. Execute auto-actions
        6. Learn from revenue feedback
        7. Generate dashboard
        """
        # Step 1: State
        self.kernel.update_state(
            game_count=game_count,
            market_count=market_count,
            last_daily_run=_today_iso(),
        )

        # Step 2: Events → Opportunities
        scores = self.opportunity.process_events(events)

        # Step 3: Priority ranking (with portfolio filtering)
        if portfolio_priorities:
            top_games = {
                g for g, r in portfolio_priorities.items()
                if r <= 5
            }
            scores = [s for s in scores if s.game_id in top_games]

        scores = self.priority.resolve_conflicts(scores)
        ranked = self.priority.rank(scores)
        top_opps = self.priority.top_k(ranked, 5)

        # Step 4-5: Workflow + Execute (auto only)
        executed_count = 0
        wf_summary: List[Dict[str, Any]] = []
        for score in top_opps:
            if self.approval.can_auto_execute(score):
                wf_id = f"wf_{score.opportunity_id}"
                self.workflow.create(wf_id)
                self.workflow.advance(wf_id)  # ANALYZED
                self.workflow.advance(wf_id)  # PLANNED
                self.workflow.advance(wf_id)  # GENERATED
                self.workflow.advance(wf_id)  # APPROVED
                task_id = self.executor.execute(
                    wf_id, score.source, score.game_id, score.market
                )
                self.workflow.advance(wf_id)  # RUNNING
                self.executor.complete(task_id, {"score": score.score})
                self.workflow.advance(wf_id)  # MEASURED
                self.workflow.advance(wf_id)  # LEARNED
                executed_count += 1
                wf_summary.append({
                    "workflow_id": wf_id,
                    "game_id": score.game_id,
                    "market": score.market,
                    "source": score.source,
                    "stage": "LEARNED",
                })

        # Step 6: Learn from revenue feedback
        patterns_learned = 0
        if revenue_feedback:
            for game_id, rev in revenue_feedback.items():
                if rev > 0:
                    self.pattern_store.record_pattern(
                        genre=game_id.split("_")[0] if "_" in game_id else "unknown",
                        market="US",
                        action="ASO_IMPROVEMENT",
                        cvr_uplift=0.1,
                        revenue_uplift=rev,
                    )
                    patterns_learned += 1

        # Expected revenue impact
        expected_impact = sum(s.revenue_impact for s in top_opps) / max(len(top_opps), 1)

        # Build report
        report = ASOOSDashboardReport(
            date=_today_iso(),
            games_scanned=game_count,
            signals_detected=len(events),
            opportunities_created=len(scores),
            actions_executed=executed_count,
            experiments_running=self.kernel.state.active_experiments,
            patterns_learned=patterns_learned,
            expected_revenue_impact=expected_impact,
            top_opportunities=top_opps[:3],
            state=self.kernel.get_state(),
            workflow_summary=wf_summary,
        )
        return report

    # ------------------------------------------------------------------ #
    def get_daily_schedule(self) -> Dict[str, str]:
        return self.scheduler.get_schedule()

    def health(self) -> str:
        return self.kernel.health_check()


__all__ = ["ASOOSAgent"]
