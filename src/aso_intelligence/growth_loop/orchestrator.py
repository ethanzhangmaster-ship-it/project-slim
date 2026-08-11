"""
E16.6.5 — ASO Growth Orchestrator.

The master loop that runs the complete ASO growth cycle:

  DISCOVER → ANALYZE → PLAN → APPROVAL → EXPERIMENT → MEASURE → LEARN

This is the final integration of E16.6.1–5: it receives signals from all
sub-modules, runs them through the priority/planning/policy pipeline,
creates experiments, collects results, evaluates revenue feedback, and
persists learned patterns.

Callers (e.g. a daily automation) call ``run_cycle()`` per game, receiving
a rich ``ASOGrowthReport``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.growth_loop.models import (
    ASOGrowthCycle,
    ASOGrowthReport,
    ASOGrowthStage,
    ASOOpportunity,
    ASOActionPlan,
)
from src.aso_intelligence.growth_loop.opportunity import ASOOpportunityAggregator
from src.aso_intelligence.growth_loop.scheduler import ASOPriorityEngine
from src.aso_intelligence.growth_loop.policy import ASOPolicyGate
from src.aso_intelligence.growth_loop.experiment_manager import ASOExperimentManager
from src.aso_intelligence.growth_loop.feedback import ASOFeedbackLoop
from src.aso_intelligence.experiment_memory.experiment_store import ASOExperimentStore
from src.aso_intelligence.experiment_memory.retriever import ASOPatternRetriever

try:  # EP0.11.4 central audit (optional; no-op when not injected)
    from audit.integration import FlowAuditor
except ImportError:  # pragma: no cover - audit package not on path
    FlowAuditor = None  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOGrowthOrchestrator:
    """Run the autonomous ASO growth loop for one or more games.

    Typical usage (daily automation):

        orchestrator = ASOGrowthOrchestrator.build(store)
        for game_id in game_ids:
            report = orchestrator.run_cycle(
                game_id=game_id,
                platform="google_play",
                # Reality signals
                cvr_drop=0.15,
                install_drop=0.10,
                # Creative signals
                screenshot_hook=0.42,
                screenshot_clarity=0.55,
                icon_focus=0.35,
                # Completed experiments to learn from
                completed_results=[...],
            )
            print(report.to_markdown())
    """

    def __init__(
        self,
        aggregator: ASOOpportunityAggregator,
        engine: ASOPriorityEngine,
        policy: ASOPolicyGate,
        experiment_manager: ASOExperimentManager,
        feedback: ASOFeedbackLoop,
        retriever: Optional[ASOPatternRetriever] = None,
        store: Optional[ASOExperimentStore] = None,
        auditor: Optional["FlowAuditor"] = None,
    ):
        self.aggregator = aggregator
        self.engine = engine
        self.policy = policy
        self.experiment_manager = experiment_manager
        self.feedback = feedback
        self.retriever = retriever
        self.store = store
        # EP0.11.4: central audit trail (growth flow:
        # opportunity -> decision -> execution -> reward). No-op when None.
        self.auditor = auditor

    @classmethod
    def build(
        cls,
        store: ASOExperimentStore,
        top_k: int = 5,
        max_concurrent: int = 3,
        auditor: Optional["FlowAuditor"] = None,
    ) -> "ASOGrowthOrchestrator":
        """Factory: build a fully-wired orchestrator with default components."""
        return cls(
            aggregator=ASOOpportunityAggregator(),
            engine=ASOPriorityEngine(top_k=top_k),
            policy=ASOPolicyGate(max_concurrent=max_concurrent),
            experiment_manager=ASOExperimentManager(store),
            feedback=ASOFeedbackLoop(store),
            retriever=ASOPatternRetriever(store),
            store=store,
            auditor=auditor,
        )

    # ------------------------------------------------------------------ #
    def run_cycle(
        self,
        game_id: str,
        platform: str = "google_play",
        *,
        # Reality signals (from ASO Reality Layer / E16.6.2)
        cvr_drop: Optional[float] = None,
        install_drop: Optional[float] = None,
        ranking_drop: Optional[float] = None,
        # Creative signals (from E16.6.3)
        screenshot_hook: Optional[float] = None,
        screenshot_clarity: Optional[float] = None,
        icon_focus: Optional[float] = None,
        creative_confidence: float = 0.8,
        # Historical patterns (from E16.6.4, optional)
        historical_patterns: Optional[List[Any]] = None,
        # Completed experiment results to learn from (optional)
        completed_results: Optional[List[Any]] = None,
    ) -> ASOGrowthReport:
        """Run one complete growth cycle for a game.

        Returns a rich ``ASOGrowthReport`` with all opportunities found,
        plans created, experiments launched, patterns learned, and
        revenue feedback applied.
        """
        cycle = ASOGrowthCycle(
            cycle_id=str(uuid4()),
            game_id=game_id,
            platform=platform,
        )

        # -------------------------------------------------------------- #
        # DISCOVER — aggregate signals into opportunities
        # -------------------------------------------------------------- #
        cycle.advance(ASOGrowthStage.DISCOVER)
        opportunities = self.aggregator.aggregate(
            game_id=game_id,
            cvr_drop=cvr_drop,
            install_drop=install_drop,
            ranking_drop=ranking_drop,
            screenshot_hook=screenshot_hook,
            screenshot_clarity=screenshot_clarity,
            icon_focus=icon_focus,
            creative_confidence=creative_confidence,
            historical_patterns=historical_patterns,
        )

        # -------------------------------------------------------------- #
        # ANALYZE — evaluate + rank opportunities
        # -------------------------------------------------------------- #
        cycle.advance(ASOGrowthStage.ANALYZE)
        ranked = self.engine.rank(opportunities)

        # EP0.11.4 audit: opportunity records (growth flow step 1)
        opp_decision_ids: Dict[str, str] = {}
        if self.auditor is not None:
            for opp in ranked:
                opp_decision_ids[opp.opportunity_id] = (
                    self.auditor.growth_opportunity(
                        game_id=game_id,
                        opportunity_type=opp.title,
                        priority=opp.priority_score,
                        evidence={"source_signals": opp.source_signals,
                                  "suggested_action": opp.suggested_action},
                    )
                )

        # -------------------------------------------------------------- #
        # PLAN — convert top opportunities into action plans
        # -------------------------------------------------------------- #
        cycle.advance(ASOGrowthStage.PLAN)
        plans = self.engine.plan(ranked)
        for plan in plans:
            cycle.add_action(plan.action)

        # -------------------------------------------------------------- #
        # APPROVAL — apply policy gates
        # -------------------------------------------------------------- #
        cycle.advance(ASOGrowthStage.APPROVAL)
        active_counts = self.experiment_manager.active_experiment_counts(
            game_ids=[game_id]
        )
        gated_plans = self.policy.apply_all(plans, active_counts)

        # EP0.11.4 audit: policy gate outcomes (growth flow step 2)
        if self.auditor is not None:
            for plan in gated_plans:
                did = opp_decision_ids.get(plan.opportunity_id)
                if did is None:
                    continue
                status = getattr(plan.approval_status, "value",
                                 str(plan.approval_status))
                self.auditor.growth_plan_gated(
                    decision_id=did,
                    game_id=game_id,
                    plan_title=plan.title,
                    approval_route=status,
                    auto_approved=(status == "auto_approved"),
                )

        # -------------------------------------------------------------- #
        # EXPERIMENT — create experiments from auto-approved plans
        # -------------------------------------------------------------- #
        cycle.advance(ASOGrowthStage.EXPERIMENT)
        experiments_created = 0
        for plan in gated_plans:
            exp = self.experiment_manager.create_experiment(
                plan,
                category=game_id.split("_")[0] if "_" in game_id else "unknown",
                condition=plan.title.lower(),
            )
            if exp is not None:
                experiments_created += 1
            # EP0.11.4 audit: execution record (growth flow step 3)
            if self.auditor is not None:
                did = opp_decision_ids.get(plan.opportunity_id)
                if did is not None:
                    self.auditor.growth_experiment(
                        decision_id=did, game_id=game_id,
                        plan_title=plan.title, created=exp is not None)

        # -------------------------------------------------------------- #
        # MEASURE — collect results from completed experiments
        # -------------------------------------------------------------- #
        cycle.advance(ASOGrowthStage.MEASURE)
        feedbacks: List[Any] = []
        if completed_results:
            for result in completed_results:
                feedback_result = self.feedback.evaluate(result)
                feedbacks.append(feedback_result)
                # EP0.11.4 audit: reward record (growth flow step 4)
                if self.auditor is not None:
                    self.auditor.growth_reward(
                        game_id=game_id,
                        experiment_id=getattr(result, "experiment_id",
                                              "unknown"),
                        reward=float(getattr(feedback_result, "reward", 0.0)
                                     or 0.0),
                    )

        # -------------------------------------------------------------- #
        # LEARN — apply revenue feedback, mine patterns, update memory
        # -------------------------------------------------------------- #
        cycle.advance(ASOGrowthStage.LEARN)
        patterns_updated = 0
        revenue_feedback_applied = bool(feedbacks)

        if completed_results:
            patterns_updated = self.feedback.adjust_pattern_rewards(
                completed_results
            )

        # -------------------------------------------------------------- #
        # Report
        # -------------------------------------------------------------- #
        report = ASOGrowthReport(
            report_id=str(uuid4()),
            game_id=game_id,
            date=_today_iso(),
            cycle=cycle,
            opportunities=ranked,
            plans=gated_plans,
            experiments_created=experiments_created,
            patterns_updated=patterns_updated,
            revenue_feedback_applied=revenue_feedback_applied,
        )
        return report


__all__ = ["ASOGrowthOrchestrator"]
