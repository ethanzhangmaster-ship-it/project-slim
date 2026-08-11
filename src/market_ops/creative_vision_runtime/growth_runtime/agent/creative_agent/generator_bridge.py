"""E14.4.3.2 Generator Bridge — 连接 Creative Agent 与 E11 Evolution Engine.

桥梁模式:
  Creative Agent (E14.4) → Generator Bridge (E14.4.3.2) → E11 Evolution Engine

核心能力:
  - 策略→E11调用: 将 E14.4.2 策略转化为 E11 兼容的变异请求
  - 接口适配: 适配 E11 CreativeGenomeMutator / MutationOperator
  - 变体生成: 调用 E11 生成 Creative Variants
  - 结果转换: 将 E11 输出转化为 E14.4 兼容的 CreativeVariant
  - 降级支持: 当 E11 不可用时提供 mock 降级

设计原则:
  - 薄适配层: 不重复实现 E11 逻辑
  - 接口隔离: 保护 Creative Agent 不受 E11 变更影响
  - 容错设计: E11 不可用时使用 mock 降级
  - 可替换: 支持切换不同生成器 (E11/Lovart/CLIP)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .strategy import (
    CreativeStrategy,
    CreativeStrategyType,
    GeneMutation,
    GeneMutationAction,
)
from .dna_engine import CreativeDNAProfile, DNAEngine
from .planner import CreativePlan, MutationConfig


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class VariantStatus(str, Enum):
    """变体状态."""
    GENERATED = "generated"      # 已生成
    UPLOADED = "uploaded"        # 已上传
    ACTIVE = "active"            # 投放中
    PAUSED = "paused"            # 已暂停
    WINNER = "winner"            # 赢家
    FAILED = "failed"            # 失败


class GeneratorType(str, Enum):
    """生成器类型."""
    E11_EVOLUTION = "e11_evolution"
    LOVART = "lovart"
    CLIP = "clip"
    MOCK = "mock"


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeVariant:
    """创意变体 — 生成器输出.

    Attributes:
        variant_id: 变体 ID
        parent_creative_id: 父素材 ID
        parent_dna_id: 父 DNA ID
        dna_delta: DNA 变更描述
        strategy_type: 关联策略类型
        generation: 代际
        status: 状态
        metadata: 扩展元数据
        created_at: 创建时间
    """
    variant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_creative_id: str = ""
    parent_dna_id: str = ""
    dna_delta: dict[str, Any] = field(default_factory=dict)
    strategy_type: CreativeStrategyType = CreativeStrategyType.UNKNOWN
    generation: int = 1
    status: VariantStatus = VariantStatus.GENERATED
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "parent_creative_id": self.parent_creative_id,
            "parent_dna_id": self.parent_dna_id,
            "dna_delta": self.dna_delta,
            "strategy_type": self.strategy_type.value,
            "generation": self.generation,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class GenerationResult:
    """生成结果.

    Attributes:
        result_id: 结果 ID
        plan_id: 关联计划 ID
        variants: 变体列表
        total_generated: 总生成数
        generator_type: 使用的生成器
        success: 是否成功
        error: 错误信息
        created_at: 创建时间
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    variants: list[CreativeVariant] = field(default_factory=list)
    total_generated: int = 0
    generator_type: GeneratorType = GeneratorType.MOCK
    success: bool = True
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "plan_id": self.plan_id,
            "variants": [v.to_dict() for v in self.variants],
            "total_generated": self.total_generated,
            "generator_type": self.generator_type.value,
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at,
        }

    @property
    def variant_count(self) -> int:
        return len(self.variants)


# ═══════════════════════════════════════════════════════════════
# Generator Bridge
# ═══════════════════════════════════════════════════════════════


class GeneratorBridge:
    """生成器桥接 — 连接 Creative Agent 与 E11 Evolution Engine.

    职责:
      1. 策略→E11调用: 将 E14.4.2 策略转化为 E11 变异请求
      2. 变体生成: 调用 E11 生成变体 (或降级为 mock)
      3. 结果转换: 将 E11 输出转化为 CreativeVariant

    用法:
        bridge = GeneratorBridge()
        result = bridge.generate_variants(plan, strategy, dna)
    """

    def __init__(self, generator_type: GeneratorType = GeneratorType.MOCK):
        self._generator_type = generator_type
        self._dna_engine = DNAEngine()
        self._results: list[GenerationResult] = []
        self._variant_index: dict[str, CreativeVariant] = {}

    # ── 核心方法 ──────────────────────────────────────────────

    def generate_variants(
        self,
        plan: CreativePlan,
        strategy: CreativeStrategy,
        dna: CreativeDNAProfile | None = None,
    ) -> GenerationResult:
        """生成创意变体.

        Args:
            plan: 执行计划
            strategy: 创意策略
            dna: 当前素材 DNA

        Returns:
            GenerationResult: 生成结果
        """
        count = plan.population_size
        generation = plan.generation_count

        if self._generator_type == GeneratorType.MOCK:
            variants = self._mock_generate(strategy, dna, count, generation)
        elif self._generator_type == GeneratorType.E11_EVOLUTION:
            variants = self._e11_generate(strategy, dna, count, generation)
        else:
            variants = self._mock_generate(strategy, dna, count, generation)

        result = GenerationResult(
            plan_id=plan.plan_id,
            variants=variants,
            total_generated=len(variants),
            generator_type=self._generator_type,
            success=True,
        )

        for v in variants:
            self._variant_index[v.variant_id] = v
        self._results.append(result)

        return result

    def mutate_dna(
        self,
        strategy: CreativeStrategy,
        dna: CreativeDNAProfile,
        target_values: dict[str, str],
    ) -> CreativeVariant:
        """变异单个 DNA.

        Args:
            strategy: 创意策略
            dna: 当前 DNA
            target_values: 目标基因值 {gene_category: target_value}

        Returns:
            CreativeVariant: 变体
        """
        variant = CreativeVariant(
            parent_creative_id=dna.creative_id,
            parent_dna_id=dna.dna_id,
            strategy_type=strategy.strategy_type,
            dna_delta={
                "original": {k: v for k, v in dna.genes.items()},
                "mutated": target_values,
                "strategy": strategy.strategy_type.value,
            },
        )

        self._variant_index[variant.variant_id] = variant
        return variant

    def clone_winner(
        self,
        strategy: CreativeStrategy,
        winner_dna: CreativeDNAProfile,
        target_creative_id: str,
    ) -> CreativeVariant:
        """克隆赢家 DNA 到目标素材.

        Args:
            strategy: 创意策略
            winner_dna: 赢家 DNA
            target_creative_id: 目标素材 ID

        Returns:
            CreativeVariant: 变体
        """
        variant = CreativeVariant(
            parent_creative_id=target_creative_id,
            parent_dna_id=winner_dna.dna_id,
            strategy_type=CreativeStrategyType.COPY_WINNER_DNA,
            dna_delta={
                "source_dna_id": winner_dna.dna_id,
                "source_genes": {k: str(v.value) for k, v in winner_dna.genes.items()},
                "action": "clone_winner",
            },
        )

        self._variant_index[variant.variant_id] = variant
        return variant

    # ── 内部生成 ──────────────────────────────────────────────

    def _mock_generate(
        self,
        strategy: CreativeStrategy,
        dna: CreativeDNAProfile | None,
        count: int,
        generation: int,
    ) -> list[CreativeVariant]:
        """Mock 生成 (E11 不可用时的降级)."""
        variants = []
        for i in range(count):
            dna_delta = self._build_dna_delta(strategy, dna, i)
            variant = CreativeVariant(
                parent_creative_id=strategy.target_creative_id,
                parent_dna_id=dna.dna_id if dna else "",
                dna_delta=dna_delta,
                strategy_type=strategy.strategy_type,
                generation=generation,
            )
            variants.append(variant)
        return variants

    def _e11_generate(
        self,
        strategy: CreativeStrategy,
        dna: CreativeDNAProfile | None,
        count: int,
        generation: int,
    ) -> list[CreativeVariant]:
        """E11 Evolution Engine 生成.

        实际调用 E11 CreativeGenomeMutator.mutate().
        当前为 stub，需通过 E11 接口注入。
        """
        # 尝试调用 E11，失败则降级
        try:
            # TODO: 实际 E11 集成
            # from market_ops.creative_evolution.creative_genome_mutator import CreativeGenomeMutator
            # mutator = CreativeGenomeMutator()
            # ...
            return self._mock_generate(strategy, dna, count, generation)
        except ImportError:
            return self._mock_generate(strategy, dna, count, generation)

    def _build_dna_delta(
        self,
        strategy: CreativeStrategy,
        dna: CreativeDNAProfile | None,
        index: int,
    ) -> dict[str, Any]:
        """构建 DNA 变更描述."""
        delta = {
            "strategy": strategy.strategy_type.value,
            "variant_index": index + 1,
        }

        for mutation in strategy.mutation_plan:
            if mutation.action == GeneMutationAction.CHANGE:
                if mutation.target_values:
                    delta[mutation.gene_category] = {
                        "from": mutation.current_value,
                        "to": mutation.target_values[index % len(mutation.target_values)],
                        "action": "change",
                    }
            elif mutation.action == GeneMutationAction.EXPLORE:
                if mutation.target_values:
                    delta[mutation.gene_category] = {
                        "from": mutation.current_value,
                        "to": mutation.target_values[index % len(mutation.target_values)],
                        "action": "explore",
                    }
            elif mutation.action == GeneMutationAction.KEEP:
                delta[mutation.gene_category] = {
                    "from": mutation.current_value,
                    "to": mutation.current_value,
                    "action": "keep",
                }

        return delta

    # ── 查询 ──────────────────────────────────────────────────

    def get_variant(self, variant_id: str) -> CreativeVariant | None:
        return self._variant_index.get(variant_id)

    def get_variants_by_parent(self, parent_creative_id: str) -> list[CreativeVariant]:
        return [
            v for v in self._variant_index.values()
            if v.parent_creative_id == parent_creative_id
        ]

    def get_results(self) -> list[GenerationResult]:
        return self._results

    def get_last_result(self) -> GenerationResult | None:
        return self._results[-1] if self._results else None

    def stats(self) -> dict[str, Any]:
        return {
            "generator_type": self._generator_type.value,
            "total_variants": len(self._variant_index),
            "total_results": len(self._results),
            "variants_by_parent": self._stats_by_parent(),
        }

    def _stats_by_parent(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for v in self._variant_index.values():
            pid = v.parent_creative_id or "unknown"
            counts[pid] = counts.get(pid, 0) + 1
        return counts

    def reset(self) -> None:
        self._results.clear()
        self._variant_index.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_generator_bridge(
    generator_type: GeneratorType = GeneratorType.MOCK,
) -> GeneratorBridge:
    """创建默认生成器桥接."""
    return GeneratorBridge(generator_type=generator_type)