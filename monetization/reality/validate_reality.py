"""
E13.3.1 — validate_reality.py
==============================

End-to-end run + self-check of the Monetization Reality Engine.

Pipeline:
  demo events (with traffic_source / user_cohort)
    -> GameEventStream.ingest  (continuous consumer)
    -> SegmentEngine.segment_aggregate
    -> FactBuilder.build_reality_facts
    -> MetricStore
    -> Opportunity Detector (E13.2.8) on base-grain facts

Checks (all must pass for EXIT 0):
  1. Demo events carry the two new dimensions
  2. Engine ingests + updates; daily + segment facts both emitted
  3. Every fact validates against the (extended) monetization_fact schema
  4. Segment facts carry real traffic_source + user_cohort values
  5. Opportunity input data is produced (E13.2.8 detectors fire)
  6. Continuous mode: incremental ingest + repeated update is stable
  7. MetricStore save/load round-trips

Writes (Lean, local files):
  monetization/reality/outputs/daily_facts.json
  monetization/reality/outputs/segment_facts.json
  monetization/reality/outputs/opportunities.json
  monetization/reality/outputs/reality_report.json
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from monetization.reality.demo_events import generate_demo            # noqa: E402
from monetization.reality.reality_engine import RealityEngine         # noqa: E402
from monetization.reality.metric_store import MetricStore             # noqa: E402

OUT = ROOT / "monetization" / "reality" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
SCHEMA = json.loads((ROOT / "schemas" / "monetization_fact.schema.json").read_text())


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
        if isinstance(t, list):
            ok = any(_matches(v, tt) for tt in t)
            if not ok:
                errs.append(f"'{k}' expected one of {t}")
        elif not _matches(v, t):
            errs.append(f"'{k}' expected {t}")
    if not isinstance(fact.get("metric"), dict):
        errs.append("'metric' must be object")
    return errs


def _matches(v, t: str) -> bool:
    if t == "string":
        return isinstance(v, str)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "array":
        return isinstance(v, list)
    if t == "object":
        return isinstance(v, dict)
    return True


def main() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    # ---- 1. demo events ------------------------------------------------
    events = generate_demo()
    with_dims = [e for e in events if e.get("traffic_source") and e.get("user_cohort")]
    check("demo_events_with_dimensions", len(with_dims) == len(events),
          f"{len(with_dims)}/{len(events)} carry traffic_source+user_cohort")
    ts_values = {e["traffic_source"] for e in events}
    coh_values = {e["user_cohort"] for e in events}
    check("traffic_source_values_present",
          {"facebook", "google", "organic"} <= ts_values,
          f"sources={sorted(ts_values)}")
    check("user_cohort_values_present",
          {"early", "late"} <= coh_values,
          f"cohorts={sorted(coh_values)}")

    # ---- 2. engine ingest + update -------------------------------------
    engine = RealityEngine()
    ingested = engine.ingest_batch(events)
    facts = engine.update()
    check("events_ingested", ingested == len(events), f"{ingested} ingested")
    check("facts_emitted", len(facts) > 0, f"{len(facts)} facts")

    daily = engine.daily_facts()
    seg = engine.segment_facts()
    check("daily_facts_present", len(daily) > 0, f"{len(daily)} daily facts")
    check("segment_facts_present", len(seg) > 0, f"{len(seg)} segment facts")

    # ---- 3. schema validity --------------------------------------------
    fact_dicts = [f.to_dict() for f in facts]
    schema_errs = []
    for fd in fact_dicts:
        schema_errs.extend(validate_fact(fd))
    check("all_facts_schema_valid", not schema_errs,
          f"{len(schema_errs)} schema errors" if schema_errs else "0 errors")

    # ---- 4. segment facts carry real dims ------------------------------
    seg_with_ts = [f for f in seg if f.traffic_source != "unknown"]
    seg_with_coh = [f for f in seg if f.user_cohort != "unknown"]
    check("segment_facts_have_traffic_source", len(seg_with_ts) > 0,
          f"{len(seg_with_ts)} have traffic_source")
    check("segment_facts_have_user_cohort", len(seg_with_coh) > 0,
          f"{len(seg_with_coh)} have user_cohort")
    # at least 2 distinct traffic sources sliced in segment facts
    seg_sources = {f.traffic_source for f in seg}
    check("multiple_traffic_source_segments", len(seg_sources - {"unknown"}) >= 2,
          f"sources={sorted(seg_sources)}")

    # ---- 5. opportunity input data (reuse E13.2.8 detector) -----------
    opps = engine.detect()
    opp_types = {o.type for o in opps}
    check("ecpm_drop_detected", "ecpm_drop" in opp_types, f"types={sorted(opp_types)}")
    check("fill_drop_detected", "fill_drop" in opp_types)
    check("ad_frequency_issue_detected", "ad_frequency_issue" in opp_types)
    check("opportunities_found", len(opps) >= 3, f"{len(opps)} opportunities")

    # ---- 6. continuous mode: incremental ingest + repeated update ------
    e2 = RealityEngine()
    half = len(events) // 2
    e2.ingest_batch(events[:half])
    f1 = e2.update()
    e2.ingest_batch(events[half:])
    f2 = e2.update()
    check("continuous_ingest_stable", len(f2) > 0 and len(f2) >= len(f1),
          f"after batch1={len(f1)} after batch2={len(f2)}")
    opps2 = e2.detect()
    check("continuous_detect_stable", any(o.type == "ecpm_drop" for o in opps2),
          f"{len(opps2)} opportunities after incremental ingest")

    # ---- 7. MetricStore save/load round-trip ---------------------------
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "store.json"
        engine.save(p)
        fresh = MetricStore()
        loaded = fresh.load(p)
        check("metricstore_roundtrip", loaded == engine.store.size(),
              f"saved={engine.store.size()} loaded={loaded}")

    # ---- write outputs -------------------------------------------------
    (OUT / "daily_facts.json").write_text(
        json.dumps([f.to_dict() for f in daily], indent=2))
    (OUT / "segment_facts.json").write_text(
        json.dumps([f.to_dict() for f in seg], indent=2))
    (OUT / "opportunities.json").write_text(
        json.dumps([o.to_dict() for o in opps], indent=2))

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)
    report = {
        "layer": "E13.3.1 Monetization Reality Engine",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events_processed": len(events),
        "facts_emitted": len(facts),
        "daily_facts": len(daily),
        "segment_facts": len(seg),
        "opportunities": len(opps),
        "checks_passed": passed,
        "checks_total": total,
        "status": "PASS" if passed == total else "FAIL",
        "checks": checks,
    }
    (OUT / "reality_report.json").write_text(json.dumps(report, indent=2))

    print(f"events={len(events)} facts={len(facts)} "
          f"daily={len(daily)} segment={len(seg)} opps={len(opps)}")
    print("opportunity types:", sorted(opp_types))
    for c in checks:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['name']} — {c['detail']}")
    print(f"RESULT: {'PASS' if passed == total else 'FAIL'} ({passed}/{total})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
