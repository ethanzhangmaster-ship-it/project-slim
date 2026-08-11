"""
E15.3 — Autonomous Revenue Operator.

Thin orchestrator that transforms the existing analyze→recommend pipeline into
an autonomous analyze→deploy→rollout→measure loop. It reuses:

  RevenueCycle      — pull data + detect opportunities + predict + plan
  ExperimentBinder  — turn experiment into RemoteConfig control/variant pair
  ConfigDeployer    — write configs for SDK consumption
  GraduatedRollout  — phase-gated traffic expansion with auto-rollback
  OptimizationMemory— record winning outcomes

This is the last-mile piece: AI from analyst to operator.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.remote_config.deployer import ConfigDeployer
from operation.remote_config.experiment_binding import ExperimentBinder
from operation.remote_config.models import RemoteConfig
from operation.revenue_optimizer.experiment.graduated_rollout import (
    GraduatedRollout, RolloutState,
)
from operation.revenue_optimizer.models import RevenueOpportunity
from operation.revenue_optimizer.opportunity.ranking import OpportunityRanker
from operation.revenue_optimizer.prediction.revenue_predictor import RevenuePredictor
from operation.revenue_optimizer.scheduler.revenue_cycle import RevenueCycle


class AutonomousOperator:
    def __init__(self, memory=None) -> None:
        self._cycle = RevenueCycle(memory=memory)
        self._pred = RevenuePredictor()
        self._ranker = OpportunityRanker()
        self._binder = ExperimentBinder()
        self._deployer = ConfigDeployer()
        self._rollout = GraduatedRollout()
        self._memory = memory
        self._active_rollouts: Dict[str, RolloutState] = {}

    # ------------------------------------------------------------------ #
    def run(self, account: str, start: str, end: str,
            rows: Optional[List[Dict[str, Any]]] = None,
            dau: Optional[float] = None,
            game_id: Optional[str] = None,
            auto_deploy: bool = False,
            agent=None) -> Dict[str, Any]:
        """Full autonomous pass: RevenueCycle + auto-deploy safe experiments."""
        summary = self._cycle.run(account, start, end, rows=rows,
                                  dau=dau, notify=False, agent=agent)
        deployed = []
        if auto_deploy and game_id:
            base = RemoteConfig.default_for(game_id)
            for action in summary.get("ai_actions", []):
                if action.get("tier") != "AUTO":
                    continue
                opp = RevenueOpportunity(
                    id=action.get("experiment_id", ""),
                    app_id=account, dimension="network",
                    rule="", action=action["target"],
                    target=action.get("target", ""),
                    expected_lift=(action.get("expected_lift_pct", 0) / 100.0),
                    confidence=action.get("confidence", 0.0),
                )
                pair = self._binder.bind(
                    base, opp.action, opp.target, opp.id)
                if pair:
                    res = self._deployer.deploy(
                        pair[0], pair[1], game_id, opp.id)
                    deployed.append(res)
                    # start graduated rollout
                    rs = self._rollout.init(opp.id)
                    self._active_rollouts[opp.id] = rs
        summary["deployed_experiments"] = len(deployed)
        summary["deployed"] = deployed
        summary["active_rollouts"] = len(self._active_rollouts)
        return summary

    # ------------------------------------------------------------------ #
    def evaluate_rollouts(self,
                          metrics: Dict[str, Dict[str, float]]
                          ) -> Dict[str, Any]:
        """Call after next day's data: evaluate all active rollouts.
        metrics = {experiment_id: {"arpdau_delta_pct": ..., ref...}}"""
        results = {}
        for exp_id, state in list(self._active_rollouts.items()):
            m = metrics.get(exp_id, {})
            updated = self._rollout.evaluate(state, m)
            results[exp_id] = updated.to_dict()
            if updated.verdict in ("complete", "rollback"):
                self._active_rollouts.pop(exp_id, None)
                if self._memory and updated.verdict == "complete":
                    self._memory.record(
                        account="", action="autonomous",
                        target=exp_id, net_impact_pct=(m.get("arpdau_delta_pct")),
                        guardrail="pass", decision="WINNER",
                        confidence=0.9, applied_at=updated.started_at)
        return {"evaluated": len(metrics), "results": results}
