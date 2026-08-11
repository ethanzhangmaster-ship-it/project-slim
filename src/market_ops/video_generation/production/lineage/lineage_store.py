"""Lineage Store - 资产血缘存储"""
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from datetime import datetime

from .asset_graph import AssetNode


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS asset_lineage (
    asset_id TEXT PRIMARY KEY,
    parent_id TEXT,
    asset_type TEXT,
    prompt_dna TEXT,
    platform TEXT,
    seed INTEGER,
    created_at TIMESTAMP,
    metrics TEXT
);

CREATE INDEX IF NOT EXISTS idx_parent_id ON asset_lineage(parent_id);
CREATE INDEX IF NOT EXISTS idx_platform ON asset_lineage(platform);
CREATE INDEX IF NOT EXISTS idx_asset_type ON asset_lineage(asset_type);
"""


class LineageStore:
    """资产血缘存储 - SQLite 持久化"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent / "lineage.db"
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

    def save(self, node: AssetNode):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO asset_lineage
                (asset_id, parent_id, asset_type, prompt_dna, platform, seed, created_at, metrics)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.asset_id,
                node.parent_id,
                node.asset_type,
                node.prompt_dna,
                node.platform,
                node.seed,
                datetime.now().isoformat(),
                json.dumps(node.metrics, ensure_ascii=False),
            ))

    def load(self, asset_id: str) -> Optional[AssetNode]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM asset_lineage WHERE asset_id = ?",
                (asset_id,)
            ).fetchone()
            if row:
                return AssetNode(
                    asset_id=row["asset_id"],
                    parent_id=row["parent_id"] or "",
                    asset_type=row["asset_type"] or "",
                    prompt_dna=row["prompt_dna"] or "",
                    platform=row["platform"] or "",
                    seed=row["seed"] or 0,
                    metrics=json.loads(row["metrics"] or "{}"),
                )
            return None

    def load_children(self, parent_id: str) -> List[AssetNode]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM asset_lineage WHERE parent_id = ?",
                (parent_id,)
            ).fetchall()
            return [
                AssetNode(
                    asset_id=r["asset_id"],
                    parent_id=r["parent_id"] or "",
                    asset_type=r["asset_type"] or "",
                    prompt_dna=r["prompt_dna"] or "",
                    platform=r["platform"] or "",
                    seed=r["seed"] or 0,
                    metrics=json.loads(r["metrics"] or "{}"),
                )
                for r in rows
            ]

    def update_metrics(self, asset_id: str, metrics: Dict[str, Any]):
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT metrics FROM asset_lineage WHERE asset_id = ?",
                (asset_id,)
            ).fetchone()
            if existing:
                current = json.loads(existing["metrics"] or "{}")
                current.update(metrics)
                conn.execute(
                    "UPDATE asset_lineage SET metrics = ? WHERE asset_id = ?",
                    (json.dumps(current, ensure_ascii=False), asset_id),
                )

    def get_by_platform(self, platform: str, limit: int = 100) -> List[AssetNode]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM asset_lineage WHERE platform = ? LIMIT ?",
                (platform, limit)
            ).fetchall()
            return [
                AssetNode(
                    asset_id=r["asset_id"],
                    parent_id=r["parent_id"] or "",
                    asset_type=r["asset_type"] or "",
                    prompt_dna=r["prompt_dna"] or "",
                    platform=r["platform"] or "",
                    seed=r["seed"] or 0,
                    metrics=json.loads(r["metrics"] or "{}"),
                )
                for r in rows
            ]

    def get_top_performers(self, min_ctr: float = 3.0, limit: int = 10) -> List[AssetNode]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM asset_lineage ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
            nodes = []
            for r in rows:
                metrics = json.loads(r["metrics"] or "{}")
                if metrics.get("ctr", 0) >= min_ctr:
                    nodes.append(AssetNode(
                        asset_id=r["asset_id"],
                        parent_id=r["parent_id"] or "",
                        asset_type=r["asset_type"] or "",
                        prompt_dna=r["prompt_dna"] or "",
                        platform=r["platform"] or "",
                        seed=r["seed"] or 0,
                        metrics=metrics,
                    ))
            return sorted(nodes, key=lambda n: n.metrics.get("ctr", 0), reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM asset_lineage").fetchone()[0]
            by_platform = {}
            rows = conn.execute("SELECT platform, COUNT(*) as cnt FROM asset_lineage GROUP BY platform").fetchall()
            for r in rows:
                by_platform[r["platform"]] = r["cnt"]
            return {
                "total_assets": total,
                "by_platform": by_platform,
            }