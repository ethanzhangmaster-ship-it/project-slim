"""E12.5.2 — Pattern Ranker。

对挖掘出的 MetaPattern 进行评分、排序和筛选，
决定哪些 Pattern 值得进入 Knowledge Graph。

评分公式:
  PatternScore = SuccessRate × 0.35
               + ROASGain  × 0.30
               + SampleFactor × 0.15
               + Confidence × 0.20

筛选条件:
  - 最低样本量: 5
  - 最低置信度: 0.60
  - 最低成功率: 0.40
"""

from __future__ import annotations

import math

from .models import GeneImpactScore, MetaPattern, PatternType


# ── Scoring Config ─────────────────────────────────────────


SCORE_WEIGHTS = {
    "success_rate": 0.35,
    "roas_gain": 0.30,
    "sample_factor": 0.15,
    "confidence": 0.20,
}

DEFAULT_FILTER = {
    "min_sample": 5,
    "min_confidence": 0.60,
    "min_success_rate": 0.40,
}


# ── PatternRanker ──────────────────────────────────────────


class PatternRanker:
    """模式排序器 —— 评分、筛选、排序。

    对 MetaPattern 进行综合评分，决定哪些模式值得进入 Knowledge Graph。

    Usage:
        >>> ranker = PatternRanker()
        >>> ranked = ranker.rank(patterns)
        >>> top = ranker.get_top_patterns(patterns, n=5)
        >>> filtered = ranker.filter_reliable(patterns)
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        filters: dict | None = None,
    ) -> None:
        self._weights = weights or SCORE_WEIGHTS
        self._filters = filters or DEFAULT_FILTER

    def rank(self, patterns: list[MetaPattern]) -> list[MetaPattern]:
        """对模式进行评分并排序。

        Args:
            patterns: MetaPattern 列表

        Returns:
            按 rank_score 降序排列的 MetaPattern 列表
        """
        for pattern in patterns:
            pattern.rank_score = self._calculate_score(pattern)

        return sorted(patterns, key=lambda p: p.rank_score, reverse=True)

    def filter_reliable(
        self,
        patterns: list[MetaPattern],
    ) -> list[MetaPattern]:
        """筛选可靠模式。

        Args:
            patterns: MetaPattern 列表

        Returns:
            满足筛选条件的 MetaPattern 列表
        """
        return [
            p for p in patterns
            if p.sample_count >= self._filters.get("min_sample", 5)
            and p.confidence >= self._filters.get("min_confidence", 0.60)
            and p.success_rate >= self._filters.get("min_success_rate", 0.40)
        ]

    def get_top_patterns(
        self,
        patterns: list[MetaPattern],
        n: int = 5,
    ) -> list[MetaPattern]:
        """获取 Top N 模式。

        Args:
            patterns: MetaPattern 列表
            n:        返回数量

        Returns:
            Top N MetaPattern 列表
        """
        ranked = self.rank(patterns)
        return ranked[:n]

    def get_top_by_type(
        self,
        patterns: list[MetaPattern],
        pattern_type: PatternType,
        n: int = 3,
    ) -> list[MetaPattern]:
        """按类型获取 Top N 模式。

        Args:
            patterns:      MetaPattern 列表
            pattern_type:  模式类型
            n:             返回数量

        Returns:
            Top N MetaPattern 列表
        """
        filtered = [p for p in patterns if p.pattern_type == pattern_type]
        ranked = self.rank(filtered)
        return ranked[:n]

    def get_mutation_priorities(
        self,
        patterns: list[MetaPattern],
    ) -> list[dict]:
        """获取突变优先级列表（供 E11 Mutation Engine 使用）。

        Args:
            patterns: MetaPattern 列表

        Returns:
            突变先验列表（按优先级降序）
        """
        ranked = self.rank(patterns)
        return [p.to_mutation_prior() for p in ranked]

    def generate_ranking_report(
        self,
        patterns: list[MetaPattern],
    ) -> dict:
        """生成排序报告。

        Args:
            patterns: MetaPattern 列表

        Returns:
            报告字典
        """
        ranked = self.rank(patterns)
        reliable = self.filter_reliable(ranked)
        top = self.get_top_patterns(ranked, n=10)

        # 按类型分组
        by_type: dict[str, list[dict]] = {}
        for p in ranked:
            type_name = p.pattern_type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append({
                "name": p.name,
                "rank_score": round(p.rank_score, 4),
                "success_rate": round(p.success_rate, 4),
                "sample_count": p.sample_count,
            })

        return {
            "total_patterns": len(patterns),
            "reliable_patterns": len(reliable),
            "top_patterns": [
                {
                    "name": p.name,
                    "type": p.pattern_type.value,
                    "rank_score": round(p.rank_score, 4),
                    "success_rate": round(p.success_rate, 4),
                    "avg_roas_gain": round(p.avg_roas_gain, 4),
                    "sample_count": p.sample_count,
                    "confidence": round(p.confidence, 4),
                    "recommendation": p.recommendation,
                }
                for p in top[:5]
            ],
            "by_type": {
                t: sorted(plist, key=lambda x: x["rank_score"], reverse=True)[:3]
                for t, plist in by_type.items()
            },
            "best_rank_score": round(top[0].rank_score, 4) if top else 0.0,
            "mutation_priorities": self.get_mutation_priorities(ranked)[:10],
        }

    # ── Private ──────────────────────────────────────────────

    def _calculate_score(self, pattern: MetaPattern) -> float:
        """计算单个模式的综合评分。

        Score = SuccessRate × 0.35
              + ROASGain  × 0.30
              + SampleFactor × 0.15
              + Confidence × 0.20

        Args:
            pattern: MetaPattern

        Returns:
            综合评分（0-1）
        """
        # 成功率评分（0-1）
        success_score = pattern.success_rate

        # ROAS 增益评分（归一化到 0-1）
        roas_gain = pattern.avg_roas_gain
        # 使用 sigmoid 归一化: 1 / (1 + e^(-5x))
        if roas_gain != 0:
            roas_score = 1.0 / (1.0 + math.exp(-5 * roas_gain))
        else:
            roas_score = 0.5

        # 样本因子（0-1）
        sample_factor = min(pattern.sample_count / 50, 1.0)

        # 置信度（0-1）
        confidence = pattern.confidence

        # 加权综合
        score = (
            success_score * self._weights["success_rate"]
            + roas_score * self._weights["roas_gain"]
            + sample_factor * self._weights["sample_factor"]
            + confidence * self._weights["confidence"]
        )

        return score

    def __repr__(self) -> str:
        return (
            f"PatternRanker(weights={self._weights}, "
            f"filters={self._filters})"
        )