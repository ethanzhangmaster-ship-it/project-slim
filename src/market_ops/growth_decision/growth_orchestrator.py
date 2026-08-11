"""E9.9.5 Module 5: Growth Orchestrator.

Orchestrates the full Growth Control Plane pipeline:

  Experiment Results
          |
          v
  Winner Detector
          |
          v
  Risk Controller
          |
          v
  Decision Router
          |
   ┌──────┼────────┬─────────┐
   v      v        v         v
  Scale  Kill    Watch    Retest
          |
          v
  Portfolio Manager
          |
          v
  Growth Report
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from market_ops.growth_decision.schemas import (
    GrowthDecision, CreativePortfolio, ScalePlan, RiskReport, GrowthReport,
    GrowthAction, WinnerLevel, PortfolioBucket, LifecycleStage, RiskLevel,
)
from market_ops.growth_decision.winner_detector import WinnerDetector
from market_ops.growth_decision.kill_engine import KillEngine
from market_ops.growth_decision.scale_engine import ScaleEngine
from market_ops.growth_decision.risk_controller import RiskController
from market_ops.growth_decision.portfolio_manager import PortfolioManager


class GrowthOrchestrator:
    """Master orchestrator for the Growth Control Plane.

    Wires WinnerDetector → RiskController → Decision Router
    → ScaleEngine / KillEngine → PortfolioManager → GrowthReport.

    Usage:
        orchestrator = GrowthOrchestrator()
        report = orchestrator.run(experiment_results, total_budget=10000)
    """

    def __init__(
        self,
        winner_detector: WinnerDetector | None = None,
        kill_engine: KillEngine | None = None,
        scale_engine: ScaleEngine | None = None,
        risk_controller: RiskController | None = None,
        portfolio_manager: PortfolioManager | None = None,
    ) -> None:
        self.winner_detector = winner_detector or WinnerDetector()
        self.kill_engine = kill_engine or KillEngine()
        self.scale_engine = scale_engine or ScaleEngine()
        self.risk_controller = risk_controller or RiskController()
        self.portfolio_manager = portfolio_manager or PortfolioManager()

    # ═══════════════════════════════════════════════════════
    # Main Pipeline
    # ═══════════════════════════════════════════════════════

    def run(
        self,
        experiment_results: list[dict[str, Any]],
        total_budget: float = 10000.0,
    ) -> dict[str, Any]:
        """Execute the full Growth Control Plane pipeline.

        Args:
            experiment_results: List of experiment result dicts, each with:
                {experiment_id, creative_id, decision, lift, confidence, ...}
            total_budget: Total budget across all creatives

        Returns:
            {
                "report": GrowthReport,
                "decisions": list[GrowthDecision],
                "portfolios": list[CreativePortfolio],
                "scale_plans": list[ScalePlan],
                "risk_reports": list[RiskReport],
            }
        """
        correlation_id = str(uuid.uuid4())

        # ── Step 1: Winner Detection ───────────────────────
        decisions = self._step_detect_winners(experiment_results)

        # ── Step 2: Risk Evaluation ────────────────────────
        risk_reports = self._step_evaluate_risk(decisions, total_budget)

        # ── Step 3: Decision Routing ───────────────────────
        scale_plans, kill_actions = self._step_route_decisions(
            decisions, risk_reports
        )

        # ── Step 4: Portfolio Management ───────────────────
        portfolios = self._step_manage_portfolio(decisions, total_budget)

        # ── Step 5: Build Report ───────────────────────────
        report = self._build_report(
            correlation_id, decisions, portfolios, scale_plans, risk_reports
        )

        return {
            "report": report,
            "decisions": decisions,
            "portfolios": portfolios,
            "scale_plans": scale_plans,
            "risk_reports": risk_reports,
        }

    # ═══════════════════════════════════════════════════════
    # Pipeline Steps
    # ═══════════════════════════════════════════════════════

    def _step_detect_winners(
        self, experiment_results: list[dict[str, Any]]
    ) -> list[GrowthDecision]:
        """Step 1: Classify experiment results into WINNER/PROMISING/FAILED/INCONCLUSIVE."""
        if not experiment_results:
            return []

        # Build GrowthDecision list from experiment results
        decisions = []
        for exp in experiment_results:
            winner_level = exp.get("decision", WinnerLevel.INCONCLUSIVE.value)
            action = self._winner_to_action(winner_level)

            decisions.append(GrowthDecision(
                decision_id=f"GD_{exp.get('experiment_id', '')}",
                experiment_id=exp.get("experiment_id", ""),
                creative_id=exp.get("creative_id", ""),
                decision=action,
                winner_level=winner_level,
                reason=exp.get("reason", f"Level={winner_level}"),
                confidence=exp.get("confidence", 0.0),
                budget_before=exp.get("budget_before", 100.0),
                budget_after=0.0,
                created_at=datetime.now(timezone.utc).isoformat(),
            ))
        return decisions

    def _winner_to_action(self, winner_level: str) -> str:
        """Map winner level to growth action."""
        mapping = {
            WinnerLevel.WINNER.value: GrowthAction.SCALE.value,
            WinnerLevel.PROMISING.value: GrowthAction.WATCH.value,
            WinnerLevel.FAILED.value: GrowthAction.KILL.value,
            WinnerLevel.INCONCLUSIVE.value: GrowthAction.RETEST.value,
        }
        return mapping.get(winner_level, GrowthAction.WATCH.value)

    def _step_evaluate_risk(
        self,
        decisions: list[GrowthDecision],
        total_budget: float,
    ) -> list[RiskReport]:
        """Step 2: Evaluate risk for all SCALE decisions."""
        risk_reports = []
        scale_decisions = [d for d in decisions if d.decision == GrowthAction.SCALE.value]

        if not scale_decisions:
            return risk_reports

        # Build portfolio snapshot for HHI calculation
        all_portfolios = self._decisions_to_portfolios_snapshot(decisions)

        for d in scale_decisions:
            # Create a scale plan for risk evaluation
            scale_plan = self.scale_engine.generate_from_winner(
                GrowthDecision(
                    decision_id=d.decision_id,
                    creative_id=d.creative_id,
                    decision=GrowthAction.SCALE.value,
                    winner_level=WinnerLevel.WINNER.value,
                    confidence=d.confidence,
                    budget_before=d.budget_before,
                ),
                current_budget=d.budget_before,
            )

            portfolio = next(
                (p for p in all_portfolios if p.creative_id == d.creative_id),
                CreativePortfolio(creative_id=d.creative_id),
            )

            report = self.risk_controller.evaluate_single(
                scale_plan=scale_plan,
                portfolio=portfolio,
                total_budget=total_budget,
                all_portfolios=all_portfolios,
            )
            risk_reports.append(report)

        return risk_reports

    def _decisions_to_portfolios_snapshot(
        self, decisions: list[GrowthDecision]
    ) -> list[CreativePortfolio]:
        """Convert decisions into a lightweight portfolio snapshot for risk calc."""
        # Archetypes for diversity: distribute across 4 types
        _archetypes = ["collector", "power", "explorer", "progression"]
        portfolios = []
        for i, d in enumerate(decisions):
            bucket = (
                PortfolioBucket.GROWTH.value
                if d.decision == GrowthAction.SCALE.value
                else PortfolioBucket.EXPLORATION.value
            )
            portfolios.append(CreativePortfolio(
                creative_id=d.creative_id,
                bucket=bucket,
                allocated_budget=d.budget_before,
                archetype=_archetypes[i % len(_archetypes)],
            ))
        return portfolios

    def _step_route_decisions(
        self,
        decisions: list[GrowthDecision],
        risk_reports: list[RiskReport],
    ) -> tuple[list[ScalePlan], list[GrowthDecision]]:
        """Step 3: Route decisions to Scale/Kill/Watch/Retest.

        If risk is blocking, SCALE is downgraded to WATCH.
        """
        # Build risk lookup
        blocking_ids: set[str] = set()
        for r in risk_reports:
            if r.blocking:
                blocking_ids.add(r.creative_id)

        scale_plans: list[ScalePlan] = []
        kill_actions: list[GrowthDecision] = []

        for d in decisions:
            action = d.decision

            # Risk blocking: downgrade SCALE → WATCH
            if action == GrowthAction.SCALE.value and d.creative_id in blocking_ids:
                d.decision = GrowthAction.WATCH.value
                action = GrowthAction.WATCH.value

            if action == GrowthAction.SCALE.value:
                plan = self.scale_engine.generate_from_winner(
                    d, current_budget=d.budget_before
                )
                scale_plans.append(plan)
                d.budget_after = plan.target_budget

            elif action == GrowthAction.KILL.value:
                kill_actions.append(d)

            elif action == GrowthAction.WATCH.value:
                d.budget_after = d.budget_before

            elif action == GrowthAction.RETEST.value:
                d.budget_after = d.budget_before * 0.5  # Retest at half budget

        return scale_plans, kill_actions

    def _step_manage_portfolio(
        self,
        decisions: list[GrowthDecision],
        total_budget: float,
    ) -> list[CreativePortfolio]:
        """Step 4: Create and allocate portfolio from decisions."""
        if not decisions:
            return []

        portfolios = self.portfolio_manager.create_portfolio(
            decisions, total_budget=total_budget
        )
        return portfolios

    # ═══════════════════════════════════════════════════════
    # Report Building
    # ═══════════════════════════════════════════════════════

    def _build_report(
        self,
        correlation_id: str,
        decisions: list[GrowthDecision],
        portfolios: list[CreativePortfolio],
        scale_plans: list[ScalePlan],
        risk_reports: list[RiskReport],
    ) -> GrowthReport:
        """Step 5: Build comprehensive GrowthReport."""
        # Counts by winner level
        winner_count = sum(1 for d in decisions if d.winner_level == WinnerLevel.WINNER.value)
        failed_count = sum(1 for d in decisions if d.winner_level == WinnerLevel.FAILED.value)
        promising_count = sum(1 for d in decisions if d.winner_level == WinnerLevel.PROMISING.value)
        inconclusive_count = sum(1 for d in decisions if d.winner_level == WinnerLevel.INCONCLUSIVE.value)

        # Counts by action
        scale_count = sum(1 for d in decisions if d.decision == GrowthAction.SCALE.value)
        kill_count = sum(1 for d in decisions if d.decision == GrowthAction.KILL.value)
        watch_count = sum(1 for d in decisions if d.decision == GrowthAction.WATCH.value)
        retest_count = sum(1 for d in decisions if d.decision == GrowthAction.RETEST.value)

        # Portfolio state
        portfolio_state = self.portfolio_manager.get_portfolio_summary(portfolios)

        # Risk status
        blocking = sum(1 for r in risk_reports if r.blocking)
        safe = sum(1 for r in risk_reports if not r.blocking)
        risk_status = {
            "total_reports": len(risk_reports),
            "blocking": blocking,
            "safe": safe,
            "any_blocking": blocking > 0,
        }

        return GrowthReport(
            report_id=correlation_id,
            total_experiments=len(decisions),
            winner_count=winner_count,
            failed_count=failed_count,
            promising_count=promising_count,
            inconclusive_count=inconclusive_count,
            scale_count=scale_count,
            kill_count=kill_count,
            watch_count=watch_count,
            retest_count=retest_count,
            portfolio_state=portfolio_state,
            risk_status=risk_status,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )