"""E11.6.4 Revenue Fitness Calculator — 收入驱动 Fitness 计算器。

将 GenomeAttributionResult（E11.6.3 输出）转换为 RevenueFitnessProfile。

核心公式：
  Revenue Fitness =
    0.35 × Revenue Score (LTV 归一化)
    + 0.25 × ROAS Score (ROAS 归一化)
    + 0.20 × Retention Score (留存加权)
    + 0.10 × Payer Rate (付费率归一化)
    + 0.10 × Creative Quality (创意质量)

数据流：
  GenomeAttributionResult → RevenueFitnessCalculator.calculate()
    → RevenueFitnessProfile
"""

from __future__ import annotations

import math
from typing import Any

from ..attribution.attribution_schema import GenomeAttributionResult
from .fitness_calibration_schema import (
    RevenueFitnessProfile,
    ROASProfile,
    RetentionProfile,
)
from .fitness_weights import (
    FitnessWeights,
    normalize_ltv,
    normalize_roas,
    normalize_payer_rate,
    normalize_retention,
    normalize_creative_score,
    calc_confidence_factor,
    RETENTION_D1_BENCHMARK,
    RETENTION_D7_BENCHMARK,
    RETENTION_D30_BENCHMARK,
)


# ═══════════════════════════════════════════════════════════
# RevenueFitnessCalculator
# ═══════════════════════════════════════════════════════════

class RevenueFitnessCalculator:
    """收入驱动 Fitness 计算器。

    将 GenomeAttributionResult 转换为 RevenueFitnessProfile。

    Usage:
        calc = RevenueFitnessCalculator()
        profile = calc.calculate(result)
        profiles = calc.calculate_batch([result1, result2])
    """

    def __init__(
        self,
        weights: FitnessWeights | None = None,
    ) -> None:
        self._weights = weights or FitnessWeights()

    @property
    def weights(self) -> FitnessWeights:
        return self._weights

    # ── 主入口 ────────────────────────────────────────

    def calculate(
        self,
        result: GenomeAttributionResult,
        *,
        roas: ROASProfile | None = None,
        retention: RetentionProfile | None = None,
        creative_score: float = 0.0,
    ) -> RevenueFitnessProfile:
        """计算单个 Genome 的 RevenueFitnessProfile。

        Args:
            result:         GenomeAttributionResult（来自 E11.6.3）
            roas:           ROAS 数据（可选，默认使用 ROASProfile()）
            retention:      留存数据（可选，默认使用 RetentionProfile()）
            creative_score: 创意质量评分（0-100，来自 Evolution）

        Returns:
            RevenueFitnessProfile
        """
        roas = roas or ROASProfile()
        retention = retention or RetentionProfile()

        # 1. Revenue Score — LTV 归一化
        revenue_score = normalize_ltv(result.d30_ltv)

        # 2. ROAS Score — 加权 D7/D30/D120
        roas_score = self._calc_roas_score(roas)

        # 3. Retention Score — 加权 D1/D7/D30
        retention_score = self._calc_retention_score(retention)

        # 4. Payer Rate Score
        payer_rate_score = normalize_payer_rate(result.payer_rate)

        # 5. Creative Quality Score
        creative_quality_score = normalize_creative_score(creative_score)

        # 6. 置信度
        sample_size = result.total_users
        confidence = calc_confidence_factor(sample_size)

        # 7. 加权综合
        w = self._weights
        revenue_fitness = round(
            revenue_score * w.revenue
            + roas_score * w.roas
            + retention_score * w.retention
            + payer_rate_score * w.payer_rate
            + creative_quality_score * w.creative_quality,
            4,
        )

        return RevenueFitnessProfile(
            genome_id=result.genome_id,
            creative_score=creative_score,
            iap_ltv=result.iap_revenue / max(result.total_users, 1),
            ad_ltv=result.ad_revenue / max(result.total_users, 1),
            total_ltv=result.d30_ltv,
            payer_rate=result.payer_rate,
            roi=roas.d120_roas,
            revenue_fitness=revenue_fitness,
            revenue_score=round(revenue_score, 4),
            roas_score=round(roas_score, 4),
            retention_score=round(retention_score, 4),
            payer_rate_score=round(payer_rate_score, 4),
            confidence=confidence,
            sample_size=sample_size,
            roas=roas,
            retention=retention,
        )

    def calculate_batch(
        self,
        results: list[GenomeAttributionResult],
        *,
        roas_map: dict[str, ROASProfile] | None = None,
        retention_map: dict[str, RetentionProfile] | None = None,
        creative_scores: dict[str, float] | None = None,
    ) -> list[RevenueFitnessProfile]:
        """批量计算 RevenueFitnessProfile。

        Args:
            results:          GenomeAttributionResult 列表
            roas_map:         {genome_id: ROASProfile}
            retention_map:    {genome_id: RetentionProfile}
            creative_scores:  {genome_id: creative_score}

        Returns:
            RevenueFitnessProfile 列表
        """
        roas_map = roas_map or {}
        retention_map = retention_map or {}
        creative_scores = creative_scores or {}

        profiles: list[RevenueFitnessProfile] = []
        for result in results:
            profile = self.calculate(
                result,
                roas=roas_map.get(result.genome_id),
                retention=retention_map.get(result.genome_id),
                creative_score=creative_scores.get(result.genome_id, 0.0),
            )
            profiles.append(profile)
        return profiles

    # ── 维度计算 ──────────────────────────────────────

    @staticmethod
    def _calc_roas_score(roas: ROASProfile) -> float:
        """计算 ROAS 评分。

        加权 D7/D30/D120：
          D7   × 0.2
          D30  × 0.5
          D120 × 0.3
        """
        d7 = normalize_roas(roas.d7_roas)
        d30 = normalize_roas(roas.d30_roas)
        d120 = normalize_roas(roas.d120_roas)
        return round(d7 * 0.2 + d30 * 0.5 + d120 * 0.3, 4)

    @staticmethod
    def _calc_retention_score(retention: RetentionProfile) -> float:
        """计算留存评分。

        加权 D1/D7/D30：
          D1  × 0.3
          D7  × 0.4
          D30 × 0.3
        """
        d1 = normalize_retention(retention.d1, RETENTION_D1_BENCHMARK)
        d7 = normalize_retention(retention.d7, RETENTION_D7_BENCHMARK)
        d30 = normalize_retention(retention.d30, RETENTION_D30_BENCHMARK)
        return round(d1 * 0.3 + d7 * 0.4 + d30 * 0.3, 4)

    # ── 排名 ──────────────────────────────────────────

    def rank_by_revenue_fitness(
        self,
        profiles: list[RevenueFitnessProfile],
    ) -> list[RevenueFitnessProfile]:
        """按 revenue_fitness 降序排名。"""
        return sorted(
            profiles,
            key=lambda p: p.revenue_fitness,
            reverse=True,
        )

    def get_top_profiles(
        self,
        profiles: list[RevenueFitnessProfile],
        top_n: int = 5,
    ) -> list[RevenueFitnessProfile]:
        """获取 Top N RevenueFitnessProfile。"""
        ranked = self.rank_by_revenue_fitness(profiles)
        return ranked[:top_n]

    # ── 冷启动检测 ────────────────────────────────────

    def get_cold_start_profiles(
        self,
        profiles: list[RevenueFitnessProfile],
    ) -> list[RevenueFitnessProfile]:
        """获取冷启动（样本量 < 100）的 Profile。"""
        return [p for p in profiles if p.is_cold_start]

    def __repr__(self) -> str:
        return f"RevenueFitnessCalculator(weights={self._weights})"