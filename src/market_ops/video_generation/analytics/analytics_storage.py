"""Analytics Storage - DuckDB + Parquet"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AnalyticsRecord:
    record_type: str = ""
    timestamp: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class AnalyticsStorage:
    """分析存储层 - 支持 DuckDB + Parquet"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).resolve().parent / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._duckdb = None
        self._try_init_duckdb()

    def _try_init_duckdb(self):
        try:
            import duckdb
            self._duckdb = duckdb.connect(str(self.data_dir / "analytics.db"))
            self._setup_tables()
        except ImportError:
            pass

    def _setup_tables(self):
        if self._duckdb:
            self._duckdb.execute("""
                CREATE TABLE IF NOT EXISTS generation (
                    id INTEGER PRIMARY KEY,
                    timestamp TIMESTAMP,
                    blueprint_id TEXT,
                    scene_id TEXT,
                    platform TEXT,
                    status TEXT,
                    cost REAL,
                    quality_score REAL,
                    duration REAL
                )
            """)
            self._duckdb.execute("""
                CREATE TABLE IF NOT EXISTS creative (
                    id INTEGER PRIMARY KEY,
                    timestamp TIMESTAMP,
                    blueprint_id TEXT,
                    style TEXT,
                    hook_type TEXT,
                    camera_move TEXT,
                    prompt_dna TEXT
                )
            """)
            self._duckdb.execute("""
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY,
                    timestamp TIMESTAMP,
                    blueprint_id TEXT,
                    variant_id TEXT,
                    platform TEXT,
                    views INTEGER,
                    ctr REAL,
                    conversions INTEGER
                )
            """)

    def insert_generation(self, record: Dict[str, Any]):
        if self._duckdb:
            max_id = self._duckdb.execute("SELECT MAX(id) FROM generation").fetchone()[0]
            next_id = (max_id or 0) + 1
            self._duckdb.execute("""
                INSERT INTO generation (id, timestamp, blueprint_id, scene_id, platform, 
                                      status, cost, quality_score, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                next_id,
                record.get("timestamp"),
                record.get("blueprint_id"),
                record.get("scene_id"),
                record.get("platform"),
                record.get("status"),
                record.get("cost"),
                record.get("quality_score"),
                record.get("duration"),
            ))
        else:
            self._save_json(record, "generation")

    def insert_creative(self, record: Dict[str, Any]):
        if self._duckdb:
            self._duckdb.execute("""
                INSERT INTO creative (timestamp, blueprint_id, style, hook_type, 
                                     camera_move, prompt_dna)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record.get("timestamp"),
                record.get("blueprint_id"),
                record.get("style"),
                record.get("hook_type"),
                record.get("camera_move"),
                record.get("prompt_dna"),
            ))
        else:
            self._save_json(record, "creative")

    def insert_performance(self, record: Dict[str, Any]):
        if self._duckdb:
            self._duckdb.execute("""
                INSERT INTO performance (timestamp, blueprint_id, variant_id, platform,
                                        views, ctr, conversions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get("timestamp"),
                record.get("blueprint_id"),
                record.get("variant_id"),
                record.get("platform"),
                record.get("views"),
                record.get("ctr"),
                record.get("conversions"),
            ))
        else:
            self._save_json(record, "performance")

    def _save_json(self, record: Dict[str, Any], table_name: str):
        file_path = self.data_dir / f"{table_name}.jsonl"
        record["timestamp"] = record.get("timestamp", datetime.now().isoformat())
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def query(self, sql: str) -> List[Dict[str, Any]]:
        if self._duckdb:
            result = self._duckdb.execute(sql).fetchall()
            columns = [desc[0] for desc in self._duckdb.description]
            return [dict(zip(columns, row)) for row in result]
        return []

    def get_daily_stats(self) -> Dict[str, Any]:
        if self._duckdb:
            result = self._duckdb.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(cost) as total_cost,
                    AVG(quality_score) as avg_quality
                FROM generation
            """).fetchone()
            return {
                "total": result[0],
                "completed": result[1],
                "total_cost": round(result[2], 2) if result[2] else 0,
                "avg_quality": round(result[3], 1) if result[3] else 0,
            }
        return {"total": 0, "completed": 0, "total_cost": 0, "avg_quality": 0}

    def close(self):
        if self._duckdb:
            self._duckdb.close()
