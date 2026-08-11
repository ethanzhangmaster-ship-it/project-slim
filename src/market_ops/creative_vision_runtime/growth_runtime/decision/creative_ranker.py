"""E13.3.3 Creative Ranker — 统一评分与排序.

核心职责: 基于多维指标，为所有 Creative 建立统一 Growth Fitness Score。

评分公式:
  Fitness = 0.25 × ROAS + 0.20 × LTV + 0.15 × Retention + 0.15 × CTR
          + 0.10 × Revenue + 0.10 × Scale Potential + 0.05 × Confidence

输入: CreativeFitnessVector[]
输出: CreativeRanking[]
"""

from __future__ import annotations

import math
from typing import Any

from ..pipeline.models import CreativeFitnessVector
from .models import (
    CreativeRanking,
    DecisionConfidence,
)


# ═══════════════════════════════════════════════════════════════
# Creative Ranker
# ═══════════════════════════════════════════════════════════════


class CreativeRanker:
    """E13.3.3 Creative Ranker — 统一评分排序引擎.

    功能:
      1. 为每个 Creative 计算 Growth Fitness Score
      2. 按得分排序
      3. 输出 CreativeRanking 列表
    """

    # 评分权重
    DEFAULT_WEIGHTS = {
        "roas": 0.25,
        "ltv": 0.20,
        "retention": 0.15,
        "ctr": 0.15,
        "revenue": 0.10,
        "scale": 0.10,
        "confidence": 0.05,
    }

    # 归一化参数
    NORMALIZATION = {
        "roas_max": 5.0,       # ROAS 5x 为满分
        "ltv_max": 20.0,       # LTV $20 为满分
        "retention_max": 0.5,  # D7 留存 50% 为满分
        "ctr_max": 0.08,       # CTR 8% 为满分
        "revenue_max": 10000,  # Revenue $10,000 为满分
        "scale_max": 1000,     # Installs 1000 为满分
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        self._rankings: list[CreativeRanking] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def weights(self) -> dict[str, float]:
        return self._weights

    @property
    def ranking_count(self) -> int:
        return len(self._rankings)

    # ── Core Ranking ──────────────────────────────────────────

    def rank(
        self, vectors: list[CreativeFitnessVector],
    ) -> list[CreativeRanking]:
        """对所有 Creative 进行排名.

        Args:
            vectors: 创意适应度向量列表

        Returns:
            list[CreativeRanking]: 按得分降序排列的排名列表
        """
        if not vectors:
            return []

        self._rankings = []

        # 1. 计算每个 Creative 的得分
        scored: list[tuple[CreativeFitnessVector, dict[str, float]]] = []
        for vector in vectors:
            scores = self._compute_scores(vector)
            scored.append((vector, scores))

        # 2. 按 fitness_score 降序排序
        scored.sort(key=lambda x: x[1]["fitness"], reverse=True)

        # 3. 生成排名
        total = len(scored)
        for rank_idx, (vector, scores) in enumerate(scored, 1):
            ranking = self._build_ranking(vector, scores, rank_idx, total)
            self._rankings.append(ranking)

        return self._rankings

    def _compute_scores(
        self, vector: CreativeFitnessVector,
    ) -> dict[str, float]:
        """计算各维度得分."""
        norm = self.NORMALIZATION

        # ROAS Score (0-1)
        roas_score = min(1.0, vector.d30_roas / norm["roas_max"])

        # LTV Score (0-1)
        ltv_score = min(1.0, vector.d30_ltv / norm["ltv_max"])

        # Retention Score (0-1)
        retention_score = min(1.0, vector.d7_retention / norm["retention_max"])

        # CTR Score (0-1)
        ctr_score = min(1.0, vector.ctr / norm["ctr_max"])

        # Revenue Score (0-1)
        revenue_score = min(1.0, vector.total_revenue / norm["revenue_max"])

        # Scale Potential Score (0-1)
        scale_score = min(1.0, vector.installs / norm["scale_max"])

        # Confidence Score (0-1)
        confidence_score = min(1.0, vector.confidence)

        # Weighted Fitness Score
        w = self._weights
        fitness = (
            w["roas"] * roas_score
            + w["ltv"] * ltv_score
            + w["retention"] * retention_score
            + w["ctr"] * ctr_score
            + w["revenue"] * revenue_score
            + w["scale"] * scale_score
            + w["confidence"] * confidence_score
        )

        return {
            "fitness": round(fitness, 4),
            "roas": round(roas_score, 4),
            "ltv": round(ltv_score, 4),
            "retention": round(retention_score, 4),
            "ctr": round(ctr_score, 4),
            "revenue": round(revenue_score, 4),
            "scale": round(scale_score, 4),
            "confidence": round(confidence_score, 4),
        }

    def _build_ranking(
        self,
        vector: CreativeFitnessVector,
        scores: dict[str, float],
        rank: int,
        total: int,
    ) -> CreativeRanking:
        """构建 CreativeRanking."""
        # 决策置信度
        if scores["confidence"] >= 0.85:
            confidence = DecisionConfidence.HIGH
        elif scores["confidence"] >= 0.70:
            confidence = DecisionConfidence.MEDIUM
        elif scores["confidence"] >= 0.50:
            confidence = DecisionConfidence.LOW
        else:
            confidence = DecisionConfidence.SPECULATIVE

        # Winner 判定: Top 20% 且 fitness >= 0.6
        is_winner = (rank <= max(1, total * 0.2)) and scores["fitness"] >= 0.6

        return CreativeRanking(
            creative_id=vector.creative_id,
            creative_name=vector.creative_name,
            genome_id=vector.genome_id,
            product_id=vector.product_id,
            rank=rank,
            total_creatives=total,
            fitness_score=scores["fitness"],
            roas_score=scores["roas"],
            ltv_score=scores["ltv"],
            retention_score=scores["retention"],
            ctr_score=scores["ctr"],
            revenue_score=scores["revenue"],
            scale_score=scores["scale"],
            confidence_score=scores["confidence"],
            is_winner=is_winner,
            is_fatigued=vector.is_fatigued,
            decision_confidence=confidence,
        )

    # ── Query ─────────────────────────────────────────────────

    def get_ranking(self, creative_id: str) -> CreativeRanking | None:
        """获取指定 Creative 的排名."""
        for r in self._rankings:
            if r.creative_id == creative_id:
                return r
        return None

    def get_all_rankings(self) -> list[CreativeRanking]:
        return list(self._rankings)

    def get_top(self, limit: int = 10) -> list[CreativeRanking]:
        """获取 Top N."""
        return self._rankings[:limit]

    def get_bottom(self, limit: int = 10) -> list[CreativeRanking]:
        """获取 Bottom N."""
        return self._rankings[-limit:] if limit <= len(self._rankings) else self._rankings

    def get_winners(self) -> list[CreativeRanking]:
        """获取 Winner."""
        return [r for r in self._rankings if r.is_winner]

    def get_fatigued(self) -> list[CreativeRanking]:
        """获取疲劳素材."""
        return [r for r in self._rankings if r.is_fatigued]

    def get_top_performers(self) -> list[CreativeRanking]:
        """获取 Top Performers."""
        return [r for r in self._rankings if r.is_top_performer]

    def get_by_confidence(
        self, confidence: DecisionConfidence,
    ) -> list[CreativeRanking]:
        """按置信度获取."""
        return [r for r in self._rankings if r.decision_confidence == confidence]

    # ── Comparison ────────────────────────────────────────────

    def compare(self, creative_id_a: str, creative_id_b: str) -> dict[str, Any]:
        """比较两个 Creative."""
        a = self.get_ranking(creative_id_a)
        b = self.get_ranking(creative_id_b)

        if not a or not b:
            return {"error": "Creative not found"}

        return {
            "creative_a": {
                "id": a.creative_id,
                "rank": a.rank,
                "fitness": a.fitness_score,
            },
            "creative_b": {
                "id": b.creative_id,
                "rank": b.rank,
                "fitness": b.fitness_score,
            },
            "winner": a.creative_id if a.fitness_score > b.fitness_score else b.creative_id,
            "delta": round(abs(a.fitness_score - b.fitness_score), 4),
        }

    # ── Lifecycle ─────────────────────────────────────────────

    def reset(self) -> None:
        self._rankings.clear()

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_ranked": self.ranking_count,
            "winners": len(self.get_winners()),
            "fatigued": len(self.get_fatigued()),
            "top_performers": len(self.get_top_performers()),
            "top_5": [
                {"rank": r.rank, "creative_id": r.creative_id, "fitness": r.fitness_score}
                for r in self.get_top(5)
            ],
            "avg_fitness": round(
                sum(r.fitness_score for r in self._rankings) / max(1, self.ranking_count), 4
            ),
        }