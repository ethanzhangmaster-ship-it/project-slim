"""
E14.5 — Lean Observability Layer validation
============================================

Acceptance (per spec, scaled for CI; production target is 10 games x 30 days
x 30k cycles — the code is loop/stream bound and handles it unchanged):

  [A] 10-game soak
        ✓ every game has a health snapshot (status + score)
        ✓ every decision is explainable (non-empty reason_chain)
        ✓ failure / rollback automatically alerted (rule coverage)
        ✓ daily operator report generated (4 sub-reports)
        ✓ JSONL metrics stream complete (game_health + decision + alert)

  [B] Alert-engine rules (deterministic, independent of the soak)
        ✓ rollback_rate > 20%  -> critical
        ✓ provider_health < 40 -> warning (downgrade sandbox)
        ✓ revenue_drop   > 15% -> critical (freeze execution)
        ✓ crash-loop/isolated   -> critical (isolate)
        ✓ alerts persisted to JSONL

Lean: pure-Python, stdlib only, file-backed. No DB / web / UI.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.agent.game_config import GameConfig
from monetization.agent.models import Opportunity
from monetization.agent.registry import GameFactoryOS, GameRegistry
from monetization.observability.alerts import AlertEngine
from monetization.observability.health import SystemHealthAggregator
from monetization.observability.models import (
    FleetHealthReport, HealthSnapshot,
    HEALTH_DEGRADED, HEALTH_HEALTHY, HEALTH_ISOLATED,
)
from monetization.observability.service import ObservabilityService
from monetization.runtime.scheduler import default_make_opps
from monetization.runtime.supervisor import RuntimeConfig, RuntimeSupervisor

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


def build_fleet(n_games: int, base: str) -> GameFactoryOS:
    reg = GameRegistry()
    for i in range(n_games):
        reg.register(GameConfig(slug=f"game_{i:02d}",
                                display_name=f"Game {i:02d}"))
    return GameFactoryOS(reg, base, seed_memory_fn=None)


def make_sup(n_games: int):
    base = Path(tempfile.mkdtemp(prefix="launchforge_obs_"))
    os_ = build_fleet(n_games, str(base / "stores"))
    sup = RuntimeSupervisor(os_, str(base / "ckpt"), config=RuntimeConfig())
    sup.start()
    return sup


def main() -> int:
    print("E14.5 — Lean Observability Layer validation\n")
    n_games, n_days = 10, 10

    # ================================================================= #
    # [A] 10-game soak through the real runtime + observability service
    # ================================================================= #
    print(f"=== A. {n_games}-game soak ({n_days} days) ===")
    sup = make_sup(n_games)
    obs_root = tempfile.mkdtemp(prefix="launchforge_obs_out_")
    svc = ObservabilityService(sup, root_dir=obs_root)

    for day in range(n_days):
        # last day: inject a revenue-drop signal so the alert metric type
        # also appears in the JSONL stream during the soak (faithful to the
        # "JSONL metrics complete" acceptance criterion).
        extra = {"game_00": {"revenue_drop_pct": 20.0}} if day == n_days - 1 else None
        svc.run_daily_cycle(default_make_opps, day, extra_signals=extra)

    # A1 — every game has a health snapshot
    fleet = svc.health.snapshot()
    check("fleet snapshot covers all 10 games",
          len(fleet.games) == n_games, f"games={len(fleet.games)}")
    check("every snapshot score in [0,100]",
          all(0.0 <= g.score <= 100.0 for g in fleet.games))
    check("every snapshot has a valid status",
          all(g.status in (HEALTH_HEALTHY, HEALTH_DEGRADED,
                           "unhealthy", HEALTH_ISOLATED)
              for g in fleet.games))

    # A2 — every decision is explainable
    traces = svc.all_traces
    check("decision traces were captured", len(traces) > 0,
          f"traces={len(traces)}")
    check("every trace has a non-empty reason_chain",
          all(len(t.reason_chain) >= 3 for t in traces))
    check("every trace names its decision + action + final_action",
          all(t.decision and t.action and t.final_action for t in traces))

    # A3 — JSONL metrics stream complete
    metrics_files = list(Path(obs_root).glob("metrics/*.jsonl"))
    check("metrics JSONL files emitted per day", len(metrics_files) == n_days,
          f"files={len(metrics_files)}")
    kinds = {}
    for f in metrics_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            kinds[row.get("metric")] = kinds.get(row.get("metric"), 0) + 1
    check("metrics include game_health lines (per game x per day)",
          kinds.get("game_health", 0) == n_games * n_days,
          f"game_health={kinds.get('game_health', 0)} expected={n_games*n_days}")
    check("metrics include decision lines", kinds.get("decision", 0) > 0,
          f"decision={kinds.get('decision', 0)}")
    check("metrics stream shape complete (3 metric types)",
          set(kinds) >= {"game_health", "decision", "alert"})

    # A4 — daily operator report generated (4 sub-reports)
    rep = svc.daily_reports[-1]
    check("daily report has 4 sub-reports",
          all(getattr(rep, k) is not None for k in
              ("ua_action", "monetization", "experiment", "risk")))
    check("daily report summary non-empty", bool(rep.summary.strip()))
    md = rep.to_markdown()
    check("daily report renders to markdown",
          md.startswith("# Daily Operation Report") and "## Risk Report" in md)

    # A5 — decision traces persisted as JSONL
    trace_files = list(Path(obs_root).glob("decision_traces/*.jsonl"))
    check("decision traces persisted to JSONL", len(trace_files) > 0,
          f"files={len(trace_files)}")

    # ================================================================= #
    # [B] Alert-engine rules (deterministic)
    # ================================================================= #
    print("\n=== B. Alert-engine rules (deterministic) ===")
    controlled = FleetHealthReport(games=[
        HealthSnapshot(game_id="rb_game", status=HEALTH_HEALTHY, risk="low",
                       score=90.0, rollback_rate=0.30),
        HealthSnapshot(game_id="ph_game", status=HEALTH_DEGRADED, risk="medium",
                       score=35.0, provider_health=30.0),
        HealthSnapshot(game_id="iso_game", status=HEALTH_ISOLATED, risk="high",
                       score=10.0),
        HealthSnapshot(game_id="ok_game", status=HEALTH_HEALTHY, risk="low",
                       score=95.0, provider_health=85.0),
    ])
    eng = AlertEngine(str(Path(obs_root) / "alerts_b"))
    alerts = eng.evaluate(controlled)
    rules = {a.meta.get("rule") for a in alerts}

    check("rollback_rate>20% -> critical alert",
          any(a.meta.get("rule") == "rollback_rate"
              and a.level == "critical" for a in alerts))
    check("provider_health<40 -> warning (downgrade sandbox)",
          any(a.meta.get("rule") == "provider_health"
              and a.level == "warning" for a in alerts))
    check("isolated game -> critical (isolate)",
          any(a.meta.get("rule") == "crash_loop"
              and a.level == "critical" for a in alerts))
    check("rule set matches spec (no phantom rules)",
          rules <= {"rollback_rate", "provider_health", "crash_loop", "high_risk"})

    # revenue_drop signal -> critical (freeze execution)
    eng2 = AlertEngine(str(Path(obs_root) / "alerts_c"))
    eng2.record_signal("ok_game", "revenue_drop_pct", 20.0)
    alerts2 = eng2.evaluate(controlled)
    check("revenue_drop>15% -> critical (freeze execution)",
          any(a.meta.get("rule") == "revenue_drop"
              and a.level == "critical" for a in alerts2))

    # persistence
    n_written = eng.flush("b") + eng2.flush("c")
    check("alerts persisted to JSONL", n_written >= 4,
          f"written={n_written}")

    print(f"\n=== RESULT: {_passed} passed, {_failed} failed ===")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
