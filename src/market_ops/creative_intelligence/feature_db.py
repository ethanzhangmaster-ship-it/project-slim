"""M2: Creative Feature Database

扩展现有 db/facebook_performance.duckdb,新增 creative_features 表。
通过 creative_id 关联 performance 数据,支持统一查询。

复用现有:
- market_ops.creative_growth_loop.01_collectors.facebook_ads_collector (DuckDB schema)
- creative_id 作为全局主键

Usage:
    from market_ops.creative_intelligence.feature_db import FeatureDatabase

    db = FeatureDatabase()
    db.save_features([feature1, feature2])
    features = db.query_features(project="P04")
    joined = db.query_features_with_performance(project="P04", min_spend=100)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = _ROOT / "db" / "facebook_performance.duckdb"

from market_ops.creative_intelligence.models import CreativeFeature


class FeatureDatabase:
    """Creative Feature 统一数据库

    表结构:
    1. creative_features - Feature Intelligence Engine 输出
    2. creative_performance - 已有(FacebookAdsCollector),通过 creative_id 关联
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS creative_features (
        creative_id VARCHAR PRIMARY KEY,
        project VARCHAR,
        campaign VARCHAR,
        adset VARCHAR,
        image_path VARCHAR,

        -- 主体特征
        subject_type VARCHAR,
        subject_count INTEGER,
        character_count INTEGER,
        subject_description VARCHAR,

        -- 视觉标记 (布尔)
        has_female BOOLEAN,
        has_monster BOOLEAN,
        has_ui BOOLEAN,
        has_reward BOOLEAN,
        has_coins BOOLEAN,
        has_chest BOOLEAN,
        has_arrow BOOLEAN,
        has_before_after BOOLEAN,
        has_explosion BOOLEAN,
        has_highlight BOOLEAN,
        has_finger_guide BOOLEAN,
        has_number BOOLEAN,
        has_text BOOLEAN,
        has_cta BOOLEAN,

        -- 颜色
        primary_color VARCHAR,
        secondary_color VARCHAR,
        warm_cool VARCHAR,
        saturation DOUBLE,
        brightness DOUBLE,
        color_distribution VARCHAR,

        -- 构图
        symmetry BOOLEAN,
        golden_ratio BOOLEAN,
        left_right_layout BOOLEAN,
        top_bottom_layout BOOLEAN,
        center_layout BOOLEAN,
        focus_grid VARCHAR,
        focus_contrast DOUBLE,

        -- 游戏元素
        game_has_merge BOOLEAN,
        game_has_level BOOLEAN,
        game_has_reward BOOLEAN,
        game_has_inventory BOOLEAN,
        game_has_collection BOOLEAN,
        game_has_progress BOOLEAN,

        -- 文案
        ocr_title VARCHAR,
        ocr_numbers VARCHAR,
        ocr_cta VARCHAR,
        ocr_keywords VARCHAR,
        overlay_text VARCHAR,

        -- 心理
        hook_type VARCHAR,
        mood VARCHAR,
        emotion_surprise BOOLEAN,
        emotion_failure BOOLEAN,
        emotion_success BOOLEAN,
        emotion_reward BOOLEAN,
        emotion_tension BOOLEAN,
        emotion_satisfaction BOOLEAN,

        -- 元信息
        analyzed_at VARCHAR,
        analyzer_version VARCHAR,
        source VARCHAR
    );
    """

    # performance表字段(参考FacebookAdsCollector,用于JOIN)
    PERF_FIELDS = "creative_id, spend, impression, click, install, ctr, ipm, cpi, roas_d1, roas_d7, date, project"

    def __init__(self, db_path: str | Path | None = None) -> None:
        if not HAS_DUCKDB:
            raise ImportError("需要安装 duckdb: pip install duckdb")

        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self._db_path), read_only=False)
        self._init_schema()

    def _init_schema(self) -> None:
        """初始化表结构"""
        self._conn.execute(self.SCHEMA)
        # 创建索引加速查询
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_cf_project ON creative_features(project)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_cf_hook ON creative_features(hook_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_cf_color ON creative_features(primary_color)")

    def save_features(self, features: list[CreativeFeature]) -> int:
        """保存/更新 Feature 列表 (upsert)"""
        if not features:
            return 0

        count = 0
        for f in features:
            d = f.to_dict()
            # 跳过空creative_id
            if not d["creative_id"]:
                continue
            self._upsert_one(d)
            count += 1

        self._conn.commit()
        return count

    def _upsert_one(self, d: dict[str, Any]) -> None:
        """单条upsert (DuckDB用INSERT OR REPLACE)"""
        cols = list(d.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        sql = f"INSERT OR REPLACE INTO creative_features ({col_names}) VALUES ({placeholders})"
        self._conn.execute(sql, [d[c] for c in cols])

    # ==================== 查询接口 ====================

    def query_features(
        self,
        project: str | None = None,
        hook_type: str | None = None,
        primary_color: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查询Feature(不带性能数据)"""
        sql = "SELECT * FROM creative_features WHERE 1=1"
        params: list[Any] = []
        if project:
            sql += " AND project = ?"
            params.append(project)
        if hook_type:
            sql += " AND hook_type = ?"
            params.append(hook_type)
        if primary_color:
            sql += " AND primary_color = ?"
            params.append(primary_color)
        sql += f" LIMIT {limit}"

        rows = self._conn.execute(sql, params).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def query_features_with_performance(
        self,
        project: str | None = None,
        min_spend: float = 0,
        min_impressions: int = 0,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """查询Feature JOIN performance数据 (核心分析查询)"""
        sql = """
        SELECT
            f.creative_id, f.project, f.image_path,
            f.subject_type, f.subject_count, f.character_count,
            f.has_female, f.has_monster, f.has_ui, f.has_reward,
            f.has_coins, f.has_chest, f.has_arrow, f.has_cta,
            f.primary_color, f.secondary_color, f.warm_cool,
            f.saturation, f.brightness,
            f.symmetry, f.center_layout, f.left_right_layout,
            f.game_has_merge, f.game_has_level, f.game_has_progress,
            f.game_has_collection, f.game_has_reward,
            f.hook_type, f.mood,
            f.emotion_surprise, f.emotion_reward, f.emotion_tension,
            f.ocr_title, f.overlay_text,
            p.spend, p.impression, p.click, p.install,
            p.ctr, p.ipm, p.cpi, p.roas_d1, p.roas_d7, p.date
        FROM creative_features f
        LEFT JOIN creative_performance p ON f.creative_id = p.creative_id
        WHERE 1=1
        """
        params: list[Any] = []
        if project:
            sql += " AND f.project = ?"
            params.append(project)
        if min_spend > 0:
            sql += " AND p.spend >= ?"
            params.append(min_spend)
        if min_impressions > 0:
            sql += " AND p.impression >= ?"
            params.append(min_impressions)
        if date_from:
            sql += " AND p.date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND p.date <= ?"
            params.append(date_to)
        sql += f" ORDER BY p.spend DESC NULLS LAST LIMIT {limit}"

        rows = self._conn.execute(sql, params).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def get_feature_count(self) -> int:
        """获取Feature总数"""
        return self._conn.execute("SELECT COUNT(*) FROM creative_features").fetchone()[0]

    def get_project_stats(self) -> list[dict[str, Any]]:
        """按项目统计Feature分布"""
        sql = """
        SELECT project, COUNT(*) as count,
               COUNT(DISTINCT hook_type) as hook_types,
               COUNT(DISTINCT primary_color) as colors
        FROM creative_features
        GROUP BY project
        ORDER BY count DESC
        """
        rows = self._conn.execute(sql).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
