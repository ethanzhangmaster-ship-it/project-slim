"""E11.6.4 Fitness Calibrator — 收入驱动 Fitness 校准器。

将 Revenue Fitness 合并进入 E11 Evolution 的 Fitness 评分体系。

核心功能：
  1. 合并 Evolution Fitness + Revenue Fitness → CalibratedFitness
  2. 冷启动保护（样本量不足时降低 Revenue 权重）
  3. 与 Selection Engine 集成（按 CalibratedFitness 排序）
  4. 与 Mutation Strategy 集成（增强赚钱 DNA 权重）

公式：
  Final Fitness = evolution_weight × Evolution Fitness
                + revenue_weight × Revenue Fitness

冷启动调整：
  当 sample_size < COLD_START_THRESHOLD 时：
    adjusted_revenue_fitness = revenue_fitness × confidence_factor
    adjusted_evolution_weight  = 1.0 - adjusted_revenue_weight
"""

from __future__ import annotations

import math
from typing import Any

from .fitness_calibration_schema import (
    RevenueFitnessProfile,
    CalibratedFitness,
)
from .fitness_weights import (
    DEFAULT_CALIBRATION_WEIGHTS,
    COLD_START_THRESHOLD,
    calc_confidence_factor,
)


# ═══════════════════════════════════════════════════════════
# FitnessCalibrator
# ═══════════════════════════════════════════════════════════

class FitnessCalibrator:
    """收入驱动 Fitness 校准器。

    合并 Evolution Fitness 和 Revenue Fitness，产出 CalibratedFitness。

    Usage:
        calibrator = FitnessCalibrator()
        calibrated = calibrator.calibrate(
            evolution_fitness=0.75,
            revenue_profile=profile,
        )
        ranked = calibrator.rank_by_calibrated_fitness(calibrated_list)
    """

    def __init__(
        self,
        evolution_weight: float = 0.6,
        revenue_weight: float = 0.4,
        cold_start_threshold: int = 100,
    ) -> None:
        """初始化。

        Args:
            evolution_weight:  Evolution 权重（默认 0.6）
            revenue_weight:    Revenue 权重（默认 0.4）
            cold_start_threshold: 冷启动阈值（默认 100）
        """
        self._evolution_weight = evolution_weight
        self._revenue_weight = revenue_weight
        self._cold_start_threshold = cold_start_threshold

    @property
    def evolution_weight(self) -> float:
        return self._evolution_weight

    @property
    def revenue_weight(self) -> float:
        return self._revenue_weight

    @property
    def cold_start_threshold(self) -> int:
        return self._cold_start_threshold

    # ── 主入口 ────────────────────────────────────────

    def calibrate(
        self,
        evolution_fitness: float,
        revenue_profile: RevenueFitnessProfile,
    ) -> CalibratedFitness:
        """合并 Evolution Fitness + Revenue Fitness。

        Args:
            evolution_fitness: Evolution 创意质量评分（0.0~1.0）
            revenue_profile:   RevenueFitnessProfile（来自 RevenueFitnessCalculator）

        Returns:
            CalibratedFitness
        """
        genome_id = revenue_profile.genome_id
        sample_size = revenue_profile.sample_size
        revenue_fitness = revenue_profile.revenue_fitness

        # 冷启动调整
        if sample_size < self._cold_start_threshold:
            return self._cold_start_calibrate(
                genome_id=genome_id,
                evolution_fitness=evolution_fitness,
                revenue_fitness=revenue_fitness,
                sample_size=sample_size,
                confidence=revenue_profile.confidence,
            )

        # 正常计算
        final_fitness = round(
            evolution_fitness * self._evolution_weight
            + revenue_fitness * self._revenue_weight,
            4,
        )

        return CalibratedFitness(
            genome_id=genome_id,
            evolution_fitness=evolution_fitness,
            revenue_fitness=revenue_fitness,
            final_fitness=final_fitness,
            cold_start_adjusted=False,
            evolution_weight=self._evolution_weight,
            revenue_weight=self._revenue_weight,
            confidence=revenue_profile.confidence,
            sample_size=sample_size,
        )

    def calibrate_from_market(
        self,
        market_fitness: dict[str, float],
        revenue_profile: RevenueFitnessProfile,
    ) -> CalibratedFitness:
        """从 E11.5 Market Fitness 合并 Revenue Fitness。

        这是 E11.5 和 E11.6 的统一入口：
          E11.5 GenomeFitness → market_fitness dict
          E11.6 RevenueFitnessProfile → revenue_profile
          → CalibratedFitness（最终进化评分）

        公式：
          Final Fitness = 0.6 × Market Fitness + 0.4 × Revenue Fitness

        Args:
            market_fitness: E11.5 GenomeFitness 的 dict 表示
                {"fitness_score": 0.91, "monetization_score": 0.95, ...}
            revenue_profile: E11.6.4 RevenueFitnessProfile

        Returns:
            CalibratedFitness
        """
        evolution_fitness = market_fitness.get("fitness_score", 0.0)
        return self.calibrate(evolution_fitness, revenue_profile)

    def calibrate_batch(
        self,
        fitness_map: dict[str, float],
        profiles: list[RevenueFitnessProfile],
    ) -> list[CalibratedFitness]:
        """批量校准。

        Args:
            fitness_map: {genome_id: evolution_fitness}
            profiles:    RevenueFitnessProfile 列表

        Returns:
            CalibratedFitness 列表
        """
        calibrated: list[CalibratedFitness] = []
        for profile in profiles:
            gid = profile.genome_id
            evol_fitness = fitness_map.get(gid, 0.0)
            calibrated.append(
                self.calibrate(evol_fitness, profile)
            )
        return calibrated

    # ── 冷启动 ────────────────────────────────────────

    def _cold_start_calibrate(
        self,
        genome_id: str,
        evolution_fitness: float,
        revenue_fitness: float,
        sample_size: int,
        confidence: float,
    ) -> CalibratedFitness:
        """冷启动调整：降低 Revenue 权重，提高 Evolution 权重。

        原因：
          新 Genome 没有足够收入数据，不能直接淘汰。
          需要保留创意质量、视觉质量、Hook Score 等。

        公式：
          adjusted_revenue_weight = revenue_weight × confidence_factor
          adjusted_evolution_weight = 1.0 - adjusted_revenue_weight
          final_fitness = evolution_fitness × adjusted_evolution_weight
                        + revenue_fitness × adjusted_revenue_weight
        """
        # 计算调整后的权重
        confidence_factor = calc_confidence_factor(sample_size)
        adjusted_revenue_weight = round(
            self._revenue_weight * confidence_factor, 4,
        )
        adjusted_evolution_weight = round(
            1.0 - adjusted_revenue_weight, 4,
        )

        final_fitness = round(
            evolution_fitness * adjusted_evolution_weight
            + revenue_fitness * adjusted_revenue_weight,
            4,
        )

        return CalibratedFitness(
            genome_id=genome_id,
            evolution_fitness=evolution_fitness,
            revenue_fitness=revenue_fitness,
            final_fitness=final_fitness,
            cold_start_adjusted=True,
            evolution_weight=adjusted_evolution_weight,
            revenue_weight=adjusted_revenue_weight,
            confidence=confidence,
            sample_size=sample_size,
        )

    def is_cold_start(self, sample_size: int) -> bool:
        """判断是否冷启动。"""
        return sample_size < self._cold_start_threshold

    # ── 排名 ──────────────────────────────────────────

    def rank_by_calibrated_fitness(
        self,
        calibrated: list[CalibratedFitness],
    ) -> list[CalibratedFitness]:
        """按 final_fitness 降序排名。"""
        return sorted(
            calibrated,
            key=lambda c: c.final_fitness,
            reverse=True,
        )

    def get_top_calibrated(
        self,
        calibrated: list[CalibratedFitness],
        top_n: int = 5,
    ) -> list[CalibratedFitness]:
        """获取 Top N CalibratedFitness。"""
        ranked = self.rank_by_calibrated_fitness(calibrated)
        return ranked[:top_n]

    def get_elite_calibrated(
        self,
        calibrated: list[CalibratedFitness],
    ) -> list[CalibratedFitness]:
        """获取精英（final_fitness >= 0.85）。"""
        return [c for c in calibrated if c.is_elite]

    def get_weak_calibrated(
        self,
        calibrated: list[CalibratedFitness],
    ) -> list[CalibratedFitness]:
        """获取弱者（final_fitness < 0.40）。"""
        return [c for c in calibrated if c.final_fitness < 0.40]

    # ── 与 Selection 集成 ─────────────────────────────

    def select_candidates(
        self,
        calibrated: list[CalibratedFitness],
        elite_count: int = 3,
        threshold_count: int = 5,
    ) -> dict[str, list[CalibratedFitness]]:
        """按 Elite → Threshold → Diversity 优先级选择。

        Args:
            calibrated:      CalibratedFitness 列表
            elite_count:     精英保留数量
            threshold_count: 阈值筛选数量

        Returns:
            {"elite": [...], "threshold": [...], "diversity": [...]}
        """
        ranked = self.rank_by_calibrated_fitness(calibrated)

        elite = ranked[:elite_count]
        remaining = ranked[elite_count:]

        threshold = [
            c for c in remaining
            if c.is_strong and not c.cold_start_adjusted
        ][:threshold_count]

        threshold_ids = {c.genome_id for c in threshold}
        diversity = [c for c in remaining if c.genome_id not in threshold_ids]

        return {
            "elite": elite,
            "threshold": threshold,
            "diversity": diversity,
        }

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "evolution_weight": self._evolution_weight,
            "revenue_weight": self._revenue_weight,
            "cold_start_threshold": self._cold_start_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessCalibrator:
        return cls(
            evolution_weight=data.get("evolution_weight", 0.6),
            revenue_weight=data.get("revenue_weight", 0.4),
            cold_start_threshold=data.get("cold_start_threshold", 100),
        )

    # ── 交叉验证 ──────────────────────────────────────

    @staticmethod
    def validate_consistency(
        market_fitness: dict[str, float],
        revenue_profile: RevenueFitnessProfile,
    ) -> dict[str, Any]:
        """验证 E11.5 Market Fitness 与 E11.6 Revenue Fitness 的一致性。

        检测不一致信号：
          - market_fitness 高但 revenue 低 → 可能虚假繁荣
          - market_fitness 低但 revenue 高 → 可能漏掉高价值 Genome

        Args:
            market_fitness: E11.5 GenomeFitness dict
            revenue_profile: E11.6.4 RevenueFitnessProfile

        Returns:
            {
                "consistent": bool,
                "flag": "ok" | "false_positive" | "false_negative" | "no_data",
                "market_score": float,
                "revenue_score": float,
                "gap": float,
            }
        """
        market_score = market_fitness.get("fitness_score", 0.0)
        revenue_score = revenue_profile.revenue_fitness
        gap = abs(market_score - revenue_score)

        if market_score == 0.0 and revenue_score == 0.0:
            return {"consistent": True, "flag": "no_data", "market_score": 0.0, "revenue_score": 0.0, "gap": 0.0}

        if market_score > 0.7 and revenue_score < 0.3:
            return {"consistent": False, "flag": "false_positive", "market_score": market_score, "revenue_score": revenue_score, "gap": gap}
        if market_score < 0.3 and revenue_score > 0.7:
            return {"consistent": False, "flag": "false_negative", "market_score": market_score, "revenue_score": revenue_score, "gap": gap}
        if gap > 0.5:
            return {"consistent": False, "flag": "large_gap", "market_score": market_score, "revenue_score": revenue_score, "gap": gap}

        return {"consistent": True, "flag": "ok", "market_score": market_score, "revenue_score": revenue_score, "gap": gap}

    def __repr__(self) -> str:
        return (
            f"FitnessCalibrator(evol_w={self._evolution_weight}, "
            f"rev_w={self._revenue_weight}, "
            f"cold_start={self._cold_start_threshold})"
        )