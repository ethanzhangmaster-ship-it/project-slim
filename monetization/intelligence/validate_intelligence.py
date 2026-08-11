"""
E13.4.3 — Validation: Strategy Intelligence Layer
=================================================

Acceptance criteria verified:
  A. Synthetic Memory      — generate 1000 closed-loop DecisionRecords
                              (700 success / 300 fail), Lean, no ML.
  B. Strategy Prior        — Bayesian Beta(α=wins+1, β=losses+1); priors
                              differ across strategies (the system learned).
  C. Calibration 生效       — deterministic factor + memory-based: applying
                              the learned correction pulls predictions toward
                              reality (aggregate error drops to ~0).
  D. Feature Builder       — Opportunity -> StrategyFeature with prior map.
  E. Strategy Ranking      — new Opportunity(US Reward eCPM drop) -> Top3
                              Strategy Probability, ordered, in [0,1], and the
                              historical prior actually influences the rank.
  F. Lightweight Model     — bucketed Laplace P(win) estimator, trains on the
                              1000 records, predicts per-candidate in [0,1].
  G. Architecture          — only stdlib; no sklearn/torch/openai/LLM etc.

Run from the launchforge root (or anywhere; sys.path is self-contained):
    python monetization/intelligence/validate_intelligence.py
Exit code 0 = all checks passed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from monetization.learning.decision_store import DecisionStore
from monetization.intelligence import (
    StrategyPriorEngine, SimulatorCalibrator, StrategyRanker,
    V1_WEIGHTS, EVOLVED_WEIGHTS, LightweightModel,
)
from monetization.intelligence.calibration import param_key
from monetization.intelligence.synthetic_memory import generate, save

OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# tiny test harness
# --------------------------------------------------------------------------- #
_PASSED, _FAILED = 0, 0
_REPORT = {}


def check(name: str, cond: bool, detail: str = "") -> bool:
    global _PASSED, _FAILED
    if cond:
        _PASSED += 1
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        _FAILED += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))
    return cond


# --------------------------------------------------------------------------- #
# A. Synthetic Memory (1000)
# --------------------------------------------------------------------------- #
print("\n=== A. Synthetic Memory (1000) ===")
recs = generate(1000, seed=42, success_target=700)
store = DecisionStore()
store._records.extend(recs)
store._by_id = {r.decision_id: r for r in recs}

check("generated 1000 records", len(recs) == 1000, f"n={len(recs)}")
check("all closed-loop (actual+signal present)",
      all(r.closed_loop and r.actual and r.learning_signal for r in recs))
n_succ = sum(1 for r in recs if r.learning_signal.success)
n_fail = len(recs) - n_succ
check("exactly 700 successes / 300 fails", n_succ == 700 and n_fail == 300,
      f"success={n_succ} fail={n_fail}")
check("store count == 1000", store.count() == 1000)
check("strategy types span the rule table",
      len({r.strategy_type for r in recs}) >= 5)
mem_path = save(recs, OUT / "memory_1000.jsonl")
check("memory persisted to JSONL", mem_path.exists())

# --------------------------------------------------------------------------- #
# B. Strategy Prior (Bayesian Beta)
# --------------------------------------------------------------------------- #
print("\n=== B. Strategy Prior (Bayesian Beta) ===")
prior = StrategyPriorEngine().learn_from_store(store)
priors = prior.all_priors()
check("built priors for >=5 strategies", len(priors) >= 5)
# Beta mean formula: (wins+1)/(wins+losses+2)
sample = prior.prior("bid_floor_adjust")
w, l = sample["wins"], sample["losses"]
# alpha = wins+1, beta = losses+1; the stored mean is rounded to 4 dp.
expected_mean = sample["alpha"] / (sample["alpha"] + sample["beta"])
check("Beta mean == alpha/(alpha+beta) with alpha=wins+1, beta=losses+1",
      abs(sample["mean"] - expected_mean) < 1e-3
      and sample["alpha"] == w + 1 and sample["beta"] == l + 1,
      f"mean={sample['mean']} expected={expected_mean:.4f} (w={w}, l={l})")
# priors must differ across strategies (the whole point of learning)
means = [p["mean"] for p in priors]
check("priors differ across strategies (learned, not flat)",
      max(means) - min(means) > 0.05,
      f"spread={round(max(means)-min(means), 3)}")
check("all prior means in (0,1)", all(0.0 < m < 1.0 for m in means))
_REPORT["priors"] = priors

# --------------------------------------------------------------------------- #
# C. Calibration 生效
# --------------------------------------------------------------------------- #
print("\n=== C. Simulator Calibration ===")
# C1: deterministic, clean correction factor
cal_clean = SimulatorCalibrator()
for _ in range(10):
    cal_clean.record("bid_floor_adjust", "review_bidding", "review_bidding:20",
                     predicted_delta=10.0, actual_delta=4.0)   # factor -> 0.4
f = cal_clean.factor("bid_floor_adjust", "review_bidding:20")
check("clean correction factor == 0.4", abs(f - 0.4) < 1e-9, f"factor={f}")
check("apply() multiplies predicted by correction",
      abs(cal_clean.apply("bid_floor_adjust", "review_bidding:20", 10.0) - 4.0) < 1e-9)
check("no-data calibrator leaves prediction unchanged",
      abs(SimulatorCalibrator().apply("x", "p", 7.0) - 7.0) < 1e-9)

# C2: learn from the 1000-record memory (systematic over-prediction present)
cal = SimulatorCalibrator().learn_from_store(store)
factors = cal.factors()
check("learned >=1 calibration factor from memory", len(factors) >= 1,
      f"n_factors={len(factors)}")
dom = max(factors, key=lambda x: x.samples)
st, pkey = dom.key.split("|", 1)
check("dominant factor shows systematic over-prediction (correction < 1.0)",
      0.3 <= dom.correction < 1.0, f"correction={dom.correction} samples={dom.samples}")
# aggregate: applying correction to the bucket mean prediction == mean actual
bucket = [r for r in store.closed()
          if r.strategy_type == st and param_key(r.strategy_mutation) == pkey]
mean_pred = sum(r.prediction_revenue_delta for r in bucket) / len(bucket)
mean_act = sum(r.actual.revenue_delta_pct for r in bucket) / len(bucket)
raw_err = abs(mean_act - mean_pred)
cal_pred = mean_pred * dom.correction
cal_err = abs(mean_act - cal_pred)
check("calibration reduces aggregate prediction error",
      cal_err < raw_err * 0.9, f"raw_err={round(raw_err,3)} cal_err={round(cal_err,3)}")
_REPORT["dominant_calibration"] = dom.to_dict()
_REPORT["calibration_factors"] = [x.to_dict() for x in factors]

# --------------------------------------------------------------------------- #
# D. Feature Builder
# --------------------------------------------------------------------------- #
print("\n=== D. Feature Builder ===")
new_opp = {
    "id": "opp_us_ecpm", "type": "ecpm_drop",
    "segment": {"country": "US", "platform": "android", "ad_format": "reward"},
    "metrics": {"ecpm": 12.5, "fill_rate": 0.92, "d1_retention_pct": 42.0},
}
from monetization.intelligence.feature_builder import build_feature
feat = build_feature(new_opp, "bid_floor_adjust", prior)
fd = feat.to_dict()
check("feature carries segment + metrics",
      fd["segment"].get("country") == "US" and fd["current_ecpm"] == 12.5)
check("feature carries history_success_rate map",
      isinstance(fd["history_success_rate"], dict) and len(fd["history_success_rate"]) >= 5)
check("feature prior_mean in (0,1)",
      0.0 < fd["prior_mean"] < 1.0, f"prior_mean={fd['prior_mean']}")
check("feature carries rule prior",
      fd["rule_expected_effect"] != "" and 0.0 < fd["rule_confidence"] <= 1.0)

# --------------------------------------------------------------------------- #
# E. Strategy Ranking / Top3
# --------------------------------------------------------------------------- #
print("\n=== E. Strategy Ranking (Top3) ===")
ranker = StrategyRanker(prior_engine=prior, calibrator=cal, store=store)
result = ranker.rank(new_opp, top_n=3)
res_d = result.to_dict()
check("ecpm_drop yields exactly 3 candidates", len(res_d["ranked"]) == 3,
      f"n={len(res_d['ranked'])}")
probs = [r["probability"] for r in res_d["ranked"]]
check("probabilities are sorted descending", probs == sorted(probs, reverse=True))
check("all probabilities in [0,1]", all(0.0 <= p <= 1.0 for p in probs))
check("top probability is the max", res_d["top"]["probability"] == max(probs))
cand_set = {"waterfall_change", "bid_floor_adjust", "network_test"}
check("top strategy is an ecpm_drop candidate",
      res_d["top"]["strategy_type"] in cand_set,
      f"top={res_d['top']['strategy_type']} p={res_d['top']['probability']}")
# historical prior actually influences the rank (vary the prior)
ranker_no_prior = StrategyRanker(prior_engine=StrategyPriorEngine(),
                                 calibrator=cal, store=store)
res_no = ranker_no_prior.rank(new_opp, top_n=3).to_dict()
priors_used = [r["historical_prior"] for r in res_d["ranked"]]
check("historical prior varies across candidates (used by ranker)",
      len(set(round(p, 4) for p in priors_used)) >= 2,
      f"priors={[round(p,3) for p in priors_used]}")
check("prior+history ranking differs from no-prior baseline",
      res_d["ranked"][0]["strategy_type"] != res_no["ranked"][0]["strategy_type"]
      or res_d["ranked"][0]["probability"] != res_no["ranked"][0]["probability"])
_REPORT["top3"] = res_d["ranked"][:3]
_REPORT["new_opportunity"] = new_opp

# evolved formula still runs and uses experiment evidence
ev = ranker.rank(new_opp, top_n=3, weights=EVOLVED_WEIGHTS)
check("evolved fusion runs and returns ranked list",
      len(ev.ranked) == 3 and all(0.0 <= r["probability"] <= 1.0 for r in ev.ranked))

# --------------------------------------------------------------------------- #
# F. Lightweight Model (optional)
# --------------------------------------------------------------------------- #
print("\n=== F. Lightweight Model ===")
lm = LightweightModel().train(store)
lm_probs = lm.predict_all(new_opp["type"], new_opp["segment"],
                          [r["strategy_type"] for r in res_d["ranked"]])
check("lightweight predicts P(win) in [0,1] for all candidates",
      all(0.0 <= v <= 1.0 for v in lm_probs.values()), str(lm_probs))
check("lightweight output covers the candidate set",
      set(lm_probs.keys()) == cand_set)
top_lm = max(lm_probs, key=lm_probs.get)
check("lightweight top pick is among the ranked candidates", top_lm in cand_set,
      f"top_lm={top_lm} ({lm_probs[top_lm]})")
_REPORT["lightweight_p_win"] = lm_probs

# --------------------------------------------------------------------------- #
# G. Architecture compliance (Lean / no external AI-ML libs)
# --------------------------------------------------------------------------- #
print("\n=== G. Architecture Compliance ===")
FORBIDDEN = ("sklearn", "tensorflow", "torch", "openai", "anthropic",
             "xgboost", "lightgbm", "numpy", "langchain")
intel_dir = Path(__file__).resolve().parent
violations = []
for py in intel_dir.glob("*.py"):
    for line in py.read_text(encoding="utf-8").splitlines():
        s = line.strip().lower()
        # Only flag ACTUAL import statements, not docstring mentions of these
        # names as future upgrade targets.
        if s.startswith("import ") or s.startswith("from "):
            for bad in FORBIDDEN:
                if bad in s:
                    violations.append(f"{py.name}: line '{line.strip()}'")
check("no forbidden external AI/ML imports in intelligence layer",
      len(violations) == 0, "; ".join(violations) if violations else "clean")
check("module imports resolve (prior/calibrator/ranker/model present)",
      all([StrategyPriorEngine, SimulatorCalibrator, StrategyRanker, LightweightModel]))

# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
_REPORT["summary"] = {
    "records": len(recs), "successes": n_succ, "fails": n_fail,
    "prior_strategies": len(priors),
    "calibration_factors": len(factors),
    "top1_strategy": res_d["top"]["strategy_type"],
    "top1_probability": res_d["top"]["probability"],
    "passed": _PASSED, "failed": _FAILED,
}
with (OUT / "intelligence_report.json").open("w", encoding="utf-8") as fh:
    json.dump(_REPORT, fh, ensure_ascii=False, indent=2)

print(f"\n=== RESULT: {_PASSED} passed, {_FAILED} failed ===")
print(f"Report: {OUT / 'intelligence_report.json'}")
sys.exit(1 if _FAILED else 0)
