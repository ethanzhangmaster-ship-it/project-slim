"""
E13.4.4 — Module 2: Planner
============================

Answers: "given this opportunity, what should the agent do next?"

It consumes the upstream analysis (E13.3.2 candidate + E13.2.9 simulation in
`ranked_strategy`, and the E13.4.3 fused ranking in `intelligence_result`),
looks up the learned prior for the chosen strategy (E13.4.1), asks the Policy
for an intended action, then lets the Guardrails enforce hard limits. The
result is a single, auditable Plan.

The Planner never executes anything — it only *recommends*. The Controller
carries the recommended Plan out.
"""
from __future__ import annotations

from typing import Optional

from monetization.agent.guardrails import Guardrails, bid_change_pct
from monetization.agent.models import Plan
from monetization.agent.policy import Policy
from monetization.intelligence.strategy_prior import StrategyPriorEngine


def _match_scored(ranked_strategy, strategy_type: str):
    """Find the scored candidate whose strategy_type matches, else top."""
    if ranked_strategy is None or ranked_strategy.top is None:
        return None
    for sc in ranked_strategy.strategies:
        if sc.candidate.strategy_type == strategy_type:
            return sc
    return ranked_strategy.top


class Planner:
    def __init__(self, policy: Optional[Policy] = None,
                 prior_engine: Optional[StrategyPriorEngine] = None,
                 guardrails: Optional[Guardrails] = None):
        self.policy = policy or Policy()
        self.prior = prior_engine or StrategyPriorEngine()
        self.guardrails = guardrails or Guardrails()

    def plan(self, opportunity, ranked_strategy, intelligence_result,
             day: int = 0, local_samples_map=None, seg_key: str = "") -> Plan:
        chosen = (intelligence_result.top if intelligence_result
                  else (ranked_strategy.top.candidate.strategy_type if ranked_strategy.top else None))
        if chosen is None:
            return Plan(opportunity.id, "observe", "no_action", 0.0,
                        "No candidate produced by the strategy engine.")
        # chosen may be a StrategyProbability dict (intelligence) or a string
        if isinstance(chosen, dict):
            st = chosen.get("strategy_type", "")
            priority = float(chosen.get("probability", chosen.get("final_score", 0.0)))
        else:
            st = str(chosen)
            priority = 0.0

        prior = self.prior.prior(st)
        sc = _match_scored(ranked_strategy, st)
        mutation = sc.candidate.mutation if sc else {}
        pred_wrap = (sc.prediction if sc else {}) or {}
        pred_inner = pred_wrap.get("prediction", {}) if isinstance(pred_wrap, dict) else {}
        target = pred_wrap.get("target", "") if isinstance(pred_wrap, dict) else ""

        sim_conf = float(pred_inner.get("confidence", 0.0))
        risk = pred_inner.get("retention_risk", "low")
        rev_delta = float(pred_inner.get("revenue_delta_pct", 0.0))
        ret_delta = float(pred_inner.get("retention_delta_pct", 0.0))
        severity = float(getattr(opportunity, "severity", 0.5))
        # a reality-detected retention crash overrides the simulated risk
        if getattr(opportunity, "forced_risk", "") == "high":
            risk = "high"

        # The agent's decision confidence blends the simulator's own confidence
        # with the learned historical prior (this is exactly what E13.4.3 fused).
        agent_conf = round(0.5 * sim_conf + 0.5 * prior["mean"], 3)

        local_n = 0
        if local_samples_map is not None and seg_key:
            local_n = len(local_samples_map.get((st, seg_key), []))

        intended = self.policy.decide(
            opportunity=opportunity, strategy_type=st, prior=prior,
            confidence=agent_conf, risk=risk,
            simulation_revenue_delta=rev_delta, retention_delta=ret_delta,
            severity=severity, guardrails=self.guardrails,
            local_samples=local_n)

        bid_change = bid_change_pct(mutation)
        action, downgrade = self.guardrails.enforce(
            intended, risk=risk, retention_delta=ret_delta,
            bid_change=bid_change, day=day)

        rationale = (f"chosen={st} | prior_mean={prior['mean']:.2f} "
                     f"(n={prior['samples']}) | sim_rev={rev_delta:+.1f}% "
                     f"sim_ret={ret_delta:+.2f}% risk={risk} sev={severity:.2f} "
                     f"conf={agent_conf:.2f} -> intended={intended} "
                     f"enforced={action}" + (f" ({downgrade})" if downgrade else ""))

        return Plan(
            opportunity_id=opportunity.id,
            recommended_action=action,
            strategy_type=st,
            priority=round(priority, 4),
            rationale=rationale,
            downgraded_by_guardrail=downgrade,
            policy_inputs={
                "intended": intended,
                "prior_mean": prior["mean"],
                "prior_samples": prior["samples"],
                "confidence": agent_conf,
                "risk": risk,
                "simulation_revenue_delta": rev_delta,
                "retention_delta": ret_delta,
                "severity": severity,
                "mutation": mutation,
                "target": target,
                "prediction_inner": pred_inner,
            },
        )
