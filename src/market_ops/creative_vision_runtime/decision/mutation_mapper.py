"""E11.4.2 — Vision Mutation Mapper。

VisionPattern → Mutation Gene 映射表。

连接 E11.3.5 Vision Intelligence 和 V5 Creative Mutation Engine。
"""

from __future__ import annotations

from typing import Any

from .models import MutationInstruction


# ── Pattern → Gene Mapping ──────────────────────────────

PATTERN_TO_GENE: dict[str, str] = {
    "high_contrast_opening": "hook_contrast",
    "bright_visual": "brightness",
    "dark_visual": "brightness",
    "high_saturation": "color_palette",
    "clean_composition": "object_count",
    "complex_scene": "object_count",
    "fast_visual_change": "scene_transition",
    "rising_brightness": "scene_transition",
}

# ── Gene → Operator Mapping ─────────────────────────────

GENE_TO_OPERATOR: dict[str, str] = {
    "hook_contrast": "increase",
    "brightness": "increase",
    "color_palette": "increase",
    "object_count": "set",
    "scene_transition": "increase",
}

# ── Gene → Description Template ─────────────────────────

GENE_DESCRIPTIONS: dict[str, str] = {
    "hook_contrast": "Visual contrast in opening scene",
    "brightness": "Overall brightness level",
    "color_palette": "Color saturation and palette",
    "object_count": "Number of visual subjects",
    "scene_transition": "Speed of visual transitions",
}


class MutationMapper:
    """Vision Pattern → Mutation Instruction 映射器。

    将 E11.3.5 检测到的视觉模式转换为 V5 Mutation Engine 可执行的突变指令。
    """

    def __init__(self) -> None:
        self._pattern_to_gene = dict(PATTERN_TO_GENE)
        self._gene_operators = dict(GENE_TO_OPERATOR)
        self._gene_descriptions = dict(GENE_DESCRIPTIONS)

    def map_to_mutation(
        self,
        pattern_name: str,
        confidence: float,
        current_value: float = 0.0,
    ) -> MutationInstruction | None:
        """将单个视觉模式映射为突变指令。

        Args:
            pattern_name:  视觉模式名称
            confidence:    模式置信度
            current_value: 当前特征值

        Returns:
            MutationInstruction 或 None（无法映射时）
        """
        gene = self._pattern_to_gene.get(pattern_name)
        if gene is None:
            return None

        operator = self._gene_operators.get(gene, "increase")
        magnitude = self._compute_magnitude(confidence, current_value)

        target_value = self._compute_target(current_value, magnitude, operator)

        return MutationInstruction(
            target_gene=gene,
            operator=operator,
            magnitude=round(magnitude, 3),
            current_value=current_value,
            target_value=round(target_value, 3),
            source_pattern=pattern_name,
            description=self._gene_descriptions.get(gene, gene),
        )

    def map_batch(
        self,
        pattern_names: list[str],
        confidences: dict[str, float] | None = None,
        current_values: dict[str, float] | None = None,
    ) -> list[MutationInstruction]:
        """批量映射多个视觉模式。

        Args:
            pattern_names:  模式名称列表
            confidences:    模式名 → 置信度
            current_values: 模式名 → 当前值

        Returns:
            MutationInstruction 列表
        """
        confidences = confidences or {}
        current_values = current_values or {}

        instructions: list[MutationInstruction] = []
        for name in pattern_names:
            conf = confidences.get(name, 0.5)
            val = current_values.get(name, 0.0)
            instruction = self.map_to_mutation(name, conf, val)
            if instruction is not None:
                instructions.append(instruction)

        return instructions

    def get_gene(self, pattern_name: str) -> str | None:
        """获取模式对应的基因名。"""
        return self._pattern_to_gene.get(pattern_name)

    def get_operator(self, gene: str) -> str:
        """获取基因对应的默认操作符。"""
        return self._gene_operators.get(gene, "increase")

    def list_mappable_patterns(self) -> list[str]:
        """列出所有可映射的模式名。"""
        return list(self._pattern_to_gene.keys())

    def list_genes(self) -> list[str]:
        """列出所有可操作的基因。"""
        return list(set(self._pattern_to_gene.values()))

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _compute_magnitude(confidence: float, current_value: float) -> float:
        """计算变异幅度。

        高置信度 → 幅度大
        当前值低 → 幅度大（有提升空间）
        """
        base = confidence * 0.3  # 最大 0.3
        if current_value < 0.5:
            base += 0.1  # 低值加码
        return min(base, 0.4)

    @staticmethod
    def _compute_target(
        current: float, magnitude: float, operator: str
    ) -> float:
        if operator == "increase":
            return min(current + magnitude, 1.0)
        if operator == "decrease":
            return max(current - magnitude, 0.0)
        if operator == "set":
            return max(magnitude, current)
        return current

    def __repr__(self) -> str:
        return (
            f"MutationMapper(patterns={len(self._pattern_to_gene)}, "
            f"genes={len(self.list_genes())})"
        )