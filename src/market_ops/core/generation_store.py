"""Phase 2.1.1: Generation Store — SQLite persistence with strict state machine.

Tracks every generation task end-to-end:
  - Task lifecycle: CREATE → PENDING → CLAIM → PROCESSING → SUCCESS/FAILED/RETRY
  - RETRY → PENDING → CLAIM → PROCESSING (retry loop)
  - Retry history with backoff timing
  - Cost tracking
  - Image metadata
"""

from __future__ import annotations

import enum
import random
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
# Status Enum
# ═══════════════════════════════════════════════════════════

class GenerationStatus(str, enum.Enum):
    """Strict state machine for generation task lifecycle."""
    PENDING = "PENDING"
    CLAIM = "CLAIM"
    PROCESSING = "PROCESSING"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

    def __str__(self) -> str:
        return self.value


# Valid transitions (including CLAIM release for crash recovery)
VALID_TRANSITIONS: dict[GenerationStatus, set[GenerationStatus]] = {
    GenerationStatus.PENDING:    {GenerationStatus.CLAIM},
    GenerationStatus.CLAIM:      {GenerationStatus.PROCESSING, GenerationStatus.PENDING},  # PENDING = release
    GenerationStatus.PROCESSING: {GenerationStatus.SUCCESS, GenerationStatus.RETRY, GenerationStatus.FAILED},
    GenerationStatus.RETRY:      {GenerationStatus.PENDING},
    GenerationStatus.SUCCESS:    set(),   # terminal
    GenerationStatus.FAILED:     set(),   # terminal
}

# Priority ordering (higher = more urgent)
PRIORITY_ORDER = {"high": 3, "normal": 2, "low": 1}

# Crash recovery timeouts (seconds)
CLAIM_TIMEOUT = 60        # CLAIM → PENDING if stuck > 60s
PROCESSING_TIMEOUT = 600  # PROCESSING → RETRY if stuck > 10min

# Retry jitter range (seconds)
RETRY_JITTER = 5  # ±5s random jitter


# ═══════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    id              TEXT PRIMARY KEY,
    creative_id     TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    negative_prompt TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'PENDING',
    priority        TEXT NOT NULL DEFAULT 'normal',
    image_path      TEXT DEFAULT '',
    image_url       TEXT DEFAULT '',
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3,
    generation_time REAL DEFAULT 0,
    cost            REAL DEFAULT 0,
    model           TEXT DEFAULT 'lovart',
    format          TEXT DEFAULT '1080x1080',
    quality_score   INTEGER DEFAULT 0,
    error_message   TEXT DEFAULT '',
    last_error      TEXT DEFAULT '',
    worker_id       TEXT DEFAULT '',
    claimed_by      TEXT DEFAULT '',
    claim_time      TEXT DEFAULT '',
    next_retry_time TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    dna_source      TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_generations_status ON generations(status);
CREATE INDEX IF NOT EXISTS idx_generations_priority ON generations(priority);
CREATE INDEX IF NOT EXISTS idx_generations_creative ON generations(creative_id);
CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at);
CREATE INDEX IF NOT EXISTS idx_generations_next_retry ON generations(next_retry_time);
"""

# Migration: add columns for DBs created before Phase 2.1.1
MIGRATION_V211 = [
    "ALTER TABLE generations ADD COLUMN last_error TEXT DEFAULT ''",
    "ALTER TABLE generations ADD COLUMN claimed_by TEXT DEFAULT ''",
    "ALTER TABLE generations ADD COLUMN claim_time TEXT DEFAULT ''",
    "ALTER TABLE generations ADD COLUMN next_retry_time TEXT DEFAULT ''",
]


# ═══════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════

class GenerationStore:
    """SQLite-backed store for generation task lifecycle with strict state machine."""

    def __init__(self, db_path: str | Path = "output/creative_analysis/generations.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        with self._get_conn() as conn:
            conn.executescript(SCHEMA)
            self._run_migrations(conn)
            conn.commit()

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Apply schema migrations for backward compatibility."""
        for sql in MIGRATION_V211:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _validate_transition(self, current: str, target: str) -> None:
        """Validate state machine transition."""
        try:
            cur = GenerationStatus(current)
            tgt = GenerationStatus(target)
        except ValueError:
            return  # Unknown status, allow for backward compat

        if tgt not in VALID_TRANSITIONS.get(cur, set()):
            raise ValueError(
                f"Invalid state transition: {cur} → {target}. "
                f"Valid: {VALID_TRANSITIONS.get(cur, set())}"
            )

    # ── CRUD ──

    def insert(self, task: dict[str, Any]) -> None:
        """Insert a new generation task."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """INSERT INTO generations
                   (id, creative_id, prompt, negative_prompt, status, priority,
                    retry_count, max_retries, format, dna_source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task["id"],
                    task.get("creative_id", ""),
                    task.get("prompt", ""),
                    task.get("negative_prompt", ""),
                    task.get("status", "PENDING"),
                    task.get("priority", "normal"),
                    task.get("retry_count", 0),
                    task.get("max_retries", 3),
                    task.get("format", "1080x1080"),
                    task.get("dna_source", ""),
                    now,
                    now,
                ),
            )
            conn.commit()

    def update_status(self, task_id: str, status: str, **kwargs: Any) -> None:
        """Update task status and optional fields. Enforces state machine transitions."""
        now = datetime.now(timezone.utc).isoformat()

        # Read current status for transition validation
        current = self.get(task_id)
        if current:
            self._validate_transition(current["status"], status)

        fields = ["status = ?", "updated_at = ?"]
        values: list[Any] = [status, now]

        for key in ("image_path", "image_url", "generation_time", "cost",
                     "model", "quality_score", "error_message", "last_error",
                     "worker_id", "claimed_by", "claim_time", "next_retry_time",
                     "retry_count"):
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])

        values.append(task_id)
        with self._lock, self._get_conn() as conn:
            conn.execute(
                f"UPDATE generations SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()

    def get(self, task_id: str) -> dict[str, Any] | None:
        """Get a single task by ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM generations WHERE id = ?", (task_id,)).fetchone()
            if row:
                return dict(row)
            return None

    def get_pending(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get pending tasks ordered by priority (HIGH→NORMAL→LOW) then creation time."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM generations
                   WHERE status = 'PENDING'
                   ORDER BY
                     CASE priority WHEN 'high' THEN 3 WHEN 'normal' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
                     created_at ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def claim_task(self, task_id: str, worker_id: str) -> bool:
        """Atomically claim a task: PENDING → CLAIM."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            cursor = conn.execute(
                """UPDATE generations SET
                   status = 'CLAIM', claimed_by = ?, claim_time = ?, updated_at = ?
                   WHERE id = ? AND status = 'PENDING'""",
                (worker_id, now, now, task_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def start_processing(self, task_id: str, worker_id: str = "") -> bool:
        """Transition a claimed task: CLAIM → PROCESSING. Validates ownership."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            if worker_id:
                # Ownership check: only the claiming worker can start processing
                cursor = conn.execute(
                    """UPDATE generations SET
                       status = 'PROCESSING', updated_at = ?
                       WHERE id = ? AND status = 'CLAIM' AND claimed_by = ?""",
                    (now, task_id, worker_id),
                )
            else:
                cursor = conn.execute(
                    """UPDATE generations SET
                       status = 'PROCESSING', updated_at = ?
                       WHERE id = ? AND status = 'CLAIM'""",
                    (now, task_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    def schedule_retry(self, task_id: str, retry_count: int, delay_seconds: int, error: str) -> None:
        """Set a task to RETRY status with next_retry_time."""
        now = datetime.now(timezone.utc)
        next_retry = (now + timedelta(seconds=delay_seconds)).isoformat()
        self.update_status(
            task_id,
            "RETRY",
            retry_count=retry_count,
            last_error=error,
            next_retry_time=next_retry,
        )

    def complete_task(self, task_id: str, image_path: str = "", image_url: str = "",
                      generation_time: float = 0, cost: float = 0, model: str = "lovart",
                      quality_score: int = 0) -> None:
        """Mark a task as successfully completed: PROCESSING → SUCCESS."""
        self.update_status(
            task_id,
            "SUCCESS",
            image_path=image_path,
            image_url=image_url,
            generation_time=generation_time,
            cost=cost,
            model=model,
            quality_score=quality_score,
        )

    def fail_task(self, task_id: str, error_message: str) -> None:
        """Mark a task as permanently failed: PROCESSING → FAILED."""
        self.update_status(
            task_id,
            "FAILED",
            error_message=error_message,
            last_error=error_message,
        )

    def get_failed_retryable(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get failed/retry tasks that can be retried."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM generations
                   WHERE status IN ('FAILED', 'RETRY') AND retry_count < max_retries
                   ORDER BY
                     CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
                     created_at ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate generation statistics with retry analysis."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as cnt FROM generations GROUP BY status"
            ).fetchall():
                by_status[row["status"]] = row["cnt"]

            avg_time = conn.execute(
                "SELECT AVG(generation_time) FROM generations WHERE status = 'SUCCESS'"
            ).fetchone()[0] or 0

            total_cost = conn.execute(
                "SELECT SUM(cost) FROM generations WHERE status = 'SUCCESS'"
            ).fetchone()[0] or 0

            avg_quality = conn.execute(
                "SELECT AVG(quality_score) FROM generations WHERE status = 'SUCCESS'"
            ).fetchone()[0] or 0

            # Retry analysis
            avg_retry = conn.execute(
                "SELECT AVG(retry_count) FROM generations WHERE status = 'SUCCESS' AND retry_count > 0"
            ).fetchone()[0] or 0

            retried_success = conn.execute(
                "SELECT COUNT(*) FROM generations WHERE status = 'SUCCESS' AND retry_count > 0"
            ).fetchone()[0]

            success_total = by_status.get("SUCCESS", 0)

            return {
                "total": total,
                "by_status": by_status,
                "success_count": success_total,
                "failed_count": by_status.get("FAILED", 0),
                "processing_count": by_status.get("PROCESSING", 0),
                "pending_count": by_status.get("PENDING", 0),
                "claim_count": by_status.get("CLAIM", 0),
                "retry_count": by_status.get("RETRY", 0),
                "success_rate": (success_total / total * 100) if total > 0 else 0,
                "avg_generation_time": round(avg_time, 1),
                "total_cost": round(total_cost, 2),
                "avg_quality": round(avg_quality, 1),
                "retry_analysis": {
                    "avg_retry_count": round(avg_retry, 1),
                    "retried_success": retried_success,
                    "retry_success_rate": (retried_success / success_total * 100) if success_total > 0 else 0,
                },
            }

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        """List all tasks, most recent first."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM generations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def reset_stuck(self, max_minutes: int = 10) -> int:
        """Reset stuck CLAIM/PROCESSING tasks back to PENDING."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            cursor = conn.execute(
                """UPDATE generations SET status = 'PENDING', error_message = 'reset: stuck',
                   last_error = 'reset: stuck > %dmin', updated_at = ?
                   WHERE status IN ('CLAIM', 'PROCESSING')
                   AND updated_at < datetime('now', ? || ' minutes')""" % max_minutes,
                (now, f'-{max_minutes}'),
            )
            conn.commit()
            return cursor.rowcount

    def recovery_scan(self) -> dict[str, int]:
        """Crash recovery: scan for zombie tasks stuck in CLAIM or PROCESSING.

        CLAIM > 60s → PENDING (worker crashed before starting)
        PROCESSING > 10min → RETRY (worker crashed mid-generation)
        """
        now = datetime.now(timezone.utc)
        result = {"claim_released": 0, "processing_retried": 0}

        with self._lock, self._get_conn() as conn:
            # Stuck CLAIM → PENDING
            claim_cutoff = (now - timedelta(seconds=CLAIM_TIMEOUT)).isoformat()
            cursor = conn.execute(
                """UPDATE generations SET
                   status = 'PENDING',
                   error_message = 'recovery: claim timeout',
                   last_error = 'recovery: claim_timeout > %ds',
                   claimed_by = '',
                   claim_time = '',
                   updated_at = ?
                   WHERE status = 'CLAIM'
                   AND updated_at < ?""",
                (now.isoformat(), claim_cutoff),
            )
            result["claim_released"] = cursor.rowcount

            # Stuck PROCESSING → RETRY
            proc_cutoff = (now - timedelta(seconds=PROCESSING_TIMEOUT)).isoformat()
            cursor = conn.execute(
                """UPDATE generations SET
                   status = 'RETRY',
                   error_message = 'recovery: processing timeout',
                   last_error = 'recovery: processing_timeout > %ds',
                   next_retry_time = ?,
                   updated_at = ?
                   WHERE status = 'PROCESSING'
                   AND updated_at < ?""",
                (now.isoformat(), now.isoformat(), proc_cutoff),
            )
            result["processing_retried"] = cursor.rowcount

            conn.commit()
        return result

    def start_recovery_thread(self, interval: int = 30, daemon: bool = True) -> threading.Thread:
        """Start a background thread that periodically runs recovery_scan."""
        def _recovery_loop():
            while True:
                time.sleep(interval)
                try:
                    result = self.recovery_scan()
                    if result["claim_released"] > 0 or result["processing_retried"] > 0:
                        print(f"  [Recovery] Released {result['claim_released']} stuck claims, "
                              f"retried {result['processing_retried']} stuck processing")
                except Exception as e:
                    print(f"  [Recovery] Error: {e}")

        t = threading.Thread(target=_recovery_loop, daemon=daemon, name="recovery")
        t.start()
        return t