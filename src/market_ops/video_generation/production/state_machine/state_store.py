"""State Store - 状态持久化存储"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from datetime import datetime

from .generation_state import GenerationState
from .state_transition import TransitionRecord


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS generation_state (
    id INTEGER PRIMARY KEY,
    generation_id TEXT,
    state TEXT,
    timestamp TIMESTAMP,
    reason TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS state_transitions (
    id INTEGER PRIMARY KEY,
    generation_id TEXT,
    from_state TEXT,
    to_state TEXT,
    timestamp TIMESTAMP,
    reason TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_generation_id ON generation_state(generation_id);
CREATE INDEX IF NOT EXISTS idx_state ON generation_state(state);
CREATE INDEX IF NOT EXISTS idx_transitions_gen_id ON state_transitions(generation_id);
"""


class StateStore:
    """状态存储 - SQLite 持久化"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent / "state.db"
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

    def save_state(self, generation_id: str, state: GenerationState, reason: str = "", metadata: Dict[str, Any] = None):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO generation_state (generation_id, state, timestamp, reason, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                generation_id,
                state.value,
                datetime.now().isoformat() if 'datetime' not in dir() else __import__('datetime').datetime.now().isoformat(),
                reason,
                json.dumps(metadata or {}, ensure_ascii=False),
            ))

    def record_transition(self, record: TransitionRecord):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO state_transitions (generation_id, from_state, to_state, timestamp, reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record.generation_id,
                record.from_state,
                record.to_state,
                record.timestamp,
                record.reason,
                json.dumps(record.metadata, ensure_ascii=False),
            ))

    def get_current_state(self, generation_id: str) -> Optional[GenerationState]:
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT state FROM generation_state
                WHERE generation_id = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (generation_id,)).fetchone()
            if row:
                return GenerationState(row["state"])
            return None

    def get_transition_history(self, generation_id: str) -> List[TransitionRecord]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM state_transitions
                WHERE generation_id = ?
                ORDER BY timestamp ASC
            """, (generation_id,)).fetchall()
            return [
                TransitionRecord(
                    generation_id=r["generation_id"],
                    from_state=r["from_state"],
                    to_state=r["to_state"],
                    timestamp=r["timestamp"],
                    reason=r["reason"],
                    metadata=json.loads(r["metadata"] or "{}"),
                )
                for r in rows
            ]

    def get_by_state(self, state: GenerationState, limit: int = 100) -> List[str]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT DISTINCT generation_id FROM generation_state
                WHERE state = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (state.value, limit)).fetchall()
            return [r["generation_id"] for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(DISTINCT generation_id) FROM generation_state").fetchone()[0]
            by_state = {}
            for state in GenerationState:
                count = conn.execute(
                    "SELECT COUNT(*) FROM generation_state WHERE state = ?",
                    (state.value,)
                ).fetchone()[0]
                by_state[state.value] = count
            return {
                "total_generations": total,
                "by_state": by_state,
            }