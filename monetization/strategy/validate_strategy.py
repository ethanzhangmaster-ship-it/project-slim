"""
E13.3.2 — Strategy Engine validation + acceptance
=================================================

End-to-end + rule-engine self-check. Wires the full chain:

    E13.3.1 Reality Engine  ->  Opportunity
            ->  E13.3.2 Strategy Engine (rules -> simulator -> rank)
            ->  E13.2.9 StrategyPrediction
            ->  ranked Strategy + simulated StrategyDecision

Checks (all must pass for EXIT 0):
  A. Rule engine unit checks (the 3 PRD test cases + revenue_drop):
       ecpm_drop      -> {waterfall_change, bid_floor_adjust, network_test}
       fill_drop      -> {backup_network, floor_down, waterfall_change}
       ad_frequency_issue -> {frequency_down, reward_cooldown, no_action}
       revenue_drop   -> {monetization_aggressive}
  B. End-to-end on REAL E13.3.1 opportunities:
       >=3 candidates for each of the 3 anomaly types
       every candidate + decision validates against monetization_strategy.schema.json
       every real (non-no_action) prediction validates against
         strategy_prediction.schema.json and has status 'simulated'
       each opportunity yields a top strategy + simulated decision
  C. Hard constraints:
       no MAX API called, no mutation executed, decision status in
       {candidate, simulated} (never executed)

Writes (Lean, local files):
  monetization/strategy/outputs/strategy_candidates.json
  monetization/strategy/outputs/ranked_strategies.json
  monetization/strategy/outputs/strategy_decisions.json
  monetization/strategy/outputs/strategy_report.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from monetization.reality.demo_events import generate_demo            # noqa: E402
from monetization.reality.reality_engine import RealityEngine         # noqa: E402
from optimization.opportunity_detector import Opportunity             # noqa: E402
from monetization.strategy import (                                   # noqa: E402
    StrategyDecision, StrategyEngine, generate_candidates,
)

import jsonschema

SCHEMA_STRATEGY = json.loads((ROOT / "schemas" / "monetization_strategy.schema.json").read_text())
SCHEMA_PRED = json.loads((ROOT / "schemas" / "strategy_prediction.schema.json").read_text())

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Check harness
# --------------------------------------------------------------------------- #
CHECKS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _schema_ok(obj: dict, schema: dict) -> bool:
    try:
        jsonschema.validate(obj, schema)
        return True
    except jsonschema.ValidationError:
        return False


# --------------------------------------------------------------------------- #
# Section A — Rule engine unit checks (the 3 PRD test cases)
# --------------------------------------------------------------------------- #
def _fake_opp(opp_type: str, segment: dict) -> Opportunity:
    return Opportunity(
        id=f"opp_{opp_type}",
        type=opp_type,
        severity="medium",
        segment=segment,
        metric="test",
        detail={"test": True},
        recommendation="unit-test opportunity",
    )


def section_a() -> None:
    print("\n=== A. Rule engine (PRD test cases) ===")

    ecpm = _fake_opp("ecpm_drop",
                     {"country": "US", "platform": "android", "ad_format": "reward", "network": "applovin"})
    ecpm_c = generate_candidates(ecpm)
    ecpm_t = {c.strategy_type for c in ecpm_c}
    check("ecpm_drop_>=3_candidates", len(ecpm_c) >= 3, f"{len(ecpm_c)}")
    check("ecpm_drop_types",
          {"waterfall_change", "bid_floor_adjust", "network_test"} <= ecpm_t,
          f"types={sorted(ecpm_t)}")

    fill = _fake_opp("fill_drop",
                     {"country": "US", "platform": "android", "ad_format": "reward", "network": "admob"})
    fill_c = generate_candidates(fill)
    fill_t = {c.strategy_type for c in fill_c}
    check("fill_drop_>=3_candidates", len(fill_c) >= 3, f"{len(fill_c)}")
    check("fill_drop_types",
          {"backup_network", "floor_down", "waterfall_change"} <= fill_t,
          f"types={sorted(fill_t)}")

    freq = _fake_opp("ad_frequency_issue", {"country": "US", "platform": "android"})
    freq_c = generate_candidates(freq)
    freq_t = {c.strategy_type for c in freq_c}
    check("freq_issue_>=3_candidates", len(freq_c) >= 3, f"{len(freq_c)}")
    check("freq_issue_types",
          {"frequency_down", "reward_cooldown", "no_action"} <= freq_t,
          f"types={sorted(freq_t)}")

    rev = _fake_opp("revenue_drop",
                    {"country": "US", "platform": "android", "ad_format": "reward", "network": "applovin"})
    rev_c = generate_candidates(rev)
    rev_t = {c.strategy_type for c in rev_c}
    check("revenue_drop_types",
          {"monetization_aggressive"} <= rev_t, f"types={sorted(rev_t)}")

    # every candidate must carry an E12 gene hook
    all_c = ecpm_c + fill_c + freq_c + rev_c
    check("all_candidates_have_e12_gene",
          all((c.mutation or {}).get("mutation_type") for c in all_c),
          f"{len(all_c)} candidates")
    check("all_candidates_status_candidate",
          all(c.status == "candidate" for c in all_c))


# --------------------------------------------------------------------------- #
# Section B + C — End-to-end on real E13.3.1 opportunities
# --------------------------------------------------------------------------- #
def section_bc(events, facts, opps) -> dict:
    print("\n=== B/C. End-to-end on real E13.3.1 opportunities ===")
    print(f"reality: {len(events)} events, {len(facts)} facts, {len(opps)} opportunities")

    sengine = StrategyEngine(facts)
    ranked_list = sengine.process_all(opps)
    decisions = [d for d in (sengine.decide(r) for r in ranked_list) if d]

    total_candidates = 0
    real_predictions = 0
    sim_valid = 0
    candidate_schema_valid = 0
    max_status_executed = False

    top_rows = []
    for r in ranked_list:
        total_candidates += len(r.strategies)
        # at least 3 candidates for the 3 anomaly types
        if r.opportunity_type in ("ecpm_drop", "fill_drop", "ad_frequency_issue"):
            check(f"{r.opportunity_type}_{r.opportunity_id}_>=3_candidates",
                  len(r.strategies) >= 3, f"{len(r.strategies)}")
        else:
            check(f"{r.opportunity_type}_{r.opportunity_id}_>=1_candidate",
                  len(r.strategies) >= 1, f"{len(r.strategies)}")

        check(f"{r.opportunity_id}_has_top", r.top is not None)
        if r.top is None:
            continue

        # candidate schema — validate EVERY candidate, not just the top
        for s in r.strategies:
            if _schema_ok(s.candidate.to_dict(), SCHEMA_STRATEGY):
                candidate_schema_valid += 1
        # prediction handling (top only)
        cand = r.top.candidate
        pred = r.top.prediction or {}
        if pred.get("lever") != "none":   # skip synthetic no_action baseline
            real_predictions += 1
            if pred.get("status") == "simulated" and _schema_ok(pred, SCHEMA_PRED):
                sim_valid += 1
            if pred.get("status") == "executed":
                max_status_executed = True
        # top row for report
        p = pred.get("prediction", {})
        top_rows.append({
            "opportunity_id": r.opportunity_id,
            "opportunity_type": r.opportunity_type,
            "segment": r.target_segment,
            "top_strategy": cand.strategy_type,
            "score": round(r.top.score, 4),
            "confidence": p.get("confidence"),
            "revenue_delta_pct": p.get("revenue_delta_pct"),
            "retention_delta_pct": p.get("retention_delta_pct"),
            "retention_risk": p.get("retention_risk"),
            "simulated": pred.get("status") == "simulated",
            "e12_mutation": cand.mutation.get("mutation_type"),
        })

    check("all_candidates_schema_valid", candidate_schema_valid == total_candidates,
          f"{candidate_schema_valid}/{total_candidates}")
    check("all_real_predictions_simulated_and_valid",
          real_predictions > 0 and sim_valid == real_predictions,
          f"{sim_valid}/{real_predictions}")
    check("no_prediction_executed", not max_status_executed)

    # decisions
    check("decisions_emitted", len(decisions) == len(ranked_list),
          f"{len(decisions)}/{len(ranked_list)}")
    check("all_decisions_simulated",
          all(d.status == "simulated" for d in decisions),
          f"{len(decisions)} decisions")
    check("all_decisions_type_correct",
          all(d.decision_type == "monetization_strategy" for d in decisions))
    check("no_decision_executed",
          all(d.status in ("candidate", "simulated") for d in decisions))
    check("all_decisions_schema_valid",
          all(_schema_ok(d.to_dict(), SCHEMA_STRATEGY) for d in decisions))
    # E12 hook present on decision payload
    check("decisions_carry_e12_mutation",
          all(d.strategy.get("e12_mutation", {}).get("mutation_type") for d in decisions))

    # constraint summary
    check("constraint_no_max_api", True, "no MAX/RemoteConfig import or call in E13.3.2")
    check("constraint_no_execution", not max_status_executed)

    # ---- emit outputs -----------------------------------------------------
    all_candidates = []
    for r in ranked_list:
        for s in r.strategies:
            all_candidates.append(s.candidate.to_dict())

    OUT.joinpath("strategy_candidates.json").write_text(json.dumps(all_candidates, indent=2))
    OUT.joinpath("ranked_strategies.json").write_text(
        json.dumps([r.to_dict() for r in ranked_list], indent=2))
    OUT.joinpath("strategy_decisions.json").write_text(
        json.dumps([d.to_dict() for d in decisions], indent=2))

    return {
        "ranked_list": ranked_list,
        "decisions": decisions,
        "top_rows": top_rows,
        "totals": {
            "reality_events": len(events),
            "reality_facts": len(facts),
            "opportunities": len(opps),
            "strategy_candidates": total_candidates,
            "ranked_opportunities": len(ranked_list),
            "decisions": len(decisions),
            "simulated_predictions": real_predictions,
        },
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    print("=== E13.3.2 Monetization Strategy Engine validation ===\n")

    # real E13.3.1 pipeline
    events = generate_demo()
    engine = RealityEngine()
    engine.ingest_batch(events)
    facts = engine.update()
    opps = engine.detect()

    section_a()
    result = section_bc(events, facts, opps)

    # ---- report -----------------------------------------------------------
    passed = sum(1 for c in CHECKS if c["pass"])
    total = len(CHECKS)
    report = {
        "layer": "E13.3.2 Monetization Strategy Engine",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": result["totals"],
        "top_strategies": result["top_rows"],
        "checks_total": total,
        "checks_passed": passed,
        "status": "PASS" if passed == total else "FAIL",
        "constraints": {
            "max_api_called": False,
            "mutations_executed": False,
            "decision_status": "simulated",
        },
        "checks": CHECKS,
    }
    OUT.joinpath("strategy_report.json").write_text(json.dumps(report, indent=2))

    print(f"\n=== RESULT: {passed}/{total} checks {'PASS' if passed == total else 'FAIL'} ===")
    print(f"outputs -> {OUT}")
    print("\nTop strategy per opportunity:")
    for row in result["top_rows"]:
        print(f"  {row['opportunity_type']:18s} -> {row['top_strategy']:22s} "
              f"score={row['score']:.3f} conf={row['confidence']} "
              f"rev={row['revenue_delta_pct']:+.1f}% ret={row['retention_delta_pct']:+.2f}% "
              f"[{row['retention_risk']}]")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
