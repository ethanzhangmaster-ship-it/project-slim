"""
E13.4.4 — Validation: Autonomous Monetization Agent
====================================================

Three acceptance tiers:

  Tier A (deterministic Policy cases — the 3 user cases)
    Case 1: repeated success strategy (prior 0.9)         -> execute
    Case 2: unknown strategy (0 samples)                  -> experiment (NEVER execute)
    Case 3: high retention risk                          -> block

  Tier B (30-day autonomous simulation)
    100 opportunities across 30 days -> the agent must:
      * never directly execute an unknown strategy
      * auto-execute low-risk known-good strategies
      * auto-block high-risk strategies
      * run experiments for unknown strategies
      * learn (prior improves over the run)

  Tier C (no-LLM / no-external-API compliance)
    the agent source contains no forbidden imports.

Hard constraints honoured: pure-Python Lean, no LLM, no MAX/LevelPlay/RC API.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

# Make the launchforge project root importable when run as a script.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.agent.controller import MonetizationAgent
from monetization.agent.guardrails import Guardrails
from monetization.agent.models import (
    ACTION_BLOCK, ACTION_EXECUTE, ACTION_EXPERIMENT, GuardrailConfig,
    Opportunity, PolicyConfig,
)
from monetization.agent.policy import Policy
from monetization.experiments.models import DEFAULT_BASELINE
from monetization.learning.decision_store import DecisionStore
from monetization.learning.models import DecisionRecord
from monetization.intelligence.synthetic_memory import generate as generate_memory

OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


# --------------------------------------------------------------------------- #
# Memory seed: synthetic history, but make `monetization_aggressive` UNKNOWN
# (0 samples) so revenue_drop opportunities force an experiment, never execute.
# --------------------------------------------------------------------------- #
def seed_memory(n: int = 600, seed: int = 7) -> DecisionStore:
    recs = generate_memory(n=n, seed=seed)
    recs = [r for r in recs if r.strategy_type != "monetization_aggressive"]
    store = DecisionStore()  # in-memory (no path -> no file IO)
    for r in recs:
        store.append(r)
    return store


# --------------------------------------------------------------------------- #
# Opportunity factory for the 30-day simulation
# --------------------------------------------------------------------------- #
# Distinct segment pool (5 x 2 x 2 x 4 = 80) so each opportunity can sit on a
# novel (strategy, segment) -> realistic per-segment experimentation.
_COUNTRIES = ["US", "JP", "DE", "BR", "IN"]
_PLATFORMS = ["android", "ios"]
_AD_FORMATS = ["reward", "interstitial"]
_NETWORKS = ["applovin", "mintegral", "ironsource", "admob"]


def _all_segments():
    segs = []
    for c in _COUNTRIES:
        for p in _PLATFORMS:
            for a in _AD_FORMATS:
                for n in _NETWORKS:
                    segs.append({"country": c, "platform": p,
                                 "ad_format": a, "network": n})
    return segs


_SEGMENT_POOL = _all_segments()


def _seg(i: int) -> dict:
    return dict(_SEGMENT_POOL[i % len(_SEGMENT_POOL)])


def _metrics(ecpm: float, severity: float) -> dict:
    m = dict(DEFAULT_BASELINE)
    m.update({"ecpm": ecpm, "fill_rate": 0.90, "impressions": 30000,
              "dau": 4000, "d1_retention_pct": 42.0})
    return m


def build_schedule() -> List[List[Opportunity]]:
    opps: List[Opportunity] = []
    s = 0
    # 20 execute-worthy: ecpm_drop, severe, low ecpm (bid_floor is known-good)
    for i in range(20):
        opps.append(Opportunity(
            id=f"exec_{i:03d}", type="ecpm_drop", segment=_seg(s),
            metrics=_metrics(8.0, 0.8), severity=0.8)); s += 1
    # 35 experiment-worthy: revenue_drop (monetization_aggressive UNKNOWN)
    # each on a distinct segment -> the agent experiments once per novel segment
    for i in range(35):
        opps.append(Opportunity(
            id=f"exp_{i:03d}", type="revenue_drop", segment=_seg(s),
            metrics=_metrics(10.0, 0.7), severity=0.7)); s += 1
    # 5 block-worthy: a detected retention crash (forced high risk)
    for i in range(5):
        opps.append(Opportunity(
            id=f"blk_{i:03d}", type="ecpm_drop", segment=_seg(s),
            metrics=_metrics(8.0, 0.8), severity=0.8, forced_risk="high")); s += 1
    # 40 observe-worthy: ecpm_drop, mild (low severity -> watch only)
    for i in range(40):
        opps.append(Opportunity(
            id=f"obs_{i:03d}", type="ecpm_drop", segment=_seg(s),
            metrics=_metrics(11.0, 0.2), severity=0.2)); s += 1

    # round-robin across 30 days (keeps daily exec/exp within guardrail caps)
    days: List[List[Opportunity]] = [[] for _ in range(30)]
    for idx, opp in enumerate(opps):
        days[idx % 30].append(opp)
    return days


# --------------------------------------------------------------------------- #
# Tier A — deterministic Policy cases
# --------------------------------------------------------------------------- #
def tier_a() -> None:
    print("\n=== Tier A: Policy decision cases ===")
    policy = Policy()
    # In the standalone Policy test the seeded "known" strategy is bid_floor_adjust;
    # monetization_aggressive is the *introduced* (unknown) one.
    policy.baseline_strategies = {"bid_floor_adjust"}
    gr = Guardrails()

    # Case 1: known, high-success strategy -> execute
    p1 = {"mean": 0.90, "samples": 50}
    a1 = policy.decide(opportunity=type("O", (), {"forced_risk": ""})(),
                       strategy_type="bid_floor_adjust", prior=p1,
                       confidence=0.9, risk="low",
                       simulation_revenue_delta=5.0, retention_delta=0.0,
                       severity=0.9, guardrails=gr)
    a1g, _ = gr.enforce(a1, risk="low", retention_delta=0.0, bid_change=20.0, day=0)
    check("Case1 known-good -> execute", a1 == ACTION_EXECUTE and a1g == ACTION_EXECUTE,
          f"policy={a1} enforced={a1g}")

    # Case 2: unknown strategy (0 samples) -> experiment, never execute
    p2 = {"mean": 0.50, "samples": 0}
    a2 = policy.decide(opportunity=type("O", (), {"forced_risk": ""})(),
                       strategy_type="monetization_aggressive", prior=p2,
                       confidence=0.9, risk="low",
                       simulation_revenue_delta=6.0, retention_delta=0.0,
                       severity=0.9, guardrails=gr)
    a2g, _ = gr.enforce(a2, risk="low", retention_delta=0.0, bid_change=20.0, day=0)
    check("Case2 unknown -> experiment (not execute)",
          a2 == ACTION_EXPERIMENT and a2g == ACTION_EXPERIMENT,
          f"policy={a2} enforced={a2g}")

    # Case 3: high retention risk -> block
    p3 = {"mean": 0.90, "samples": 50}
    a3 = policy.decide(opportunity=type("O", (), {"forced_risk": "high"})(),
                       strategy_type="bid_floor_adjust", prior=p3,
                       confidence=0.9, risk="high",
                       simulation_revenue_delta=5.0, retention_delta=-8.0,
                       severity=0.9, guardrails=gr)
    a3g, why = gr.enforce(a3, risk="high", retention_delta=-8.0, bid_change=20.0, day=0)
    check("Case3 high-risk -> block",
          a3 == ACTION_BLOCK and a3g == ACTION_BLOCK,
          f"policy={a3} enforced={a3g} reason={why}")


# --------------------------------------------------------------------------- #
# Tier B — 30-day autonomous simulation
# --------------------------------------------------------------------------- #
def tier_b() -> dict:
    print("\n=== Tier B: 30-day autonomous simulation (100 opportunities) ===")
    store = seed_memory()
    agent = MonetizationAgent(store=store)
    schedule = build_schedule()
    report = agent.run_simulation(schedule)
    rep = report.to_dict()
    (OUT / "agent_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                                           encoding="utf-8")

    print(f"  cycles={report.cycles} opportunities={report.opportunities} "
          f"experiments={report.experiments} executions={report.executions} "
          f"executed_actually={report.executed_actually} pending={report.pending_human} "
          f"rollbacks={report.rollbacks} blocks={report.blocks} "
          f"observes={report.observes} improvement={report.strategy_improvement_pct}%")

    # ---- the three crucial invariants ----
    # 1) the agent NEVER directly executes an unknown strategy
    unknown_exec = [a for a in report.actions
                   if a.action == ACTION_EXECUTE and a.prior_samples <= 0]
    check("never executes unknown strategy", len(unknown_exec) == 0,
          f"{len(unknown_exec)} violations")

    # 2) low-risk known-good strategies are auto-executed
    check("known-good strategies auto-executed", report.executed_actually > 0,
          f"executed_actually={report.executed_actually}")

    # 3) high-risk strategies are auto-blocked
    check("high-risk strategies auto-blocked", report.blocks > 0,
          f"blocks={report.blocks}")

    # 4) experiments were run for unknown strategies
    check("experiments run for unknowns", report.experiments > 0,
          f"experiments={report.experiments}")

    # 5) rollbacks occurred and were contained (mock, no real API)
    check("rollbacks contained (mock)", report.rollbacks >= 1,
          f"rollbacks={report.rollbacks}")
    real_api = any(
        a.result_summary.get("real_api_called") is True
        for a in report.actions if a.action == ACTION_EXECUTE)
    check("no real ad-platform API called", not real_api)

    # 6) guardrail daily caps respected (exec <= 3/day, exp <= 5/day)
    cap_ok = all(c.n_execute <= 3 and c.n_experiment <= 5 for c in report.per_day)
    check("daily guardrail caps respected", cap_ok)

    # 7) the agent learned (prior improved over the run)
    check("agent learned (prior improved)", report.strategy_improvement_pct > 0,
          f"improvement={report.strategy_improvement_pct}%")

    # 8) totals consistent with the 100-opportunity input
    check("totals sum to 100 opportunities",
          report.executions + report.experiments + report.blocks + report.observes == 100,
          f"sum={report.executions + report.experiments + report.blocks + report.observes}")

    # 9) the three headline numbers are in a believable ballpark of the
    #    user's illustrative targets (35 experiments / 20 executions / ~2 rollbacks)
    check("experiments in believable range", 25 <= report.experiments <= 45,
          f"experiments={report.experiments}")
    check("executions in believable range", 10 <= report.executions <= 30,
          f"executions={report.executions}")
    check("blocks present", report.blocks >= 1, f"blocks={report.blocks}")

    return rep


# --------------------------------------------------------------------------- #
# Tier C — no-LLM / no-external-API compliance
# --------------------------------------------------------------------------- #
def tier_c() -> None:
    print("\n=== Tier C: Lean / no-LLM compliance ===")
    agent_dir = Path(__file__).resolve().parent
    forbidden = ("sklearn", "tensorflow", "torch", "openai", "anthropic",
                 "xgboost", "lightgbm", "langchain", "requests.get",
                 "urllib.request", "http.client")
    violations = []
    for py in agent_dir.glob("*.py"):
        if py.name == "validate_agent.py":   # the harness defines `forbidden`
            continue
        low = py.read_text(encoding="utf-8").lower()
        for bad in forbidden:
            if bad in low:
                violations.append(f"{py.name}: {bad}")
    check("no forbidden (LLM/API) imports in agent", len(violations) == 0,
          "; ".join(violations) if violations else "clean")


def main() -> int:
    print("E13.4.4 Autonomous Monetization Agent — Validation")
    tier_a()
    rep = tier_b()
    tier_c()
    print(f"\n=== RESULT: {_passed} passed, {_failed} failed ===")
    print(f"Report written to: {OUT / 'agent_report.json'}")
    return 1 if _failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
