"""Phase 4.2.1 — Player Journey Analyzer.

分析 Creative → Player Journey 完整行为轨迹。

不是只看"这个创意带来多少付费用户"，
而是分析"这个创意带来的用户从安装到付费经历了什么"。

核心流程：
  1. FTUE Completion → 新手引导完成率
  2. Retention Curve → D1/D3/D7/D30 留存
  3. Progression → D1/D3/D7 进度
  4. Feature Usage → 功能使用模式
  5. Payment Journey → 付费时间线
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .models import PlayerJourneyProfile


class PlayerJourneyAnalyzer:
    """Creative → Player Journey 分析器。

    分析一个创意吸引的用户群体的完整行为轨迹。
    """

    def __init__(self) -> None:
        self._profiles: dict[str, PlayerJourneyProfile] = {}

    # ── Loading ─────────────────────────────────────────────

    def load_from_player_data(self, data: dict[str, Any]) -> int:
        """从玩家数据加载旅程分析。

        Args:
            data: {"players": [{...}, ...]} 格式的玩家数据

        Returns:
            加载的 Creative 数量
        """
        players = data.get("players", [])
        if not players:
            return 0

        # 按 creative_id 分组
        by_creative: dict[str, list[dict]] = {}
        for p in players:
            cid = p.get("creative_id", "unknown")
            if cid not in by_creative:
                by_creative[cid] = []
            by_creative[cid].append(p)

        for cid, group in by_creative.items():
            self._profiles[cid] = self._compute_journey(cid, group)

        return len(self._profiles)

    def _compute_journey(self, creative_id: str, players: list[dict]) -> PlayerJourneyProfile:
        """计算单个 Creative 的玩家旅程画像."""
        profile = PlayerJourneyProfile(
            creative_id=creative_id,
            install_count=len(players),
            sample_size=len(players),
        )

        if not players:
            return profile

        # FTUE
        completed = sum(1 for p in players if p.get("ftue_completed", True))
        skipped = sum(1 for p in players if p.get("tutorial_skipped", False))
        profile.ftue_completion_rate = completed / len(players)
        profile.tutorial_skip_rate = skipped / len(players)

        # 留存
        for day in ("d1", "d3", "d7", "d30"):
            key = f"{day}_retained"
            retained = sum(1 for p in players if p.get(key, True))
            setattr(profile, f"{day}_retention", retained / len(players))

        # 进度
        for day in ("d1", "d3", "d7"):
            key = f"{day}_progress"
            values = [p.get(key, 0) for p in players if p.get(key) is not None]
            if values:
                setattr(profile, key, sum(values) / len(values))

        # 玩法参与
        profile.avg_level_reached = self._avg(players, "level", 0)
        profile.avg_areas_unlocked = self._avg(players, "areas_unlocked", 0)
        profile.avg_merge_count = self._avg(players, "merge_count", 0)
        profile.avg_merge_speed = self._avg(players, "merge_speed", 0)
        profile.avg_collection_rate = self._avg(players, "collection_rate", 0)
        profile.avg_session_count = self._avg(players, "total_sessions", 0)
        profile.avg_session_duration = self._avg(players, "session_duration", 0)

        # 功能使用
        feature_counter = Counter()
        for p in players:
            features = p.get("features_used", [])
            for f in features:
                feature_counter[f] += 1
        total = len(players)
        profile.feature_usage = {
            f: c / total for f, c in feature_counter.most_common(10)
        }

        # 付费旅程
        payers = [p for p in players if p.get("is_payer", False)
                   or float(p.get("total_spend", 0)) > 0]
        profile.payer_conversion_rate = len(payers) / max(len(players), 1)

        if payers:
            first_purchase_hours = [
                p.get("first_purchase_hour", p.get("first_purchase_day", 0) * 24)
                for p in payers
            ]
            profile.first_purchase_hour = (
                sum(first_purchase_hours) / len(first_purchase_hours)
            )

            purchase_counts = [p.get("total_purchases", 0) for p in payers]
            profile.avg_purchase_count = sum(purchase_counts) / len(purchase_counts)

            order_values = [p.get("avg_order_value", 0) for p in payers]
            profile.avg_order_value = sum(order_values) / max(len(order_values), 1)

            repeat = sum(1 for p in payers if p.get("total_purchases", 0) > 1)
            profile.repeat_purchase_rate = repeat / max(len(payers), 1)

        return profile

    @staticmethod
    def _avg(players: list[dict], key: str, default: float) -> float:
        values = [p.get(key, default) for p in players]
        return sum(values) / max(len(values), 1)

    # ── Query ───────────────────────────────────────────────

    def get(self, creative_id: str) -> PlayerJourneyProfile | None:
        return self._profiles.get(creative_id)

    def get_all(self) -> list[PlayerJourneyProfile]:
        return list(self._profiles.values())

    def get_high_quality_journeys(self) -> list[PlayerJourneyProfile]:
        """获取高质量玩家旅程的 Creative."""
        return [p for p in self._profiles.values() if p.is_high_quality_journey]

    def get_by_ftue(self, min_ftue: float = 0.80) -> list[PlayerJourneyProfile]:
        """按 FTUE 完成率筛选."""
        return [
            p for p in self._profiles.values()
            if p.ftue_completion_rate >= min_ftue
        ]

    def get_by_retention(self, min_d7: float = 0.30) -> list[PlayerJourneyProfile]:
        """按 D7 留存筛选."""
        return [
            p for p in self._profiles.values()
            if p.d7_retention >= min_d7
        ]

    def get_by_payer_conversion(self, min_rate: float = 0.05) -> list[PlayerJourneyProfile]:
        """按付费转化率筛选."""
        return [
            p for p in self._profiles.values()
            if p.payer_conversion_rate >= min_rate
        ]

    def rank_by_journey_quality(self, top_n: int = 10) -> list[PlayerJourneyProfile]:
        """按玩家旅程质量排序."""
        sorted_profiles = sorted(
            self._profiles.values(),
            key=lambda p: p.journey_quality_score,
            reverse=True,
        )
        return sorted_profiles[:top_n]

    def compare_journeys(self, cid_a: str, cid_b: str) -> dict[str, Any]:
        """对比两个 Creative 的玩家旅程."""
        a = self._profiles.get(cid_a)
        b = self._profiles.get(cid_b)
        if not a or not b:
            return {"error": "creative not found"}

        return {
            "creative_a": {"id": cid_a, "journey_score": a.journey_quality_score},
            "creative_b": {"id": cid_b, "journey_score": b.journey_quality_score},
            "diff": {
                "ftue": round(a.ftue_completion_rate - b.ftue_completion_rate, 3),
                "d7": round(a.d7_retention - b.d7_retention, 3),
                "payer_conversion": round(
                    a.payer_conversion_rate - b.payer_conversion_rate, 3
                ),
                "journey_score": round(
                    a.journey_quality_score - b.journey_quality_score, 3
                ),
            },
            "better_overall": cid_a
            if a.journey_quality_score > b.journey_quality_score
            else cid_b,
        }

    # ── Statistics ──────────────────────────────────────────

    def journey_stats(self) -> dict[str, Any]:
        """全局玩家旅程统计."""
        profiles = list(self._profiles.values())
        if not profiles:
            return {"total_creatives": 0}

        return {
            "total_creatives": len(profiles),
            "with_journey_data": len(profiles),
            "avg_ftue_completion": round(
                sum(p.ftue_completion_rate for p in profiles) / len(profiles), 3
            ),
            "avg_d7_retention": round(
                sum(p.d7_retention for p in profiles) / len(profiles), 3
            ),
            "avg_d30_retention": round(
                sum(p.d30_retention for p in profiles) / len(profiles), 3
            ),
            "avg_payer_conversion": round(
                sum(p.payer_conversion_rate for p in profiles) / len(profiles), 3
            ),
            "avg_journey_quality": round(
                sum(p.journey_quality_score for p in profiles) / len(profiles), 3
            ),
            "high_quality_count": sum(
                1 for p in profiles if p.is_high_quality_journey
            ),
            "avg_first_purchase_hour": round(
                sum(p.first_purchase_hour for p in profiles if p.first_purchase_hour > 0)
                / max(sum(1 for p in profiles if p.first_purchase_hour > 0), 1), 1
            ),
            "avg_repeat_purchase_rate": round(
                sum(p.repeat_purchase_rate for p in profiles) / len(profiles), 3
            ),
        }