"""Phase 2.2A: Observability Store — independent SQLite database for observability.

Provides:
  - Separate SQLite observability database (read-only on core production data)
  - Worker status tracking with heartbeat
  - Metrics snapshots for throughput/latency/queue analysis
  - Alert log

All modules are READ-ONLY on Phase 2.1/2.1.1 core business state.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════

OBSERVABILITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS worker_status (
    worker_id       TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'IDLE',
    current_task    TEXT DEFAULT '',
    heartbeat_at    TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    last_error      TEXT DEFAULT '',
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS generation_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at     TEXT NOT NULL,
    metric_name     TEXT NOT NULL,
    metric_value    REAL NOT NULL,
    tags            TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS latency_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    queue_wait_ms   REAL DEFAULT 0,
    claim_delay_ms  REAL DEFAULT 0,
    generation_ms   REAL DEFAULT 0,
    validation_ms   REAL DEFAULT 0,
    download_ms     REAL DEFAULT 0,
    total_ms        REAL DEFAULT 0,
    recorded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_at        TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'WARN',
    category        TEXT NOT NULL,
    message         TEXT NOT NULL,
    metric_value    REAL DEFAULT 0,
    threshold       REAL DEFAULT 0,
    acknowledged    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_snapshots_metric ON generation_snapshots(metric_name, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_time ON generation_snapshots(snapshot_at);
CREATE INDEX IF NOT EXISTS idx_latency_task ON latency_records(task_id);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON alert_log(alert_at);
"""


# ═══════════════════════════════════════════════════════════
# Observability Store
# ═══════════════════════════════════════════════════════════

class ObservabilityStore:
    """Read-only observability layer on top of core production data."""

    HEARTBEAT_TIMEOUT = 30  # seconds before worker considered offline

    def __init__(self, db_path: str | Path = "output/creative_analysis/observability.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        with self._get_conn() as conn:
            conn.executescript(OBSERVABILITY_SCHEMA)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    # ── Worker Status ──

    def register_worker(self, worker_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO worker_status (worker_id, heartbeat_at, started_at)
                   VALUES (?, ?, ?)""",
                (worker_id, now, now),
            )
            conn.commit()

    def heartbeat(self, worker_id: str, status: str = "RUNNING",
                  current_task: str = "", last_error: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """UPDATE worker_status SET
                   status = ?, heartbeat_at = ?, current_task = ?, last_error = ?
                   WHERE worker_id = ?""",
                (status, now, current_task, last_error, worker_id),
            )
            conn.commit()

    def increment_completed(self, worker_id: str) -> None:
        with self._lock, self._get_conn() as conn:
            conn.execute(
                "UPDATE worker_status SET tasks_completed = tasks_completed + 1 WHERE worker_id = ?",
                (worker_id,),
            )
            conn.commit()

    def increment_failed(self, worker_id: str) -> None:
        with self._lock, self._get_conn() as conn:
            conn.execute(
                "UPDATE worker_status SET tasks_failed = tasks_failed + 1 WHERE worker_id = ?",
                (worker_id,),
            )
            conn.commit()

    def get_workers(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM worker_status").fetchall()
            workers = []
            for r in rows:
                w = dict(r)
                try:
                    hb = datetime.fromisoformat(w["heartbeat_at"])
                    w["online"] = (now - hb).total_seconds() < self.HEARTBEAT_TIMEOUT
                except (ValueError, TypeError):
                    w["online"] = False
                workers.append(w)
            return workers

    # ── Snapshots ──

    def record_snapshot(self, metric_name: str, value: float, tags: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            conn.execute(
                "INSERT INTO generation_snapshots (snapshot_at, metric_name, metric_value, tags) VALUES (?, ?, ?, ?)",
                (now, metric_name, value, tags),
            )
            conn.commit()

    def get_snapshots(self, metric_name: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM generation_snapshots WHERE metric_name = ? ORDER BY snapshot_at DESC LIMIT ?",
                (metric_name, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_snapshot(self, metric_name: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM generation_snapshots WHERE metric_name = ? ORDER BY snapshot_at DESC LIMIT 1",
                (metric_name,),
            ).fetchone()
            return dict(row) if row else None

    # ── Latency ──

    def record_latency(self, task_id: str, queue_wait_ms: float = 0, claim_delay_ms: float = 0,
                       generation_ms: float = 0, validation_ms: float = 0, download_ms: float = 0,
                       total_ms: float = 0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """INSERT INTO latency_records
                   (task_id, queue_wait_ms, claim_delay_ms, generation_ms, validation_ms, download_ms, total_ms, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, queue_wait_ms, claim_delay_ms, generation_ms, validation_ms, download_ms, total_ms, now),
            )
            conn.commit()

    def get_latency_stats(self, hours: int = 24) -> dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT
                   COUNT(*) as count,
                   AVG(queue_wait_ms) as avg_queue_wait,
                   AVG(generation_ms) as avg_generation,
                   AVG(total_ms) as avg_total
                   FROM latency_records WHERE recorded_at > ?""",
                (cutoff,),
            ).fetchone()

            if not row or row["count"] == 0:
                return {"count": 0, "avg_queue_wait_ms": 0, "avg_generation_ms": 0, "avg_total_ms": 0}

            # Percentiles
            percentiles = {}
            for p in [50, 90, 95, 99]:
                p_row = conn.execute(
                    """SELECT total_ms FROM latency_records
                       WHERE recorded_at > ?
                       ORDER BY total_ms ASC
                       LIMIT 1 OFFSET (SELECT COUNT(*) FROM latency_records WHERE recorded_at > ?) * ? / 100 - 1""",
                    (cutoff, cutoff, p),
                ).fetchone()
                percentiles[f"p{p}"] = round(p_row["total_ms"], 0) if p_row and p_row["total_ms"] else 0

            return {
                "count": row["count"],
                "avg_queue_wait_ms": round(row["avg_queue_wait"] or 0, 1),
                "avg_generation_ms": round(row["avg_generation"] or 0, 1),
                "avg_total_ms": round(row["avg_total"] or 0, 1),
                "percentiles": percentiles,
            }

    # ── Alerts ──

    def log_alert(self, severity: str, category: str, message: str,
                  metric_value: float = 0, threshold: float = 0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """INSERT INTO alert_log (alert_at, severity, category, message, metric_value, threshold)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (now, severity, category, message, metric_value, threshold),
            )
            conn.commit()

    def get_recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM alert_log ORDER BY alert_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Throughput ──

    def get_throughput(self, hours: int = 1) -> dict[str, Any]:
        """Calculate throughput from snapshots."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM generation_snapshots
                   WHERE metric_name = 'image_generated' AND snapshot_at > ?""",
                (cutoff,),
            ).fetchone()
            count = row["cnt"] if row else 0
            return {
                "images_per_hour": count / hours if hours > 0 else 0,
                "period_hours": hours,
            }

    # ── Snapshot aggregator ──

    def snapshot_current_state(self, core_stats: dict[str, Any]) -> None:
        """Take a snapshot of current core production state. Called periodically."""
        self.record_snapshot("pending_count", core_stats.get("pending_count", 0))
        self.record_snapshot("processing_count", core_stats.get("processing_count", 0))
        self.record_snapshot("retry_count", core_stats.get("retry_count", 0))
        self.record_snapshot("success_count", core_stats.get("success_count", 0))
        self.record_snapshot("failed_count", core_stats.get("failed_count", 0))
        self.record_snapshot("success_rate", core_stats.get("success_rate", 0))
        self.record_snapshot("avg_generation_time", core_stats.get("avg_generation_time", 0))
        self.record_snapshot("total_cost", core_stats.get("total_cost", 0))