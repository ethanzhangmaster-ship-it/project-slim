"""Memory Engine - 长期创意记忆存储

使用 DuckDB 存储，支持：
- variables 变量记忆（每个变量维度的历史表现）
- creatives 创意记忆（每个创意的完整特征+表现）
- audiences 受众记忆（不同受众的表现差异）
- campaigns 活动记忆
- countries 国家记忆
- placements 版位记忆
- projects 项目记忆

接口：
- memory.get()
- memory.update()
- memory.merge()
- memory.search()
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


class VideoMemoryEngine:
    """视频创意记忆引擎 - 基于 DuckDB 的长期记忆存储"""

    def __init__(self, db_path: str | Path = "video_memory.duckdb") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = "duckdb" if HAS_DUCKDB else ("sqlite" if HAS_SQLITE else "memory")
        self._conn: Any = None
        self._memory_store: dict[str, list[dict[str, Any]]] = {}
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
            self._memory_store = {
                "variable_memory": [],
                "creative_memory": [],
                "audience_memory": [],
                "country_memory": [],
                "placement_memory": [],
                "project_memory": [],
            }

    def _init_schema(self) -> None:
        if self._backend == "duckdb":
            self._init_duckdb_schema()
        elif self._backend == "sqlite":
            self._init_sqlite_schema()

    def _init_duckdb_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS variable_memory (
                variable_key VARCHAR PRIMARY KEY,
                dimension VARCHAR,
                value VARCHAR,
                ctr_mean DOUBLE DEFAULT 0,
                roas_mean DOUBLE DEFAULT 0,
                cvr_mean DOUBLE DEFAULT 0,
                ipm_mean DOUBLE DEFAULT 0,
                frequency DOUBLE DEFAULT 0,
                sample_count INTEGER DEFAULT 0,
                projects VARCHAR DEFAULT '[]',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS creative_memory (
                creative_id VARCHAR PRIMARY KEY,
                variant_id VARCHAR,
                project VARCHAR,
                campaign VARCHAR,
                dna_json VARCHAR DEFAULT '{}',
                features_json VARCHAR DEFAULT '{}',
                performance_json VARCHAR DEFAULT '{}',
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR DEFAULT 'active'
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS audience_memory (
                audience_key VARCHAR PRIMARY KEY,
                country VARCHAR,
                age_range VARCHAR,
                gender VARCHAR,
                os VARCHAR,
                placement VARCHAR,
                ctr_mean DOUBLE DEFAULT 0,
                roas_mean DOUBLE DEFAULT 0,
                sample_count INTEGER DEFAULT 0
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS country_memory (
                country VARCHAR PRIMARY KEY,
                ctr_mean DOUBLE DEFAULT 0,
                roas_mean DOUBLE DEFAULT 0,
                top_creatures VARCHAR DEFAULT '[]',
                top_themes VARCHAR DEFAULT '[]',
                sample_count INTEGER DEFAULT 0
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS placement_memory (
                placement VARCHAR PRIMARY KEY,
                ctr_mean DOUBLE DEFAULT 0,
                roas_mean DOUBLE DEFAULT 0,
                best_hook_type VARCHAR DEFAULT '',
                sample_count INTEGER DEFAULT 0
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS project_memory (
                project VARCHAR PRIMARY KEY,
                total_creatives INTEGER DEFAULT 0,
                top_roas DOUBLE DEFAULT 0,
                top_variables VARCHAR DEFAULT '[]',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_var_dim ON variable_memory(dimension)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_var_roas ON variable_memory(roas_mean)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_creative_project ON creative_memory(project)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_audience_country ON audience_memory(country)")

    def _init_sqlite_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS variable_memory (
                variable_key TEXT PRIMARY KEY,
                dimension TEXT,
                value TEXT,
                ctr_mean REAL DEFAULT 0,
                roas_mean REAL DEFAULT 0,
                cvr_mean REAL DEFAULT 0,
                ipm_mean REAL DEFAULT 0,
                frequency REAL DEFAULT 0,
                sample_count INTEGER DEFAULT 0,
                projects TEXT DEFAULT '[]',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creative_memory (
                creative_id TEXT PRIMARY KEY,
                variant_id TEXT,
                project TEXT,
                campaign TEXT,
                dna_json TEXT DEFAULT '{}',
                features_json TEXT DEFAULT '{}',
                performance_json TEXT DEFAULT '{}',
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audience_memory (
                audience_key TEXT PRIMARY KEY,
                country TEXT,
                age_range TEXT,
                gender TEXT,
                os TEXT,
                placement TEXT,
                ctr_mean REAL DEFAULT 0,
                roas_mean REAL DEFAULT 0,
                sample_count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS country_memory (
                country TEXT PRIMARY KEY,
                ctr_mean REAL DEFAULT 0,
                roas_mean REAL DEFAULT 0,
                top_creatures TEXT DEFAULT '[]',
                top_themes TEXT DEFAULT '[]',
                sample_count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS placement_memory (
                placement TEXT PRIMARY KEY,
                ctr_mean REAL DEFAULT 0,
                roas_mean REAL DEFAULT 0,
                best_hook_type TEXT DEFAULT '',
                sample_count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_memory (
                project TEXT PRIMARY KEY,
                total_creatives INTEGER DEFAULT 0,
                top_roas REAL DEFAULT 0,
                top_variables TEXT DEFAULT '[]',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_var_dim ON variable_memory(dimension)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_var_roas ON variable_memory(roas_mean)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creative_project ON creative_memory(project)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audience_country ON audience_memory(country)")
        self._conn.commit()

    def _make_key(self, dimension: str, value: str) -> str:
        return f"{dimension}:{value}"

    def _execute(self, sql: str, params: list[Any] | None = None) -> Any:
        params = params or []
        if self._backend in ("duckdb", "sqlite"):
            return self._conn.execute(sql, params)
        return None

    def _fetchall(self, cursor: Any) -> list[dict[str, Any]]:
        if self._backend == "duckdb":
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        elif self._backend == "sqlite":
            return [dict(r) for r in cursor.fetchall()]
        return []

    def _fetchone(self, cursor: Any) -> dict[str, Any] | None:
        rows = self._fetchall(cursor)
        return rows[0] if rows else None

    def update_variable(self, dimension: str, value: str, metrics: dict[str, Any]) -> None:
        """更新单个变量记忆

        Args:
            dimension: 变量维度，如 'creature_type', 'hook_type'
            value: 变量值
            metrics: 指标字典，支持 ctr, roas, cvr, ipm, sample_count, project
        """
        key = self._make_key(dimension, value)
        existing = self.get_variable(dimension, value)

        if existing:
            old_count = existing.get("sample_count", 0)
            new_count = metrics.get("sample_count", 1)
            total_count = old_count + new_count

            def weighted_mean(old_val: float, new_val: float) -> float:
                if total_count == 0:
                    return new_val
                return (old_val * old_count + new_val * new_count) / total_count

            ctr_mean = weighted_mean(existing.get("ctr_mean", 0), metrics.get("ctr", 0))
            roas_mean = weighted_mean(existing.get("roas_mean", 0), metrics.get("roas", 0))
            cvr_mean = weighted_mean(existing.get("cvr_mean", 0), metrics.get("cvr", 0))
            ipm_mean = weighted_mean(existing.get("ipm_mean", 0), metrics.get("ipm", 0))

            projects = json.loads(existing.get("projects", "[]"))
            project = metrics.get("project")
            if project and project not in projects:
                projects.append(project)

            new_version = existing.get("version", 1) + 1

            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    UPDATE variable_memory
                    SET ctr_mean = ?, roas_mean = ?, cvr_mean = ?, ipm_mean = ?,
                        sample_count = ?, projects = ?, last_updated = CURRENT_TIMESTAMP,
                        version = ?
                    WHERE variable_key = ?
                """, [ctr_mean, roas_mean, cvr_mean, ipm_mean, total_count,
                      json.dumps(projects), new_version, key])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                for item in self._memory_store["variable_memory"]:
                    if item["variable_key"] == key:
                        item.update({
                            "ctr_mean": ctr_mean,
                            "roas_mean": roas_mean,
                            "cvr_mean": cvr_mean,
                            "ipm_mean": ipm_mean,
                            "sample_count": total_count,
                            "projects": json.dumps(projects),
                            "last_updated": datetime.now().isoformat(),
                            "version": new_version,
                        })
                        break
        else:
            projects = [metrics["project"]] if metrics.get("project") else []
            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    INSERT INTO variable_memory
                    (variable_key, dimension, value, ctr_mean, roas_mean, cvr_mean,
                     ipm_mean, sample_count, projects, last_updated, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
                """, [key, dimension, value,
                      metrics.get("ctr", 0), metrics.get("roas", 0),
                      metrics.get("cvr", 0), metrics.get("ipm", 0),
                      metrics.get("sample_count", 1), json.dumps(projects)])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                self._memory_store["variable_memory"].append({
                    "variable_key": key,
                    "dimension": dimension,
                    "value": value,
                    "ctr_mean": metrics.get("ctr", 0),
                    "roas_mean": metrics.get("roas", 0),
                    "cvr_mean": metrics.get("cvr", 0),
                    "ipm_mean": metrics.get("ipm", 0),
                    "frequency": 0,
                    "sample_count": metrics.get("sample_count", 1),
                    "projects": json.dumps(projects),
                    "last_updated": datetime.now().isoformat(),
                    "version": 1,
                })

    def update_creative(self, creative_id: str, dna: dict[str, Any],
                        performance: dict[str, Any],
                        project: str = "", campaign: str = "",
                        variant_id: str = "") -> None:
        """更新创意记忆

        Args:
            creative_id: 创意ID
            dna: DNA 字典
            performance: 表现字典
            project: 项目名
            campaign: 活动名
            variant_id: 变体ID
        """
        existing = self._get_creative(creative_id)

        if existing:
            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    UPDATE creative_memory
                    SET dna_json = ?, features_json = ?, performance_json = ?,
                        last_seen = CURRENT_TIMESTAMP, project = ?, campaign = ?, variant_id = ?
                    WHERE creative_id = ?
                """, [json.dumps(dna), json.dumps(dna), json.dumps(performance),
                      project, campaign, variant_id, creative_id])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                for item in self._memory_store["creative_memory"]:
                    if item["creative_id"] == creative_id:
                        item.update({
                            "dna_json": json.dumps(dna),
                            "features_json": json.dumps(dna),
                            "performance_json": json.dumps(performance),
                            "last_seen": datetime.now().isoformat(),
                            "project": project,
                            "campaign": campaign,
                            "variant_id": variant_id,
                        })
                        break
        else:
            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    INSERT INTO creative_memory
                    (creative_id, variant_id, project, campaign, dna_json,
                     features_json, performance_json, first_seen, last_seen, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'active')
                """, [creative_id, variant_id, project, campaign,
                      json.dumps(dna), json.dumps(dna), json.dumps(performance)])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                self._memory_store["creative_memory"].append({
                    "creative_id": creative_id,
                    "variant_id": variant_id,
                    "project": project,
                    "campaign": campaign,
                    "dna_json": json.dumps(dna),
                    "features_json": json.dumps(dna),
                    "performance_json": json.dumps(performance),
                    "first_seen": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat(),
                    "status": "active",
                })

    def _get_creative(self, creative_id: str) -> dict[str, Any] | None:
        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute("SELECT * FROM creative_memory WHERE creative_id = ?", [creative_id])
            return self._fetchone(cursor)
        else:
            for item in self._memory_store["creative_memory"]:
                if item["creative_id"] == creative_id:
                    return item
            return None

    def get_variable(self, dimension: str, value: str) -> dict[str, Any] | None:
        """查询变量记忆

        Args:
            dimension: 变量维度
            value: 变量值

        Returns:
            变量记忆字典，不存在返回 None
        """
        key = self._make_key(dimension, value)
        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute("SELECT * FROM variable_memory WHERE variable_key = ?", [key])
            return self._fetchone(cursor)
        else:
            for item in self._memory_store["variable_memory"]:
                if item["variable_key"] == key:
                    return item
            return None

    def search_variables(self, dimension: str | None = None,
                         min_roas: float | None = None,
                         min_samples: int = 0,
                         limit: int = 100) -> list[dict[str, Any]]:
        """搜索变量记忆

        Args:
            dimension: 按维度过滤
            min_roas: 最低 ROAS 阈值
            min_samples: 最少样本数
            limit: 返回数量限制

        Returns:
            变量记忆列表
        """
        sql = "SELECT * FROM variable_memory WHERE 1=1"
        params: list[Any] = []

        if dimension:
            sql += " AND dimension = ?"
            params.append(dimension)
        if min_roas is not None:
            sql += " AND roas_mean >= ?"
            params.append(min_roas)
        if min_samples > 0:
            sql += " AND sample_count >= ?"
            params.append(min_samples)

        sql += " ORDER BY roas_mean DESC"

        if self._backend == "duckdb":
            sql += " LIMIT ?"
            params.append(limit)
        elif self._backend == "sqlite":
            sql += " LIMIT ?"
            params.append(limit)

        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute(sql, params)
            return self._fetchall(cursor)
        else:
            results = []
            for item in self._memory_store["variable_memory"]:
                if dimension and item["dimension"] != dimension:
                    continue
                if min_roas is not None and item.get("roas_mean", 0) < min_roas:
                    continue
                if min_samples > 0 and item.get("sample_count", 0) < min_samples:
                    continue
                results.append(item)
            results.sort(key=lambda x: x.get("roas_mean", 0), reverse=True)
            return results[:limit]

    def merge_variables(self, other_engine: "VideoMemoryEngine") -> int:
        """合并另一个记忆引擎的变量数据

        Args:
            other_engine: 另一个记忆引擎

        Returns:
            合并的变量数量
        """
        other_vars = other_engine.search_variables(limit=10000)
        count = 0
        for var in other_vars:
            metrics = {
                "ctr": var.get("ctr_mean", 0),
                "roas": var.get("roas_mean", 0),
                "cvr": var.get("cvr_mean", 0),
                "ipm": var.get("ipm_mean", 0),
                "sample_count": var.get("sample_count", 1),
            }
            projects = json.loads(var.get("projects", "[]"))
            if projects:
                metrics["project"] = projects[0]
            self.update_variable(var["dimension"], var["value"], metrics)
            count += 1
        return count

    def get_top_variables(self, dimension: str, metric: str = "roas",
                          limit: int = 10, min_samples: int = 5) -> list[dict[str, Any]]:
        """获取 Top 变量

        Args:
            dimension: 变量维度
            metric: 排序指标 (roas, ctr, cvr, ipm)
            limit: 返回数量
            min_samples: 最少样本数

        Returns:
            Top 变量列表
        """
        metric_map = {
            "roas": "roas_mean",
            "ctr": "ctr_mean",
            "cvr": "cvr_mean",
            "ipm": "ipm_mean",
        }
        sort_col = metric_map.get(metric, "roas_mean")

        if self._backend in ("duckdb", "sqlite"):
            sql = f"""
                SELECT * FROM variable_memory
                WHERE dimension = ? AND sample_count >= ?
                ORDER BY {sort_col} DESC
                LIMIT ?
            """
            cursor = self._execute(sql, [dimension, min_samples, limit])
            return self._fetchall(cursor)
        else:
            results = []
            for item in self._memory_store["variable_memory"]:
                if item["dimension"] != dimension:
                    continue
                if item.get("sample_count", 0) < min_samples:
                    continue
                results.append(item)
            results.sort(key=lambda x: x.get(sort_col, 0), reverse=True)
            return results[:limit]

    def get_country_performance(self, country: str) -> dict[str, Any] | None:
        """获取国家表现

        Args:
            country: 国家代码

        Returns:
            国家表现字典
        """
        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute("SELECT * FROM country_memory WHERE country = ?", [country])
            return self._fetchone(cursor)
        else:
            for item in self._memory_store["country_memory"]:
                if item["country"] == country:
                    return item
            return None

    def get_placement_performance(self, placement: str) -> dict[str, Any] | None:
        """获取版位表现

        Args:
            placement: 版位名称

        Returns:
            版位表现字典
        """
        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute("SELECT * FROM placement_memory WHERE placement = ?", [placement])
            return self._fetchone(cursor)
        else:
            for item in self._memory_store["placement_memory"]:
                if item["placement"] == placement:
                    return item
            return None

    def update_country_performance(self, country: str, metrics: dict[str, Any],
                                   top_creatures: list[str] | None = None,
                                   top_themes: list[str] | None = None) -> None:
        """更新国家表现

        Args:
            country: 国家代码
            metrics: 指标字典 (ctr, roas, sample_count)
            top_creatures: Top 生物列表
            top_themes: Top 主题列表
        """
        existing = self.get_country_performance(country)

        if existing:
            old_count = existing.get("sample_count", 0)
            new_count = metrics.get("sample_count", 1)
            total_count = old_count + new_count

            def weighted_mean(old_val: float, new_val: float) -> float:
                if total_count == 0:
                    return new_val
                return (old_val * old_count + new_val * new_count) / total_count

            ctr_mean = weighted_mean(existing.get("ctr_mean", 0), metrics.get("ctr", 0))
            roas_mean = weighted_mean(existing.get("roas_mean", 0), metrics.get("roas", 0))

            creatures = top_creatures if top_creatures else json.loads(existing.get("top_creatures", "[]"))
            themes = top_themes if top_themes else json.loads(existing.get("top_themes", "[]"))

            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    UPDATE country_memory
                    SET ctr_mean = ?, roas_mean = ?, top_creatures = ?, top_themes = ?,
                        sample_count = ?
                    WHERE country = ?
                """, [ctr_mean, roas_mean, json.dumps(creatures), json.dumps(themes),
                      total_count, country])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                for item in self._memory_store["country_memory"]:
                    if item["country"] == country:
                        item.update({
                            "ctr_mean": ctr_mean,
                            "roas_mean": roas_mean,
                            "top_creatures": json.dumps(creatures),
                            "top_themes": json.dumps(themes),
                            "sample_count": total_count,
                        })
                        break
        else:
            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    INSERT INTO country_memory
                    (country, ctr_mean, roas_mean, top_creatures, top_themes, sample_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [country, metrics.get("ctr", 0), metrics.get("roas", 0),
                      json.dumps(top_creatures or []), json.dumps(top_themes or []),
                      metrics.get("sample_count", 1)])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                self._memory_store["country_memory"].append({
                    "country": country,
                    "ctr_mean": metrics.get("ctr", 0),
                    "roas_mean": metrics.get("roas", 0),
                    "top_creatures": json.dumps(top_creatures or []),
                    "top_themes": json.dumps(top_themes or []),
                    "sample_count": metrics.get("sample_count", 1),
                })

    def update_placement_performance(self, placement: str, metrics: dict[str, Any],
                                     best_hook_type: str = "") -> None:
        """更新版位表现

        Args:
            placement: 版位名称
            metrics: 指标字典 (ctr, roas, sample_count)
            best_hook_type: 最佳 Hook 类型
        """
        existing = self.get_placement_performance(placement)

        if existing:
            old_count = existing.get("sample_count", 0)
            new_count = metrics.get("sample_count", 1)
            total_count = old_count + new_count

            def weighted_mean(old_val: float, new_val: float) -> float:
                if total_count == 0:
                    return new_val
                return (old_val * old_count + new_val * new_count) / total_count

            ctr_mean = weighted_mean(existing.get("ctr_mean", 0), metrics.get("ctr", 0))
            roas_mean = weighted_mean(existing.get("roas_mean", 0), metrics.get("roas", 0))

            hook = best_hook_type or existing.get("best_hook_type", "")

            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    UPDATE placement_memory
                    SET ctr_mean = ?, roas_mean = ?, best_hook_type = ?, sample_count = ?
                    WHERE placement = ?
                """, [ctr_mean, roas_mean, hook, total_count, placement])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                for item in self._memory_store["placement_memory"]:
                    if item["placement"] == placement:
                        item.update({
                            "ctr_mean": ctr_mean,
                            "roas_mean": roas_mean,
                            "best_hook_type": hook,
                            "sample_count": total_count,
                        })
                        break
        else:
            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    INSERT INTO placement_memory
                    (placement, ctr_mean, roas_mean, best_hook_type, sample_count)
                    VALUES (?, ?, ?, ?, ?)
                """, [placement, metrics.get("ctr", 0), metrics.get("roas", 0),
                      best_hook_type, metrics.get("sample_count", 1)])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                self._memory_store["placement_memory"].append({
                    "placement": placement,
                    "ctr_mean": metrics.get("ctr", 0),
                    "roas_mean": metrics.get("roas", 0),
                    "best_hook_type": best_hook_type,
                    "sample_count": metrics.get("sample_count", 1),
                })

    def update_audience_memory(self, country: str, age_range: str = "",
                               gender: str = "", os: str = "",
                               placement: str = "",
                               metrics: dict[str, Any] | None = None) -> None:
        """更新受众记忆

        Args:
            country: 国家
            age_range: 年龄段
            gender: 性别
            os: 操作系统
            placement: 版位
            metrics: 指标字典
        """
        metrics = metrics or {}
        audience_key = f"{country}:{age_range}:{gender}:{os}:{placement}"

        existing = None
        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute("SELECT * FROM audience_memory WHERE audience_key = ?", [audience_key])
            existing = self._fetchone(cursor)
        else:
            for item in self._memory_store["audience_memory"]:
                if item["audience_key"] == audience_key:
                    existing = item
                    break

        if existing:
            old_count = existing.get("sample_count", 0)
            new_count = metrics.get("sample_count", 1)
            total_count = old_count + new_count

            def weighted_mean(old_val: float, new_val: float) -> float:
                if total_count == 0:
                    return new_val
                return (old_val * old_count + new_val * new_count) / total_count

            ctr_mean = weighted_mean(existing.get("ctr_mean", 0), metrics.get("ctr", 0))
            roas_mean = weighted_mean(existing.get("roas_mean", 0), metrics.get("roas", 0))

            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    UPDATE audience_memory
                    SET ctr_mean = ?, roas_mean = ?, sample_count = ?
                    WHERE audience_key = ?
                """, [ctr_mean, roas_mean, total_count, audience_key])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                for item in self._memory_store["audience_memory"]:
                    if item["audience_key"] == audience_key:
                        item.update({
                            "ctr_mean": ctr_mean,
                            "roas_mean": roas_mean,
                            "sample_count": total_count,
                        })
                        break
        else:
            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    INSERT INTO audience_memory
                    (audience_key, country, age_range, gender, os, placement,
                     ctr_mean, roas_mean, sample_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [audience_key, country, age_range, gender, os, placement,
                      metrics.get("ctr", 0), metrics.get("roas", 0),
                      metrics.get("sample_count", 1)])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                self._memory_store["audience_memory"].append({
                    "audience_key": audience_key,
                    "country": country,
                    "age_range": age_range,
                    "gender": gender,
                    "os": os,
                    "placement": placement,
                    "ctr_mean": metrics.get("ctr", 0),
                    "roas_mean": metrics.get("roas", 0),
                    "sample_count": metrics.get("sample_count", 1),
                })

    def update_project_memory(self, project: str, total_creatives: int | None = None,
                              top_roas: float | None = None,
                              top_variables: list[str] | None = None) -> None:
        """更新项目记忆

        Args:
            project: 项目名
            total_creatives: 创意总数
            top_roas: 最高 ROAS
            top_variables: Top 变量列表
        """
        existing = None
        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute("SELECT * FROM project_memory WHERE project = ?", [project])
            existing = self._fetchone(cursor)
        else:
            for item in self._memory_store["project_memory"]:
                if item["project"] == project:
                    existing = item
                    break

        if existing:
            tc = total_creatives if total_creatives is not None else existing.get("total_creatives", 0)
            tr = top_roas if top_roas is not None else existing.get("top_roas", 0)
            tv = top_variables if top_variables is not None else json.loads(existing.get("top_variables", "[]"))

            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    UPDATE project_memory
                    SET total_creatives = ?, top_roas = ?, top_variables = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE project = ?
                """, [tc, tr, json.dumps(tv), project])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                for item in self._memory_store["project_memory"]:
                    if item["project"] == project:
                        item.update({
                            "total_creatives": tc,
                            "top_roas": tr,
                            "top_variables": json.dumps(tv),
                            "last_updated": datetime.now().isoformat(),
                        })
                        break
        else:
            if self._backend in ("duckdb", "sqlite"):
                self._execute("""
                    INSERT INTO project_memory
                    (project, total_creatives, top_roas, top_variables, last_updated)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, [project, total_creatives or 0, top_roas or 0,
                      json.dumps(top_variables or [])])
                if self._backend == "sqlite":
                    self._conn.commit()
            else:
                self._memory_store["project_memory"].append({
                    "project": project,
                    "total_creatives": total_creatives or 0,
                    "top_roas": top_roas or 0,
                    "top_variables": json.dumps(top_variables or []),
                    "last_updated": datetime.now().isoformat(),
                })

    def incremental_update(self, creative_results: list[dict[str, Any]]) -> int:
        """增量更新（从广告平台结果回流）

        Args:
            creative_results: 创意结果列表，每个元素包含:
                - creative_id: 创意ID
                - dna: DNA 字典 (可选)
                - features: 特征字典 (可选)
                - performance: 表现字典
                - project: 项目名 (可选)
                - campaign: 活动名 (可选)
                - country: 国家 (可选)
                - placement: 版位 (可选)

        Returns:
            更新的创意数量
        """
        count = 0
        for result in creative_results:
            creative_id = result.get("creative_id")
            if not creative_id:
                continue

            dna = result.get("dna", {})
            performance = result.get("performance", {})
            project = result.get("project", "")
            campaign = result.get("campaign", "")

            self.update_creative(creative_id, dna, performance, project, campaign)

            for dim_key, dim_val in dna.items():
                if isinstance(dim_val, (str, int, float)):
                    metrics = {
                        "ctr": performance.get("ctr", 0),
                        "roas": performance.get("roas_d7", performance.get("roas", 0)),
                        "cvr": performance.get("cvr", 0),
                        "ipm": performance.get("ipm", 0),
                        "sample_count": 1,
                        "project": project,
                    }
                    self.update_variable(dim_key, str(dim_val), metrics)

            country = result.get("country")
            if country:
                country_metrics = {
                    "ctr": performance.get("ctr", 0),
                    "roas": performance.get("roas_d7", performance.get("roas", 0)),
                    "sample_count": 1,
                }
                self.update_country_performance(country, country_metrics)

            placement = result.get("placement")
            if placement:
                placement_metrics = {
                    "ctr": performance.get("ctr", 0),
                    "roas": performance.get("roas_d7", performance.get("roas", 0)),
                    "sample_count": 1,
                }
                self.update_placement_performance(placement, placement_metrics)

            if project:
                self.update_project_memory(project)

            count += 1

        return count

    def get(self, table: str, key: str) -> dict[str, Any] | None:
        """通用 get 接口

        Args:
            table: 表名
            key: 主键值

        Returns:
            记录字典
        """
        table_map = {
            "variable": ("variable_memory", "variable_key"),
            "creative": ("creative_memory", "creative_id"),
            "country": ("country_memory", "country"),
            "placement": ("placement_memory", "placement"),
            "project": ("project_memory", "project"),
        }
        if table not in table_map:
            return None

        table_name, key_col = table_map[table]
        if self._backend in ("duckdb", "sqlite"):
            cursor = self._execute(f"SELECT * FROM {table_name} WHERE {key_col} = ?", [key])
            return self._fetchone(cursor)
        else:
            for item in self._memory_store.get(table_name, []):
                if item.get(key_col) == key:
                    return item
            return None

    def update(self, table: str, key: str, data: dict[str, Any]) -> None:
        """通用 update 接口

        Args:
            table: 表名
            key: 主键值
            data: 更新数据
        """
        if table == "variable":
            dimension = data.get("dimension", "")
            value = data.get("value", "")
            self.update_variable(dimension, value, data)
        elif table == "creative":
            dna = data.get("dna", {})
            performance = data.get("performance", {})
            self.update_creative(key, dna, performance,
                                 data.get("project", ""), data.get("campaign", ""))
        elif table == "country":
            self.update_country_performance(key, data)
        elif table == "placement":
            self.update_placement_performance(key, data)

    def merge(self, other_engine: "VideoMemoryEngine") -> int:
        """通用 merge 接口 - 合并另一个引擎的所有数据

        Args:
            other_engine: 另一个记忆引擎

        Returns:
            合并的总记录数
        """
        count = 0
        count += self.merge_variables(other_engine)
        return count

    def search(self, table: str, filters: dict[str, Any] | None = None,
               limit: int = 100) -> list[dict[str, Any]]:
        """通用 search 接口

        Args:
            table: 表名
            filters: 过滤条件
            limit: 返回数量限制

        Returns:
            记录列表
        """
        if table == "variable":
            filters = filters or {}
            return self.search_variables(
                dimension=filters.get("dimension"),
                min_roas=filters.get("min_roas"),
                min_samples=filters.get("min_samples", 0),
                limit=limit,
            )
        return []

    def close(self) -> None:
        """关闭连接"""
        if self._backend in ("duckdb", "sqlite") and self._conn:
            self._conn.close()

    def __enter__(self) -> "VideoMemoryEngine":
        return self

    def __exit__(self, *args) -> None:
        self.close()
