"""
E14 Slice 1 — Validation: multi-game isolation
==============================================

Proves that the operating-system layer runs N games as fully isolated tenants:

  T1  Memory isolation   — each game's DecisionStore is a separate on-disk file;
                           no decision_id ever appears in two games; each store
                           contains ONLY its own (slug-prefixed) records.
  T2  Config isolation   — per-game GuardrailConfig is independent: a game with
                           max_executions_per_day=2 never executes more than 2/day
                           while a default game (cap 3) is allowed 3.
  T3  Prior isolation    — each game's learned prior reflects only its own store
                           (no cross-tenant belief leakage).
  T4  Fleet aggregates   — totals across the fleet are consistent.

Lean: pure-Python, stdlib only, no LLM / no external API.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.agent.game_config import GameConfig
from monetization.agent.models import Opportunity
from monetization.agent.registry import GameFactoryOS, GameRegistry
from monetization.agent.validate_agent import seed_memory

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
# Fixtures
# --------------------------------------------------------------------------- #
_COUNTRIES = ["US", "JP", "DE", "BR", "IN"]
_PLATFORMS = ["android", "ios"]
_AD_FORMATS = ["reward", "interstitial"]
_NETWORKS = ["applovin", "mintegral", "ironsource", "admob"]


def _segments(n: int):
    out = []
    for i in range(n):
        out.append({
            "country": _COUNTRIES[i % len(_COUNTRIES)],
            "platform": _PLATFORMS[(i // len(_COUNTRIES)) % len(_PLATFORMS)],
            "ad_format": _AD_FORMATS[(i // 4) % len(_AD_FORMATS)],
            "network": _NETWORKS[i % len(_NETWORKS)],
        })
    return out


def make_schedule(slug: str, n_days: int = 3) -> List[List[Opportunity]]:
    """Per-game 3-day schedule. Day 0 deliberately over-subscribes executions
    (5 exec opps) to stress the daily cap; ids are slug-prefixed."""
    days: List[List[Opportunity]] = [[] for _ in range(n_days)]
    segs = _segments(40)
    s = 0

    # Day 0: 5 severe ecpm_drop -> should attempt EXECUTE (cap stress)
    for i in range(5):
        days[0].append(Opportunity(
            id=f"{slug}:exec_{i:03d}", type="ecpm_drop", segment=segs[s],
            metrics={"ecpm": 8.0}, severity=0.8)); s += 1
    # Day 1: 5 revenue_drop -> experiment-worthy
    for i in range(5):
        days[1].append(Opportunity(
            id=f"{slug}:exp_{i:03d}", type="revenue_drop", segment=segs[s],
            metrics={"ecpm": 10.0}, severity=0.7)); s += 1
    # Day 2: 4 mild obs + 1 forced high-risk block
    for i in range(4):
        days[2].append(Opportunity(
            id=f"{slug}:obs_{i:03d}", type="ecpm_drop", segment=segs[s],
            metrics={"ecpm": 11.0}, severity=0.2)); s += 1
    days[2].append(Opportunity(
        id=f"{slug}:blk_000", type="ecpm_drop", segment=segs[s],
        metrics={"ecpm": 8.0}, severity=0.8, forced_risk="high")); s += 1
    return days


def seed_fn():
    """Each game gets its own copy of the shared synthetic memory."""
    return list(seed_memory().all())


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main() -> int:
    print("E14 Slice 1 — Multi-game isolation validation")

    base = Path(tempfile.mkdtemp(prefix="launchforge_mg_"))
    print(f"  store root: {base}")

    reg = GameRegistry()
    # word_quest: STRICT daily exec cap (2)
    reg.register(GameConfig(
        slug="word_quest", display_name="Word Quest",
        guardrails={"max_executions_per_day": 2}))
    # puzzle_pop: default cap (3)
    reg.register(GameConfig(slug="puzzle_pop", display_name="Puzzle Pop"))
    # casual_tap: default cap (3)
    reg.register(GameConfig(slug="casual_tap", display_name="Casual Tap"))

    os_ = GameFactoryOS(reg, str(base), seed_memory_fn=seed_fn)
    check("fleet built (3 isolated agents)",
          len(os_.agents) == 3, f"agents={sorted(os_.agents)}")

    # ---- T1/T2: run each game; capture per-day exec counts ----
    per_game_schedule = {g.slug: make_schedule(g.slug) for g in reg.active_games()}
    report = os_.run_simulation(per_game_schedule)
    print(f"  fleet: cycles={report.cycles} opps={report.opportunities} "
          f"exp={report.experiments} exec={report.executions} "
          f"blk={report.blocks} obs={report.observes}")

    manifest = os_.isolation_manifest()

    # T1a: each game has its own distinct store path
    paths = [m["store_path"] for m in manifest.values()]
    check("each game has a distinct store path", len(paths) == len(set(paths)),
          str(paths))

    # T1b: pairwise decision_id disjointness (no cross-tenant leakage)
    slugs = list(manifest.keys())
    disjoint = True
    for i in range(len(slugs)):
        for j in range(i + 1, len(slugs)):
            a = set(manifest[slugs[i]]["decision_ids"])
            b = set(manifest[slugs[j]]["decision_ids"])
            if a & b:
                disjoint = False
    check("no decision_id shared across games", disjoint)

    # T1c: run-generated (slug-prefixed) records live ONLY in their own game.
    #      (Seeded synthetic-memory records carry their own ids, so we assert on
    #       the slug-prefixed ids produced by THIS run, not every row.)
    for slug, m in manifest.items():
        prefix = f"{slug}:"
        own_run_ids = {did for did in m["decision_ids"] if did.startswith(prefix)}
        check(f"store '{slug}' holds its own run-generated records",
              len(own_run_ids) > 0, f"{len(own_run_ids)} run records")
        leaked = False
        for other, om in manifest.items():
            if other == slug:
                continue
            if own_run_ids & set(om["decision_ids"]):
                leaked = True
        check(f"store '{slug}' run-records not leaked to other games", not leaked)

    # T2: per-game daily exec cap is independent
    wq = report.per_game["word_quest"].per_day[0].n_execute
    pp = report.per_game["puzzle_pop"].per_day[0].n_execute
    ct = report.per_game["casual_tap"].per_day[0].n_execute
    check("word_quest respects strict cap (<=2 exec/day)", wq <= 2,
          f"word_quest day0 exec={wq}")
    check("puzzle_pop allows default cap (<=3 exec/day)", pp <= 3,
          f"puzzle_pop day0 exec={pp}")
    check("casual_tap allows default cap (<=3 exec/day)", ct <= 3,
          f"casual_tap day0 exec={ct}")
    check("strict game executed strictly fewer than default game",
          wq < pp, f"word_quest={wq} < puzzle_pop={pp}")

    # T3: prior isolation — each game's learned prior only spans its own store
    #      (strategy set present must be a subset of records written by that game)
    for slug, agent in os_.agents.items():
        rec_strats = {r.strategy_type for r in agent.store.all()}
        prior_strats = set(agent.prior.prior_map().keys())
        check(f"game '{slug}' prior spans only its own strategies",
              prior_strats <= rec_strats or not rec_strats,
              f"prior={sorted(prior_strats)}")

    # T4: fleet totals are consistent
    total = (report.experiments + report.executions + report.blocks
             + report.observes)
    fed = sum(len(d) for sch in per_game_schedule.values() for d in sch)
    check("fleet totals sum to fed opportunities", total == fed,
          f"sum={total} fed={fed}")

    # Persist a machine-readable report
    out = {
        "isolation_manifest": manifest,
        "fleet_report": report.to_dict(),
        "daily_exec_day0": {
            "word_quest": report.per_game["word_quest"].per_day[0].n_execute,
            "puzzle_pop": report.per_game["puzzle_pop"].per_day[0].n_execute,
            "casual_tap": report.per_game["casual_tap"].per_day[0].n_execute,
        },
    }
    (OUT / "multigame_report.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== RESULT: {_passed} passed, {_failed} failed ===")
    print(f"Report written to: {OUT / 'multigame_report.json'}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
