"""Generation Storage - SQLite 存储"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from ..orchestrator.generation_task import GenerationTask
from ..orchestrator.generation_state import GenerationStatus


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS generation_tasks (
    task_id TEXT PRIMARY KEY,
    blueprint_id TEXT,
    scene_id TEXT,
    platform TEXT,
    status TEXT,
    priority INTEGER,
    progress REAL,
    cost REAL,
    prompt TEXT,
    result TEXT,
    error TEXT,
    retry_count INTEGER,
    max_retries INTEGER,
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    duration REAL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS generation_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    video_path TEXT,
    thumbnail_path TEXT,
    quality_score REAL,
    hook_score REAL,
    product_visibility REAL,
    review_result TEXT,
    review_notes TEXT,
    created_at TEXT,
    FOREIGN KEY (task_id) REFERENCES generation_tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON generation_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_platform ON generation_tasks(platform);
CREATE INDEX IF NOT EXISTS idx_outputs_task_id ON generation_outputs(task_id);
"""


class GenerationStorage:
    """SQLite 存储层"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent / "generation.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA_SQL)

    def save_task(self, task: GenerationTask):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO generation_tasks
                (task_id, blueprint_id, scene_id, platform, status, priority, progress,
                 cost, prompt, result, error, retry_count, max_retries,
                 created_at, started_at, completed_at, duration, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.blueprint_id,
                task.scene_id,
                task.platform,
                task.status.value if isinstance(task.status, GenerationStatus) else str(task.status),
                task.priority,
                task.progress,
                task.cost,
                json.dumps(task.prompt, ensure_ascii=False),
                json.dumps(task.result, ensure_ascii=False),
                task.error,
                task.retry_count,
                task.max_retries,
                task.created_at,
                task.started_at,
                task.completed_at,
                task.duration,
                json.dumps(task.metadata, ensure_ascii=False),
            ))

    def get_task(self, task_id: str) -> Optional[GenerationTask]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM generation_tasks WHERE task_id = ?",
                (task_id,)
            ).fetchone()
            if row:
                return self._row_to_task(row)
            return None

    def list_tasks(self, status: str = None, platform: str = None, limit: int = 100) -> List[GenerationTask]:
        query = "SELECT * FROM generation_tasks WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(row) for row in rows]

    def _row_to_task(self, row: sqlite3.Row) -> GenerationTask:
        return GenerationTask(
            task_id=row["task_id"],
            blueprint_id=row["blueprint_id"] or "",
            scene_id=row["scene_id"] or "",
            platform=row["platform"] or "",
            status=GenerationStatus(row["status"]) if row["status"] else GenerationStatus.CREATED,
            priority=row["priority"] or 5,
            progress=row["progress"] or 0.0,
            cost=row["cost"] or 0.0,
            prompt=json.loads(row["prompt"] or "{}"),
            result=json.loads(row["result"] or "{}"),
            error=row["error"],
            retry_count=row["retry_count"] or 0,
            max_retries=row["max_retries"] or 3,
            created_at=row["created_at"] or "",
            started_at=row["started_at"] or "",
            completed_at=row["completed_at"] or "",
            duration=row["duration"] or 0.0,
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def add_output(self, task_id: str, video_path: str, quality_score: float = 0.0,
                   review_result: str = "pending"):
        from datetime import datetime
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO generation_outputs
                (task_id, video_path, quality_score, review_result, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                task_id,
                video_path,
                quality_score,
                review_result,
                datetime.now().isoformat(),
            ))

    def get_outputs(self, task_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM generation_outputs WHERE task_id = ? ORDER BY created_at DESC",
                (task_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM generation_tasks").fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM generation_tasks WHERE status = 'completed'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM generation_tasks WHERE status = 'failed'"
            ).fetchone()[0]
            total_cost = conn.execute(
                "SELECT COALESCE(SUM(cost), 0) FROM generation_tasks"
            ).fetchone()[0]

            return {
                "total_tasks": total,
                "completed": completed,
                "failed": failed,
                "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
                "total_cost": round(total_cost, 2),
            }
