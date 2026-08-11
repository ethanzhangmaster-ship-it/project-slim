"""
E13.4.3 — Synthetic 1000-Decision Memory Generator
===================================================

Generates a realistic closed-loop DecisionRecord corpus for the E13.4.3
acceptance test (1000 records, 700 success / 300 fail). Pure-Python.

The corpus is the "operating history" the Intelligence Layer learns from:
  * candidates are drawn from the real E13.3.2 RULES (so strategy types are
    consistent with the live system);
  * predictions come from the real E13.2.9 Simulator;
  * a **systematic bias** is injected (REALIZATION = 0.6) so the Simulator
    over-predicts revenue -> the Calibration module has something real to learn.

All records are closed-loop (actual outcome + learning signal already filled)
so the Strategy Prior and Calibrator can be trained immediately.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

from simulation.strategy_simulator import simulate_strategy
from monetization.strategy.strategy_rules import RULES, candidate_specs
from monetization.learning.models import (
    DecisionRecord, ActualOutcome, LearningSignal, new_id,
)


COUNTRIES = ["US", "JP", "DE", "BR", "IN"]
PLATFORMS = ["android", "ios"]
AD_FORMATS = ["reward", "interstitial"]
NETWORKS = ["applovin", "mintegral", "ironsource", "admob"]
OPP_TYPES = list(RULES.keys())

# Simulator over-predicts revenue by 40% in this synthetic world
# (calibration should learn a correction ~0.6).
REALIZATION = 0.6

# Per-strategy base success rate (averages ~0.7 overall).
BASE_RATE = {
    "bid_floor_adjust": 0.80, "waterfall_change": 0.62, "network_test": 0.55,
    "backup_network": 0.60, "floor_down": 0.58, "frequency_down": 0.72,
    "reward_cooldown": 0.68, "monetization_aggressive": 0.50, "no_action": 0.90,
}


def _param_key(mutation) -> str:
    m = mutation or {}
    at = m.get("action_type") or ""
    params = m.get("params", {}) or {}
    if at == "review_bidding" and m.get("increase_bid_floor"):
        mag = params.get("bid_floor_pct")
    elif at in ("change_waterfall", "review_bidding", "adjust_ad_frequency"):
        mag = params.get("magnitude_pct")
    else:
        mag = None
    return f"{at}:{round(float(mag))}" if mag is not None else (at or "unknown")


def _metrics_for() -> dict:
    return {
        "ecpm": random.uniform(8, 18),
        "fill_rate": random.uniform(0.70, 0.95),
        "impressions": random.randint(20000, 80000),
        "dau": random.randint(2000, 10000),
        "ads_per_dau": random.uniform(4, 8),
        "d1_retention_pct": random.uniform(35, 50),
    }


def generate(n: int = 1000, seed: int = 42,
             success_target: int = 700) -> List[DecisionRecord]:
    """Generate `n` closed-loop DecisionRecords with exactly `success_target`
    successes (rest are failures)."""
    random.seed(seed)
    recs: List[DecisionRecord] = []

    for _ in range(n):
        opp_type = random.choice(OPP_TYPES)
        seg = {
            "country": random.choice(COUNTRIES),
            "platform": random.choice(PLATFORMS),
            "ad_format": random.choice(AD_FORMATS),
            "network": random.choice(NETWORKS),
        }
        spec = random.choice(candidate_specs(opp_type))
        st = spec["strategy_type"]
        mut = spec["mutation"]
        metrics = _metrics_for()
        target = "_".join(str(seg[k]) for k in
                          ("country", "platform", "ad_format", "network"))
        pred = simulate_strategy(
            mut.get("action_type") or "", mut.get("params", {}) or {}, metrics,
            target=target, decision_id=new_id()).to_dict()
        pred_rev = float(pred["prediction"]["revenue_delta_pct"])
        pred_ret = float(pred["prediction"]["retention_delta_pct"])

        is_success = random.random() < BASE_RATE.get(st, 0.65)

        if is_success:
            actual_rev = max(0.4, pred_rev * REALIZATION + random.uniform(-0.4, 0.8))
            actual_ret = max(-0.9, pred_ret * 0.9 + random.uniform(-0.5, 0.5))
        else:
            if random.random() < 0.5:
                actual_rev = pred_rev * 0.3 - random.uniform(0.5, 3.0)
            else:
                actual_rev = max(-2.0, pred_rev * REALIZATION * 0.5)
            actual_ret = pred_ret - random.uniform(1.5, 4.0)   # retention harmed

        actual = ActualOutcome(
            revenue_delta_pct=round(actual_rev, 3),
            retention_delta_pct=round(actual_ret, 3),
            sample_size=random.randint(500, 5000),
            source="synthetic_memory",
        )
        pe_rev = round(actual_rev - pred_rev, 3)
        success = (actual_rev >= 0.0) and (actual_ret >= -1.0)
        signal = LearningSignal(
            prediction_error_revenue=pe_rev,
            prediction_error_retention=round(actual_ret - pred_ret, 3),
            revenue_bias=pe_rev,
            success=success,
            slack=round(actual_rev, 3),
        )
        recs.append(DecisionRecord(
            decision_id=new_id(),
            opportunity_id=new_id("opp"),
            opportunity_type=opp_type,
            segment=seg,
            strategy_type=st,
            strategy_score=round(random.uniform(0.5, 0.9), 3),
            strategy_mutation=mut,
            prediction=pred,
            prediction_confidence=float(pred["prediction"]["confidence"]),
            prediction_revenue_delta=pred_rev,
            prediction_retention_delta=pred_ret,
            gate_verdict="approved",
            execution_status="executed",
            execution_changes=random.randint(1, 3),
            actual=actual,
            learning_signal=signal,
            closed_loop=True,
        ))

    # ---- force exactly `success_target` successes ----
    succ = [r for r in recs if r.learning_signal.success]
    fail = [r for r in recs if not r.learning_signal.success]
    diff = success_target - len(succ)
    diff = max(-len(succ), min(len(fail), diff))   # clamp to available
    if diff > 0:
        for r in fail[:diff]:
            r.actual.revenue_delta_pct = max(0.5, abs(r.actual.revenue_delta_pct))
            r.actual.retention_delta_pct = max(-0.9, r.actual.retention_delta_pct)
            r.learning_signal.success = True
            r.learning_signal.prediction_error_revenue = round(
                r.actual.revenue_delta_pct - r.prediction_revenue_delta, 3)
            r.learning_signal.revenue_bias = r.learning_signal.prediction_error_revenue
            r.learning_signal.slack = r.actual.revenue_delta_pct
    elif diff < 0:
        for r in succ[:-diff]:
            r.actual.revenue_delta_pct = -abs(r.actual.revenue_delta_pct) - 1.0
            r.actual.retention_delta_pct = -2.0
            r.learning_signal.success = False
            r.learning_signal.prediction_error_revenue = round(
                r.actual.revenue_delta_pct - r.prediction_revenue_delta, 3)
            r.learning_signal.revenue_bias = r.learning_signal.prediction_error_revenue
            r.learning_signal.slack = r.actual.revenue_delta_pct
    return recs


def save(recs: List[DecisionRecord], path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    return path
