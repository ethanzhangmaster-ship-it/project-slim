"""
E13.3.3 — Module 5: Execution Orchestrator  (Controlled Execution Layer)
========================================================================

The only component allowed to turn a simulated Decision into concrete config
changes. It enforces the mandatory flow and NEVER executes without the gate:

    Decision (simulated)
        |
        |  (1) Decision Validation     — required fields present, status=='simulated'
        v
    Approval Gate  ->  rejected | manual_review | approved
        |
        |  (2) Config Mutator          — generate Change records (dry, no side effects)
        v
    Provider.apply(change)  x N        — MOCK in v1 (real_api_called=false)
        |
        |  (3) any apply() fails?      -> rollback ALL applied so far -> 'rolled_back'
        v
    ExecutionResult                     — status executed | rolled_back | failed | rejected | pending

Two entry points:
    * execute(request)        — takes a fully-built ExecutionRequest (tests / API)
    * execute_decision(d)     — takes an E13.3.2 StrategyDecision.to_dict(); it
                                derives score/confidence/risk/sim_positive and
                                reuses the gate's repeat_count history.

Safety guarantees (asserted in validate_executor.py):
    * No ExecutionResult with status in (executed, rolled_back, failed) is ever
      produced from a Decision whose gate verdict was not 'approved'.
    * Every provider response in an executed/rolled_back result has
      real_api_called == false.
    * Rollback is always attempted on the first provider failure.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from monetization.executor.approval_gate import ApprovalGate
from monetization.executor.config_mutator import ConfigMutator
from monetization.executor.models import (
    EXEC_APPROVED, EXEC_EXECUTED, EXEC_FAILED, EXEC_PENDING, EXEC_REJECTED,
    EXEC_ROLLED_BACK, Change, ExecutionRequest, ExecutionResult, RollbackOperation,
    new_id,
)
from monetization.executor.provider_resolver import (
    LegacyProviderResolver, ProviderResolver,
)
from monetization.executor.providers import (
    LevelPlayProvider, MaxProvider, RemoteConfigProvider,
)
from monetization.providers.models import SandboxMode


class ExecutionOrchestrator:
    """Drives a Decision through the gated, reversible execution flow."""

    def __init__(self, gate: Optional[ApprovalGate] = None,
                 mutator: Optional[ConfigMutator] = None,
                 providers: Optional[Dict[str, object]] = None,
                 resolver: Optional[ProviderResolver] = None,
                 game_id: str = "",
                 sandbox: Optional[SandboxMode] = None):
        self.gate = gate or ApprovalGate()
        self.mutator = mutator or ConfigMutator()
        # The legacy provider dict is kept for direct test access
        # (e.g. `orch.providers['RemoteConfig'].set_fail_next(True)`) and for
        # the default resolver to wrap verbatim.
        self.providers = providers or {
            "MAX": MaxProvider(),
            "LevelPlay": LevelPlayProvider(),
            "RemoteConfig": RemoteConfigProvider(),
        }
        # Default resolver wraps the legacy dict -> E13.3.3 behaviour identical.
        # Pass a ContractProviderResolver(registry) to re-point at the frozen
        # E14.3.1 provider contract (game-isolated, credential-aware).
        self.resolver = resolver or LegacyProviderResolver(self.providers)
        self.game_id = game_id
        self.sandbox = sandbox or SandboxMode.SIMULATION

    # ------------------------------------------------------------------ #
    def provider_for(self, change: Change):
        # The ONLY seam that changed in the migration: delegate to the pluggable
        # resolver (legacy dict by default, contract registry when injected).
        return self.resolver.provider_for(change, game_id=self.game_id,
                                          sandbox=self.sandbox)

    # ------------------------------------------------------------------ #
    def _derive_gate_inputs(self, request: ExecutionRequest) -> dict:
        """Pull gate inputs from the request (already resolved by caller)."""
        return dict(
            score=request.simulation_score,
            risk=request.risk,
            confidence=request.confidence,
            simulation_positive=request.simulation_positive,
            repeat_count=request.repeat_count,
            strategy_type=request.strategy_type,
            segment=request.target_segment,
        )

    def _validate_decision(self, request: ExecutionRequest) -> Optional[str]:
        """Decision Validation gate. Returns an error string or None."""
        if not request.decision_id:
            return "missing decision_id"
        if not request.strategy_type:
            return "missing strategy_type"
        if not isinstance(request.mutation, dict):
            return "mutation must be a dict"
        return None

    # ------------------------------------------------------------------ #
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Run the full gated flow for a pre-built request."""
        # (1) Decision Validation
        err = self._validate_decision(request)
        if err:
            return self._result(EXEC_REJECTED, "rejected", request,
                                error=f"validation_failed: {err}")

        # (2) Approval Gate
        verdict = self.gate.decide(**self._derive_gate_inputs(request))

        if verdict == "rejected":
            return self._result(EXEC_REJECTED, "rejected", request,
                                error="approval_gate_rejected")

        if verdict == "manual_review":
            # not executed; awaits a human. status stays 'pending'.
            return self._result(EXEC_PENDING, "manual_review", request,
                                error="awaiting_human_approval")

        # verdict == 'approved' -> proceed to mutate + apply
        request.approved = True
        changes = self.mutator.generate_changes(
            request.strategy_type, request.mutation, request.target_segment)

        # no_action / none -> nothing to mutate; still record an executed (vacuous) run
        if not changes:
            res = self._result(EXEC_EXECUTED, "approved", request, changes=changes)
            res.rollback_available = True
            # record success so future repeats auto-approve
            self.gate.record_success(request.strategy_type, request.target_segment)
            return res

        # (3) apply each change; rollback on first failure
        applied: List[tuple] = []   # (provider, change, response)
        provider_responses: List[dict] = []
        fail_response = None
        for ch in changes:
            prov = self.provider_for(ch)
            if request.simulate_fail and not getattr(prov, "_fail_next", False):
                # honour request-level simulate_fail by arming the provider once
                prov.set_fail_next(True)
            resp = prov.apply(ch)
            provider_responses.append(resp)
            if resp.get("status") == "simulated_failed":
                fail_response = resp
                break
            applied.append((prov, ch, resp))

        if fail_response is not None:
            # Rollback everything applied so far, in reverse order
            rollback = RollbackOperation(execution_id="")
            rb_responses: List[dict] = []
            for prov, ch, _ in reversed(applied):
                rb = prov.rollback(ch)
                rb_responses.append(rb)
                rollback.reverted_changes.append(ch)
            rollback.provider_responses = rb_responses
            rollback.execution_id = new_id()
            res = self._result(EXEC_ROLLED_BACK, "approved", request,
                               changes=[c for _, c, _ in applied],
                               error=f"provider_failure: {fail_response.get('error')}")
            res.rollback_available = (len(rb_responses) > 0)
            res.provider_response = {
                "applied": [r for _, _, r in applied],
                "failed": fail_response,
                "rollback": rollback.to_dict(),
                "real_api_called": False,
            }
            return res

        # all applied successfully
        self.gate.record_success(request.strategy_type, request.target_segment)
        res = self._result(EXEC_EXECUTED, "approved", request, changes=[c for _, c, _ in applied])
        res.rollback_available = True
        res.provider_response = {
            "applied": provider_responses,
            "real_api_called": False,
        }
        return res

    # ------------------------------------------------------------------ #
    def execute_decision(self, decision: dict,
                         repeat_count: Optional[int] = None) -> ExecutionResult:
        """Build an ExecutionRequest from an E13.3.2 StrategyDecision dict and run.

        Extracts score/confidence/risk/simulation_positive from the decision's
        `strategy.prediction`. If `repeat_count` is None, the gate's in-memory
        history is used (so re-running the same strategy accumulates approvals).
        """
        strat = decision.get("strategy", {}) or {}
        pred = (strat.get("prediction") or {}).get("prediction", {}) or {}
        seg = _seg_from_decision(decision)

        confidence = float(pred.get("confidence", 0.0))
        risk = pred.get("retention_risk", "low")
        rev_delta = float(pred.get("revenue_delta_pct", 0.0))
        simulation_positive = rev_delta >= 0.0
        score = float(strat.get("score", 0.0))
        stype = strat.get("type", "")

        if repeat_count is None:
            repeat_count = self.gate.repeat_count_for(stype, seg)

        req = ExecutionRequest(
            decision_id=decision.get("opportunity_id", "") or decision.get("decision_id", ""),
            strategy_type=stype,
            target_segment=seg,
            mutation=strat.get("mutation", {}),
            simulation_score=score,
            confidence=confidence,
            risk=risk,
            simulation_positive=simulation_positive,
            repeat_count=repeat_count,
        )
        return self.execute(req)

    # ------------------------------------------------------------------ #
    def _result(self, status: str, verdict: str, request: ExecutionRequest,
                changes: List[Change] = None, error: Optional[str] = None) -> ExecutionResult:
        return ExecutionResult(
            execution_id=new_id(),
            status=status,
            gate_verdict=verdict,
            decision_id=request.decision_id,
            strategy_type=request.strategy_type,
            changes=changes or [],
            rollback_available=False,
            provider_response={},
            error=error,
            score=request.simulation_score,
            confidence=request.confidence,
            risk=request.risk,
            simulation_positive=request.simulation_positive,
            repeat_count=request.repeat_count,
        )


def _seg_from_decision(decision: dict) -> dict:
    """Recover a coarse segment from a StrategyDecision's rationale/target.

    The E13.3.2 decision does not carry the raw segment dict, so we parse it
    back from the prediction's `target` string (e.g. 'US_android_reward_applovin').
    """
    strat = decision.get("strategy", {}) or {}
    pred = strat.get("prediction", {}) or {}
    target = pred.get("target", "") or ""
    parts = [p for p in target.split("_") if p]
    seg = {}
    if len(parts) >= 1:
        seg["country"] = parts[0]
    if len(parts) >= 2:
        seg["platform"] = parts[1]
    if len(parts) >= 3:
        seg["ad_format"] = parts[2]
    if len(parts) >= 4:
        seg["network"] = parts[3]
    return seg
