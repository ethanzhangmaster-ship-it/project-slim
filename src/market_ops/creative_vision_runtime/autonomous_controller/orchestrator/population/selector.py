"""E11.7.3 — Population Selector。

核心进化选择器：根据 fitness 排名进行精英保留、突变选择、退役决策。

选择规则：
  - Elite:  top 20% → 保留
  - Mutate: middle 50% (20%-70%) → 突变
  - Retire: bottom 30% → 淘汰
  - Explore: 多样性不足时强制探索
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    GenomeIndividual,
    GenomeStatus,
    PopulationDecision,
)
from .evaluator import PopulationEvaluator

logger = logging.getLogger(__name__)


class PopulationSelector:
    """种群选择器。

    Attributes:
        elite_ratio:      精英保留比例 (0.0-1.0)
        mutate_ratio:     突变比例 (0.0-1.0)
        retire_ratio:     退役比例 (0.0-1.0)
        min_population:   最小种群数量（低于此值不退役）
        select_count:     选择次数
    """

    def __init__(
        self,
        elite_ratio: float = 0.2,
        mutate_ratio: float = 0.5,
        retire_ratio: float = 0.3,
        min_population: int = 5,
    ) -> None:
        if not abs(elite_ratio + mutate_ratio + retire_ratio - 1.0) < 0.01:
            raise ValueError(
                f"elite_ratio + mutate_ratio + retire_ratio must equal 1.0, "
                f"got {elite_ratio}+{mutate_ratio}+{retire_ratio}={elite_ratio + mutate_ratio + retire_ratio}"
            )
        self._elite_ratio = elite_ratio
        self._mutate_ratio = mutate_ratio
        self._retire_ratio = retire_ratio
        self._min_population = min_population
        self._select_count: int = 0

    # ── 核心接口 ──────────────────────────────────────────

    def select(
        self,
        individuals: list[GenomeIndividual],
        generation: int = 0,
        diversity_score: float = 0.0,
    ) -> PopulationDecision:
        """根据 fitness 排名进行种群选择。

        Args:
            individuals:     个体列表
            generation:      代数
            diversity_score: 多样性评分

        Returns:
            PopulationDecision
        """
        self._select_count += 1

        if not individuals:
            return PopulationDecision(
                generation=generation,
                diversity_score=diversity_score,
                summary="Empty population",
            )

        # 排名
        ranked = PopulationEvaluator.rank(individuals)
        total = len(ranked)

        # 计算各层级数量
        elite_n = max(1, int(total * self._elite_ratio))
        retire_n = int(total * self._retire_ratio)
        mutate_n = total - elite_n - retire_n

        # 精英
        elite_ids = [ind.genome_id for ind in ranked[:elite_n]]
        for ind in ranked[:elite_n]:
            ind.status = GenomeStatus.ELITE

        # 突变
        mutate_ids = [ind.genome_id for ind in ranked[elite_n : elite_n + mutate_n]]
        for ind in ranked[elite_n : elite_n + mutate_n]:
            ind.status = GenomeStatus.MUTATING

        # 退役
        retire_ids: list[str] = []
        if total > self._min_population:
            retire_ids = [ind.genome_id for ind in ranked[-retire_n:]]
            for ind in ranked[-retire_n:]:
                ind.status = GenomeStatus.RETIRED

        # 多样性检查
        explore_ids: list[str] = []
        needs_exploration = False
        if diversity_score < 0.2 and len(mutate_ids) > 0:
            # 从突变池中取一部分强制探索
            explore_n = max(1, len(mutate_ids) // 3)
            explore_ids = mutate_ids[:explore_n]
            needs_exploration = True

        summary = (
            f"Gen {generation}: {len(elite_ids)} elite, "
            f"{len(mutate_ids)} mutate, "
            f"{len(retire_ids)} retire"
            + (f", {len(explore_ids)} explore" if needs_exploration else "")
        )

        return PopulationDecision(
            generation=generation,
            elite=elite_ids,
            mutate=mutate_ids,
            retire=retire_ids,
            explore=explore_ids,
            diversity_score=diversity_score,
            needs_exploration=needs_exploration,
            summary=summary,
        )

    def select_batch(
        self,
        generation_snapshots: list[tuple[list[GenomeIndividual], int, float]],
    ) -> list[PopulationDecision]:
        """批量选择。"""
        return [
            self.select(individuals, gen, diversity)
            for individuals, gen, diversity in generation_snapshots
        ]

    # ── 配置 ──────────────────────────────────────────────

    @property
    def elite_ratio(self) -> float:
        return self._elite_ratio

    @property
    def mutate_ratio(self) -> float:
        return self._mutate_ratio

    @property
    def retire_ratio(self) -> float:
        return self._retire_ratio

    def set_ratios(
        self,
        elite_ratio: float | None = None,
        mutate_ratio: float | None = None,
        retire_ratio: float | None = None,
    ) -> None:
        """动态调整比例。"""
        if elite_ratio is not None:
            self._elite_ratio = elite_ratio
        if mutate_ratio is not None:
            self._mutate_ratio = mutate_ratio
        if retire_ratio is not None:
            self._retire_ratio = retire_ratio

    # ── Stats ─────────────────────────────────────────────

    @property
    def select_count(self) -> int:
        return self._select_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "select_count": self._select_count,
            "elite_ratio": self._elite_ratio,
            "mutate_ratio": self._mutate_ratio,
            "retire_ratio": self._retire_ratio,
        }

    def reset(self) -> None:
        self._select_count = 0

    def __repr__(self) -> str:
        return (
            f"PopulationSelector(elite={self._elite_ratio}, "
            f"mutate={self._mutate_ratio}, "
            f"retire={self._retire_ratio})"
        )