"""
E13.2.9 — Simulator validation
===============================
End-to-end + assertion runner. Reuses the E13.2.8 pipeline
(synthetic events -> aggregation -> facts -> opportunities -> decisions),
then simulates each proposed Decision against the current Fact state, and
runs 4 explicit scenarios with sign assertions.

No MAX API. No execution. Emits:
  simulation/outputs/strategy_predictions.json   (decisions from real anomalies)
  simulation/outputs/scenario_predictions.json   (4 explicit scenarios)
  simulation/outputs/simulator_report.json       (summary + checks)

Run:  python simulation/validate_simulator.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.synthetic_events import generate
from analytics.aggregation.event_aggregator import aggregate
from monetization.facts import build_monetization_facts
from optimization.opportunity_detector import detect_opportunities
from optimization.decision_interface import create_decisions
from simulation.strategy_simulator import simulate_decision, simulate_strategy

import jsonschema

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
SCHEMA = os.path.join(HERE, "..", "schemas", "strategy_prediction.schema.json")

with open(SCHEMA) as f:
    PRED_SCHEMA = json.load(f)


# --------------------------------------------------------------------------- #
# Pick the current (latest) baseline fact for a decision
# --------------------------------------------------------------------------- #
def _baseline_for(decision, facts):
    t = decision.target
    matches = []
    for f in facts:
        if f.segment_type == "ad":
            key = "_".join(str(x) for x in (f.country, f.platform, f.ad_format, f.network) if x)
            if key == t:
                matches.append(f)
        elif f.segment_type == "user":
            key = "_".join(str(x) for x in (f.country, f.platform) if x)
            if key == t or t.startswith(key):
                matches.append(f)
    if not matches:
        return None
    return max(matches, key=lambda f: f.date)


# --------------------------------------------------------------------------- #
# Run pipeline
# --------------------------------------------------------------------------- #
def run_pipeline():
    events = generate()
    agg = aggregate(events)
    facts = build_monetization_facts(agg)
    opps = detect_opportunities(facts)
    decisions = create_decisions(opps)
    return facts, opps, decisions


# --------------------------------------------------------------------------- #
# Assertions
# --------------------------------------------------------------------------- #
CHECKS = []


def check(name: str, cond: bool, detail: str = ""):
    CHECKS.append({"name": name, "passed": bool(cond), "detail": detail})
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    print("=== E13.2.9 Strategy Simulator validation ===\n")
    facts, opps, decisions = run_pipeline()
    print(f"pipeline: {len(facts)} facts, {len(opps)} opportunities, {len(decisions)} decisions\n")

    # 1) simulate every proposed decision against its baseline fact
    preds = []
    for d in decisions:
        bf = _baseline_for(d, facts)
        if bf is None:
            print(f"  (skip {d.decision_id}: no baseline fact for target '{d.target}')")
            continue
        pred = simulate_decision(d, bf)
        preds.append(pred.to_dict())
        print(f"  {d.action_type:20s} {d.target:28s} -> rev {pred.prediction['revenue_delta_pct']:+.1f}% "
              f"eCPM {pred.prediction['ecpm_delta_pct']:+.1f}% fill {pred.prediction['fill_delta_pct']:+.1f}% "
              f"conf {pred.prediction['confidence']} risk {pred.prediction['retention_risk']}")

    print()
    check("decisions_simulated", len(preds) == len(decisions),
          f"{len(preds)}/{len(decisions)}")
    check("no_decision_executed", all(p["status"] == "simulated" for p in preds))
    check("all_predictions_schema_valid",
          all(_schema_ok(p) for p in preds), "validated against strategy_prediction.schema.json")

    # 2) explicit scenarios with expected sign assertions
    print("\n--- explicit scenarios ---")
    scenarios = []

    # S1: raise bid floor +20% -> revenue up, eCPM up, fill down, retention low
    s1 = simulate_strategy("review_bidding",
                           {"increase_bid_floor": True, "bid_floor_pct": 20},
                           {"ecpm": 30.0, "fill_rate": 0.90, "impressions": 12000, "revenue": 324.0},
                           target="US_android_reward_applovin", decision_id="S1")
    scenarios.append(s1.to_dict())
    p1 = s1.prediction
    check("S1_revenue_up", p1["revenue_delta_pct"] > 0, f"{p1['revenue_delta_pct']:+.1f}%")
    check("S1_ecpm_up", p1["ecpm_delta_pct"] > 0)
    check("S1_fill_down", p1["fill_delta_pct"] < 0)
    check("S1_retention_low", p1["retention_risk"] == "low")

    # S2: promote high-eCPM network (waterfall) +20% -> revenue up, eCPM up, fill down
    s2 = simulate_strategy("change_waterfall",
                           {"magnitude_pct": 20},
                           {"ecpm": 28.0, "fill_rate": 0.88, "impressions": 9500, "revenue": 263.2},
                           target="US_android_reward_applovin", decision_id="S2")
    scenarios.append(s2.to_dict())
    p2 = s2.prediction
    check("S2_revenue_up", p2["revenue_delta_pct"] > 0, f"{p2['revenue_delta_pct']:+.1f}%")
    check("S2_ecpm_up", p2["ecpm_delta_pct"] > 0)
    check("S2_fill_down", p2["fill_delta_pct"] < 0)

    # S3: increase ad frequency +10% -> revenue up, retention risk, retention down
    s3 = simulate_strategy("adjust_ad_frequency",
                           {"direction": "up", "magnitude_pct": 10},
                           {"ads_per_dau": 3.0, "dau": 8000, "d1_retention_est": 0.40},
                           target="US_android", decision_id="S3")
    scenarios.append(s3.to_dict())
    p3 = s3.prediction
    check("S3_revenue_up", p3["revenue_delta_pct"] > 0, f"{p3['revenue_delta_pct']:+.1f}%")
    check("S3_retention_down", p3["retention_delta_pct"] < 0, f"{p3['retention_delta_pct']:+.2f}%")
    check("S3_risk_not_low", p3["retention_risk"] in ("medium", "high"), p3["retention_risk"])

    # S4: decrease ad frequency +10% -> revenue down, retention improves
    s4 = simulate_strategy("adjust_ad_frequency",
                           {"direction": "down", "magnitude_pct": 10},
                           {"ads_per_dau": 3.0, "dau": 8000, "d1_retention_est": 0.40},
                           target="US_android", decision_id="S4")
    scenarios.append(s4.to_dict())
    p4 = s4.prediction
    check("S4_revenue_down", p4["revenue_delta_pct"] < 0, f"{p4['revenue_delta_pct']:+.1f}%")
    check("S4_retention_up", p4["retention_delta_pct"] > 0, f"{p4['retention_delta_pct']:+.2f}%")
    check("S4_risk_low", p4["retention_risk"] == "low")

    check("scenarios_schema_valid", all(_schema_ok(s) for s in scenarios))

    # 3) confidence bounds
    check("confidence_in_range",
          all(0.0 < p["prediction"]["confidence"] <= 1.0 for p in preds + scenarios))

    # 4) emit outputs
    os.makedirs(OUT, exist_ok=True)
    _dump("strategy_predictions.json", preds)
    _dump("scenario_predictions.json", scenarios)

    passed = sum(1 for c in CHECKS if c["passed"])
    total = len(CHECKS)
    report = {
        "module": "E13.2.9 Monetization Strategy Simulator",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": {"facts": len(facts), "opportunities": len(opps), "decisions": len(decisions)},
        " simulated_decisions": len(preds),
        "scenarios": len(scenarios),
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
    _dump("simulator_report.json", report)

    print(f"\n=== RESULT: {passed}/{total} checks {'PASS' if passed == total else 'FAIL'} ===")
    print(f"outputs -> {OUT}")
    return 0 if passed == total else 1


def _schema_ok(pred: dict) -> bool:
    try:
        jsonschema.validate(pred, PRED_SCHEMA)
        return True
    except jsonschema.ValidationError:
        return False


def _dump(name: str, obj) -> None:
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
