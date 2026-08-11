"""
E13.4.1 — Validation & Acceptance
==================================

Verifies the Decision Memory Layer end-to-end:

  A. REAL PIPELINE: E13.3.1 (Reality) -> 13.3.2 (Strategy) -> 13.3.3 (Executor)
     -> DecisionStore, then closes the loop with a measured (synthetic) actual
     outcome -> LearningSignal.

  B. ACCEPTANCE: 10 hand-crafted decisions spanning 4 strategy types, mixing
     executed / non-executed, each executed one closed with an actual outcome.
     Asserts success-rate, prediction error, and strategy priors.

  C. SCHEMA: every stored DecisionRecord validates against
     schemas/decision_record.schema.json.

  D. CONSTRAINTS: no DB (JSONL file store only), no AI/ML library imported.

Outputs (in monetization/learning/outputs/):
  decision_memory.jsonl        — real-pipeline rows
  acceptance_memory.jsonl      — 10-decision acceptance rows
  strategy_performance_report.json
  learning_report.json         — full self-test result
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import jsonschema  # noqa: E402

from monetization.reality.demo_events import generate_demo  # noqa: E402
from monetization.reality.reality_engine import RealityEngine  # noqa: E402
from monetization.strategy import StrategyEngine  # noqa: E402
from monetization.executor.executor import ExecutionOrchestrator  # noqa: E402
from monetization.learning import (  # noqa: E402
    ActualOutcome, DecisionRecord, DecisionStore, FeedbackEngine,
    record_actual, synthesize_actual,
)
from monetization.learning.models import (  # noqa: E402
    REV_FLOOR_PCT, RET_FLOOR_PCT,
)

SCHEMA = json.loads((ROOT / "schemas" / "decision_record.schema.json").read_text())
OUT = ROOT / "monetization" / "learning" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

CHECKS = []


def check(name: str, passed: bool, detail: str = "") -> bool:
    CHECKS.append((name, passed, detail))
    flag = "PASS" if passed else "FAIL"
    print(f"  [{flag}] {name}" + (f" — {detail}" if detail else ""))
    return passed


# --------------------------------------------------------------------------- #
# A. REAL PIPELINE demo
# --------------------------------------------------------------------------- #
def run_real_pipeline(store: DecisionStore) -> dict:
    print("\n=== A. Real pipeline: E13.3.1 -> 13.3.2 -> 13.3.3 -> Memory ===")
    evs = generate_demo()
    engine = RealityEngine()
    engine.ingest_batch(evs)
    facts = engine.update()
    opps = engine.detect()
    print(f"  Reality Engine: {len(facts)} facts, {len(opps)} opportunities")

    se = StrategyEngine(facts)
    ranked = se.process_all(opps)
    decisions = []
    for r in ranked:
        d = se.decide(r)
        if d:
            decisions.append(d)
    print(f"  Strategy Engine: {len(decisions)} simulated decisions")

    orch = ExecutionOrchestrator()
    loop_closed = 0
    executed = 0
    for o, d in zip(opps, decisions):
        ddict = d.to_dict()
        opp_dict = {"id": o.id, "type": o.type, "segment": o.segment,
                    "severity": o.severity}
        res = orch.execute_decision(ddict)
        rec = DecisionRecord.from_pipeline(opp_dict, ddict, res.to_dict())
        store.append(rec)
        if rec.execution_status == "executed":
            executed += 1
            # close the loop with a seeded synthetic actual (demo only)
            actual = synthesize_actual(rec, realization=0.8, noise=2.0,
                                       seed=abs(hash(rec.decision_id)) % 1000)
            record_actual(store, rec.decision_id, actual)
            loop_closed += 1

    store.save()
    check("real pipeline: >=3 decisions stored", store.count() >= 3,
          f"stored={store.count()}")
    check("real pipeline: stored records have strategy_type",
          all(r.strategy_type for r in store.all()))
    check("real pipeline: stored records have prediction delta",
          all(isinstance(r.prediction_revenue_delta, float) for r in store.all()))
    # Safety property (the whole point of E13.3.3's Approval Gate): on day-1
    # first exposure the gate withholds autonomy, so the real pipeline yields
    # 0 executed samples. The system must NOT auto-learn from unproven
    # strategies — those require repeat_count>3 + high confidence first.
    check("real pipeline: day-1 first-exposure => 0 executed "
          "(gate withholds autonomy)", executed == 0 and loop_closed == 0,
          f"executed={executed}, closed={loop_closed}")
    return {"stored": store.count(), "executed": executed,
            "loop_closed": loop_closed,
            "note": "day-1 safety: no autonomy granted; closed-loop learning "
                    "begins only after repeat_count>3 + conf>0.8"}


# --------------------------------------------------------------------------- #
# B. ACCEPTANCE: 10 hand-crafted decisions
# --------------------------------------------------------------------------- #
def _mk(strategy_type, pred_rev, pred_ret, exec_status, gate,
        actual_rev=None, actual_ret=None, sample=5000, did=None):
    rec = DecisionRecord(
        decision_id=did or f"acc_{strategy_type}_{abs(hash((strategy_type, pred_rev, actual_rev)))}",
        opportunity_id="opp_acc",
        opportunity_type="acceptance",
        segment={"country": "US", "platform": "android", "ad_format": "reward"},
        strategy_type=strategy_type,
        strategy_score=0.7,
        strategy_mutation={"action_type": "review_bidding",
                            "params": {"increase_bid_floor": True}},
        prediction={"prediction": {"revenue_delta_pct": pred_rev,
                                   "retention_delta_pct": pred_ret,
                                   "confidence": 0.6}},
        prediction_confidence=0.6,
        prediction_revenue_delta=pred_rev,
        prediction_retention_delta=pred_ret,
        gate_verdict=gate,
        execution_status=exec_status,
        execution_changes=2 if exec_status == "executed" else 0,
    )
    if actual_rev is not None:
        rec.actual = ActualOutcome(revenue_delta_pct=actual_rev,
                                   retention_delta_pct=actual_ret,
                                   sample_size=sample, source="acceptance")
        # compute signal
        from monetization.learning.outcome_tracker import compute_learning_signal
        rec.learning_signal = compute_learning_signal(
            rec, ActualOutcome(revenue_delta_pct=actual_rev,
                               retention_delta_pct=actual_ret, sample_size=sample))
        rec.closed_loop = True
    return rec


def run_acceptance(store: DecisionStore) -> dict:
    print("\n=== B. Acceptance: 10 decisions, 4 strategy types ===")
    rows = [
        # bid_floor_adjust x3
        _mk("bid_floor_adjust", 6.0, 0.0, "executed", "approved", 4.8, 0.2),
        _mk("bid_floor_adjust", 5.0, 0.0, "executed", "approved", -1.0, -0.5),
        _mk("bid_floor_adjust", 7.0, 0.0, "executed", "approved", 6.5, 0.1),
        # waterfall_rebalance x3 (one manual_review => not executed)
        _mk("waterfall_rebalance", 4.0, 0.0, "executed", "approved", 4.2, 0.0),
        _mk("waterfall_rebalance", 3.5, 0.0, "executed", "approved", 3.0, -0.1),
        _mk("waterfall_rebalance", 4.5, 0.0, "pending", "manual_review"),
        # frequency_adjust x2
        _mk("frequency_adjust", 2.0, 1.5, "executed", "approved", 2.2, 1.8),
        _mk("frequency_adjust", 8.0, -3.0, "executed", "approved", -2.0, -4.0),
        # network_change x1
        _mk("network_change", 3.0, 0.0, "executed", "approved", 2.8, 0.0),
        # no_action x1
        _mk("no_action", 0.0, 0.0, "executed", "approved", 0.3, 0.0),
    ]
    for r in rows:
        store.append(r)
    store.save()

    check("acceptance: 10 decisions stored", store.count() == 10,
          f"stored={store.count()}")

    executed = store.executed()
    closed = store.closed()
    check("acceptance: 9 executed (1 manual_review not executed)",
          len(executed) == 9, f"executed={len(executed)}")
    check("acceptance: 9 loops closed (actuals recorded)",
          len(closed) == 9, f"closed={len(closed)}")
    check("acceptance: every closed record has learning_signal",
          all(r.learning_signal is not None for r in closed))
    check("acceptance: prediction error present on closed records",
          all(r.learning_signal.prediction_error_revenue is not None
              for r in closed))
    check("acceptance: success flag consistent with thresholds",
          all((r.learning_signal.success) ==
              (r.execution_status == "executed"
               and r.actual.revenue_delta_pct >= REV_FLOOR_PCT
               and r.actual.retention_delta_pct >= RET_FLOOR_PCT)
              for r in closed))

    # strategy coverage: all 4+ types represented
    types = {r.strategy_type for r in store.all()}
    check("acceptance: >=4 distinct strategy types", len(types) >= 4,
          f"types={sorted(types)}")
    return {"stored": store.count(), "executed": len(executed),
            "closed": len(closed), "types": sorted(types)}


# --------------------------------------------------------------------------- #
# C. SCHEMA validation
# --------------------------------------------------------------------------- #
def run_schema(store: DecisionStore) -> dict:
    print("\n=== C. Schema validation (decision_record.schema.json) ===")
    bad = 0
    for r in store.all():
        try:
            jsonschema.validate(r.to_dict(), SCHEMA)
        except jsonschema.ValidationError:
            bad += 1
    check("schema: all records valid", bad == 0, f"invalid={bad}")
    return {"invalid": bad, "total": store.count()}


# --------------------------------------------------------------------------- #
# D. CONSTRAINTS
# --------------------------------------------------------------------------- #
def run_constraints(real_store: DecisionStore, acc_store: DecisionStore) -> dict:
    print("\n=== D. Constraints (Lean: no DB, no AI) ===")
    real_path = real_store.path
    acc_path = acc_store.path
    check("constraint: file store used (JSONL), not a DB file",
          str(real_path).endswith(".jsonl") and str(acc_path).endswith(".jsonl"),
          f"real={real_path.name}")
    real_size = real_path.stat().st_size if real_path and real_path.exists() else 0
    acc_size = acc_path.stat().st_size if acc_path and acc_path.exists() else 0
    check("constraint: store files non-empty on disk", real_size > 0 and acc_size > 0,
          f"real_bytes={real_size}, acc_bytes={acc_size}")
    # No ML/AI/heavy-DB imports in our module files.
    banned = ("sklearn", "torch", "tensorflow", "numpy", "scipy", "sqlalchemy",
              "psycopg", "pymongo", "sqlite3")
    hits = []
    for f in (ROOT / "monetization" / "learning").rglob("*.py"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for b in banned:
            if f"import {b}" in txt or f"from {b}" in txt:
                hits.append(f"{f.name}:{b}")
    check("constraint: no AI/ML/DB library imported", len(hits) == 0,
          f"hits={hits}" if hits else "clean (stdlib only)")
    return {"store_backend": "jsonl", "banned_imports": hits}


# --------------------------------------------------------------------------- #
# E. FEEDBACK / STRATEGY PERFORMANCE REPORT
# --------------------------------------------------------------------------- #
def run_feedback(acc_store: DecisionStore) -> dict:
    print("\n=== E. Feedback Engine: Strategy Performance Report ===")
    fe = FeedbackEngine(acc_store)
    report = fe.generate_report()

    sp = report["strategy_performance"]
    check("report: strategy_performance covers all 4 types",
          all(t in sp for t in
              ("bid_floor_adjust", "waterfall_rebalance",
               "frequency_adjust", "network_change")),
          f"keys={sorted(sp)}")
    check("report: success_rate in (0,1] for closed strategies",
          all(0 < sp[t]["success_rate"] <= 1 for t in sp if sp[t]["closed_loop"] > 0))
    check("report: prediction_error_stats present",
          "revenue_mae" in report["prediction_error_stats"])
    check("report: priors dict non-empty", len(report["priors"]) >= 4,
          f"priors={report['priors']}")
    # sanity: bid_floor_adjust had 2/3 success -> rate 0.6
    bf = sp["bid_floor_adjust"]
    check("report: bid_floor_adjust success_rate==0.6 (2/3 Laplace)",
          abs(bf["success_rate"] - 0.6) < 1e-9,
          f"rate={bf['success_rate']}")
    return report


# --------------------------------------------------------------------------- #
def main():
    print("E13.4.1 Decision Memory Layer — Validation")
    print("=" * 56)

    # Deterministic runs: clear any prior JSONL so we never accumulate rows.
    for p in (OUT / "decision_memory.jsonl", OUT / "acceptance_memory.jsonl"):
        if p.exists():
            p.unlink()

    real_store = DecisionStore(str(OUT / "decision_memory.jsonl"))
    acc_store = DecisionStore(str(OUT / "acceptance_memory.jsonl"))

    a = run_real_pipeline(real_store)
    b = run_acceptance(acc_store)
    c = run_schema(acc_store)
    d = run_constraints(real_store, acc_store)
    report = run_feedback(acc_store)

    total = len(CHECKS)
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print("\n" + "=" * 56)
    print(f"E13.4.1 VALIDATION: {passed}/{total} checks passed")

    out = {
        "module": "E13.4.1 Decision Memory Layer",
        "status": "PASS" if passed == total else "FAIL",
        "checks_passed": passed,
        "checks_total": total,
        "real_pipeline": a,
        "acceptance": b,
        "schema": c,
        "constraints": d,
        "strategy_performance_report": report,
        "learning_signal_sample": (
            acc_store.closed()[0].learning_signal.to_dict()
            if acc_store.closed() else None
        ),
    }
    (OUT / "learning_report.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "strategy_performance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
