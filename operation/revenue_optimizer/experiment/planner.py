"""
E15.2.6 §6 — Experiment Planner.

Every monetization opportunity becomes a formal A/B experiment (A=current,
B=variant) measured on the single North Star KPI: IAA Revenue / DAU. Reuses the
proven ABExperimentGenerator so the plan and the daily report never diverge.
"""
from __future__ import annotations

from typing import List, Optional

from operation.optimizer.experiments.experiment_generator import (
    ABExperimentGenerator,
)
from operation.optimizer.experiments.experiment_models import (
    AB_ELIGIBLE_ACTIONS, ExperimentDefinition, exp_id,
)
from operation.optimizer.intel_models import IntelSignal, MonetizationDailyReport
from operation.revenue_optimizer.models import (
    OptimizationExperiment, RevenueOpportunity,
)


class ExperimentPlanner:
    def __init__(self) -> None:
        self._gen = ABExperimentGenerator()

    def plan(self, report: MonetizationDailyReport,
             dau: Optional[float] = None) -> List[OptimizationExperiment]:
        # OptimizationExperiment is an alias of ExperimentDefinition.
        # If the report has no pre-built validated_actions (e.g. a freshly
        # detected signal set), synthesise them from the signals so planning
        # works straight off the detector output.
        saved = report.validated_actions
        if not saved:
            report.validated_actions = [{
                "action": s.action, "target": s.target, "title": s.target,
                "source_rule": s.rule, "expected_impact": "",
                "rationale": s.reason,
            } for s in report.signals
                if s.action in AB_ELIGIBLE_ACTIONS]
        try:
            return self._gen.generate(report, dau)
        finally:
            report.validated_actions = saved

    def plan_one(self, opp: RevenueOpportunity,
                 report: MonetizationDailyReport,
                 dau: Optional[float] = None) -> Optional[OptimizationExperiment]:
        eid = exp_id(report.account, opp.action, opp.target)
        for exp in self.plan(report, dau):
            if exp.exp_id == eid:
                return exp
        return None
