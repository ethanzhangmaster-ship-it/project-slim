"""Command interface for the durable growth loop."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from .closed_loop import GrowthLoop
from .evidence_adapter import assert_fresh, assert_performance_coverage_fresh, from_decision_engine
from .platform_write_readiness import facebook_write_readiness


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the safe Market Ops growth loop")
    parser.add_argument("--database", type=Path, default=Path("output/active/growth_loop.sqlite3"))
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="turn normalized experiment evidence into auditable actions")
    plan.add_argument("--input", type=Path, required=True); plan.add_argument("--total-budget", type=float, required=True)
    real = commands.add_parser("plan-decision-report", help="plan only fresh, trusted creative decisions")
    real.add_argument("--input", type=Path, required=True); real.add_argument("--performance-csv", type=Path, required=True); real.add_argument("--as-of", type=date.fromisoformat, default=date.today()); real.add_argument("--max-age-days", type=int, default=7); real.add_argument("--max-data-age-days", type=int, default=2)
    execute = commands.add_parser("execute", help="execute only auto-approved or already approved tasks"); execute.add_argument("cycle_id")
    approve = commands.add_parser("approve", help="record a human approval for a planned task"); approve.add_argument("task_id"); approve.add_argument("--by", required=True)
    observe = commands.add_parser("observe", help="record attributable post-execution performance"); observe.add_argument("task_id"); observe.add_argument("--metrics", type=Path, required=True)
    cycle = commands.add_parser("cycle", help="view one complete audit trail"); cycle.add_argument("cycle_id")
    commands.add_parser("overview", help="view outstanding approvals and loop state")
    args = parser.parse_args(); load_dotenv(args.database.parent.parent.parent / ".env", override=False); loop = GrowthLoop(args.database)
    if args.command == "plan": output = loop.plan(_load_json(args.input), args.total_budget)
    elif args.command == "plan-decision-report":
        report = _load_json(args.input); assert_fresh(report, as_of=args.as_of, max_age_days=args.max_age_days); assert_performance_coverage_fresh(args.performance_csv, as_of=args.as_of, max_age_days=args.max_data_age_days); batch = from_decision_engine(report)
        output = {"cycle": loop.plan(batch.results, batch.total_budget), "skipped": batch.skipped}
    elif args.command == "execute":
        gate = facebook_write_readiness(args.database.parent / "campaign_bindings.json")
        if not gate.ready:
            raise ValueError("Platform execution is blocked: " + "; ".join(gate.reasons))
        output = loop.execute(args.cycle_id)
    elif args.command == "approve": output = loop.approve(args.task_id, args.by)
    elif args.command == "observe": output = loop.observe(args.task_id, _load_json(args.metrics))
    elif args.command == "cycle": output = loop.cycle(args.cycle_id)
    else: output = loop.overview()
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
