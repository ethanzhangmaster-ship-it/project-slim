"""
E13.3.3 — Validation & Acceptance
==================================

Runs the Controlled Execution Layer end-to-end and asserts the safety
contracts. Three kinds of evidence:

  A. REAL PIPELINE  — E13.3.1 Reality Engine -> E13.3.2 Strategy Engine ->
     E13.3.3 Executor. First-exposure strategies must default to
     manual_review (pending); nothing auto-executes on day one. No real API.

  B. EXPLICIT CASES (from the PRD):
     Case 1  low-risk bid_floor_adjust (conf 0.9, repeat>3) -> approved -> executed(mock)
     Case 2  frequency_up, high risk                    -> rejected
     Case 3  provider failure mid-apply                 -> rolled_back (rollback invoked)

  C. SAFETY CONTRACTS — verified across every executed/rolled_back result:
     * gate_verdict == 'approved' is a prerequisite for any executed/rolled_back
     * every provider response has real_api_called == false
     * rollback is attempted whenever a provider fails

Outputs (in monetization/executor/outputs/):
    executor_report.json      — summary + checks + case results + constraints
    execution_results.json    — all ExecutionResult dicts
    rollback_report.json      — Case 3 detail (applied + reverted + responses)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from monetization.reality.demo_events import generate_demo
from monetization.reality.reality_engine import RealityEngine
from monetization.strategy import StrategyEngine

from monetization.executor import (
    ApprovalGate, ConfigMutator, ExecutionOrchestrator,
    EXEC_EXECUTED, EXEC_PENDING, EXEC_REJECTED, EXEC_ROLLED_BACK,
    GATE_APPROVED, GATE_MANUAL_REVIEW, GATE_REJECTED,
    ExecutionRequest,
)
from monetization.executor.providers import MaxProvider, RemoteConfigProvider

import jsonschema
SCHEMA_EXEC = json.loads(
    (ROOT / "schemas" / "execution_result.schema.json").read_text())

OUT = ROOT / "monetization" / "executor" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

CHECKS = []  # (name, passed, detail)


def check(name: str, passed: bool, detail: str = "") -> bool:
    CHECKS.append((name, passed, detail))
    return passed


def _no_real_api(obj) -> bool:
    """Recursively assert no provider response ever called a real API."""
    if isinstance(obj, dict):
        if "real_api_called" in obj:
            if obj["real_api_called"] is not True:
                return True
            return False
        return all(_no_real_api(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_real_api(v) for v in obj)
    return True


def _valid_schema(result_dict: dict) -> bool:
    try:
        jsonschema.validate(result_dict, SCHEMA_EXEC)
        return True
    except jsonschema.ValidationError:
        return False


def main():
    # ----------------------------------------------------------------- #
    # A. REAL PIPELINE: E13.3.1 -> E13.3.2 -> E13.3.3
    # ----------------------------------------------------------------- #
    evs = generate_demo()
    engine = RealityEngine()
    engine.ingest_batch(evs)
    facts = engine.update()
    opps = engine.detect()

    strat_engine = StrategyEngine(facts)
    ranked = strat_engine.process_all(opps)
    decisions = [strat_engine.decide(r) for r in ranked if r.top is not None]
    decisions = [d.to_dict() for d in decisions if d]

    check("A1 real_pipeline_produced_decisions", len(decisions) >= 1,
          f"{len(decisions)} decisions from real E13.3.1 opportunities")

    orch = ExecutionOrchestrator()
    pipeline_results = []
    all_no_api = True
    all_schema_ok = True
    first_exposure_safe = True
    for d in decisions:
        res = orch.execute_decision(d)   # repeat_count=None -> gate history (0 on first run)
        rd = res.to_dict()
        pipeline_results.append(rd)
        if not _valid_schema(rd):
            all_schema_ok = False
        if not _no_real_api(rd.get("provider_response", {})):
            all_no_api = False
        # First-exposure strategies must NOT auto-execute; default to review.
        if res.status in (EXEC_EXECUTED, EXEC_ROLLED_BACK):
            # would only happen if repeat_count>3 seeded; none here
            if res.gate_verdict != GATE_APPROVED:
                first_exposure_safe = False
        # on first exposure the verdict should be manual_review (or rejected)
        if res.gate_verdict not in (GATE_MANUAL_REVIEW, GATE_REJECTED):
            first_exposure_safe = False

    check("A2 pipeline_schema_valid", all_schema_ok,
          "all pipeline ExecutionResults validate against schema")
    check("A3 pipeline_no_real_api", all_no_api,
          "no provider response ever set real_api_called=true")
    check("A4 first_exposure_not_auto_executed",
          first_exposure_safe and all(r["gate_verdict"] in (GATE_MANUAL_REVIEW, GATE_REJECTED)
                                      for r in pipeline_results),
          "first-exposure strategies default to manual_review/rejected (safe)")
    check("A5 pipeline_status_known",
          all(r["status"] in (EXEC_PENDING, EXEC_REJECTED) for r in pipeline_results),
          f"pipeline statuses: {[r['status'] for r in pipeline_results]}")

    # ----------------------------------------------------------------- #
    # B. EXPLICIT CASES
    # ----------------------------------------------------------------- #
    # ---- Case 1: low-risk bid_floor_adjust, conf 0.9, repeat>3 -------- #
    gate = ApprovalGate()
    orch1 = ExecutionOrchestrator(gate=gate)
    req1 = ExecutionRequest(
        decision_id="case1", strategy_type="bid_floor_adjust",
        target_segment={"country": "US", "platform": "android", "ad_format": "reward", "network": "applovin"},
        mutation={"action_type": "review_bidding",
                  "params": {"increase_bid_floor": True, "bid_floor_pct": 20},
                  "description": "Raise bid floor +20%",
                  "mutation_type": "bid_floor_gene", "gene": {"bid_floor_delta": 0.20}},
        simulation_score=0.85, confidence=0.9, risk="low",
        simulation_positive=True, repeat_count=5,
    )
    res1 = orch1.execute(req1)
    rd1 = res1.to_dict()
    check("C1 gate_approved", res1.gate_verdict == GATE_APPROVED,
          f"verdict={res1.gate_verdict}")
    check("C2 executed", res1.status == EXEC_EXECUTED,
          f"status={res1.status}")
    check("C3 has_changes", len(res1.changes) >= 1,
          f"{len(res1.changes)} change(s): {[c.change_type for c in res1.changes]}")
    check("C4 rollback_available", res1.rollback_available is True,
          "rollback_available=True after a successful execution")
    check("C5 no_real_api_case1", _no_real_api(rd1.get("provider_response", {})),
          "provider responses certify real_api_called=false")
    check("C6 schema_case1", _valid_schema(rd1), "Case 1 result validates")

    # ---- Case 2: frequency_up, high retention risk -> rejected -------- #
    gate2 = ApprovalGate()
    orch2 = ExecutionOrchestrator(gate=gate2)
    req2 = ExecutionRequest(
        decision_id="case2", strategy_type="frequency_adjust",
        target_segment={"country": "US", "platform": "android"},
        mutation={"action_type": "adjust_ad_frequency",
                  "params": {"direction": "up", "magnitude_pct": 10},
                  "description": "Increase ad frequency",
                  "mutation_type": "frequency_gene", "gene": {"reward_interval_delta": -1}},
        simulation_score=0.70, confidence=0.45, risk="high",
        simulation_positive=False, repeat_count=0,
    )
    res2 = orch2.execute(req2)
    rd2 = res2.to_dict()
    check("C7 gate_rejected", res2.gate_verdict == GATE_REJECTED,
          f"verdict={res2.gate_verdict}")
    check("C8 not_executed", res2.status == EXEC_REJECTED,
          f"status={res2.status}")
    check("C9 nothing_applied_on_reject", len(res2.changes) == 0,
          "rejected decision produced zero applied changes")
    check("C10 schema_case2", _valid_schema(rd2), "Case 2 result validates")

    # ---- Case 3: provider failure mid-apply -> rollback --------------- #
    # The bid_floor strategy emits two changes (MAX floor + RemoteConfig
    # mirror). We arm the RemoteConfig provider to fail on its apply, so the
    # MAX change is applied FIRST and then must be rolled back.
    gate3 = ApprovalGate()
    orch3 = ExecutionOrchestrator(gate=gate3)
    orch3.providers["RemoteConfig"].set_fail_next(True)
    req3 = ExecutionRequest(
        decision_id="case3", strategy_type="bid_floor_adjust",
        target_segment={"country": "US", "platform": "android", "ad_format": "reward", "network": "applovin"},
        mutation={"action_type": "review_bidding",
                  "params": {"increase_bid_floor": True, "bid_floor_pct": 20},
                  "description": "Raise bid floor +20% (RemoteConfig mirror will fail)",
                  "mutation_type": "bid_floor_gene", "gene": {"bid_floor_delta": 0.20}},
        simulation_score=0.85, confidence=0.9, risk="low",
        simulation_positive=True, repeat_count=5,
    )
    res3 = orch3.execute(req3)
    rd3 = res3.to_dict()
    rb = rd3.get("provider_response", {}).get("rollback")
    check("C11 rolled_back", res3.status == EXEC_ROLLED_BACK,
          f"status={res3.status}")
    check("C12 rollback_invoked", bool(rb) and len(rb.get("reverted_changes", [])) >= 1,
          f"reverted {len(rb.get('reverted_changes', [])) if rb else 0} change(s)")
    check("C13 rollback_no_real_api",
          _no_real_api(rd3.get("provider_response", {})),
          "rollback responses also certify real_api_called=false")
    check("C14 schema_case3", _valid_schema(rd3), "Case 3 result validates")

    # ----------------------------------------------------------------- #
    # C. SAFETY CONTRACTS (cross-cutting)
    # ----------------------------------------------------------------- #
    all_results = pipeline_results + [rd1, rd2, rd3]
    contract_ok = True
    for r in all_results:
        if r["status"] in (EXEC_EXECUTED, EXEC_ROLLED_BACK):
            if r["gate_verdict"] != GATE_APPROVED:
                contract_ok = False
    check("S1 executed_requires_approval", contract_ok,
          "no executed/rolled_back result lacks gate approval")
    check("S2 never_direct_from_opportunity",
          all(r["gate_verdict"] in (GATE_APPROVED, GATE_MANUAL_REVIEW, GATE_REJECTED)
              for r in all_results),
          "every result passed through the gate (no Opportunity->API shortcut)")
    check("S3 global_no_real_api",
          _no_real_api({"x": all_results}),
          "global: real_api_called never true in any result")

    # ----------------------------------------------------------------- #
    # Write outputs
    # ----------------------------------------------------------------- #
    report = {
        "module": "E13.3.3 Autonomous Monetization Executor",
        "status": "PASS" if all(p for _, p, _ in CHECKS) else "FAIL",
        "checks_passed": sum(1 for _, p, _ in CHECKS if p),
        "checks_total": len(CHECKS),
        "pipeline": {
            "decisions": len(decisions),
            "results": pipeline_results,
        },
        "cases": {
            "case1_low_risk_approved_executed": rd1,
            "case2_high_risk_rejected": rd2,
            "case3_provider_failure_rolled_back": rd3,
        },
        "constraints": {
            "no_real_api_called": True,
            "approval_gate_mandatory": True,
            "rollback_on_failure": True,
            "direct_opportunity_to_api_forbidden": True,
        },
        "checks": [
            {"name": n, "passed": p, "detail": d} for n, p, d in CHECKS
        ],
    }
    (OUT / "executor_report.json").write_text(json.dumps(report, indent=2))
    (OUT / "execution_results.json").write_text(json.dumps(all_results, indent=2))
    (OUT / "rollback_report.json").write_text(json.dumps(rd3, indent=2))

    # ----------------------------------------------------------------- #
    # Console summary
    # ----------------------------------------------------------------- #
    print("=" * 70)
    print("E13.3.3 Executor validation")
    print("=" * 70)
    for n, p, d in CHECKS:
        print(f"  [{'PASS' if p else 'FAIL'}] {n}: {d}")
    print("-" * 70)
    print(f"  Pipeline decisions: {len(decisions)}  (all -> manual_review/rejected on first exposure)")
    print(f"  Case1: {rd1['gate_verdict']} -> {rd1['status']}  changes={len(rd1['changes'])}")
    print(f"  Case2: {rd2['gate_verdict']} -> {rd2['status']}")
    print(f"  Case3: {rd3['gate_verdict']} -> {rd3['status']}  reverted={len(rb.get('reverted_changes', [])) if rb else 0}")
    print("-" * 70)
    passed = sum(1 for _, p, _ in CHECKS if p)
    print(f"  CHECKS: {passed}/{len(CHECKS)}  STATUS: {'PASS' if passed == len(CHECKS) else 'FAIL'}")
    print("=" * 70)
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
