"""E11.7.3 — Diversity Engine。

种群多样性计算与监控。

核心职责：
  - 计算种群多样性评分（0.0-1.0）
  - 检测是否陷入局部最优
  - 触发探索信号
"""

from __future__ import annotations

import logging
from typing import Any

from .models import GenomeIndividual

logger = logging.getLogger(__name__)


class DiversityEngine:
    """多样性引擎。

    通过比较个体基因特征计算种群多样性。

    Attributes:
        diversity_threshold: 多样性阈值（低于此值触发探索）
        calculate_count:     计算次数
    """

    def __init__(self, diversity_threshold: float = 0.2) -> None:
        self._diversity_threshold = diversity_threshold
        self._calculate_count: int = 0
        self._history: list[float] = []

    # ── 核心接口 ──────────────────────────────────────────

    def calculate(
        self, individuals: list[GenomeIndividual]
    ) -> float:
        """计算种群多样性评分。

        算法：基于特征向量的成对 Jaccard 距离平均值。
        特征来自 GenomeIndividual.features 字典。

        Args:
            individuals: 个体列表

        Returns:
            多样性评分 (0.0-1.0)
        """
        self._calculate_count += 1

        if len(individuals) <= 1:
            self._history.append(0.0)
            return 0.0

        # 提取所有特征值
        feature_vectors = self._extract_feature_vectors(individuals)

        if not feature_vectors or all(len(fv) == 0 for fv in feature_vectors):
            self._history.append(0.0)
            return 0.0

        # 计算成对距离
        total_distance = 0.0
        pair_count = 0

        for i in range(len(feature_vectors)):
            for j in range(i + 1, len(feature_vectors)):
                distance = self._jaccard_distance(feature_vectors[i], feature_vectors[j])
                total_distance += distance
                pair_count += 1

        if pair_count == 0:
            self._history.append(0.0)
            return 0.0

        diversity = total_distance / pair_count
        self._history.append(diversity)
        return round(diversity, 4)

    def calculate_batch(
        self,
        generation_populations: list[list[GenomeIndividual]],
    ) -> list[float]:
        """批量计算多代多样性。"""
        return [self.calculate(pop) for pop in generation_populations]

    # ── 判断 ──────────────────────────────────────────────

    def is_diverse(
        self, individuals: list[GenomeIndividual]
    ) -> bool:
        """种群是否足够多样化。"""
        return self.calculate(individuals) >= self._diversity_threshold

    def needs_exploration(
        self, individuals: list[GenomeIndividual]
    ) -> bool:
        """是否需要强制探索。"""
        return not self.is_diverse(individuals)

    def is_stagnant(self, window: int = 3) -> bool:
        """是否多样性停滞（最近 N 次计算波动小于阈值）。"""
        if len(self._history) < window:
            return False
        recent = self._history[-window:]
        variation = max(recent) - min(recent)
        return variation < 0.05

    # ── 特征提取 ──────────────────────────────────────────

    @staticmethod
    def _extract_feature_vectors(
        individuals: list[GenomeIndividual],
    ) -> list[set[str]]:
        """从个体特征中提取特征向量集合。"""
        vectors: list[set[str]] = []
        for ind in individuals:
            features: set[str] = set()
            for key, value in ind.features.items():
                if isinstance(value, (list, set, tuple)):
                    for v in value:
                        features.add(f"{key}:{v}")
                else:
                    features.add(f"{key}:{value}")
            # 如果没有 features，用 genome_id 作为最小特征
            if not features:
                features.add(f"id:{ind.genome_id}")
            vectors.append(features)
        return vectors

    @staticmethod
    def _jaccard_distance(set_a: set[str], set_b: set[str]) -> float:
        """计算两个集合的 Jaccard 距离。

        Jaccard 距离 = 1 - |A ∩ B| / |A ∪ B|
        """
        if not set_a and not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return 1.0 - intersection / union

    # ── 查询 ──────────────────────────────────────────────

    @property
    def diversity_threshold(self) -> float:
        return self._diversity_threshold

    def get_latest_diversity(self) -> float:
        return self._history[-1] if self._history else 0.0

    def get_history(self) -> list[float]:
        return list(self._history)

    def get_average_diversity(self) -> float:
        if not self._history:
            return 0.0
        return round(sum(self._history) / len(self._history), 4)

    # ── Stats ─────────────────────────────────────────────

    @property
    def calculate_count(self) -> int:
        return self._calculate_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "calculate_count": self._calculate_count,
            "latest_diversity": self.get_latest_diversity(),
            "average_diversity": self.get_average_diversity(),
            "threshold": self._diversity_threshold,
            "history_size": len(self._history),
        }

    def reset(self) -> None:
        self._calculate_count = 0
        self._history.clear()

    def __repr__(self) -> str:
        return (
            f"DiversityEngine(threshold={self._diversity_threshold}, "
            f"latest={self.get_latest_diversity():.3f})"
        )