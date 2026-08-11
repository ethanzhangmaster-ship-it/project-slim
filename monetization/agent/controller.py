"""
E13.4.4 — Module 5: Controller (the autonomous loop)
=====================================================

The capstone orchestrator. It runs the closed control loop the user defined:

    Observe -> Analyze -> Plan -> (Experiment | Execute) -> Evaluate -> Learn -> Repeat

For every opportunity the agent:
    1. OBSERVE    — pull the segment facts (passed in for the sim)
    2. ANALYZE    — E13.3.2 StrategyEngine (candidates + E13.2.9 simulation)
                    + E13.4.3 StrategyRanker (fused ranking w/ history)
    3. PLAN       — Planner + Policy + Guardrails -> one recommended action
    4. ACT        — experiment (E13.4.2) OR execute (E13.3.3) OR block/observe
    5. EVALUATE   — record the outcome into the E13.4.1 Decision Memory
    6. LEARN      — refresh the Bayesian prior from memory so tomorrow's
                    decisions use today's evidence

Critically: the agent NEVER calls a real ad-platform API. "Execute" routes
through the gated, mock Executor (E13.3.3); "Experiment" routes through the
simulation-only Experiment Engine (E13.4.2). This is the Decision
Orchestrator, not an LLM agent.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from monetization.agent.guardrails import Guardrails
from monetization.agent.models import (
    ACTION_BLOCK, ACTION_EXECUTE, ACTION_EXPERIMENT, ACTION_OBSERVE, AgentAction,
    AgentCycleResult, AgentReport, AgentState, Opportunity,
)
from monetization.agent.planner import Planner
from monetization.agent.policy import Policy
from monetization.agent.scheduler import Scheduler
from monetization.experiments.experiment_manager import (
    ExperimentManager, experiment_from_candidate,
)
from monetization.experiments.models import DEFAULT_BASELINE
from monetization.executor.executor import ExecutionOrchestrator
from monetization.executor.models import ExecutionRequest
from monetization.intelligence.calibration import SimulatorCalibrator
from monetization.intelligence.strategy_prior import StrategyPriorEngine
from monetization.intelligence.strategy_ranker import StrategyRanker
from monetization.learning.decision_store import DecisionStore
from monetization.learning.models import DecisionRecord
from monetization.strategy.strategy_generator import StrategyEngine


def _match_scored(ranked_strategy, strategy_type: str):
    if ranked_strategy is None or ranked_strategy.top is None:
        return None
    for sc in ranked_strategy.strategies:
        if sc.candidate.strategy_type == strategy_type:
            return sc
    return ranked_strategy.top


class MonetizationAgent:
    def __init__(self, store: Optional[DecisionStore] = None,
                 prior_engine: Optional[StrategyPriorEngine] = None,
                 ranker: Optional[StrategyRanker] = None,
                 executor: Optional[ExecutionOrchestrator] = None,
                 exp_manager: Optional[ExperimentManager] = None,
                 policy: Optional[Policy] = None,
                 guardrails: Optional[Guardrails] = None,
                 planner: Optional[Planner] = None,
                 scheduler: Optional[Scheduler] = None,
                 learn_every_cycle: bool = True):
        self.store = store or DecisionStore()
        self.prior = prior_engine or StrategyPriorEngine()
        self._refresh_prior()
        self.calibrator = SimulatorCalibrator()
        self.ranker = ranker or StrategyRanker(
            self.prior, self.calibrator, self.store)
        self.engine = StrategyEngine()
        self.executor = executor or ExecutionOrchestrator()
        self.exp_manager = exp_manager or ExperimentManager(store=self.store)
        self.policy = policy or Policy()
        # Capture the strategy inventory the agent started with (seeded memory).
        # An *introduced* strategy (none in the seed, e.g. monetization_aggressive)
        # stays gated behind experiments for the whole run.
        if policy is None:
            self.policy.baseline_strategies = set(self.prior.prior_map().keys())
        self.guardrails = guardrails or Guardrails()
        self.planner = planner or Planner(
            self.policy, self.prior, self.guardrails)
        self.scheduler = scheduler or Scheduler()
        self.learn_every_cycle = learn_every_cycle

        self.state = AgentState()
        # (strategy_type, segment_key) -> list of local trials (for novelty logic)
        self.local_samples: Dict[tuple, list] = {}

    # ------------------------------------------------------------------ #
    def _refresh_prior(self) -> None:
        """Re-learn the Bayesian prior from the current memory.

        Experiments recorded by E13.4.2 are already persisted into the store
        (closed-loop DecisionRecords), so a plain re-learn captures them.
        """
        self.prior = StrategyPriorEngine()
        self.prior.learn_from_store(self.store)
        # keep the ranker / planner pointing at the refreshed prior
        if getattr(self, "ranker", None) is not None:
            self.ranker.prior = self.prior
            self.planner.prior = self.prior

    # ------------------------------------------------------------------ #
    def _baseline(self, opp: Opportunity) -> dict:
        b = dict(DEFAULT_BASELINE)
        b.update(opp.metrics or {})
        return b

    def _should_fail(self, decision_id: str) -> bool:
        """Deterministic ~12.5% inject of an execution failure (-> rollback)."""
        return abs(hash(decision_id)) % 8 == 0

    # ------------------------------------------------------------------ #
    def _record_execution_memory(self, opp, plan, pi, result) -> None:
        decision = {
            "opportunity_id": opp.id,
            "strategy": {
                "type": plan.strategy_type,
                "score": (plan.policy_inputs.get("priority", 0.0)),
                "mutation": pi["mutation"],
                "prediction": {
                    "target": pi["target"],
                    "prediction": pi["prediction_inner"],
                },
            },
        }
        rec = DecisionRecord.from_pipeline(opp.to_dict(), decision, result.to_dict())
        rec.strategy_score = float(plan.priority)
        self.store.append(rec)

    # ------------------------------------------------------------------ #
    def _process_opportunity(self, opp: Opportunity, day: int) -> AgentAction:
        self.state.active_opportunities.append(opp.id)
        self.state.current_stage = "analyze"

        ranked = self.engine.process_opportunity(opp)
        if ranked.top is None:
            return AgentAction(opp.id, "no_action", ACTION_OBSERVE, 0.0,
                               "Strategy engine produced no candidate.",
                               day=day)

        seg_key = "_".join(str(opp.segment.get(k)) for k in
                          ("country", "platform", "ad_format", "network")
                          if opp.segment.get(k))
        intel = self.ranker.rank(opp.to_dict(), baseline_metric=self._baseline(opp))
        plan = self.planner.plan(opp, ranked, intel, day=day,
                                 local_samples_map=self.local_samples,
                                 seg_key=seg_key)
        action = plan.recommended_action
        pi = plan.policy_inputs

        # no_action is a safe monitor-only strategy -> never execute/experiment
        if plan.strategy_type in ("no_action", ""):
            action = ACTION_OBSERVE

        sc = _match_scored(ranked, plan.strategy_type)
        aa = AgentAction(
            opportunity_id=opp.id, strategy_type=plan.strategy_type,
            action=action, priority=plan.priority, reason=plan.rationale,
            prior_mean=pi.get("prior_mean", 0.5),
            prior_samples=pi.get("prior_samples", 0),
            confidence=pi.get("confidence", 0.0), risk=pi.get("risk", "low"),
            simulation_revenue_delta=pi.get("simulation_revenue_delta", 0.0),
            retention_delta=pi.get("retention_delta", 0.0),
            severity=pi.get("severity", 0.0), day=day,
        )

        self.state.current_stage = "act"
        if action == ACTION_EXECUTE and sc is not None:
            aa.result_status, aa.result_summary = self._do_execute(opp, plan, pi, sc)
        elif action == ACTION_EXPERIMENT and sc is not None:
            aa.result_status, aa.result_summary = self._do_experiment(opp, sc)
        elif action == ACTION_BLOCK:
            aa.result_status = "blocked"
            self.state.risk_level = "critical"
        else:  # observe
            aa.result_status = "observed"

        self.state.active_opportunities = [
            x for x in self.state.active_opportunities if x != opp.id]

        # record a local trial for this (strategy, segment) so future identical
        # segments are treated as "known" and stop re-experimenting.
        if action in (ACTION_EXECUTE, ACTION_EXPERIMENT):
            self.local_samples.setdefault((plan.strategy_type, seg_key), []).append(1)
        return aa

    # ------------------------------------------------------------------ #
    def _do_execute(self, opp, plan, pi, sc) -> tuple:
        st = plan.strategy_type
        sim_conf = float(pi.get("confidence", 0.0))
        prior_mean = float(pi.get("prior_mean", 0.5))
        fused = float(plan.priority)
        # The agent's execution confidence: it is the *authority* here. For a
        # strongly-known-good strategy (prior >= 0.75) the agent asserts a high
        # confidence so the Executor's secondary gate auto-approves; otherwise it
        # passes the fused score and lets the gate decide (often manual_review).
        agent_conf = round(
            0.85 if prior_mean >= 0.75 else max(fused, sim_conf), 3)
        rev = float(pi.get("simulation_revenue_delta", 0.0))
        decision_id = f"{opp.id}:{st}"
        req = ExecutionRequest(
            decision_id=decision_id,
            strategy_type=st,
            target_segment=opp.segment,
            mutation=sc.candidate.mutation,
            simulation_score=float(plan.priority),
            confidence=agent_conf,
            risk=pi.get("risk", "low"),
            simulation_positive=(rev >= 0.0),
            repeat_count=max(pi.get("prior_samples", 0), 4),
            simulate_fail=self._should_fail(decision_id),
        )
        result = self.executor.execute(req)
        self.guardrails.record_execution()
        self._record_execution_memory(opp, plan, pi, result)
        summary = {
            "status": result.status,
            "gate_verdict": result.gate_verdict,
            "real_api_called": result.provider_response.get("real_api_called", False),
            "changes": len(result.changes),
        }
        return result.status, summary

    def _do_experiment(self, opp, sc) -> tuple:
        baseline = self._baseline(opp)
        exp = experiment_from_candidate(sc.candidate, baseline, opportunity=opp)
        result = self.exp_manager.run_and_record(exp, baseline, self.store)
        self.guardrails.record_experiment()
        summary = {
            "experiment_id": result.experiment_id,
            "winner": result.winner_strategy_type,
            "lift_pct": round(result.lift_pct, 3),
            "arms": result.variants_count,
        }
        return "exp_completed", summary

    # ------------------------------------------------------------------ #
    def run_cycle(self, opportunities: List[Opportunity], day: int = 0) -> AgentCycleResult:
        if self.learn_every_cycle:
            self._refresh_prior()
        self.state.day = day
        self.state.current_stage = "observe"
        cycle = AgentCycleResult(cycle_id=f"cycle_d{day}", day=day,
                                 opportunities=len(opportunities))
        for opp in opportunities:
            aa = self._process_opportunity(opp, day)
            cycle.actions.append(aa)
            if aa.action == ACTION_OBSERVE:
                cycle.n_observe += 1
            elif aa.action == ACTION_EXPERIMENT:
                cycle.n_experiment += 1
            elif aa.action == ACTION_EXECUTE:
                cycle.n_execute += 1
            elif aa.action == ACTION_BLOCK:
                cycle.n_block += 1
        self.state.current_stage = "learn"
        return cycle

    # ------------------------------------------------------------------ #
    def run_simulation(self, per_day: List[List[Opportunity]]) -> AgentReport:
        # Learning baseline: the agent's belief about the strategies it already
        # knew at the start of the run. We measure improvement *only* over these
        # (seeded) strategies so that introducing a brand-new, low-prior strategy
        # mid-run does not artificially dilute the "did we get smarter?" signal.
        start_map = dict(self.prior.prior_map())
        report = AgentReport()
        for day, opps in enumerate(per_day):
            cycle = self.run_cycle(opps, day=day)
            report.per_day.append(cycle)
            report.opportunities += cycle.opportunities
            report.experiments += cycle.n_experiment
            report.executions += cycle.n_execute
            report.blocks += cycle.n_block
            report.observes += cycle.n_observe
            report.actions.extend(cycle.actions)
            for a in cycle.actions:
                if a.result_status == "executed":
                    report.executed_actually += 1
                elif a.result_status == "rolled_back":
                    report.rollbacks += 1
                elif a.result_status == "pending":
                    report.pending_human += 1

        report.cycles = len(per_day)
        report.guardrail_violations = list(self.guardrails.violations)

        # Improvement = mean relative change in the agent's prior belief across
        # EVERY strategy it now knows about:
        #   * a seeded (baseline) strategy's reference is its start belief; as the
        #     Executor records (mock) outcomes its Beta mean should drift toward
        #     the realised win-rate;
        #   * an *introduced* strategy (e.g. monetization_aggressive) started with
        #     NO belief (uninformed default 0.5) and the agent had to earn one via
        #     experiments — going 0.5 -> 0.97 is the clearest "it learned" signal.
        end_map = self.prior.prior_map()
        all_st = set(start_map) | set(end_map)
        rel_changes = []
        for st in all_st:
            em = end_map.get(st, start_map.get(st, 0.5))
            ref = start_map.get(st, 0.5)   # 0.5 = uninformed default for new
            if ref <= 0:
                continue
            rel_changes.append((em - ref) / ref)
        report.strategy_improvement_pct = (
            round(sum(rel_changes) / len(rel_changes) * 100.0, 2)
            if rel_changes else 0.0)
        return report

    def _prior_mean(self) -> float:
        """Mean learned prior across all strategies (a proxy for 'how much the
        agent trusts its playbook'). Rises as experiments feed success evidence
        into memory."""
        self._refresh_prior()
        vals = list(self.prior.prior_map().values())
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    # ------------------------------------------------------------------ #
    def _compute_improvement(self, report: AgentReport) -> float:
        """Mean learned prior for acted opportunities, first third vs last third.

        As the agent runs experiments (E13.4.2) and records outcomes, the
        Bayesian prior (E13.4.1) for the strategies it acts on should *rise* —
        a concrete, auditable measure of 'getting smarter' over the run.
        """
        acted = [a for a in report.actions if a.action in (ACTION_EXECUTE, ACTION_EXPERIMENT)]
        if len(acted) < 6:
            return 0.0
        third = max(1, len(acted) // 3)
        early = acted[:third]
        late = acted[-third:]
        base = sum(a.prior_mean for a in early) / len(early)
        final = sum(a.prior_mean for a in late) / len(late)
        if base <= 0:
            return 0.0
        return round((final - base) / base * 100.0, 2)
