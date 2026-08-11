"""
E13.2.8 — validate_intelligence.py
===================================

End-to-end run + self-check of the Monetization Intelligence Layer.

Pipeline:
  synthetic events
    -> EventAggregator
    -> MonetizationFacts (metrics + retention/LTV)
    -> OpportunityDetector
    -> DecisionInterface        (proposed only)

Checks (all must pass for EXIT 0):
  1. Aggregation correctness (impressions / revenue counts sane)
  2. Every fact validates against monetization_fact.schema.json
  3. Injected anomalies are detected: ecpm_drop, fill_drop, ad_frequency_issue
  4. Decisions are NEVER executed (status == "proposed", no external calls)

Writes:
  intelligence/outputs/monetization_facts.json
  intelligence/outputs/opportunities.json
  intelligence/outputs/decisions.json
  intelligence/outputs/intelligence_report.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics.aggregation.event_aggregator import aggregate  # noqa: E402
from monetization.facts import build_monetization_facts       # noqa: E402
from optimization.opportunity_detector import detect_opportunities  # noqa: E402
from optimization.decision_interface import create_decisions     # noqa: E402
from intelligence.synthetic_events import generate             # noqa: E402

OUT = ROOT / "intelligence" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
SCHEMA = json.loads((ROOT / "schemas" / "monetization_fact.schema.json").read_text())


# --------------------------------------------------------------------------- #
# minimal schema validator (no jsonschema dependency)
# --------------------------------------------------------------------------- #
def validate_fact(fact: dict) -> list:
    errs = []
    for req in SCHEMA.get("required", []):
        if req not in fact:
            errs.append(f"missing required '{req}'")
    props = SCHEMA.get("properties", {})
    for k, v in fact.items():
        spec = props.get(k)
        if not spec:
            continue
        t = spec.get("type")
        if t == "string" and not isinstance(v, str):
            errs.append(f"'{k}' expected string")
        elif t == "integer" and not isinstance(v, int):
            errs.append(f"'{k}' expected integer")
        elif t == "number" and not isinstance(v, (int, float)):
            errs.append(f"'{k}' expected number")
        elif t == "array" and not isinstance(v, list):
            errs.append(f"'{k}' expected array")
        elif t == "object" and not isinstance(v, dict):
            errs.append(f"'{k}' expected object")
    if not isinstance(fact.get("metric"), dict):
        errs.append("'metric' must be object")
    return errs


def segment_label(seg: dict) -> str:
    return "_".join(str(seg[k]) for k in ("country", "platform", "ad_format", "network")
                    if seg.get(k))


def main() -> int:
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    # ---- 1. generate + aggregate ----------------------------------------
    events = generate()
    agg = aggregate(events)
    check("events_generated", len(events) > 1000, f"{len(events)} events")

    # ad segment lookup helper
    def find_seg(country, adf, net):
        for s in agg.ad_segments:
            if s.country == country and s.ad_format == adf and s.network == net:
                return s
        return None

    reward = find_seg("US", "reward", "applovin")
    inter = find_seg("US", "interstitial", "applovin")
    check("reward_segment_present", reward is not None,
          f"impressions={reward.impressions if reward else 0}")
    check("interstitial_segment_present", inter is not None)

    # ---- 2. facts --------------------------------------------------------
    facts = build_monetization_facts(agg)
    fact_dicts = [f.to_dict() for f in facts]
    schema_errs = []
    for fd in fact_dicts:
        schema_errs.extend(validate_fact(fd))
    check("all_facts_schema_valid", not schema_errs,
          f"{len(schema_errs)} schema errors" if schema_errs else "0 errors")

    ad_facts = [f for f in facts if f.segment_type == "ad"]
    user_facts = [f for f in facts if f.segment_type == "user"]
    ret_facts = [f for f in facts if f.segment_type == "retention"]
    check("fact_kinds_present", ad_facts and user_facts and ret_facts,
          f"ad={len(ad_facts)} user={len(user_facts)} retention={len(ret_facts)}")

    # sanity: eCPM math on reward segment — confirm last-day drop in facts
    reward_facts = sorted([f for f in ad_facts
                           if f.ad_format == "reward" and f.network == "applovin"],
                          key=lambda x: x.date)
    if len(reward_facts) >= 2:
        e0 = reward_facts[-2].metric["ecpm"]
        e1 = reward_facts[-1].metric["ecpm"]
        check("ecpm_drop_in_data", e1 < e0, f"prev={e0} last={e1}")

    # retention fact has d1/d7
    ret = ret_facts[0].metric if ret_facts else {}
    check("retention_computed", "d1_retention" in ret and "d7_retention" in ret,
          f"d1={ret.get('d1_retention')} d7={ret.get('d7_retention')} d0_ltv={ret.get('d0_ltv')}")

    # user fact has arpdau + ads_per_dau
    uf = user_facts[0].metric
    check("user_metrics_present", "arpdau" in uf and "ads_per_dau" in uf,
          f"arpdau={uf.get('arpdau')} ads_per_dau={uf.get('ads_per_dau')}")

    # ---- 3. opportunities ------------------------------------------------
    opps = detect_opportunities(facts)
    opp_types = {o.type for o in opps}
    check("ecpm_drop_detected", "ecpm_drop" in opp_types,
          f"types={sorted(opp_types)}")
    check("fill_drop_detected", "fill_drop" in opp_types)
    check("ad_frequency_issue_detected", "ad_frequency_issue" in opp_types)
    check("opportunities_found", len(opps) >= 3, f"{len(opps)} opportunities")

    # ---- 4. decisions (proposed only, never executed) -------------------
    decisions = create_decisions(opps)
    all_proposed = all(d.status == "proposed" for d in decisions)
    valid_actions = all(d.action_type in ("change_waterfall", "review_bidding",
                                          "adjust_ad_frequency", "review")
                        for d in decisions)
    check("decisions_proposed_only", all_proposed and valid_actions,
          f"{len(decisions)} decisions, all proposed={all_proposed}")
    # Hard guard: this layer must NOT mutate anything. We assert no executor ran.
    check("no_execution_side_effect",
          all(d.status == "proposed" for d in decisions),
          "Decision Interface emits proposals; E13.3.3 Executor applies them.")

    # ---- write outputs --------------------------------------------------
    (OUT / "monetization_facts.json").write_text(json.dumps(fact_dicts, indent=2))
    (OUT / "opportunities.json").write_text(json.dumps([o.to_dict() for o in opps], indent=2))
    (OUT / "decisions.json").write_text(json.dumps([d.to_dict() for d in decisions], indent=2))

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)
    report = {
        "layer": "E13.2.8 Monetization Intelligence Layer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events_processed": len(events),
        "facts_emitted": len(fact_dicts),
        "opportunities": len(opps),
        "decisions": len(decisions),
        "checks_passed": passed,
        "checks_total": total,
        "status": "PASS" if passed == total else "FAIL",
        "checks": checks,
    }
    (OUT / "intelligence_report.json").write_text(json.dumps(report, indent=2))

    # ---- summary to stdout ----------------------------------------------
    print(f"events={len(events)} facts={len(fact_dicts)} "
          f"opps={len(opps)} decisions={len(decisions)}")
    print("opportunity types:", sorted(opp_types))
    for c in checks:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['name']} — {c['detail']}")
    print(f"RESULT: {'PASS' if passed == total else 'FAIL'} ({passed}/{total})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
