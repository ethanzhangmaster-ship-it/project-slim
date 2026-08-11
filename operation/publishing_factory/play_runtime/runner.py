"""E13.5 — Unified Play Runtime daily orchestrator.

Runs all five Google Play console agents in ONE deterministic, fault-isolated
sweep so the operator never has to fire five separate CLIs to keep the morning
briefing's Play sections (6-10) alive:

    Health  ->  Release  ->  Review  ->  Experiment  ->  Tester Pool

Design (follows the system's Lean / gated / zero-LLM contract):
  * Deterministic order: observability (Health) first, then the rollout action
    (Release), then user engagement (Review), store optimization (Experiment),
    and finally the growth supply line (Tester Pool).
  * Fault-isolated: one agent crashing never blocks the others; the failure is
    recorded in the consolidated run log, never raised.
  * Gated: default SIMULATION => ZERO network (every connector call returns
    RECOMMEND, real_api_called=False). ``--apply`` flips each agent's apply
    flag, but the connector's own gate still enforces the RELEASE unlock, so
    even ``--apply`` is safe against an unlocked connector.
  * Consolidated output: data/play_runtime/daily_run/<date>.json holds the
    per-agent results + an aggregate (counts, real_api_called, gate mode) so
    the morning briefing can show one "Play Ops daily sweep" line.

Usage:
  PYTHONPATH=. python -m operation.publishing_factory.play_runtime.runner
  PYTHONPATH=. python -m operation.publishing_factory.play_runtime.runner --apply
  PYTHONPATH=. python -m operation.publishing_factory.play_runtime.runner \
      --packages com.a,com.b
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# Resolve the workspace root (launchforge/) so data/ is written consistently
# regardless of the caller's CWD. _THIS =
# launchforge/operation/publishing_factory/play_runtime -> 3 levels up = launchforge.
_THIS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_THIS, "..", "..", ".."))
DATA_DIR = os.path.join(ROOT, "data", "play_runtime", "daily_run")

# Determinism: the order the five agents sweep the fleet each morning.
AGENT_ORDER = ["health", "release", "review", "experiment", "tester_pool"]


def discover_packages(explicit: Optional[List[str]] = None) -> List[str]:
    """Return the google_play package list to operate on.

    Priority: explicit CLI list -> catalog game_registry (android packages
    with a non-empty package_name) -> LAUNCHFORGE_PLAY_PACKAGES env -> empty.
    """
    if explicit:
        return [p.strip() for p in explicit if p.strip()]
    try:
        from operation.publishing_factory.catalog.game_registry import (
            GameRegistry)
        reg = GameRegistry().load()
        pkgs: List[str] = []
        for p in reg.list_all():
            if "google_play" in getattr(p, "platforms", []) and getattr(
                    p, "package_name", None):
                pkgs.append(p.package_name)
        if pkgs:
            return sorted(set(pkgs))
    except Exception:
        pass
    env = os.environ.get("LAUNCHFORGE_PLAY_PACKAGES")
    if env:
        return [x.strip() for x in env.split(",") if x.strip()]
    return []


def _safe(fn, name: str) -> Dict[str, Any]:
    """Run one agent's sweep; never raise. Returns a uniform result dict."""
    t0 = time.time()
    try:
        out = fn()
        return {"agent": name, "status": "OK",
                "seconds": round(time.time() - t0, 3), "result": out}
    except Exception as exc:  # noqa: BLE001 — isolation is the whole point
        return {"agent": name, "status": "FAIL",
                "seconds": round(time.time() - t0, 3),
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(limit=2)}


def _count_items(result: Any) -> int:
    """Best-effort item count for a per-agent result (for the run summary)."""
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        pp = result.get("per_package")
        if isinstance(pp, dict):
            return len(pp)
        if "recommendations" in result and isinstance(
                result["recommendations"], list):
            return len(result["recommendations"])
        if "posted_this_run" in result and isinstance(
                result["posted_this_run"], list):
            return len(result["posted_this_run"])
    return 0


def _any_real_api(result: Any) -> bool:
    """Recursively scan a result tree for any real_api_called=True flag."""
    if isinstance(result, dict):
        if result.get("real_api_called") is True:
            return True
        if result.get("ok") is True and result.get(
                "stage") == "EXECUTE":
            # executed writes count as real API even if the flag is nested
            return True
        return any(_any_real_api(v) for v in result.values())
    if isinstance(result, list):
        return any(_any_real_api(v) for v in result)
    return False


def _mode_of(agent) -> str:
    """Report the connector sandbox mode of an agent (SIMULATION default)."""
    try:
        sb = getattr(getattr(agent, "connector", None), "sandbox", None)
        return str(sb).split(".")[-1] if sb is not None else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def run_play_ops(packages: Optional[List[str]] = None, *,
                 apply: bool = False,
                 today: Optional[date] = None) -> Dict[str, Any]:
    """Run the full Play console fleet sweep and persist a consolidated log.

    SIMULATION by default (zero network). ``apply=True`` flips each agent's
    apply flag but the connector gate still enforces the RELEASE unlock.
    Returns the run summary dict (also written to data/play_runtime/daily_run).
    """
    pkgs = discover_packages(packages)
    today = today or date.today()

    # Lazily import so the orchestrator is importable even when an individual
    # agent module has an unrelated import error in another context.
    from operation.publishing_factory.play_runtime.connector \
        import PlayConnector, SandboxMode
    from operation.publishing_factory.play_runtime.health_agent \
        import HealthAgent
    from operation.publishing_factory.play_runtime.release_agent \
        import ReleaseAgent
    from operation.publishing_factory.play_runtime.review_agent \
        import ReviewAgent
    from operation.publishing_factory.play_runtime.experiment_agent \
        import ListingExperimentAgent
    from operation.publishing_factory.play_runtime.tester_pool_agent \
        import TesterPoolAgent

    # One shared gated facade: SIMULATION by default (zero network). A real
    # connector under SHADOW/PROD would be wired here by the environment.
    sandbox = SandboxMode.PRODUCTION if apply else SandboxMode.SIMULATION
    conn = PlayConnector(sandbox=sandbox)

    health = HealthAgent(conn)
    release = ReleaseAgent(conn)
    review = ReviewAgent(conn)
    exp = ListingExperimentAgent(conn)
    pool = TesterPoolAgent(conn)

    mode = _mode_of(health)

    steps = [
        ("health", lambda: health.run_daily(pkgs, apply=apply)),
        ("release", lambda: release.run_daily(pkgs, apply=apply)),
        ("review", lambda: review.run_daily(pkgs, apply=apply)),
        ("experiment", lambda: exp.run_daily(pkgs)),
        ("tester_pool", lambda: pool.run_daily(pkgs, apply=apply)),
    ]

    agents_out: Dict[str, Any] = {}
    failures: List[str] = []
    real_api = False
    for name, fn in steps:
        res = _safe(fn, name)
        agents_out[name] = {
            "status": res["status"],
            "seconds": res["seconds"],
            "items": _count_items(res.get("result")),
        }
        if res["status"] == "FAIL":
            agents_out[name]["error"] = res.get("error")
            failures.append(f"{name}: {res.get('error')}")
        if res["status"] == "OK":
            real_api = real_api or _any_real_api(res.get("result"))

    ok_count = sum(1 for v in agents_out.values() if v["status"] == "OK")
    summary = {
        "date": today.isoformat(),
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "apply": apply,
        "packages_count": len(pkgs),
        "packages": pkgs,
        "agents": agents_out,
        "agents_ok": ok_count,
        "agents_total": len(AGENT_ORDER),
        "real_api_called": real_api,
        "failures": failures,
        "status": "OK" if not failures else "DEGRADED",
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{today.isoformat()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    summary["path"] = path
    return summary


def render_status_line(s: Dict[str, Any]) -> str:
    """One-line human-readable status for the morning digest / CLI."""
    mode = s["mode"]
    api = "REAL-API" if s["real_api_called"] else "zero-API"
    flag = "🌐" if s["real_api_called"] else "🧪"
    return (f"{flag} Play Ops 每日巡检：{s['agents_ok']}/{s['agents_total']} "
            f"Agent 正常 · 包 {s['packages_count']} · 模式 {mode} · {api}"
            + (f" · ⚠️ {len(s['failures'])} 失败" if s["failures"] else ""))


def main() -> int:  # pragma: no cover — thin CLI wrapper
    args = sys.argv[1:]
    apply = "--apply" in args
    pkgs = None
    for a in args:
        if a.startswith("--packages="):
            pkgs = a.split("=", 1)[1].split(",")
    s = run_play_ops(pkgs, apply=apply)
    print(render_status_line(s))
    for name, v in s["agents"].items():
        tag = "✅" if v["status"] == "OK" else "❌"
        print(f"  {tag} {name:12s} {v['status']:8s} "
              f"items={v.get('items', 0)} {v.get('seconds', 0)}s")
    if s["failures"]:
        for f in s["failures"]:
            print(f"   ⚠️ {f}")
    print(f"   log -> {s['path']}")
    return 0 if s["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
