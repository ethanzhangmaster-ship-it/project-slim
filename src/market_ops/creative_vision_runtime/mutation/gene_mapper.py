"""E11.4.2 — Genome Gene Mapper。

升级版 Vision Pattern → Genome Gene 映射表。

将 E11.4.1 的中间基因名映射到 V5 Genome 标准基因名。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GeneMapping:
    """基因映射条目。

    Attributes:
        genome_gene:    V5 Genome 标准基因名
        default_range:  默认值域 [min, max]
        default_operator: 默认操作符
        description:    基因描述
    """

    genome_gene: str
    default_range: tuple[float, float] = (0.0, 1.0)
    default_operator: str = "increase"
    description: str = ""


# ── Pattern → Genome Gene Mapping ────────────────────────

PATTERN_TO_GENOME: dict[str, GeneMapping] = {
    "high_contrast_opening": GeneMapping(
        genome_gene="hook_contrast",
        default_range=(0.0, 1.0),
        default_operator="increase",
        description="Visual contrast in the opening hook scene",
    ),
    "bright_visual": GeneMapping(
        genome_gene="color_brightness",
        default_range=(0.0, 1.0),
        default_operator="increase",
        description="Overall brightness of the creative",
    ),
    "dark_visual": GeneMapping(
        genome_gene="color_brightness",
        default_range=(0.0, 1.0),
        default_operator="increase",
        description="Overall brightness of the creative",
    ),
    "high_saturation": GeneMapping(
        genome_gene="color_saturation",
        default_range=(0.0, 1.0),
        default_operator="increase",
        description="Color saturation level",
    ),
    "clean_composition": GeneMapping(
        genome_gene="object_density",
        default_range=(0.0, 1.0),
        default_operator="set",
        description="Number and density of visual subjects",
    ),
    "complex_scene": GeneMapping(
        genome_gene="object_density",
        default_range=(0.0, 1.0),
        default_operator="decrease",
        description="Number and density of visual subjects",
    ),
    "fast_visual_change": GeneMapping(
        genome_gene="transition_speed",
        default_range=(0.0, 1.0),
        default_operator="increase",
        description="Speed of visual transitions between scenes",
    ),
    "rising_brightness": GeneMapping(
        genome_gene="reward_reveal_curve",
        default_range=(0.0, 1.0),
        default_operator="increase",
        description="Curve of brightness increase toward reward reveal",
    ),
}

# ── E11.4.1 intermediate gene → Genome gene ──────────────

INTERMEDIATE_TO_GENOME: dict[str, str] = {
    "hook_contrast": "hook_contrast",
    "brightness": "color_brightness",
    "color_palette": "color_saturation",
    "object_count": "object_density",
    "scene_transition": "transition_speed",
}


class GeneMapper:
    """Genome Gene 映射器。

    将 Vision Pattern 或 E11.4.1 中间基因名映射到 V5 Genome 标准基因名。
    """

    def __init__(self) -> None:
        self._pattern_to_genome = dict(PATTERN_TO_GENOME)
        self._intermediate_to_genome = dict(INTERMEDIATE_TO_GENOME)

    def pattern_to_genome_gene(self, pattern_name: str) -> str | None:
        """Vision Pattern → Genome Gene。"""
        mapping = self._pattern_to_genome.get(pattern_name)
        return mapping.genome_gene if mapping else None

    def intermediate_to_genome_gene(self, intermediate_gene: str) -> str | None:
        """E11.4.1 中间基因名 → Genome Gene。"""
        return self._intermediate_to_genome.get(intermediate_gene)

    def get_operator_for_pattern(self, pattern_name: str) -> str:
        """获取模式对应的默认操作符。"""
        mapping = self._pattern_to_genome.get(pattern_name)
        return mapping.default_operator if mapping else "increase"

    def get_range_for_pattern(self, pattern_name: str) -> tuple[float, float]:
        """获取模式对应的值域。"""
        mapping = self._pattern_to_genome.get(pattern_name)
        return mapping.default_range if mapping else (0.0, 1.0)

    def get_range_for_gene(self, genome_gene: str) -> tuple[float, float]:
        """获取 Genome 基因的值域。"""
        for mapping in self._pattern_to_genome.values():
            if mapping.genome_gene == genome_gene:
                return mapping.default_range
        return (0.0, 1.0)

    def get_description(self, pattern_name: str) -> str:
        """获取模式描述。"""
        mapping = self._pattern_to_genome.get(pattern_name)
        return mapping.description if mapping else ""

    def list_patterns(self) -> list[str]:
        return list(self._pattern_to_genome.keys())

    def list_genome_genes(self) -> list[str]:
        genes: set[str] = set()
        for m in self._pattern_to_genome.values():
            genes.add(m.genome_gene)
        return sorted(genes)

    def __repr__(self) -> str:
        return (
            f"GeneMapper(patterns={len(self._pattern_to_genome)}, "
            f"genes={len(self.list_genome_genes())})"
        )