"""E11.4.2 Generation Manager — 代数管理器。

管理多代进化循环中的世代流转：

  create_generation()  — 创建新代（从当前种群）
  next_generation()    — 推进到下一代（从幸存者）
  complete_generation() — 记录代完成信息

数据流：
  Population → GenerationManager → GenerationRecord
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .generation_schema import GenerationStatus, GenerationRecord
from .population_schema import GenomePopulation


class GenerationManager:
    """代数管理器。

    负责创建、推进和完成每一代进化。

    Usage:
        manager = GenerationManager()
        gen = manager.create_generation(population, generation=1)
        # ... 执行进化操作 ...
        manager.complete_generation(gen, pop)
        next_gen = manager.next_generation(survivors_pop, generation=2)
    """

    def __init__(self) -> None:
        self._generation_counter: int = 0

    # ── 创建 ──────────────────────────────────────────

    def create_generation(
        self,
        population: GenomePopulation,
        generation: int | None = None,
    ) -> GenerationRecord:
        """创建新代记录。

        Args:
            population: 当前种群
            generation: 代数编号（默认使用 population.generation）

        Returns:
            GenerationRecord
        """
        gen = generation if generation is not None else population.generation
        self._generation_counter += 1

        record = GenerationRecord(
            generation=gen,
            population_id=population.population_id,
            status=GenerationStatus.CREATED,
        )
        return record

    def next_generation(
        self,
        survivors: GenomePopulation,
        generation: int | None = None,
    ) -> GenerationRecord:
        """从幸存者种群创建下一代。

        Args:
            survivors: 上一代筛选后的幸存者种群
            generation: 下一代编号（默认递增）

        Returns:
            新 GenerationRecord
        """
        gen = generation if generation is not None else survivors.generation + 1

        record = GenerationRecord(
            generation=gen,
            population_id=survivors.population_id,
            status=GenerationStatus.CREATED,
        )
        return record

    # ── 完成 ──────────────────────────────────────────

    def complete_generation(
        self,
        record: GenerationRecord,
        population: GenomePopulation,
    ) -> GenerationRecord:
        """记录代完成信息。

        从种群中提取 best_score, best_genome_id, 等统计信息。

        Args:
            record: 要完成的 GenerationRecord
            population: 当前种群

        Returns:
            更新后的 GenerationRecord
        """
        best = population.best_member
        record.best_genome_id = best.genome_id if best else ""
        record.best_score = best.score if best else 0.0
        record.avg_score = population.avg_score
        record.survivor_count = population.size
        record.complete()
        return record

    def fail_generation(
        self,
        record: GenerationRecord,
        error_message: str = "",
    ) -> GenerationRecord:
        """标记代为失败。

        Args:
            record: 要标记的 GenerationRecord
            error_message: 错误信息

        Returns:
            更新后的 GenerationRecord
        """
        record.fail()
        return record

    # ── 查询 ──────────────────────────────────────────

    @property
    def generation_count(self) -> int:
        """已创建的代数计数。"""
        return self._generation_counter

    def reset(self) -> None:
        """重置代数计数器。"""
        self._generation_counter = 0