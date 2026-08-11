"""Prompt Memory - Prompt 表现记忆存储

保存 Prompt -> CTR -> ROAS -> Learning，自动知道哪些 Prompt 赚钱。

使用 DuckDB 存储，支持增量更新和查询。
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


class PromptMemory:
    """Prompt 记忆引擎

    存储每个 Prompt 的生成历史、表现数据和优化轨迹。
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS prompt_history (
        prompt_id VARCHAR PRIMARY KEY,
        variant_id VARCHAR,
        master_prompt TEXT,
        hook_type VARCHAR,
        style VARCHAR,
        placement VARCHAR,
        model VARCHAR,
        negative_prompt TEXT,
        storyboard_json TEXT,
        image_task_json TEXT,
        generated_at TIMESTAMP,
        -- 表现数据 (投放后回填)
        ctr FLOAT,
        cvr FLOAT,
        roas FLOAT,
        ipm FLOAT,
        spend FLOAT,
        impressions INTEGER,
        clicks INTEGER,
        conversions INTEGER,
        -- 元数据
        project VARCHAR,
        version INTEGER DEFAULT 1,
        parent_prompt_id VARCHAR,
        optimization_notes TEXT,
        tags VARCHAR[],
        status VARCHAR DEFAULT 'generated'  -- generated / deployed / winning / losing / archived
    )
    """

    def __init__(self, db_path: str | Path = "prompt_memory.duckdb") -> None:
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
    def save_prompt(
        self,
        prompt_id: str,
        master_prompt: str,
        variant_id: str = "",
        hook_type: str = "",
        style: str = "",
        placement: str = "",
        model: str = "",
        negative_prompt: str = "",
        storyboard: dict[str, Any] | None = None,
        image_task: dict[str, Any] | None = None,
        project: str = "P04",
        parent_prompt_id: str = "",
        tags: list[str] | None = None,
    ) -> None:
        """保存 Prompt 记录"""
        tags_arr = tags or []
        now = datetime.now().isoformat()

        if self._backend in ("duckdb", "sqlite"):
            self._execute("""
                INSERT OR REPLACE INTO prompt_history
                (prompt_id, variant_id, master_prompt, hook_type, style, placement,
                 model, negative_prompt, storyboard_json, image_task_json,
                 generated_at, project, parent_prompt_id, tags, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                prompt_id, variant_id, master_prompt, hook_type, style, placement,
                model, negative_prompt,
                json.dumps(storyboard) if storyboard else "",
                json.dumps(image_task) if image_task else "",
                now, project, parent_prompt_id, json.dumps(tags_arr), "generated",
            ])
            if self._backend == "sqlite":
                self._conn.commit()
        else:
            self._memory_store.append({
                "prompt_id": prompt_id,
                "variant_id": variant_id,
                "master_prompt": master_prompt,
                "hook_type": hook_type,
                "style": style,
                "placement": placement,
                "model": model,
                "generated_at": now,
                "project": project,
                "status": "generated",
            })

    def update_performance(
        self,
        prompt_id: str,
        ctr: float | None = None,
        cvr: float | None = None,
        roas: float | None = None,
        ipm: float | None = None,
        spend: float | None = None,
        impressions: int | None = None,
        clicks: int | None = None,
        conversions: int | None = None,
        status: str | None = None,
    ) -> None:
        """更新 Prompt 的投放表现"""
        updates = []
        params: list[Any] = []
        for col, val in [
            ("ctr", ctr), ("cvr", cvr), ("roas", roas), ("ipm", ipm),
            ("spend", spend), ("impressions", impressions),
            ("clicks", clicks), ("conversions", conversions),
            ("status", status),
        ]:
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)

        if not updates:
            return

        params.append(prompt_id)

        if self._backend in ("duckdb", "sqlite"):
            self._execute(
                f"UPDATE prompt_history SET {', '.join(updates)} WHERE prompt_id = ?",
                params,
            )
            if self._backend == "sqlite":
                self._conn.commit()

    def get_prompt(self, prompt_id: str) -> dict[str, Any] | None:
        """获取单个 Prompt 记录"""
        if self._backend in ("duckdb", "sqlite"):
            rows = self._execute(
                "SELECT * FROM prompt_history WHERE prompt_id = ?", [prompt_id]
            ).fetchall()
            if rows:
                row = rows[0]
                return {k: row[k] if hasattr(row, "keys") else row[i]
                        for i, k in enumerate(row.keys() if hasattr(row, "keys") else [])}
        else:
            for item in self._memory_store:
                if item.get("prompt_id") == prompt_id:
                    return dict(item)
        return None

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def search(
        self,
        hook_type: str | None = None,
        style: str | None = None,
        status: str | None = None,
        min_roas: float | None = None,
        project: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """搜索 Prompt 历史"""
        conditions = []
        params: list[Any] = []

        if hook_type:
            conditions.append("hook_type = ?")
            params.append(hook_type)
        if style:
            conditions.append("style = ?")
            params.append(style)
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
        sql = f"SELECT * FROM prompt_history {where} ORDER BY roas DESC NULLS LAST LIMIT ?"
        params.append(limit)

        if self._backend in ("duckdb", "sqlite"):
            rows = self._execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        else:
            results = self._memory_store[:limit]
            return [dict(r) for r in results]

    def get_top_prompts(
        self,
        metric: str = "roas",
        limit: int = 10,
        min_spend: float = 10.0,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取表现最好的 Prompt"""
        metric_col = metric if metric in ("ctr", "cvr", "roas", "ipm") else "roas"

        conditions = [f"{metric_col} IS NOT NULL", "spend >= ?"]
        params: list[Any] = [min_spend]
        if project:
            conditions.append("project = ?")
            params.append(project)

        where = "WHERE " + " AND ".join(conditions)
        sql = f"""
            SELECT prompt_id, master_prompt, hook_type, style, {metric_col}, spend, ctr, roas
            FROM prompt_history
            {where}
            ORDER BY {metric_col} DESC
            LIMIT ?
        """
        params.append(limit)

        if self._backend in ("duckdb", "sqlite"):
            rows = self._execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        return []

    def get_prompt_stats(self, project: str | None = None) -> dict[str, Any]:
        """获取 Prompt 统计"""
        conditions = "WHERE project = ?" if project else ""
        params = [project] if project else []

        sql = f"""
            SELECT
                COUNT(*) as total_prompts,
                COUNT(DISTINCT hook_type) as hook_types,
                COUNT(DISTINCT style) as styles,
                AVG(ctr) as avg_ctr,
                AVG(roas) as avg_roas,
                MAX(roas) as max_roas,
                COUNT(CASE WHEN status = 'winning' THEN 1 END) as winning_count
            FROM prompt_history
            {conditions}
        """

        if self._backend in ("duckdb", "sqlite"):
            row = self._execute(sql, params).fetchone()
            if row:
                keys = [d[0] for d in row.cursor_description] if hasattr(row, "cursor_description") else row.keys()
                return dict(zip(keys, row))
        return {
            "total_prompts": len(self._memory_store),
            "hook_types": 0,
            "styles": 0,
        }

    # ------------------------------------------------------------------
    # 学习
    # ------------------------------------------------------------------
    def learn_from_performance(self, min_spend: float = 50.0) -> dict[str, Any]:
        """从表现数据中学习，找出赚钱 Prompt 的特征"""
        top = self.get_top_prompts("roas", limit=20, min_spend=min_spend)
        bottom = self.search(min_roas=0, status="deployed", limit=20)
        bottom = [b for b in bottom if b.get("roas", 999) < 1.0]

        return {
            "top_prompts": [
                {"prompt_id": p["prompt_id"], "roas": p.get("roas"), "hook": p.get("hook_type")}
                for p in top
            ],
            "bottom_prompts": [
                {"prompt_id": p["prompt_id"], "roas": p.get("roas"), "hook": p.get("hook_type")}
                for p in bottom
            ],
            "learned_at": datetime.now().isoformat(),
        }
