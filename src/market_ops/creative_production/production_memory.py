"""Production Memory - 生产记忆存储（DuckDB）

记录：
- Creative Script
- Storyboard
- Shot
- Workflow
- CTR
- CVR
- ROAS
- Spend
- Winner

支持持续学习。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


# 表 DDL
DDL_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS strategies (
        variant_id        VARCHAR PRIMARY KEY,
        objective         VARCHAR,
        hook              VARCHAR,
        emotion           VARCHAR,
        duration          DOUBLE,
        priority          INTEGER,
        platform          VARCHAR,
        country           VARCHAR,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata          JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scripts (
        script_id         VARCHAR PRIMARY KEY,
        variant_id        VARCHAR,
        total_duration    DOUBLE,
        segment_count     INTEGER,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        segments          JSON,
        metadata          JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS storyboards (
        storyboard_id     VARCHAR PRIMARY KEY,
        variant_id        VARCHAR,
        platform          VARCHAR,
        aspect_ratio      VARCHAR,
        scene_count       INTEGER,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        scenes            JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shot_lists (
        shot_list_id      VARCHAR PRIMARY KEY,
        variant_id        VARCHAR,
        total_shots       INTEGER,
        total_duration    DOUBLE,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        shots             JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS production_plans (
        plan_id           VARCHAR PRIMARY KEY,
        variant_id        VARCHAR,
        total_cost        DOUBLE,
        total_time_sec    DOUBLE,
        review_count      INTEGER,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source_summary    JSON,
        assignments       JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workflows (
        workflow_id       VARCHAR PRIMARY KEY,
        variant_id        VARCHAR,
        total_steps       INTEGER,
        total_duration_sec DOUBLE,
        executors_used    JSON,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        steps             JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS performance (
        id                BIGINT DEFAULT nextval('seq_performance') PRIMARY KEY,
        variant_id        VARCHAR,
        ctr               DOUBLE,
        cvr               DOUBLE,
        roas              DOUBLE,
        spend             DOUBLE,
        impressions       BIGINT,
        clicks            BIGINT,
        conversions       BIGINT,
        is_winner         BOOLEAN,
        recorded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata          JSON
    )
    """,
]


class ProductionMemory:
    """生产记忆存储"""

    def __init__(self, db_path: str = "output/creative_production/production_memory.duckdb"):
        self.db_path = db_path
        self._conn = None
        if HAS_DUCKDB:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            self._conn = duckdb.connect(db_path)
            self._init_schema()

    def _init_schema(self) -> None:
        if not self._conn:
            return
        # 先创建 sequence（如果不存在）
        try:
            self._conn.execute(
                "CREATE SEQUENCE IF NOT EXISTS seq_performance START 1"
            )
        except Exception:
            pass
        for ddl in DDL_STATEMENTS:
            try:
                self._conn.execute(ddl)
            except Exception:
                pass

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    def save_strategy(self, strategy: Any) -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO strategies
                (variant_id, objective, hook, emotion, duration, priority, platform, country, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    strategy.variant_id,
                    strategy.objective,
                    strategy.hook,
                    strategy.emotion,
                    strategy.duration,
                    strategy.priority,
                    strategy.platform,
                    strategy.country,
                    json.dumps(strategy.metadata or {}, ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    def save_script(self, script: Any) -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO scripts
                (script_id, variant_id, total_duration, segment_count, segments, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    script.script_id,
                    script.variant_id,
                    script.total_duration,
                    len(script.segments),
                    json.dumps([s.to_dict() for s in script.segments], ensure_ascii=False),
                    json.dumps(script.metadata or {}, ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    def save_storyboard(self, storyboard: Any) -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO storyboards
                (storyboard_id, variant_id, platform, aspect_ratio, scene_count, scenes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    storyboard.storyboard_id,
                    storyboard.variant_id,
                    storyboard.platform,
                    storyboard.aspect_ratio,
                    len(storyboard.scenes),
                    json.dumps([s.to_dict() for s in storyboard.scenes], ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    def save_shot_list(self, shot_list: Any) -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO shot_lists
                (shot_list_id, variant_id, total_shots, total_duration, shots)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    shot_list.shot_list_id,
                    shot_list.variant_id,
                    shot_list.total_shots,
                    shot_list.total_duration,
                    json.dumps([s.to_dict() for s in shot_list.shots], ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    def save_production_plan(self, plan: Any) -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO production_plans
                (plan_id, variant_id, total_cost, total_time_sec, review_count, source_summary, assignments)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    plan.plan_id,
                    plan.variant_id,
                    plan.total_estimated_cost,
                    plan.total_estimated_time_sec,
                    plan.requires_human_review_count,
                    json.dumps(plan.source_summary, ensure_ascii=False),
                    json.dumps([a.to_dict() for a in plan.assignments], ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    def save_workflow(self, workflow: Any) -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO workflows
                (workflow_id, variant_id, total_steps, total_duration_sec, executors_used, steps)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    workflow.workflow_id,
                    workflow.variant_id,
                    workflow.total_steps,
                    workflow.total_estimated_duration_sec,
                    json.dumps(workflow.executors_used, ensure_ascii=False),
                    json.dumps([s.to_dict() for s in workflow.steps], ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 性能记录
    # ------------------------------------------------------------------
    def record_performance(
        self,
        variant_id: str,
        ctr: float = 0.0,
        cvr: float = 0.0,
        roas: float = 0.0,
        spend: float = 0.0,
        impressions: int = 0,
        clicks: int = 0,
        conversions: int = 0,
        is_winner: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                """
                INSERT INTO performance
                (variant_id, ctr, cvr, roas, spend, impressions, clicks, conversions, is_winner, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    variant_id, ctr, cvr, roas, spend,
                    impressions, clicks, conversions, is_winner,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ],
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def get_winners(
        self,
        min_roas: float = 1.5,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取 Winner 列表（用于历史复用）"""
        if not self._conn:
            return []
        try:
            rows = self._conn.execute(
                """
                SELECT variant_id, ctr, cvr, roas, spend, impressions, clicks,
                       conversions, is_winner, recorded_at, metadata
                FROM performance
                WHERE is_winner = TRUE AND roas >= ?
                ORDER BY roas DESC
                LIMIT ?
                """,
                [min_roas, limit],
            ).fetchall()

            keys = [
                "variant_id", "ctr", "cvr", "roas", "spend", "impressions",
                "clicks", "conversions", "is_winner", "recorded_at", "metadata",
            ]
            out = []
            for row in rows:
                d = dict(zip(keys, row))
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except Exception:
                        pass
                out.append(d)
            return out
        except Exception:
            return []

    def get_strategy(self, variant_id: str) -> dict[str, Any] | None:
        """查询 strategy"""
        if not self._conn:
            return None
        try:
            row = self._conn.execute(
                "SELECT variant_id, objective, hook, emotion, duration, priority, platform, country FROM strategies WHERE variant_id = ?",
                [variant_id],
            ).fetchone()
            if not row:
                return None
            keys = ["variant_id", "objective", "hook", "emotion", "duration", "priority", "platform", "country"]
            return dict(zip(keys, row))
        except Exception:
            return None

    def get_stats(self) -> dict[str, Any]:
        """统计信息"""
        if not self._conn:
            return {}
        try:
            stats: dict[str, Any] = {}
            for table in ("strategies", "scripts", "storyboards", "shot_lists",
                          "production_plans", "workflows", "performance"):
                try:
                    cnt = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    stats[table] = cnt
                except Exception:
                    stats[table] = 0

            # 性能统计
            try:
                row = self._conn.execute(
                    """
                    SELECT AVG(ctr), AVG(roas), MAX(roas), SUM(spend), SUM(is_winner::INT)
                    FROM performance
                    """
                ).fetchone()
                if row:
                    stats.update({
                        "avg_ctr": float(row[0] or 0),
                        "avg_roas": float(row[1] or 0),
                        "max_roas": float(row[2] or 0),
                        "total_spend": float(row[3] or 0),
                        "winner_count": int(row[4] or 0),
                    })
            except Exception:
                pass

            return stats
        except Exception:
            return {}

    def learn(
        self,
        variant_id: str,
        ctr: float,
        cvr: float,
        roas: float,
        spend: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """持续学习入口"""
        is_winner = roas >= 1.5
        self.record_performance(
            variant_id=variant_id,
            ctr=ctr, cvr=cvr, roas=roas, spend=spend,
            is_winner=is_winner,
            metadata=kwargs,
        )
