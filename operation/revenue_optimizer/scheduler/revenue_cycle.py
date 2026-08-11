"""
E15.2.6 §11 — Daily Autonomous Revenue Cycle.

Orchestrates the full autopilot loop on top of the proven engine:

    Reality Data -> Opportunity Detection -> Prediction ->
    Experiment Planning -> Change Package -> Safety Gate ->
    (operator applies in MAX) -> Impact Measurement (next day) ->
    Memory Learning -> next optimization

It REUSES MonetizationIntelligenceAgent (MAX + Adjust ingestion, report
generation) and only adds the autopilot decision layers. The existing
09:30 automation (daily_briefing) is left untouched; this is the canonical
programmatic entry the automation can later call.

Output matches spec §12 (IAA Revenue Report): account, DAU, period revenue,
ARPDAU, AI actions with $/day impact, experiments running/winners.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.optimizer.intel_models import MonetizationDailyReport
from operation.revenue_optimizer.experiment.evaluator import ExperimentEvaluator
from operation.revenue_optimizer.experiment.planner import ExperimentPlanner
from operation.revenue_optimizer.executor.approval_gate import ApprovalGate
from operation.revenue_optimizer.executor.change_package import ChangePackageBuilder
from operation.revenue_optimizer.models import RevenueOpportunity
from operation.revenue_optimizer.opportunity.detector import OpportunityDetector
from operation.revenue_optimizer.opportunity.ranking import OpportunityRanker
from operation.revenue_optimizer.opportunity.scorer import OpportunityScorer
from operation.revenue_optimizer.prediction.revenue_predictor import RevenuePredictor


class RevenueCycle:
    def __init__(self, memory=None) -> None:
        self._det = OpportunityDetector()
        self._scorer = OpportunityScorer()
        self._ranker = OpportunityRanker()
        self._pred = RevenuePredictor()
        self._planner = ExperimentPlanner()
        self._pkg = ChangePackageBuilder()
        self._gate = ApprovalGate()
        self._eval = ExperimentEvaluator()
        self._memory = memory

    # ------------------------------------------------------------------ #
    def run(self, account: str, start: str, end: str,
            rows: Optional[List[Dict[str, Any]]] = None,
            dau: Optional[float] = None,
            notify: bool = False,
            agent=None) -> Dict[str, Any]:
        """Pull data (or use provided rows) and run the full autopilot pass."""
        if agent is None:
            from operation.optimizer.intelligence_agent import (
                MonetizationIntelligenceAgent)
            from operation.optimizer.daily_briefing import _fetch_user_metrics
            agent = MonetizationIntelligenceAgent()
        if rows is None:
            report = agent.run(account, start, end, notify=notify)
        else:
            um = _fetch_user_metrics(account, start, end) if dau is None \
                else None
            report = agent.run(account, start, end, rows=rows,
                               user_metrics=um, save=False)
        return self.process(report, dau, account)

    # ------------------------------------------------------------------ #
    def process(self, report: MonetizationDailyReport,
                dau: Optional[float],
                account: str) -> Dict[str, Any]:
        um = report.user_metrics or {}
        if dau is None:
            dau = um.get("dau")
        ctx = {
            "total_revenue": report.revenue,
            "blended_ecpm": report.blended_ecpm,
            "total_impressions": report.impressions,
            "dau": dau or 0.0,
        }

        opps = self._det.detect(report, dau)
        ranked = self._ranker.rank(opps)
        actions_out = []
        tiers = {"AUTO": 0, "APPROVAL": 0, "REJECT": 0}
        period_days = max(_span_days(report.period_start, report.period_end), 1)
        for opp, score in ranked:
            pred = self._pred.predict(opp, ctx, self._memory)
            gate = self._gate.check(opp, pred)
            tiers[gate["tier"]] = tiers.get(gate["tier"], 0) + 1
            impact_per_day = (report.revenue * (pred.lift_percent / 100.0)
                              / period_days) if pred.lift_percent else 0.0
            actions_out.append({
                "target": opp.target,
                "action": opp.action,
                "expected_lift_pct": round(pred.lift_percent, 2),
                "confidence": pred.confidence,
                "score": score,
                "tier": gate["tier"],
                "impact_per_day_usd": round(impact_per_day, 2),
                "change_package": self._pkg.build(
                    opp, opp.id).to_dict(),
                "reasons": gate["reasons"],
            })

        exps = self._planner.plan(report, dau)
        gr = report.growth_report or {}
        total_ai_per_day = sum(a["impact_per_day_usd"] for a in actions_out)

        return {
            "account": account,
            "dau": dau,
            "period_revenue": round(report.revenue, 2),
            "arpdau": gr.get("arpdau"),
            "revenue_per_dau": gr.get("revenue_per_dau"),
            "opportunities": len(opps),
            "ai_actions": actions_out,
            "total_ai_estimated_per_day_usd": round(total_ai_per_day, 2),
            "experiments_planned": len(exps),
            "safety_tiers": tiers,
            "growth_report": gr,
        }


def _span_days(start: str, end: str) -> int:
    try:
        from datetime import date
        a = date.fromisoformat(start)
        b = date.fromisoformat(end)
        return max((b - a).days, 1)
    except Exception:
        return 10
