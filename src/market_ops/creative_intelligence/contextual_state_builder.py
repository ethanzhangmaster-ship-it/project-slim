"""Contextual State Builder — 从 Bandit 到 Contextual Bandit 的桥梁

将 Facebook + Adjust + CreativeGraph 数据统一为 state_t 表。

四维状态空间:
  state_t = {user_context, delivery_context, creative_context, economic_context}

核心洞察:
  - Bandit 把环境压缩成 reward → 不收敛
  - Contextual Bandit 建模 state → 可收敛
  - 当前系统不需要改算法, 需要的是 state 建模能力

MVP 版本 (最小可运行):
  state = {creative_id, geo, device_type, cpm_bucket, frequency_bucket, roas_d1}

完整版本 (需要 Facebook Insights breakdowns):
  state = {user_context(6) + delivery_context(6) + creative_context(8) + economic_context(6)}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import numpy as np


# ============================================================================
# State Schema
# ============================================================================

@dataclass
class UserContext:
    """用户状态 — 当前缺失最严重的一层

    需要 Facebook Insights breakdown by country/device/platform
    当前为 placeholder, 标记为 unknown
    """
    geo_country: str = "unknown"
    platform: str = "unknown"       # iOS / Android
    os_version: str = "unknown"
    device_price_bucket: str = "unknown"  # low / mid / high
    network_type: str = "unknown"   # wifi / 4g / 5g
    language: str = "unknown"

    def to_dict(self) -> dict[str, str]:
        return {
            "geo_country": self.geo_country,
            "platform": self.platform,
            "os_version": self.os_version,
            "device_price_bucket": self.device_price_bucket,
            "network_type": self.network_type,
            "language": self.language,
        }

    @classmethod
    def unknown(cls) -> "UserContext":
        return cls()


@dataclass
class DeliveryContext:
    """投放环境状态 — Facebook 拍卖环境

    CPM: spend / (impressions/1000)
    Frequency: impressions / reach (需要 Facebook Insights)
    Impression share: 当前无数据, 用 CPC/CTR 代理
    """
    cpm: float = 0.0
    cpm_bucket: str = "unknown"     # low(<$5) / medium($5-15) / high(>$15)
    ctr: float = 0.0
    cpc: float = 0.0
    auction_pressure: str = "unknown"  # low / medium / high (CTR/CPC 代理)
    adset_budget_level: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpm": round(self.cpm, 4),
            "cpm_bucket": self.cpm_bucket,
            "ctr": round(self.ctr, 4),
            "cpc": round(self.cpc, 4),
            "auction_pressure": self.auction_pressure,
            "adset_budget_level": self.adset_budget_level,
        }

    @classmethod
    def from_metrics(cls, spend: float, impressions: int, clicks: int, ctr: float) -> "DeliveryContext":
        cpm = (spend / impressions * 1000) if impressions > 0 else 0.0
        cpc = (spend / clicks) if clicks > 0 else 0.0

        cpm_bucket = "unknown"
        if cpm > 0:
            if cpm < 5:
                cpm_bucket = "low"
            elif cpm < 15:
                cpm_bucket = "medium"
            else:
                cpm_bucket = "high"

        # auction pressure proxy: high CTR + high CPC = competitive
        auction_pressure = "unknown"
        if ctr > 0 and cpc > 0:
            if ctr > 3.0 and cpc > 1.0:
                auction_pressure = "high"
            elif ctr > 1.5 or cpc > 0.5:
                auction_pressure = "medium"
            else:
                auction_pressure = "low"

        return cls(
            cpm=cpm, cpm_bucket=cpm_bucket,
            ctr=ctr, cpc=cpc,
            auction_pressure=auction_pressure,
        )


@dataclass
class CreativeContext:
    """创意状态 — 最完整的一层

    来源: creative_features 表, 58 个字段
    """
    creative_id: str = ""
    project: str = ""
    hook_type: str = "unknown"
    visual_density: str = "unknown"    # low / medium / high (saturation+brightness 计算)
    emotion_tag: str = "unknown"
    game_mechanic_type: str = "unknown"
    primary_color: str = "unknown"
    warm_cool: str = "unknown"
    overlay_text: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "project": self.project,
            "hook_type": self.hook_type,
            "visual_density": self.visual_density,
            "emotion_tag": self.emotion_tag,
            "game_mechanic_type": self.game_mechanic_type,
            "primary_color": self.primary_color,
            "warm_cool": self.warm_cool,
            "overlay_text": self.overlay_text,
        }

    @classmethod
    def from_features_row(cls, row: dict[str, Any]) -> "CreativeContext":
        # 计算 visual_density: saturation * brightness → 离散化
        saturation = float(row.get("saturation", 0) or 0)
        brightness = float(row.get("brightness", 0) or 0)
        density_score = saturation * brightness
        if density_score > 0.5:
            visual_density = "high"
        elif density_score > 0.2:
            visual_density = "medium"
        else:
            visual_density = "low"

        # 聚合 emotion 标签
        emotion_tags = []
        for em in ["surprise", "failure", "success", "reward", "tension", "satisfaction"]:
            if row.get(f"emotion_{em}"):
                emotion_tags.append(em)
        emotion_tag = "+".join(emotion_tags) if emotion_tags else "neutral"

        # 聚合 game mechanic
        mechanics = []
        for gm in ["merge", "level", "reward", "inventory", "collection", "progress"]:
            if row.get(f"game_has_{gm}"):
                mechanics.append(gm)
        game_mechanic_type = "+".join(mechanics) if mechanics else "unknown"

        return cls(
            creative_id=str(row.get("creative_id", "")),
            project=str(row.get("project", "")),
            hook_type=str(row.get("hook_type", "unknown")),
            visual_density=visual_density,
            emotion_tag=emotion_tag,
            game_mechanic_type=game_mechanic_type,
            primary_color=str(row.get("primary_color", "unknown")),
            warm_cool=str(row.get("warm_cool", "unknown")),
            overlay_text=str(row.get("overlay_text", "unknown")),
        )


@dataclass
class EconomicContext:
    """经济状态 — 区分"便宜转化 vs 高质量转化"

    来源: creative_performance 表
    """
    spend_to_date: float = 0.0
    roas_d1: float = 0.0
    roas_d7: float = 0.0
    cpi: float = 0.0
    ipm: float = 0.0
    budget_pressure: str = "unknown"  # low / medium / high (spend/install 比值)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spend_to_date": round(self.spend_to_date, 2),
            "roas_d1": round(self.roas_d1, 4),
            "roas_d7": round(self.roas_d7, 4),
            "cpi": round(self.cpi, 2),
            "ipm": round(self.ipm, 2),
            "budget_pressure": self.budget_pressure,
        }

    @classmethod
    def from_metrics_row(cls, row: dict[str, Any]) -> "EconomicContext":
        spend = float(row.get("spend", 0) or 0)
        installs = int(row.get("install", 0) or 0)
        cpi = spend / installs if installs > 0 else 999

        # budget_pressure: high CPI = 高成本获取 = 高压力
        if cpi < 3:
            budget_pressure = "low"
        elif cpi < 10:
            budget_pressure = "medium"
        else:
            budget_pressure = "high"

        return cls(
            spend_to_date=spend,
            roas_d1=float(row.get("roas_d1", 0) or 0),
            roas_d7=float(row.get("roas_d7", 0) or 0),
            cpi=cpi,
            ipm=float(row.get("ipm", 0) or 0),
            budget_pressure=budget_pressure,
        )


@dataclass
class ContextualState:
    """完整 state_t — 四维状态空间"""
    creative_id: str
    date: str
    user: UserContext = field(default_factory=UserContext.unknown)
    delivery: DeliveryContext = field(default_factory=DeliveryContext)
    creative: CreativeContext = field(default_factory=CreativeContext)
    economic: EconomicContext = field(default_factory=EconomicContext)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "date": self.date,
            "user": self.user.to_dict(),
            "delivery": self.delivery.to_dict(),
            "creative": self.creative.to_dict(),
            "economic": self.economic.to_dict(),
        }

    @property
    def state_key(self) -> str:
        """状态哈希键 — 用于 Bandit 按 state 分组学习

        格式: creative_id|geo|platform|cpm_bucket|auction_pressure|hook_type|emotion|roas_d7_bucket
        """
        roas_bucket = "unknown"
        if self.economic.roas_d7 > 0.3:
            roas_bucket = "high"
        elif self.economic.roas_d7 > 0.1:
            roas_bucket = "medium"
        elif self.economic.roas_d7 > 0:
            roas_bucket = "low"

        return "|".join([
            self.creative_id,
            self.user.geo_country,
            self.user.platform,
            self.delivery.cpm_bucket,
            self.delivery.auction_pressure,
            self.creative.hook_type,
            self.creative.emotion_tag,
            roas_bucket,
        ])

    @property
    def state_vector(self) -> list[float]:
        """状态向量 — 用于 ML 模型输入

        将离散维度 one-hot 编码为连续向量
        当前返回 14 维占位向量
        """
        cpm_map = {"low": 0, "medium": 1, "high": 2, "unknown": -1}
        auction_map = {"low": 0, "medium": 1, "high": 2, "unknown": -1}
        density_map = {"low": 0, "medium": 1, "high": 2, "unknown": -1}
        pressure_map = {"low": 0, "medium": 1, "high": 2, "unknown": -1}

        return [
            float(cpm_map.get(self.delivery.cpm_bucket, -1)),
            float(auction_map.get(self.delivery.auction_pressure, -1)),
            float(density_map.get(self.creative.visual_density, -1)),
            float(pressure_map.get(self.economic.budget_pressure, -1)),
            self.delivery.ctr,
            self.delivery.cpc,
            self.economic.roas_d1,
            self.economic.roas_d7,
            self.economic.cpi,
            self.economic.ipm,
            self.economic.spend_to_date,
        ]


# ============================================================================
# Contextual State Builder
# ============================================================================

class ContextualStateBuilder:
    """从 DuckDB 构建 contextual_state 表

    数据源:
      - creative_performance: spend, impression, click, install, ctr, cpi, roas
      - creative_features: hook, emotion, color, layout, game mechanics
      - (未来) Facebook Insights breakdowns: geo, platform, device

    输出:
      - contextual_state 表: 每个 (creative_id, date) 一条 state_t
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def build(self) -> int:
        """构建 contextual_state 表, 返回行数"""
        print("  [StateBuilder] 构建 contextual_state 表...")

        # 创建表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS contextual_state (
                creative_id VARCHAR,
                date VARCHAR,
                state_key VARCHAR,
                state_json VARCHAR,
                -- User
                geo_country VARCHAR DEFAULT 'unknown',
                platform VARCHAR DEFAULT 'unknown',
                -- Delivery
                cpm DOUBLE,
                cpm_bucket VARCHAR,
                ctr DOUBLE,
                cpc DOUBLE,
                auction_pressure VARCHAR,
                -- Creative
                project VARCHAR,
                hook_type VARCHAR,
                visual_density VARCHAR,
                emotion_tag VARCHAR,
                game_mechanic_type VARCHAR,
                primary_color VARCHAR,
                warm_cool VARCHAR,
                -- Economic
                spend_to_date DOUBLE,
                roas_d1 DOUBLE,
                roas_d7 DOUBLE,
                cpi DOUBLE,
                ipm DOUBLE,
                budget_pressure VARCHAR,
                -- Meta
                built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (creative_id, date)
            )
        """)

        # 合并 creative_performance + creative_features
        self.conn.execute("""
            INSERT OR REPLACE INTO contextual_state
            SELECT
                cp.creative_id,
                cp.date,
                cp.creative_id || '|unknown|unknown|' ||
                    CASE
                        WHEN cp.spend / NULLIF(cp.impression, 0) * 1000 < 5 THEN 'low'
                        WHEN cp.spend / NULLIF(cp.impression, 0) * 1000 < 15 THEN 'medium'
                        ELSE 'high'
                    END || '|' ||
                    CASE
                        WHEN cp.ctr > 3.0 AND cp.spend / NULLIF(cp.click, 0) > 1.0 THEN 'high'
                        WHEN cp.ctr > 1.5 OR cp.spend / NULLIF(cp.click, 0) > 0.5 THEN 'medium'
                        ELSE 'low'
                    END || '|' ||
                    COALESCE(cf.hook_type, 'unknown') || '|' ||
                    CASE
                        WHEN COALESCE(cf.emotion_surprise, FALSE) THEN 'surprise'
                        WHEN COALESCE(cf.emotion_failure, FALSE) THEN 'failure'
                        WHEN COALESCE(cf.emotion_success, FALSE) THEN 'success'
                        WHEN COALESCE(cf.emotion_reward, FALSE) THEN 'reward'
                        WHEN COALESCE(cf.emotion_tension, FALSE) THEN 'tension'
                        WHEN COALESCE(cf.emotion_satisfaction, FALSE) THEN 'satisfaction'
                        ELSE 'neutral'
                    END || '|' ||
                    CASE
                        WHEN COALESCE(cp.roas_d7, 0) > 0.3 THEN 'high'
                        WHEN COALESCE(cp.roas_d7, 0) > 0.1 THEN 'medium'
                        WHEN COALESCE(cp.roas_d7, 0) > 0 THEN 'low'
                        ELSE 'unknown'
                    END AS state_key,
                json_object(
                    'user', json_object('geo_country', 'unknown', 'platform', 'unknown'),
                    'delivery', json_object(
                        'cpm', ROUND(cp.spend / NULLIF(cp.impression, 0) * 1000, 4),
                        'cpm_bucket', CASE
                            WHEN cp.spend / NULLIF(cp.impression, 0) * 1000 < 5 THEN 'low'
                            WHEN cp.spend / NULLIF(cp.impression, 0) * 1000 < 15 THEN 'medium'
                            ELSE 'high'
                        END,
                        'ctr', cp.ctr,
                        'cpc', ROUND(cp.spend / NULLIF(cp.click, 0), 4),
                        'auction_pressure', CASE
                            WHEN cp.ctr > 3.0 AND cp.spend / NULLIF(cp.click, 0) > 1.0 THEN 'high'
                            WHEN cp.ctr > 1.5 OR cp.spend / NULLIF(cp.click, 0) > 0.5 THEN 'medium'
                            ELSE 'low'
                        END
                    ),
                    'creative', json_object(
                        'hook_type', COALESCE(cf.hook_type, 'unknown'),
                        'visual_density', CASE
                            WHEN COALESCE(cf.saturation, 0) * COALESCE(cf.brightness, 0) > 0.5 THEN 'high'
                            WHEN COALESCE(cf.saturation, 0) * COALESCE(cf.brightness, 0) > 0.2 THEN 'medium'
                            ELSE 'low'
                        END,
                        'emotion_tag', CASE
                            WHEN COALESCE(cf.emotion_surprise, FALSE) THEN 'surprise'
                            WHEN COALESCE(cf.emotion_failure, FALSE) THEN 'failure'
                            WHEN COALESCE(cf.emotion_success, FALSE) THEN 'success'
                            WHEN COALESCE(cf.emotion_reward, FALSE) THEN 'reward'
                            WHEN COALESCE(cf.emotion_tension, FALSE) THEN 'tension'
                            WHEN COALESCE(cf.emotion_satisfaction, FALSE) THEN 'satisfaction'
                            ELSE 'neutral'
                        END,
                        'game_mechanic_type', CASE
                            WHEN COALESCE(cf.game_has_merge, FALSE) THEN 'merge'
                            WHEN COALESCE(cf.game_has_level, FALSE) THEN 'level'
                            WHEN COALESCE(cf.game_has_reward, FALSE) THEN 'reward'
                            ELSE 'unknown'
                        END,
                        'primary_color', COALESCE(cf.primary_color, 'unknown'),
                        'warm_cool', COALESCE(cf.warm_cool, 'unknown')
                    ),
                    'economic', json_object(
                        'spend_to_date', cp.spend,
                        'roas_d1', COALESCE(cp.roas_d1, 0),
                        'roas_d7', COALESCE(cp.roas_d7, 0),
                        'cpi', COALESCE(cp.cpi, 0),
                        'ipm', COALESCE(cp.ipm, 0),
                        'budget_pressure', CASE
                            WHEN COALESCE(cp.cpi, 999) < 3 THEN 'low'
                            WHEN COALESCE(cp.cpi, 999) < 10 THEN 'medium'
                            ELSE 'high'
                        END
                    )
                ) AS state_json,
                'unknown' AS geo_country,
                'unknown' AS platform,
                ROUND(cp.spend / NULLIF(cp.impression, 0) * 1000, 4) AS cpm,
                CASE
                    WHEN cp.spend / NULLIF(cp.impression, 0) * 1000 < 5 THEN 'low'
                    WHEN cp.spend / NULLIF(cp.impression, 0) * 1000 < 15 THEN 'medium'
                    ELSE 'high'
                END AS cpm_bucket,
                cp.ctr,
                ROUND(cp.spend / NULLIF(cp.click, 0), 4) AS cpc,
                CASE
                    WHEN cp.ctr > 3.0 AND cp.spend / NULLIF(cp.click, 0) > 1.0 THEN 'high'
                    WHEN cp.ctr > 1.5 OR cp.spend / NULLIF(cp.click, 0) > 0.5 THEN 'medium'
                    ELSE 'low'
                END AS auction_pressure,
                COALESCE(cf.project, cp.project) AS project,
                COALESCE(cf.hook_type, 'unknown') AS hook_type,
                CASE
                    WHEN COALESCE(cf.saturation, 0) * COALESCE(cf.brightness, 0) > 0.5 THEN 'high'
                    WHEN COALESCE(cf.saturation, 0) * COALESCE(cf.brightness, 0) > 0.2 THEN 'medium'
                    ELSE 'low'
                END AS visual_density,
                CASE
                    WHEN COALESCE(cf.emotion_surprise, FALSE) THEN 'surprise'
                    WHEN COALESCE(cf.emotion_failure, FALSE) THEN 'failure'
                    WHEN COALESCE(cf.emotion_success, FALSE) THEN 'success'
                    WHEN COALESCE(cf.emotion_reward, FALSE) THEN 'reward'
                    WHEN COALESCE(cf.emotion_tension, FALSE) THEN 'tension'
                    WHEN COALESCE(cf.emotion_satisfaction, FALSE) THEN 'satisfaction'
                    ELSE 'neutral'
                END AS emotion_tag,
                CASE
                    WHEN COALESCE(cf.game_has_merge, FALSE) THEN 'merge'
                    WHEN COALESCE(cf.game_has_level, FALSE) THEN 'level'
                    WHEN COALESCE(cf.game_has_reward, FALSE) THEN 'reward'
                    ELSE 'unknown'
                END AS game_mechanic_type,
                COALESCE(cf.primary_color, 'unknown') AS primary_color,
                COALESCE(cf.warm_cool, 'unknown') AS warm_cool,
                cp.spend AS spend_to_date,
                COALESCE(cp.roas_d1, 0) AS roas_d1,
                COALESCE(cp.roas_d7, 0) AS roas_d7,
                COALESCE(cp.cpi, 0) AS cpi,
                COALESCE(cp.ipm, 0) AS ipm,
                CASE
                    WHEN COALESCE(cp.cpi, 999) < 3 THEN 'low'
                    WHEN COALESCE(cp.cpi, 999) < 10 THEN 'medium'
                    ELSE 'high'
                END AS budget_pressure,
                CURRENT_TIMESTAMP AS built_at
            FROM creative_performance cp
            LEFT JOIN creative_features cf ON cp.creative_id = cf.creative_id
            WHERE cp.creative_id IS NOT NULL
        """)

        count = self.conn.execute("SELECT COUNT(*) FROM contextual_state").fetchone()[0]
        print(f"  [StateBuilder] 构建完成: {count} 行 contextual_state")

        # 维度覆盖报告
        self._print_coverage()

        return count

    def _print_coverage(self) -> None:
        """打印各维度的覆盖率"""
        dims = [
            ("geo_country", "用户-国家"),
            ("platform", "用户-平台"),
            ("cpm_bucket", "投放-CPM分桶"),
            ("auction_pressure", "投放-拍卖压力"),
            ("hook_type", "创意-Hook类型"),
            ("visual_density", "创意-视觉密度"),
            ("emotion_tag", "创意-情感标签"),
            ("game_mechanic_type", "创意-游戏机制"),
            ("budget_pressure", "经济-预算压力"),
        ]
        total = self.conn.execute("SELECT COUNT(*) FROM contextual_state").fetchone()[0]
        if total == 0:
            return

        print(f"\n  {'维度':<20} {'覆盖率':>10} {'状态'}")
        print(f"  {'─'*20} {'─'*10} {'─'*10}")
        for col, label in dims:
            non_unknown = self.conn.execute(
                f"SELECT COUNT(*) FROM contextual_state WHERE {col} != 'unknown' AND {col} IS NOT NULL"
            ).fetchone()[0]
            pct = non_unknown / total * 100
            status = "✅" if pct > 80 else ("⚠️" if pct > 30 else "❌")
            print(f"  {label:<20} {pct:>9.1f}% {status}")

    def get_state_distribution(self, dimension: str, top_n: int = 10) -> list[dict[str, Any]]:
        """获取某个维度的分布"""
        rows = self.conn.execute(f"""
            SELECT {dimension}, COUNT(*) AS cnt
            FROM contextual_state
            GROUP BY {dimension}
            ORDER BY cnt DESC
            LIMIT {top_n}
        """).fetchall()
        return [{"value": r[0], "count": r[1]} for r in rows]

    def query_states(
        self, creative_id: str | None = None, hook_type: str | None = None,
        cpm_bucket: str | None = None, limit: int = 10,
    ) -> list[dict[str, Any]]:
        """按条件查询 state"""
        wheres = []
        params = []

        if creative_id:
            wheres.append("creative_id = ?")
            params.append(creative_id)
        if hook_type:
            wheres.append("hook_type = ?")
            params.append(hook_type)
        if cpm_bucket:
            wheres.append("cpm_bucket = ?")
            params.append(cpm_bucket)

        where_clause = " AND ".join(wheres) if wheres else "1=1"

        rows = self.conn.execute(
            f"SELECT state_json FROM contextual_state WHERE {where_clause} LIMIT {limit}",
            params,
        ).fetchall()

        return [json.loads(r[0]) for r in rows]


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Contextual State Builder")
    parser.add_argument("--db", type=str, default="db/facebook_performance.duckdb")
    parser.add_argument("--distribution", type=str, default=None,
                        help="查看某维度分布 (如 cpm_bucket, hook_type, emotion_tag)")
    args = parser.parse_args()

    builder = ContextualStateBuilder(args.db)
    try:
        count = builder.build()

        if args.distribution:
            dist = builder.get_state_distribution(args.distribution)
            print(f"\n  {args.distribution} 分布:")
            for d in dist:
                print(f"    {d['value']:<20} {d['count']:>5}")

        return 0
    finally:
        builder.close()


if __name__ == "__main__":
    main()