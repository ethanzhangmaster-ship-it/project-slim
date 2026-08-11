"""Generation Memory - 视频生成记忆引擎

使用 DuckDB 存储:
- Video Prompt
- Storyboard
- Workflow
- Facebook Result (CTR/CVR/ROAS/Spend)
- Winner 标记

实现 Prompt 学习和 Winner 分析。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

try:
    import sqlite3
    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


class GenerationMemory:
    """视频生成记忆引擎
    
    存储完整的视频生成历史和投放表现。
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS video_history (
        video_id VARCHAR PRIMARY KEY,
        variant_id VARCHAR,
        video_prompt TEXT,
        storyboard_json TEXT,
        shot_list_json TEXT,
        workflow_json TEXT,
        model VARCHAR,
        platform VARCHAR,
        placement VARCHAR,
        duration FLOAT,
        hook_type VARCHAR,
        style VARCHAR,
        created_at TIMESTAMP,
        -- 投放表现 (投放后回填)
        ctr FLOAT,
        cvr FLOAT,
        roas FLOAT,
        ipm FLOAT,
        spend FLOAT,
        impressions INTEGER,
        video_views INTEGER,
        conversions INTEGER,
        -- 元数据
        project VARCHAR,
        status VARCHAR DEFAULT 'generated',  -- generated / deployed / winning / losing / archived
        winner_score FLOAT,
        notes TEXT,
        tags VARCHAR[]
    )
    """

    def __init__(self, db_path: str | Path = "video_memory.duckdb") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = "duckdb" if HAS_DUCKDB else ("sqlite" if HAS_SQLITE else "memory")
        self._conn: Any = None
        self._memory_store: list[dict[str, Any]] = []
        self._init_connection()
        self._init_schema()

    def _init_connection(self) -> None:
        if self._backend == "duckdb":
            self._conn = duckdb.connect(str(self._db_path), read_only=False)
        elif self._backend == "sqlite":
            sqlite_path = self._db_path.with_suffix(".db")
            self._conn = sqlite3.connect(str(sqlite_path))
            self._conn.row_factory = sqlite3.Row
        else:
            self._memory_store = []

    def _init_schema(self) -> None:
        if self._backend in ("duckdb", "sqlite"):
            self._conn.execute(self.SCHEMA)
            if self._backend == "sqlite":
                self._conn.commit()

    def _execute(self, sql: str, params: list[Any] | None = None) -> Any:
        if self._backend in ("duckdb", "sqlite"):
            return self._conn.execute(sql, params or [])
        return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def save_video(
        self,
        video_id: str,
        variant_id: str,
        video_prompt: str,
        storyboard: dict[str, Any] | None = None,
        shot_list: dict[str, Any] | None = None,
        workflow: dict[str, Any] | None = None,
        model: str = "",
        platform: str = "facebook",
        placement: str = "feed",
        duration: float = 15.0,
        hook_type: str = "collection",
        style: str = "pixar",
        project: str = "P04",
        tags: list[str] | None = None,
    ) -> None:
        """保存视频生成记录"""
        tags_arr = tags or []
        now = datetime.now().isoformat()

        if self._backend in ("duckdb", "sqlite"):
            self._execute("""
                INSERT OR REPLACE INTO video_history
                (video_id, variant_id, video_prompt, storyboard_json, shot_list_json,
                 workflow_json, model, platform, placement, duration, hook_type, style,
                 created_at, project, tags, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                video_id, variant_id, video_prompt,
                json.dumps(storyboard) if storyboard else "",
                json.dumps(shot_list) if shot_list else "",
                json.dumps(workflow) if workflow else "",
                model, platform, placement, duration, hook_type, style,
                now, project, json.dumps(tags_arr), "generated",
            ])
            if self._backend == "sqlite":
                self._conn.commit()
        else:
            self._memory_store.append({
                "video_id": video_id,
                "variant_id": variant_id,
                "video_prompt": video_prompt,
                "model": model,
                "platform": platform,
                "created_at": now,
                "project": project,
                "status": "generated",
            })

    def update_performance(
        self,
        video_id: str,
        ctr: float | None = None,
        cvr: float | None = None,
        roas: float | None = None,
        ipm: float | None = None,
        spend: float | None = None,
        impressions: int | None = None,
        video_views: int | None = None,
        conversions: int | None = None,
        status: str | None = None,
        winner_score: float | None = None,
        notes: str | None = None,
    ) -> None:
        """更新视频投放表现"""
        updates = []
        params: list[Any] = []
        for col, val in [
            ("ctr", ctr), ("cvr", cvr), ("roas", roas), ("ipm", ipm),
            ("spend", spend), ("impressions", impressions),
            ("video_views", video_views), ("conversions", conversions),
            ("status", status), ("winner_score", winner_score), ("notes", notes),
        ]:
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)

        if not updates:
            return

        params.append(video_id)

        if self._backend in ("duckdb", "sqlite"):
            self._execute(
                f"UPDATE video_history SET {', '.join(updates)} WHERE video_id = ?",
                params,
            )
            if self._backend == "sqlite":
                self._conn.commit()

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        """获取单个视频记录"""
        if self._backend in ("duckdb", "sqlite"):
            rows = self._execute(
                "SELECT * FROM video_history WHERE video_id = ?", [video_id]
            ).fetchall()
            if rows:
                row = rows[0]
                return {k: row[k] if hasattr(row, "keys") else row[i]
                        for i, k in enumerate(row.keys() if hasattr(row, "keys") else [])}
        else:
            for item in self._memory_store:
                if item.get("video_id") == video_id:
                    return dict(item)
        return None

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def search(
        self,
        hook_type: str | None = None,
        model: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        min_roas: float | None = None,
        project: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """搜索视频历史"""
        conditions = []
        params: list[Any] = []

        if hook_type:
            conditions.append("hook_type = ?")
            params.append(hook_type)
        if model:
            conditions.append("model = ?")
            params.append(model)
        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if min_roas is not None:
            conditions.append("roas >= ?")
            params.append(min_roas)
        if project:
            conditions.append("project = ?")
            params.append(project)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM video_history {where} ORDER BY roas DESC NULLS LAST LIMIT ?"
        params.append(limit)

        if self._backend in ("duckdb", "sqlite"):
            rows = self._execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        else:
            return [dict(r) for r in self._memory_store[:limit]]

    def get_top_videos(
        self,
        metric: str = "roas",
        limit: int = 10,
        min_spend: float = 50.0,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取表现最好的视频"""
        metric_col = metric if metric in ("ctr", "cvr", "roas", "ipm") else "roas"

        conditions = [f"{metric_col} IS NOT NULL", "spend >= ?"]
        params: list[Any] = [min_spend]
        if project:
            conditions.append("project = ?")
            params.append(project)

        where = "WHERE " + " AND ".join(conditions)
        sql = f"""
            SELECT video_id, variant_id, video_prompt, hook_type, model,
                   {metric_col}, spend, ctr, roas, status
            FROM video_history
            {where}
            ORDER BY {metric_col} DESC
            LIMIT ?
        """
        params.append(limit)

        if self._backend in ("duckdb", "sqlite"):
            rows = self._execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        return []

    def get_winning_videos(self, project: str | None = None) -> list[dict[str, Any]]:
        """获取 Winner 视频"""
        conditions = ["status = 'winning'"]
        params: list[Any] = []
        if project:
            conditions.append("project = ?")
            params.append(project)

        where = "WHERE " + " AND ".join(conditions)
        sql = f"SELECT * FROM video_history {where} ORDER BY winner_score DESC"
        if self._backend in ("duckdb", "sqlite"):
            rows = self._execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        return []

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def get_stats(self, project: str | None = None) -> dict[str, Any]:
        """获取视频统计"""
        conditions = "WHERE project = ?" if project else ""
        params = [project] if project else []

        sql = f"""
            SELECT
                COUNT(*) as total_videos,
                COUNT(DISTINCT hook_type) as hook_types,
                COUNT(DISTINCT model) as models,
                AVG(ctr) as avg_ctr,
                AVG(roas) as avg_roas,
                MAX(roas) as max_roas,
                COUNT(CASE WHEN status = 'winning' THEN 1 END) as winning_count,
                SUM(spend) as total_spend
            FROM video_history
            {conditions}
        """

        if self._backend in ("duckdb", "sqlite"):
            row = self._execute(sql, params).fetchone()
            if row:
                if hasattr(row, "keys"):
                    keys = list(row.keys())
                else:
                    # tuple / list: 需要从 SQL 获取列名
                    keys = ["total_videos", "hook_types", "models", "avg_ctr", "avg_roas", "max_roas", "winning_count", "total_spend"]
                return dict(zip(keys, row))
        return {"total_videos": len(self._memory_store)}

    # ------------------------------------------------------------------
    # 学习
    # ------------------------------------------------------------------
    def learn_from_winners(self, min_spend: float = 100.0) -> dict[str, Any]:
        """从 Winner 视频中学习"""
        winners = self.get_top_videos("roas", limit=20, min_spend=min_spend)

        return {
            "winning_videos": [
                {"video_id": w["video_id"], "roas": w.get("roas"), "hook_type": w.get("hook_type")}
                for w in winners
            ],
            "winning_hook_types": list(set(w.get("hook_type") for w in winners if w.get("hook_type"))),
            "winning_models": list(set(w.get("model") for w in winners if w.get("model"))),
            "avg_winner_roas": sum(w.get("roas", 0) for w in winners) / len(winners) if winners else 0,
            "learned_at": datetime.now().isoformat(),
        }

    def mark_winner(self, video_id: str, winner_score: float) -> None:
        """标记 Winner"""
        self.update_performance(video_id, status="winning", winner_score=winner_score)

    def mark_losing(self, video_id: str) -> None:
        """标记 Losing"""
        self.update_performance(video_id, status="losing")