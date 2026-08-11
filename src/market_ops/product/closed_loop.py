"""Durable, safe orchestration of the growth decision loop."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.execution_runtime.execution_engine import ExecutionEngine
from market_ops.execution_runtime.feedback_loop import FeedbackLoop
from market_ops.execution_runtime.schemas import ExecutionStatus, ExecutionTask, PerformanceSnapshot
from market_ops.growth_decision.growth_orchestrator import GrowthOrchestrator


class GrowthLoop:
    """The single durable path from evidence to a safe action and back."""

    def __init__(self, database_path: Path, *, engine: ExecutionEngine | None = None) -> None:
        self.database_path = database_path
        self.engine = engine or ExecutionEngine()
        self.feedback = FeedbackLoop()
        self._initialize()

    def plan(self, experiment_results: list[dict[str, Any]], total_budget: float) -> dict[str, Any]:
        fingerprint = self._fingerprint(experiment_results, total_budget)
        existing = self._cycle_by_fingerprint(fingerprint)
        if existing:
            return self.cycle(existing)
        outcome = GrowthOrchestrator().run(experiment_results, total_budget=total_budget)
        cycle_id, now = str(uuid.uuid4()), self._now()
        self._execute("INSERT INTO cycles(cycle_id, fingerprint, status, created_at, input_json) VALUES(?,?,?,?,?)", (cycle_id, fingerprint, "PLANNED", now, self._encode({"results": experiment_results, "total_budget": total_budget})))
        risks = {item.creative_id: item for item in outcome["risk_reports"]}
        for decision in outcome["decisions"]:
            task = self.engine.create_task({"creative_id": decision.creative_id, "action": decision.decision, "budget_change": {"current": decision.budget_before, "target": decision.budget_after}, "reason": [decision.reason]})
            risk = risks.get(decision.creative_id)
            if risk:
                risk_level = "CRITICAL" if risk.blocking else ("WARNING" if "WARNING" in {risk.budget_risk, risk.scale_risk, risk.diversity_risk} else "SAFE")
                task.risk_level = risk_level
                task.approval_required = risk_level != "SAFE" or task.action_type == "KILL"
            task.experiment_id, task.growth_decision_id = decision.experiment_id, decision.decision_id
            self._record_task(cycle_id, task.to_dict(), now)
            self._record_event(cycle_id, task.task_id, "TASK_CREATED", task.status, task.to_dict(), now)
        self._execute("UPDATE cycles SET status=? WHERE cycle_id=?", ("AWAITING_EXECUTION", cycle_id))
        return self.cycle(cycle_id)

    def execute(self, cycle_id: str) -> dict[str, Any]:
        snapshot = self.cycle(cycle_id)
        if snapshot is None:
            raise KeyError(f"Unknown cycle: {cycle_id}")
        for row in snapshot["tasks"]:
            task = self._hydrate_task(row["task_id"])
            result = self.engine.execute(task)
            self._save_task(task.to_dict())
            self._record_event(cycle_id, task.task_id, "EXECUTION_RESULT", result.status, result.to_dict(), self._now())
            approval = self.engine.approval_gate.get_decision_for_task(task.task_id)
            if approval:
                self._save_approval(cycle_id, approval.to_dict())
        self._refresh_cycle_status(cycle_id)
        return self.cycle(cycle_id)

    def approve(self, task_id: str, approved_by: str) -> dict[str, Any]:
        task = self._hydrate_task(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        approved = self.engine.approve_task(task_id, approved_by=approved_by)
        if approved is None:
            raise ValueError(f"Task cannot be approved: {task_id}")
        self._save_task(approved.to_dict())
        cycle_id, decision = self._task_cycle(task_id), self.engine.approval_gate.get_decision_for_task(task_id)
        if cycle_id and decision:
            self._save_approval(cycle_id, decision.to_dict())
            self._record_event(cycle_id, task_id, "APPROVAL_GRANTED", approved.status, {"approved_by": approved_by}, self._now())
        return approved.to_dict()

    def observe(self, task_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        task = self._one("SELECT status FROM tasks WHERE task_id=?", (task_id,))
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        if task["status"] != ExecutionStatus.COMPLETED.value:
            raise ValueError("Performance evidence is accepted only after completed execution")
        spend, revenue = float(metrics.get("spend", 0.0) or 0.0), float(metrics.get("revenue", 0.0) or 0.0)
        snapshot = PerformanceSnapshot(task_id=task_id, impressions=int(metrics.get("impressions", 0) or 0), clicks=int(metrics.get("clicks", 0) or 0), conversions=int(metrics.get("conversions", 0) or 0), spend=spend, revenue=revenue, roas=float(metrics.get("roas", revenue / spend if spend else 0.0) or 0.0), ctr=float(metrics.get("ctr", 0.0) or 0.0), cvr=float(metrics.get("cvr", 0.0) or 0.0), status=str(metrics.get("status", "active")))
        signal, cycle_id = self.feedback.generate(snapshot), self._task_cycle(task_id)
        self._execute("INSERT INTO observations(observation_id, cycle_id, task_id, snapshot_json, signal_json, created_at) VALUES(?,?,?,?,?,?)", (snapshot.snapshot_id, cycle_id, task_id, self._encode(snapshot.to_dict()), self._encode(signal.to_dict()), self._now()))
        if cycle_id:
            self._record_event(cycle_id, task_id, "LEARNING_SIGNAL", signal.feedback_type, signal.to_dict(), self._now())
        return {"snapshot": snapshot.to_dict(), "signal": signal.to_dict()}

    def cycle(self, cycle_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM cycles WHERE cycle_id=?", (cycle_id,))
        if row is None:
            return None
        return {"cycle_id": row["cycle_id"], "status": row["status"], "created_at": row["created_at"], "tasks": [json.loads(x["task_json"]) for x in self._all("SELECT task_json FROM tasks WHERE cycle_id=? ORDER BY created_at", (cycle_id,))], "approvals": [json.loads(x["approval_json"]) for x in self._all("SELECT approval_json FROM approvals WHERE cycle_id=? ORDER BY created_at", (cycle_id,))], "observations": [{"snapshot": json.loads(x["snapshot_json"]), "signal": json.loads(x["signal_json"])} for x in self._all("SELECT snapshot_json, signal_json FROM observations WHERE cycle_id=? ORDER BY created_at", (cycle_id,))]}

    def overview(self) -> dict[str, Any]:
        rows = self._all("SELECT status, COUNT(*) AS count FROM cycles GROUP BY status")
        pending = self._one("SELECT COUNT(*) AS count FROM tasks WHERE status=?", (ExecutionStatus.PENDING_APPROVAL.value,))
        return {"cycles": {x["status"]: x["count"] for x in rows}, "pending_approvals": pending["count"] if pending else 0}

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS cycles (cycle_id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, input_json TEXT NOT NULL); CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL, status TEXT NOT NULL, task_json TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS approvals (decision_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL, task_id TEXT NOT NULL, approval_json TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS observations (observation_id TEXT PRIMARY KEY, cycle_id TEXT, task_id TEXT NOT NULL, snapshot_json TEXT NOT NULL, signal_json TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS audit_events (event_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL, task_id TEXT, event_type TEXT NOT NULL, state TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);""")

    def _record_task(self, cycle_id: str, task: dict[str, Any], now: str) -> None:
        self._execute("INSERT INTO tasks(task_id, cycle_id, status, task_json, created_at) VALUES(?,?,?,?,?)", (task["task_id"], cycle_id, task["status"], self._encode(task), now))

    def _save_task(self, task: dict[str, Any]) -> None:
        self._execute("UPDATE tasks SET status=?, task_json=? WHERE task_id=?", (task["status"], self._encode(task), task["task_id"]))

    def _save_approval(self, cycle_id: str, approval: dict[str, Any]) -> None:
        self._execute("INSERT OR REPLACE INTO approvals(decision_id, cycle_id, task_id, approval_json, created_at) VALUES(?,?,?,?,?)", (approval["decision_id"], cycle_id, approval["task_id"], self._encode(approval), approval["created_at"]))

    def _record_event(self, cycle_id: str, task_id: str | None, event: str, state: str, payload: dict[str, Any], now: str) -> None:
        self._execute("INSERT INTO audit_events(event_id, cycle_id, task_id, event_type, state, payload_json, created_at) VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()), cycle_id, task_id, event, state, self._encode(payload), now))

    def _refresh_cycle_status(self, cycle_id: str) -> None:
        statuses = [x["status"] for x in self._all("SELECT status FROM tasks WHERE cycle_id=?", (cycle_id,))]
        status = "EXECUTED" if statuses and all(x in {ExecutionStatus.COMPLETED.value, ExecutionStatus.ROLLED_BACK.value} for x in statuses) else "AWAITING_APPROVAL" if ExecutionStatus.PENDING_APPROVAL.value in statuses else "AWAITING_EXECUTION"
        self._execute("UPDATE cycles SET status=? WHERE cycle_id=?", (status, cycle_id))

    def _cycle_by_fingerprint(self, fingerprint: str) -> str | None:
        row = self._one("SELECT cycle_id FROM cycles WHERE fingerprint=?", (fingerprint,))
        return row["cycle_id"] if row else None

    def _hydrate_task(self, task_id: str) -> ExecutionTask | None:
        task = self.engine.get_task(task_id)
        if task is not None:
            return task
        row = self._one("SELECT task_json FROM tasks WHERE task_id=?", (task_id,))
        if row is None:
            return None
        payload = json.loads(row["task_json"])
        task = ExecutionTask(**payload)
        self.engine._tasks[task.task_id] = task
        return task

    def _task_cycle(self, task_id: str) -> str | None:
        row = self._one("SELECT cycle_id FROM tasks WHERE task_id=?", (task_id,))
        return row["cycle_id"] if row else None

    @staticmethod
    def _fingerprint(results: list[dict[str, Any]], budget: float) -> str:
        return hashlib.sha256(json.dumps({"results": results, "total_budget": budget}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _encode(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.database_path)
        c.row_factory = sqlite3.Row
        return c

    def _execute(self, sql: str, args: tuple[Any, ...]) -> None:
        with self._connect() as c:
            c.execute(sql, args)

    def _one(self, sql: str, args: tuple[Any, ...]) -> sqlite3.Row | None:
        with self._connect() as c:
            return c.execute(sql, args).fetchone()

    def _all(self, sql: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._connect() as c:
            return c.execute(sql, args).fetchall()
