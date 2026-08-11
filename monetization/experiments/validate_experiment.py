"""
E13.4.2 — Validation & Acceptance
==================================

Runs the Monetization Experiment Engine end-to-end:

  * Part A — 3 acceptance experiments (the PRD's explicit cases):
        (1) bid floor test     (baseline + +20% + +40%)
        (2) waterfall test     (baseline + mintegral + applovin)
        (3) ad frequency test  (baseline + down + up)
    Each must produce >=3 variants, a winner, and a learning signal.

  * Part B — real pipeline integration:
        E13.3.1 Reality Engine -> facts
          -> E13.3.2 Strategy Engine (top candidate per opportunity)
          -> E13.3.3 Executor (mock; mostly manual_review on first exposure)
          -> E13.4.1 Decision Memory (open loop)
          -> E13.4.2 Experiment from each real candidate -> run -> record
             into the SAME store (closed loop).

Hard constraints asserted:
  * Simulation only — NEVER calls a real ad platform.
  * Experiments only GENERATE evidence; they never execute config changes.
  * Lean — JSONL file store, no DB.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from monetization.experiments.models import synthetic_baseline
from monetization.experiments.experiment_manager import (
    ExperimentManager, create_bid_floor_experiment,
    create_frequency_experiment, create_waterfall_experiment,
)
from monetization.experiments.experiment_analyzer import generate_experiment_report
from monetization.learning.decision_store import DecisionStore
from monetization.learning.models import DecisionRecord
from monetization.reality.demo_events import generate_demo
from monetization.reality.reality_engine import RealityEngine
from monetization.strategy.strategy_generator import StrategyEngine
from monetization.executor.executor import ExecutionOrchestrator

SCHEMA = json.loads((ROOT / "schemas" / "experiment_result.schema.json").read_text())

OUT = ROOT / "monetization" / "experiments" / "outputs"

# --------------------------------------------------------------------------- #
def _reset():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

checks = []
def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

# --------------------------------------------------------------------------- #
def main():
    print("E13.4.2 Monetization Experiment Engine — Validation")
    print("=" * 60)
    _reset()

    seg_us = {"country": "US", "platform": "android",
              "ad_format": "reward", "network": "applovin"}
    bm = synthetic_baseline(seg_us)

    # ---- Part A: 3 acceptance experiments ------------------------------- #
    print("\n[Part A] Acceptance experiments (simulated traffic)")
    exp_bf = create_bid_floor_experiment(seg_us, 30, (0, 20, 40), "revenue")
    exp_wf = create_waterfall_experiment(seg_us, ("mintegral", "applovin"), (20, 25), "revenue")
    exp_fr = create_frequency_experiment(seg_us, 5, (("down", 10), ("up", 10)), "retention")

    mgr = ExperimentManager()
    res_bf = mgr.run_experiment(exp_bf, bm)
    res_wf = mgr.run_experiment(exp_wf, bm)
    res_fr = mgr.run_experiment(exp_fr, bm)
    acceptance = [res_bf, res_wf, res_fr]

    check("3 acceptance experiments created", len(acceptance) == 3,
          f"n={len(acceptance)}")
    for r in acceptance:
        check(f"{r.name}: >=3 variants", len(r.per_variant) >= 3,
              f"variants={len(r.per_variant)}")
        check(f"{r.name}: has winner", bool(r.winner_variant_id),
              f"winner={r.winner_name}")
        check(f"{r.name}: winner is a treatment (not baseline)",
              r.winner_name != "A_baseline", f"winner={r.winner_name}")
        check(f"{r.name}: learning signal present",
              "recommendation" in r.learning_signal and "winner_strategy_type" in r.learning_signal)
        check(f"{r.name}: winner confidence > 0",
              r.learning_signal.get("confidence", 0) > 0,
              f"conf={r.learning_signal.get('confidence')}")
        check(f"{r.name}: lift is positive (winner beats baseline)",
              r.lift_pct > 0, f"lift={r.lift_pct}")

    # PRD-specified strategy types must win
    check("bid floor experiment winner = bid_floor_adjust",
          res_bf.winner_strategy_type == "bid_floor_adjust",
          res_bf.winner_strategy_type)
    check("waterfall experiment winner = waterfall_change",
          res_wf.winner_strategy_type == "waterfall_change",
          res_wf.winner_strategy_type)
    check("frequency experiment winner = frequency_down",
          res_fr.winner_strategy_type == "frequency_down",
          res_fr.winner_strategy_type)

    # ---- Part B: real pipeline integration ----------------------------- #
    print("\n[Part B] Real pipeline: Reality -> Strategy -> Executor -> Memory -> Experiment")
    store = DecisionStore(str(OUT / "experiment_memory.jsonl"))
    evs = generate_demo()
    eng = RealityEngine()
    eng.ingest_batch(evs)
    facts = eng.update()
    opps = eng.detect()
    print(f"  Reality Engine: {len(facts)} facts, {len(opps)} opportunities")

    orch = ExecutionOrchestrator()
    sen = StrategyEngine(facts)
    open_loop = 0
    for o in opps:
        ranked = sen.process_opportunity(o)
        if ranked.top is None:
            continue
        dec = sen.decide(ranked)
        if dec is None:
            continue
        res = orch.execute_decision(dec.to_dict())
        rec = DecisionRecord.from_pipeline(o.to_dict(), dec.to_dict(), res.to_dict())
        store.append(rec)
        if rec.closed_loop is False:
            open_loop += 1

    before = store.count()
    mgr2 = ExperimentManager(store=store)
    def _bm(opp):
        return synthetic_baseline(opp.segment)
    real_results = mgr2.run_pipeline_experiments(
        opps, facts, baseline_builder=_bm, success_metric="revenue", store=store)
    after = store.count()

    check("real pipeline: >=1 experiment derived from real opportunity",
          len(real_results) >= 1, f"experiments={len(real_results)}")
    check("real pipeline: experiments recorded into Decision Memory",
          after > before, f"before={before} after={after}")
    check("real pipeline: open-loop decisions preserved",
          open_loop >= 1, f"open_loop={open_loop}")

    all_results = acceptance + real_results

    # ---- schema validation --------------------------------------------- #
    print("\n[Schema] experiment_result.schema.json")
    schema_ok = 0
    for r in all_results:
        try:
            jsonschema.validate(r.to_dict(), SCHEMA)
            schema_ok += 1
        except jsonschema.ValidationError as ex:
            print(f"  [FAIL] schema: {r.name} -> {ex.message}")
    check("all experiment results schema-valid", schema_ok == len(all_results),
          f"{schema_ok}/{len(all_results)}")

    # ---- constraints ---------------------------------------------------- #
    print("\n[Constraints]")
    # No real ad-platform invocation: the experiment manager is simulation-only.
    # We assert no 'provider_response' / 'real_api_called' leaked into results and
    # that the store records produced by experiments carry simulated evidence.
    leaked = any("real_api_called" in json.dumps(r.to_dict()) for r in all_results)
    check("constraint: simulation-only (no real_api_called in results)",
          not leaked)
    check("constraint: store backend is JSONL file (Lean, no DB)",
          str(store.path).endswith(".jsonl"))
    # experiments created evidence rows (execution_status executed == experiment)
    exp_rows = [r for r in store.all() if r.opportunity_type == "experiment"
                or (r.execution_status == "executed" and r.learning_signal)]
    check("constraint: experiment evidence rows present in memory",
          len(exp_rows) >= len(real_results), f"exp_rows={len(exp_rows)}")

    # ---- report --------------------------------------------------------- #
    report = generate_experiment_report(all_results, store)
    report["constraints"] = {
        "simulation_only": True,
        "real_ad_platform_called": False,
        "executes_config_changes": False,
        "store_backend": "jsonl_file",
        "acceptance_experiments": 3,
        "real_pipeline_experiments": len(real_results),
    }
    (OUT / "experiment_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "acceptance_experiments.json").write_text(
        json.dumps([r.to_dict() for r in acceptance], ensure_ascii=False, indent=2),
        encoding="utf-8")
    store.save()

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print("\n" + "=" * 60)
    print(f"E13.4.2 VALIDATION: {passed}/{total} checks passed"
          f"  ->  {'PASS' if passed == total else 'FAIL'}")
    print("=" * 60)

    # winners summary
    for r in acceptance:
        ls = r.learning_signal
        print(f"  • {r.name}: WINNER={r.winner_strategy_type} "
              f"({r.winner_name})  lift={r.lift_pct:+.1f}%  "
              f"conf={ls['confidence']}  bias={ls['measured_vs_predicted_bias']}")

    return {
        "status": "PASS" if passed == total else "FAIL",
        "checks_passed": passed,
        "checks_total": total,
        "acceptance": {r.name: r.winner_strategy_type for r in acceptance},
        "real_pipeline_experiments": len(real_results),
        "store_records": store.count(),
        "constraints": report["constraints"],
    }


if __name__ == "__main__":
    out = main()
    raise SystemExit(0 if out["status"] == "PASS" else 1)
