"""E11.8.2 — Mutation Mapper。

核心：Strategy → 具体 Gene 突变操作。

将 EvolutionStrategy 的 StrategyType + MutationFocus 映射为：
  - MutationOperation(s)：操作类型
  - MutationParameter(s)：具体基因修改参数

映射规则：
  EXPLOIT_WINNER → MODIFY/CLONE, small intensity
  FIX_FAILURE    → MODIFY + CROSSOVER, large intensity
  DIVERSIFY      → CREATE, radical intensity
  SCALE_SUCCESS  → CLONE + MODIFY, medium intensity
  EXPLORE_NEW    → CREATE, medium intensity
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import (
    EvolutionStrategy,
    Intensity,
    MutationFocus,
    StrategyType,
)
from .models import (
    MutationOperation,
    MutationParameter,
)

logger = logging.getLogger(__name__)

# 强度映射
INTENSITY_MAP: dict[Intensity, float] = {
    Intensity.SMALL: 0.2,
    Intensity.MEDIUM: 0.4,
    Intensity.LARGE: 0.7,
    Intensity.RADICAL: 0.9,
}

# MutationFocus → 目标基因列表
FOCUS_GENES: dict[MutationFocus, list[str]] = {
    MutationFocus.HOOK: ["hook_pattern", "opening_scene", "first_3_seconds"],
    MutationFocus.VISUAL: ["visual_style", "color_palette", "composition"],
    MutationFocus.GAMEPLAY: ["gameplay_display", "difficulty_curve", "progression"],
    MutationFocus.REWARD: ["reward_timing", "reward_amount", "incentive_type"],
    MutationFocus.PACING: ["pacing_rhythm", "tension_curve", "duration"],
    MutationFocus.FULL: [
        "hook_pattern", "opening_scene", "visual_style",
        "gameplay_display", "reward_timing", "pacing_rhythm",
        "difficulty_curve", "color_palette",
    ],
}

# 操作描述模板
OPERATION_DESCRIPTIONS: dict[StrategyType, dict[str, str]] = {
    StrategyType.EXPLOIT_WINNER: {
        MutationOperation.MODIFY.value: "Fine-tune {focus} genes to preserve winner quality",
        MutationOperation.CLONE.value: "Clone winner with minor {focus} variations",
    },
    StrategyType.FIX_FAILURE: {
        MutationOperation.MODIFY.value: "Overhaul {focus} genes to fix failure pattern",
        MutationOperation.CROSSOVER.value: "Cross with successful genome to introduce winning genes",
    },
    StrategyType.DIVERSIFY: {
        MutationOperation.CREATE.value: "Create new genome with diverse {focus} gene combinations",
    },
    StrategyType.SCALE_SUCCESS: {
        MutationOperation.CLONE.value: "Clone successful genome with {focus} optimization",
        MutationOperation.MODIFY.value: "Refine {focus} genes for scaling",
    },
    StrategyType.EXPLORE_NEW: {
        MutationOperation.CREATE.value: "Create new genome exploring {focus} direction",
        MutationOperation.MODIFY.value: "Experiment with {focus} gene variations",
    },
}


class MutationMapper:
    """突变映射器。

    将 EvolutionStrategy 转换为 MutationOperation + MutationParameter 列表。

    Attributes:
        intensity_map: 强度数值映射
        focus_genes:   聚焦维度 → 基因列表
        descriptions:  操作描述模板
    """

    def __init__(
        self,
        intensity_map: dict[Intensity, float] | None = None,
        focus_genes: dict[MutationFocus, list[str]] | None = None,
        descriptions: dict[StrategyType, dict[str, str]] | None = None,
    ) -> None:
        self._intensity_map = intensity_map or INTENSITY_MAP
        self._focus_genes = focus_genes or FOCUS_GENES
        self._descriptions = descriptions or OPERATION_DESCRIPTIONS

    # ── 主入口 ──────────────────────────────────────────

    def map(self, strategy: EvolutionStrategy) -> dict[str, Any]:
        """将 EvolutionStrategy 映射为操作和参数。

        Args:
            strategy: EvolutionStrategy

        Returns:
            {
                "operations": list[MutationOperation],
                "mutations": list[MutationParameter],
            }
        """
        handler = self._get_handler(strategy.strategy_type)
        return handler(strategy)

    def _get_handler(self, strategy_type: StrategyType):
        """根据策略类型获取处理函数。"""
        handlers = {
            StrategyType.EXPLOIT_WINNER: self._map_exploit_winner,
            StrategyType.FIX_FAILURE: self._map_fix_failure,
            StrategyType.DIVERSIFY: self._map_diversify,
            StrategyType.SCALE_SUCCESS: self._map_scale_success,
            StrategyType.EXPLORE_NEW: self._map_explore_new,
        }
        return handlers.get(strategy_type, self._map_explore_new)

    # ── 策略映射实现 ─────────────────────────────────────

    def _map_exploit_winner(self, strategy: EvolutionStrategy) -> dict[str, Any]:
        """EXPLOIT_WINNER → MODIFY + CLONE, small intensity。

        保持赢家稳定，只做小幅变体。
        """
        intensity = self._intensity_map.get(strategy.intensity, 0.2)
        focus = strategy.mutation_focus
        genes = self._focus_genes.get(focus, [focus.value])

        operations = [MutationOperation.MODIFY, MutationOperation.CLONE]
        mutations = self._build_mutations(
            focus=focus,
            intensity=intensity,
            genes=genes,
            strategy_type=StrategyType.EXPLOIT_WINNER,
            operation=MutationOperation.MODIFY,
        )

        return {
            "operations": operations,
            "mutations": mutations,
        }

    def _map_fix_failure(self, strategy: EvolutionStrategy) -> dict[str, Any]:
        """FIX_FAILURE → MODIFY + CROSSOVER, large intensity。

        大幅修改 + 交叉引入成功基因。
        """
        intensity = self._intensity_map.get(strategy.intensity, 0.7)
        focus = strategy.mutation_focus
        if focus == MutationFocus.HOOK or focus == MutationFocus.FULL:
            focus = MutationFocus.FULL  # 失败修复默认全维度
        genes = self._focus_genes.get(focus, [focus.value])

        operations = [MutationOperation.MODIFY, MutationOperation.CROSSOVER]
        mutations = self._build_mutations(
            focus=focus,
            intensity=intensity,
            genes=genes,
            strategy_type=StrategyType.FIX_FAILURE,
            operation=MutationOperation.MODIFY,
        )

        return {
            "operations": operations,
            "mutations": mutations,
        }

    def _map_diversify(self, strategy: EvolutionStrategy) -> dict[str, Any]:
        """DIVERSIFY → CREATE, radical intensity。

        种群塌缩 → 创建全新基因组。
        """
        intensity = self._intensity_map.get(strategy.intensity, 0.9)
        focus = MutationFocus.FULL
        genes = self._focus_genes.get(focus, [])

        operations = [MutationOperation.CREATE]
        mutations = self._build_mutations(
            focus=focus,
            intensity=intensity,
            genes=genes,
            strategy_type=StrategyType.DIVERSIFY,
            operation=MutationOperation.CREATE,
        )

        return {
            "operations": operations,
            "mutations": mutations,
        }

    def _map_scale_success(self, strategy: EvolutionStrategy) -> dict[str, Any]:
        """SCALE_SUCCESS → CLONE + MODIFY, medium intensity。

        克隆赢家 + 针对性优化。
        """
        intensity = self._intensity_map.get(strategy.intensity, 0.4)
        focus = strategy.mutation_focus
        genes = self._focus_genes.get(focus, [focus.value])

        operations = [MutationOperation.CLONE, MutationOperation.MODIFY]
        mutations = self._build_mutations(
            focus=focus,
            intensity=intensity,
            genes=genes,
            strategy_type=StrategyType.SCALE_SUCCESS,
            operation=MutationOperation.MODIFY,
        )

        return {
            "operations": operations,
            "mutations": mutations,
        }

    def _map_explore_new(self, strategy: EvolutionStrategy) -> dict[str, Any]:
        """EXPLORE_NEW → CREATE, medium intensity。

        探索新方向。
        """
        intensity = self._intensity_map.get(strategy.intensity, 0.4)
        focus = strategy.mutation_focus
        genes = self._focus_genes.get(focus, [focus.value])

        operations = [MutationOperation.CREATE]
        mutations = self._build_mutations(
            focus=focus,
            intensity=intensity,
            genes=genes,
            strategy_type=StrategyType.EXPLORE_NEW,
            operation=MutationOperation.CREATE,
        )

        return {
            "operations": operations,
            "mutations": mutations,
        }

    # ── 辅助方法 ─────────────────────────────────────────

    def _build_mutations(
        self,
        focus: MutationFocus,
        intensity: float,
        genes: list[str],
        strategy_type: StrategyType,
        operation: MutationOperation,
    ) -> list[MutationParameter]:
        """为每个目标基因构建 MutationParameter。"""
        templates = self._descriptions.get(strategy_type, {})
        template = templates.get(operation.value, "Modify {focus} genes")

        mutations: list[MutationParameter] = []
        for gene in genes:
            description = template.format(focus=focus.value)
            mutations.append(
                MutationParameter(
                    focus=focus.value,
                    intensity=intensity,
                    target_gene=gene,
                    description=description,
                    metadata={
                        "strategy_type": strategy_type.value,
                        "operation": operation.value,
                    },
                )
            )

        return mutations

    def __repr__(self) -> str:
        return f"MutationMapper()"