"""
E15.2.5+ — Experiment lifecycle CLI (operator seam).

The agent proposes; YOU apply in the MAX dashboard; then anchor the
change here so the outcome-learning loop can measure before/after:

  # list experiments and their lifecycle state
  python operation/optimizer/experiments/cli.py list ACCT_2

  # after applying a change in the MAX dashboard:
  python operation/optimizer/experiments/cli.py apply ACCT_2 <exp_id> [YYYY-MM-DD]

  # inspect the "what worked" memory (optionally filter by action)
  python operation/optimizer/experiments/cli.py memory [action]

  # supply today's DAU (zero-credential seam) so Revenue/DAU + ARPDAU
  # guardrail go live. Adjust/Firebase auto-fetch plugs into the same
  # path later; until then, one command per day:
  python operation/optimizer/experiments/cli.py dau ACCT_2 123456 [YYYY-MM-DD]

  # supply per-app DAU (keyed by the SAME app id in the MAX report) so
  # fleet_bridge reports each game's own Rev/DAU vs the $0.03 north star:
  python operation/optimizer/experiments/cli.py dau-apps ACCT_1 '{"com.foo.bar": 8400, "com.foo.baz": 2100}' [YYYY-MM-DD]

Zero MAX writes — this only moves local bookkeeping state.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..")))

from operation.optimizer.experiments.experiment_store import ExperimentStore  # noqa: E402
from operation.optimizer.experiments.optimization_memory import (  # noqa: E402
    OptimizationMemory)
from operation.optimizer.user_metrics import (  # noqa: E402
    save_dropin_dau, save_dropin_dau_apps)


def _list(account: str) -> None:
    store = ExperimentStore()
    defs = store.load(account)
    if not defs:
        print(f"no experiments for {account}")
        return
    print(f"{'exp_id':14} {'status':12} {'decision':9} "
          f"{'applied_at':11} {'impact':>8}  title")
    for d in defs.values():
        imp = d.impact.get("net_impact_pct") if d.impact else None
        imp_s = f"{imp:+.1f}%" if isinstance(imp, (int, float)) else "-"
        print(f"{d.exp_id:14} {d.status:12} {d.decision or '-':9} "
              f"{d.applied_at or '-':11} {imp_s:>8}  {d.title[:60]}")


def _apply(account: str, exp_id: str, when: str = "") -> None:
    store = ExperimentStore()
    exp = store.mark_applied(account, exp_id, when or None)
    if exp is None:
        print(f"ERROR: experiment {exp_id} not found for {account}")
        sys.exit(1)
    print(f"OK — {exp.title}")
    print(f"    status={exp.status} applied_at={exp.applied_at}")
    print("    impact will be measured on the next daily briefing run "
          "(needs >= 2 before / 3 after report days).")


def _memory(action: str = "") -> None:
    mem = OptimizationMemory()
    q = mem.query(action=action or None)
    p = q["prior"]
    print(f"optimization memory: {len(q['precedents'])} row(s)"
          + (f" for action={action}" if action else ""))
    for r in q["precedents"]:
        imp = r.get("net_impact_pct")
        imp_s = f"{imp:+.1f}%" if isinstance(imp, (int, float)) else "n/a"
        print(f"  {r.get('decided_at')} {r.get('account')} "
              f"{r.get('action')} -> {r.get('target')} : {imp_s} "
              f"({r.get('decision')}, conf {r.get('confidence')})")
    if p["n"]:
        print(f"prior: n={p['n']} mean={p['mean_impact_pct']:+.1f}% "
              f"hit-rate={p['hit_rate']:.0%} conf={p['confidence']:.2f}")


def _dau(account: str, dau: str, as_of: str = "") -> None:
    from datetime import date as _date
    dau_i = int(dau)
    day = as_of or _date.today().isoformat()
    p = save_dropin_dau(account, dau_i, day)
    print(f"OK — DAU drop-in saved for {account}: {dau_i:,} (as_of {day})")
    print(f"    next daily run will compute Revenue/DAU + activate ARPDAU guardrail")
    print(f"    file: {p}")


def _dau_apps(account: str, apps_json: str, as_of: str = "") -> None:
    from datetime import date as _date
    import json as _json
    try:
        apps = _json.loads(apps_json)
    except ValueError as e:
        print(f"ERROR: apps must be valid JSON object {{app_id: dau}}: {e}")
        sys.exit(1)
    if not isinstance(apps, dict):
        print("ERROR: apps must be a JSON object {app_id: dau}")
        sys.exit(1)
    day = as_of or _date.today().isoformat()
    p = save_dropin_dau_apps(account, apps, day)
    print(f"OK — per-app DAU saved for {account}: {len(apps)} game(s) (as_of {day})")
    print(f"    fleet_bridge will now report each game's Rev/DAU vs north star")
    print(f"    file: {p}")


def main(argv) -> None:
    if len(argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = argv[1]
    if cmd == "list" and len(argv) >= 3:
        _list(argv[2])
    elif cmd == "apply" and len(argv) >= 4:
        _apply(argv[2], argv[3], argv[4] if len(argv) > 4 else "")
    elif cmd == "memory":
        _memory(argv[2] if len(argv) > 2 else "")
    elif cmd == "dau" and len(argv) >= 4:
        _dau(argv[2], argv[3], argv[4] if len(argv) > 4 else "")
    elif cmd == "dau-apps" and len(argv) >= 4:
        _dau_apps(argv[2], argv[3], argv[4] if len(argv) > 4 else "")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
