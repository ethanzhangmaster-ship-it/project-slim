"""E11.5.3 — Evaluator。

PerformanceSignal → FitnessScore。

核心职责：
  1. 多维性能评分（ROI/CTR/CVR/Revenue）
  2. 加权综合评分
  3. 排名计算
  4. 基准对比

评分规则：
  - ROI:  >= 1.5 → 100, 1.0-1.5 → 60, < 1.0 → 20
  - CTR:  >= 3% → 100, 1-3% → 60, < 1% → 20
  - CVR:  >= 5% → 100, 2-5% → 60, < 2% → 20
  - Revenue: > 0 and sufficient data → 80, else → 40

综合权重：
  overall = roi_score * 0.5 + ctr_score * 0.3 + cvr_score * 0.2
"""

from __future__ import annotations

import logging
from typing import Any

from .models import PerformanceSignal, FitnessScore

logger = logging.getLogger(__name__)


class Evaluator:
    """Genome 适应度评估器。

    PerformanceSignal → FitnessScore。

    Attributes:
        evaluate_count: 已评估数
    """

    # 评分权重
    ROI_WEIGHT = 0.5
    CTR_WEIGHT = 0.3
    CVR_WEIGHT = 0.2

    # 基准阈值
    ROI_HIGH = 1.5
    ROI_MEDIUM = 1.0
    CTR_HIGH = 0.03
    CTR_MEDIUM = 0.01
    CVR_HIGH = 0.05
    CVR_MEDIUM = 0.02

    # 评分等级
    SCORE_HIGH = 100
    SCORE_MEDIUM = 60
    SCORE_LOW = 20

    def __init__(self) -> None:
        self._evaluate_count: int = 0
        self._all_scores: list[FitnessScore] = []

    # ── 核心接口 ──────────────────────────────────────

    def evaluate(
        self,
        signal: PerformanceSignal,
    ) -> FitnessScore:
        """评估单个性能信号。

        Args:
            signal: 性能信号

        Returns:
            FitnessScore
        """
        roi_score = self._score_roi(signal.roi)
        ctr_score = self._score_ctr(signal.ctr)
        cvr_score = self._score_cvr(signal.cvr)
        revenue_score = self._score_revenue(signal)

        overall = round(
            roi_score * self.ROI_WEIGHT
            + ctr_score * self.CTR_WEIGHT
            + cvr_score * self.CVR_WEIGHT,
            2,
        )

        fitness = FitnessScore(
            genome_id=signal.genome_id,
            overall_score=overall,
            roi_score=roi_score,
            ctr_score=ctr_score,
            cvr_score=cvr_score,
            revenue_score=revenue_score,
        )

        self._all_scores.append(fitness)
        self._evaluate_count += 1

        # 更新排名
        self._update_ranks()

        return fitness

    def evaluate_batch(
        self,
        signals: list[PerformanceSignal],
    ) -> list[FitnessScore]:
        """批量评估。"""
        scores = [self.evaluate(s) for s in signals]
        self._update_ranks()
        return scores

    # ── 评分方法 ──────────────────────────────────────

    @classmethod
    def _score_roi(cls, roi: float) -> float:
        if roi >= cls.ROI_HIGH:
            return cls.SCORE_HIGH
        elif roi >= cls.ROI_MEDIUM:
            return cls.SCORE_MEDIUM
        else:
            return cls.SCORE_LOW

    @classmethod
    def _score_ctr(cls, ctr: float) -> float:
        if ctr >= cls.CTR_HIGH:
            return cls.SCORE_HIGH
        elif ctr >= cls.CTR_MEDIUM:
            return cls.SCORE_MEDIUM
        else:
            return cls.SCORE_LOW

    @classmethod
    def _score_cvr(cls, cvr: float) -> float:
        if cvr >= cls.CVR_HIGH:
            return cls.SCORE_HIGH
        elif cvr >= cls.CVR_MEDIUM:
            return cls.SCORE_MEDIUM
        else:
            return cls.SCORE_LOW

    @classmethod
    def _score_revenue(cls, signal: PerformanceSignal) -> float:
        if signal.revenue > 0 and signal.has_sufficient_data:
            return 80.0
        return 40.0

    # ── 排名 ──────────────────────────────────────────

    def _update_ranks(self) -> None:
        """更新所有评分排名。"""
        sorted_scores = sorted(
            self._all_scores,
            key=lambda s: (s.overall_score, s.roi_score),
            reverse=True,
        )
        for i, score in enumerate(sorted_scores):
            score.rank = i + 1

    def get_rank(self, genome_id: str) -> int:
        """获取指定 genome 的排名。"""
        for score in self._all_scores:
            if score.genome_id == genome_id:
                return score.rank
        return 0

    def get_top(self, n: int = 3) -> list[FitnessScore]:
        """获取排名前 N 的评分。"""
        sorted_scores = sorted(
            self._all_scores,
            key=lambda s: (s.overall_score, s.roi_score),
            reverse=True,
        )
        return sorted_scores[:n]

    # ── Stats ──────────────────────────────────────────

    @property
    def evaluate_count(self) -> int:
        return self._evaluate_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "evaluate_count": self._evaluate_count,
            "total_genomes": len(self._all_scores),
            "top_genome": self._all_scores[0].genome_id if self._all_scores else None,
            "top_score": self._all_scores[0].overall_score if self._all_scores else 0.0,
        }

    def reset(self) -> None:
        self._evaluate_count = 0
        self._all_scores.clear()

    def __repr__(self) -> str:
        return (
            f"Evaluator(evaluated={self._evaluate_count}, "
            f"genomes={len(self._all_scores)})"
        )