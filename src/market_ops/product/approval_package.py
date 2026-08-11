"""Render an auditable, non-executing approval package for a growth cycle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .closed_loop import GrowthLoop
from .platform_write_readiness import facebook_write_readiness


def build(database: Path, cycle_id: str, output: Path) -> Path:
    load_dotenv(output.parent.parent.parent / ".env", override=False)
    cycle = GrowthLoop(database).cycle(cycle_id)
    if not cycle:
        raise ValueError(f"Unknown cycle: {cycle_id}")
    gate = facebook_write_readiness(output.parent / "campaign_bindings.json")
    tasks = cycle.get("tasks") or []
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "cycle_id": cycle_id,
        "cycle_status": cycle.get("status"), "execution_permitted": False,
        "blocking_conditions": gate.reasons or ["Human approval remains required for every platform write"],
        "tasks": [{"task_id": item.get("task_id"), "creative_id": item.get("creative_id"), "action_type": item.get("action_type"), "before_budget": (item.get("budget_change") or {}).get("before"), "after_budget": (item.get("budget_change") or {}).get("after"), "approval_required": item.get("approval_required"), "status": item.get("status")} for item in tasks],
    }
    candidates_path = output.parent / "approval_binding_candidates.json"
    if candidates_path.exists():
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        matched = {str(item.get("creative_id") or "") for item in candidates}
        for task in payload["tasks"]:
            if str(task["creative_id"]) not in matched:
                task["execution_state"] = "REQUIRES_REBINDING_EVIDENCE"
        payload["binding_audit"] = {"matched_creatives": len(matched), "unmatched_tasks": sum(1 for item in payload["tasks"] if item.get("execution_state"))}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a non-executing Market Ops approval package")
    parser.add_argument("cycle_id"); parser.add_argument("--database", type=Path, default=Path("output/active/growth_loop.sqlite3")); parser.add_argument("--output", type=Path, default=Path("output/active/approval_package.json"))
    args = parser.parse_args(); print(build(args.database, args.cycle_id, args.output))


if __name__ == "__main__": main()
