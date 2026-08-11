"""Blueprint Memory - 蓝图记忆存储

使用 DuckDB 保存 Blueprint 与学习结果。

保存:
Blueprint → Video → CTR → IPM → Retention → Replay → ROAS → Winner

接口:
save_blueprint()
update_result()
top_blueprints()
winner_patterns()
learning_report()

数据库: blueprint_library.duckdb
"""
from __future__ import annotations

import json
import os
from typing import Any

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


DDL_STATEMENTS: list[str] = [
    "CREATE SEQUENCE IF NOT EXISTS seq_blueprint START 1",
    """
    CREATE TABLE IF NOT EXISTS blueprints (
        id                BIGINT DEFAULT nextval('seq_blueprint') PRIMARY KEY,
        variant_id        VARCHAR,
        dna               JSON,
        blueprint         JSON,
        storyboard        JSON,
        shotlist          JSON,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS results (
        id                BIGINT DEFAULT nextval('seq_blueprint') PRIMARY KEY,
        variant_id        VARCHAR,
        ctr               DOUBLE,
        ipm               DOUBLE,
        retention         DOUBLE,
        replay_rate       DOUBLE,
        roas              DOUBLE,
        spend             DOUBLE,
        is_winner         BOOLEAN,
        recorded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata          JSON
    )
    """,
]


class BlueprintMemory:
    """蓝图记忆存储"""

    def __init__(self, db_path: str = "output/video_blueprint/database/blueprint_library.duckdb"):
        self.db_path = db_path
        self._conn = None
        if HAS_DUCKDB:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            self._conn = duckdb.connect(db_path)
            self._init_schema()

    def _init_schema(self) -> None:
        if not self._conn:
            return
        for ddl in DDL_STATEMENTS:
            try:
                self._conn.execute(ddl)
            except Exception:
                pass

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def save_blueprint(
        self,
        variant_id: str,
        dna: dict[str, Any],
        blueprint: dict[str, Any],
        storyboard: dict[str, Any],
        shotlist: dict[str, Any],
    ) -> None:
        """保存 Blueprint"""
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT INTO blueprints (variant_id, dna, blueprint, storyboard, shotlist)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    variant_id,
                    json.dumps(dna, ensure_ascii=False),
                    json.dumps(blueprint, ensure_ascii=False),
                    json.dumps(storyboard, ensure_ascii=False),
                    json.dumps(shotlist, ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    def update_result(
        self,
        variant_id: str,
        ctr: float = 0.0,
        ipm: float = 0.0,
        retention: float = 0.0,
        replay_rate: float = 0.0,
        roas: float = 0.0,
        spend: float = 0.0,
        is_winner: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """更新表现结果"""
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT INTO results (variant_id, ctr, ipm, retention, replay_rate, roas, spend, is_winner, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    variant_id, ctr, ipm, retention, replay_rate, roas, spend, is_winner,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    def top_blueprints(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取 Top Blueprints"""
        if not self._conn:
            return []
        try:
            rows = self._conn.execute(
                """
                SELECT b.variant_id, b.dna, b.blueprint,
                       r.ctr, r.roas, r.is_winner
                FROM blueprints b
                LEFT JOIN results r ON b.variant_id = r.variant_id
                ORDER BY r.roas DESC NULLS LAST
                LIMIT ?
                """,
                [limit],
            ).fetchall()
            keys = ["variant_id", "dna", "blueprint", "ctr", "roas", "is_winner"]
            return [dict(zip(keys, row)) for row in rows]
        except Exception:
            return []

    def winner_patterns(self, min_roas: float = 1.5) -> list[dict[str, Any]]:
        """获取 Winner 模式"""
        if not self._conn:
            return []
        try:
            rows = self._conn.execute(
                """
                SELECT b.dna, COUNT(*) as count, AVG(r.roas) as avg_roas
                FROM blueprints b
                JOIN results r ON b.variant_id = r.variant_id
                WHERE r.is_winner = TRUE AND r.roas >= ?
                GROUP BY b.dna
                ORDER BY avg_roas DESC
                LIMIT 20
                """,
                [min_roas],
            ).fetchall()
            keys = ["dna", "count", "avg_roas"]
            return [dict(zip(keys, row)) for row in rows]
        except Exception:
            return []

    def learning_report(self) -> dict[str, Any]:
        """生成学习报告"""
        if not self._conn:
            return {}
        try:
            stats = {}
            for table in ("blueprints", "results"):
                cnt = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                stats[table] = cnt

            row = self._conn.execute(
                """
                SELECT AVG(ctr), AVG(ipm), AVG(retention), AVG(roas),
                       SUM(is_winner::INT), SUM(spend)
                FROM results
                """
            ).fetchone()
            if row:
                stats.update({
                    "avg_ctr": float(row[0] or 0),
                    "avg_ipm": float(row[1] or 0),
                    "avg_retention": float(row[2] or 0),
                    "avg_roas": float(row[3] or 0),
                    "winner_count": int(row[4] or 0),
                    "total_spend": float(row[5] or 0),
                })
            return stats
        except Exception:
            return {}
