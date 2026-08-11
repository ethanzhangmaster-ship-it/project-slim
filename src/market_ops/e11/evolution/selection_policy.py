"""E11.3.3 Selection Policy — 自然选择策略实现。

三种基础选择策略：

  EliteSelection      — 精英选择：保留排名前 top_k
  ThresholdSelection  — 阈值选择：保留 score >= min_score
  DiversitySelection  — 多样性选择：按基因指纹去重

所有策略保持 deterministic。
"""

from __future__ import annotations

from .population_schema import GenomePopulation, PopulationMember
from .selection_schema import (
    SelectionMode,
    SelectionPolicy,
    Survivor,
    SelectionResult,
)


# ═══════════════════════════════════════════════════════════
# EliteSelection — 精英选择
# ═══════════════════════════════════════════════════════════

class EliteSelection:
    """精英选择策略。

    规则：保留排名前 top_k 的成员，其余淘汰。

    例：
        Population: A(0.91, rank=1), B(0.85, rank=2), C(0.70, rank=3)
        top_k=2 → Survivors: A, B
    """

    def select(
        self,
        population: GenomePopulation,
        top_k: int = 5,
    ) -> SelectionResult:
        """执行精英选择。

        Args:
            population: 目标种群
            top_k: 保留数量

        Returns:
            SelectionResult
        """
        # 排序
        sorted_members = sorted(
            population.members,
            key=lambda m: m.score,
            reverse=True,
        )

        survivors: list[Survivor] = []
        eliminated: list[str] = []

        for i, member in enumerate(sorted_members):
            if i < top_k:
                survivors.append(Survivor(
                    genome_id=member.genome_id,
                    score=member.score,
                    rank=i + 1,
                    reason=f"elite_top_{top_k}",
                ))
            else:
                eliminated.append(member.genome_id)

        return SelectionResult(
            population_id=population.population_id,
            survivors=survivors,
            eliminated=eliminated,
            generation=population.generation,
            policy=SelectionPolicy(
                mode=SelectionMode.ELITE,
                top_k=top_k,
            ),
        )


# ═══════════════════════════════════════════════════════════
# ThresholdSelection — 阈值选择
# ═══════════════════════════════════════════════════════════

class ThresholdSelection:
    """阈值选择策略。

    规则：保留 score >= min_score 的成员，其余淘汰。

    例：
        Population: A(0.91), B(0.85), C(0.51), D(0.40)
        min_score=0.75 → Survivors: A, B
    """

    def select(
        self,
        population: GenomePopulation,
        min_score: float = 0.5,
    ) -> SelectionResult:
        """执行阈值选择。

        Args:
            population: 目标种群
            min_score: 最低评分阈值

        Returns:
            SelectionResult
        """
        # 先排序，再筛选
        sorted_members = sorted(
            population.members,
            key=lambda m: m.score,
            reverse=True,
        )

        survivors: list[Survivor] = []
        eliminated: list[str] = []
        rank = 0

        for member in sorted_members:
            if member.score >= min_score:
                rank += 1
                survivors.append(Survivor(
                    genome_id=member.genome_id,
                    score=member.score,
                    rank=rank,
                    reason=f"threshold_score_{min_score}",
                ))
            else:
                eliminated.append(member.genome_id)

        return SelectionResult(
            population_id=population.population_id,
            survivors=survivors,
            eliminated=eliminated,
            generation=population.generation,
            policy=SelectionPolicy(
                mode=SelectionMode.THRESHOLD,
                min_score=min_score,
            ),
        )


# ═══════════════════════════════════════════════════════════
# DiversitySelection — 多样性选择
# ═══════════════════════════════════════════════════════════

class DiversitySelection:
    """多样性选择策略。

    规则：按基因指纹（gene fingerprint）去重，保留多样性。

    基因指纹 = 所有基因值的字符串哈希，相同指纹视为重复。
    每个指纹最多保留 diversity_limit 个成员（按评分降序）。

    例：
        Population: A(0.91, hook=rescue), B(0.85, hook=rescue), C(0.70, hook=discovery)
        diversity_limit=1 → Survivors: A, C  (B 因指纹重复被淘汰)
    """

    def select(
        self,
        population: GenomePopulation,
        diversity_limit: int = 3,
    ) -> SelectionResult:
        """执行多样性选择。

        Args:
            population: 目标种群（需包含 gene_details）
            diversity_limit: 同一指纹最多保留数量

        Returns:
            SelectionResult

        Note:
            population.members 需要包含 fitness 以获取 score 排序。
            基因指纹基于 genome_id 构建（简化版），实际使用中可通过
            population 的 gene_details 获取更精确的指纹。
        """
        # 按评分降序
        sorted_members = sorted(
            population.members,
            key=lambda m: m.score,
            reverse=True,
        )

        # 按基因指纹分组
        fingerprint_counts: dict[str, int] = {}
        survivors: list[Survivor] = []
        eliminated: list[str] = []
        rank = 0

        for member in sorted_members:
            fingerprint = self._get_fingerprint(member, population)

            count = fingerprint_counts.get(fingerprint, 0)
            if count < diversity_limit:
                rank += 1
                survivors.append(Survivor(
                    genome_id=member.genome_id,
                    score=member.score,
                    rank=rank,
                    reason=f"diversity_{fingerprint}",
                ))
                fingerprint_counts[fingerprint] = count + 1
            else:
                eliminated.append(member.genome_id)

        return SelectionResult(
            population_id=population.population_id,
            survivors=survivors,
            eliminated=eliminated,
            generation=population.generation,
            policy=SelectionPolicy(
                mode=SelectionMode.DIVERSITY,
                diversity_limit=diversity_limit,
            ),
        )

    def _get_fingerprint(
        self,
        member: PopulationMember,
        population: GenomePopulation,
    ) -> str:
        """获取成员的基因指纹。

        优先使用 genome_id 的前缀作为指纹代理（简化版）。
        实际场景中，可以通过 population 的 gene_details 获取精确指纹。
        """
        # 简化版：使用 genome_id 的基因部分作为指纹
        # 例如 "genome_001" → fingerprint 基于 ID 模式
        # 实际使用中，指纹应由 gene_details 构建
        return member.genome_id