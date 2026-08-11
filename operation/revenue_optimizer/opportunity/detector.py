"""
E15.2.6 §4 — Opportunity Detection.

Wraps the proven 6 intel rules (operation.optimizer.analyzers) which already
live inside `MonetizationDailyReport.signals`. Each A/B-eligible signal is
turned into a `RevenueOpportunity`, reusing the EXACT conservative lift math
from ABExperimentGenerator so detection and experiment planning never diverge.
"""
from __future__ import annotations

from typing import List, Optional

from operation.optimizer.experiments.experiment_generator import (
    ABExperimentGenerator, AB_ELIGIBLE_ACTIONS,
)
from operation.optimizer.experiments.experiment_models import exp_id
from operation.optimizer.intel_models import (
    IntelSignal, MonetizationDailyReport,
)
from operation.revenue_optimizer.models import RevenueOpportunity


class OpportunityDetector:
    """Turn a daily report's intel signals into ranked revenue opportunities."""

    def __init__(self) -> None:
        self._gen = ABExperimentGenerator()

    def detect(self, report: MonetizationDailyReport,
               dau: Optional[float] = None) -> List[RevenueOpportunity]:
        out: List[RevenueOpportunity] = []
        for sig in report.signals:
            if sig.action not in AB_ELIGIBLE_ACTIONS:
                continue
            va = {
                "action": sig.action, "target": sig.target,
                "title": sig.target, "source_rule": sig.rule,
                "expected_impact": "", "rationale": sig.reason,
            }
            eid = exp_id(report.account, sig.action, sig.target)
            exp = self._gen._build(report, va, sig, dau, eid)
            if exp is not None:
                out.append(RevenueOpportunity.from_experiment(exp, sig))
        # stable order: by expected lift desc, then confidence
        out.sort(key=lambda o: (o.expected_lift, o.confidence), reverse=True)
        return out

    def detect_signals(self, account: str,
                       signals: List[IntelSignal],
                       *, revenue: float = 0.0, blended_ecpm: float = 0.0,
                       impressions: int = 0,
                       dau: Optional[float] = None) -> List[RevenueOpportunity]:
        """Lightweight entry for tests / direct-analyzer use without a full
        MonetizationDailyReport — synthesises a minimal report context."""
        fake = MonetizationDailyReport(
            account=account, date="", period_start="", period_end="",
            revenue=revenue, impressions=impressions, attempts=impressions,
            blended_ecpm=blended_ecpm, waterfall_depth=0.0,
            health_score=0, health_grade="",
            signals=signals, validated_actions=[])
        return self.detect(fake, dau)
