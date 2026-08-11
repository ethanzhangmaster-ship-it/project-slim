"""E11.1 DNA Mapper — 将历史 Winner DNA 转换为 CreativeGenome。

连接现有系统：
  Winner DNA (creative_dna / winner_analysis)
      ↓
  CreativeGenome (E11 进化体系)

支持从多种来源格式映射：
  - CreativeDnaItem (creative_dna.py)
  - WinnerPattern (creative_evolution/schemas.py)
  - 原始 dict 格式
"""

from __future__ import annotations

from typing import Any

from .schema import CreativeGenome, GenomeLineage, GENE_SLOTS
from .exceptions import DNAMappingError


class DNAMapper:
    """DNA → Genome 转换器。

    将现有系统中的 Winner DNA 数据结构映射为 E11 CreativeGenome。

    Usage:
        mapper = DNAMapper()
        genome = mapper.map_winner_dna(
            dna={"hook": "rescue", "visual": "fantasy", ...},
            source_id="winner_001",
        )
    """

    # 字段映射表：源字段 → (基因槽位, 子字段, 默认值)
    # 覆盖 creative_dna.py 的 CreativeDnaItem / FIELDS
    _FIELD_MAPPING: dict[str, tuple[str, str, Any]] = {
        # hook 维度
        "hook_type": ("hook", "type", ""),
        "hook": ("hook", "type", ""),
        "first_3s_density": ("hook", "strength", 0.5),
        # visual 维度
        "visual_style": ("visual", "style", ""),
        "fantasy": ("visual", "style", ""),
        "asset_type": ("visual", "composition", ""),
        "video_structure": ("visual", "composition", ""),
        "composition": ("visual", "composition", ""),
        # reward 维度
        "reward": ("reward", "type", ""),
        "cta_strength": ("reward", "intensity", 0.5),
        "reward_type": ("reward", "type", ""),
        # emotion 维度
        "emotion": ("emotion", "primary", ""),
        "pace": ("emotion", "primary", ""),
        "conflict_strength": ("emotion", "primary", ""),
        # gameplay 维度
        "mechanism": ("gameplay", "mechanic", ""),
        "gameplay": ("gameplay", "mechanic", ""),
        "ui_type": ("gameplay", "mechanic", ""),
    }

    # 性能字段映射
    _FITNESS_MAPPING: dict[str, str] = {
        "roi": "roas_d7",
        "roas": "roas_d7",
        "roas_d7": "roas_d7",
        "ctr": "ctr",
        "cpi": "cpi",
        "spend": "spend",
        "revenue": "revenue",
        "installs": "installs",
        "predicted_scalability": "predicted_scalability",
    }

    def __init__(self) -> None:
        self._mapped_count: int = 0

    # ── 核心映射 ──────────────────────────────────────

    def map_winner_dna(
        self,
        dna: dict[str, Any],
        source_id: str = "",
        genome_id: str | None = None,
        label_confidence: float = 0.0,
    ) -> CreativeGenome:
        """将 Winner DNA 字典映射为 CreativeGenome。

        Args:
            dna: Winner DNA 数据字典
            source_id: 来源 ID（如 winner_001）
            genome_id: 目标 Genome ID（默认自动生成）
            label_confidence: DNA 标签置信度

        Returns:
            CreativeGenome 实例

        Raises:
            DNAMappingError: 映射失败
        """
        if not dna:
            raise DNAMappingError("Empty DNA data, cannot map.", source_id=source_id)

        # 提取基因
        genes = self._extract_genes(dna)
        if not genes:
            raise DNAMappingError(
                "No valid genes extracted from DNA data.",
                source_id=source_id,
            )

        # 提取 fitness
        fitness = self._extract_fitness(dna)

        # 生成 ID
        gid = genome_id or f"genome_{source_id}" if source_id else "genome_unknown"

        # 构建 lineage
        lineage = GenomeLineage(
            source=source_id,
            created_by="dna_mapper",
        )

        self._mapped_count += 1

        return CreativeGenome(
            genome_id=gid,
            parent_id=None,
            generation=0,
            genes=genes,
            fitness=fitness,
            lineage=lineage,
        )

    def map_from_creative_dna_item(
        self,
        dna_item: Any,
        genome_id: str | None = None,
    ) -> CreativeGenome:
        """从 CreativeDnaItem 对象映射。

        Args:
            dna_item: CreativeDnaItem 实例或兼容对象
            genome_id: 目标 Genome ID

        Returns:
            CreativeGenome
        """
        # 尝试转为 dict
        if hasattr(dna_item, "__dict__"):
            dna_dict = {k: v for k, v in dna_item.__dict__.items() if not k.startswith("_")}
        elif hasattr(dna_item, "to_dict"):
            dna_dict = dna_item.to_dict()
        elif isinstance(dna_item, dict):
            dna_dict = dna_item
        else:
            raise DNAMappingError(
                f"Unsupported DNA item type: {type(dna_item).__name__}",
            )

        source_id = dna_dict.get("creative_id", dna_dict.get("creative_name", ""))
        confidence = dna_dict.get("label_confidence", 0.0)

        return self.map_winner_dna(
            dna=dna_dict,
            source_id=source_id,
            genome_id=genome_id,
            label_confidence=confidence,
        )

    def map_batch(
        self,
        dna_list: list[dict[str, Any]],
        prefix: str = "genome",
    ) -> list[CreativeGenome]:
        """批量映射 DNA 列表。

        Args:
            dna_list: DNA 字典列表
            prefix: Genome ID 前缀

        Returns:
            CreativeGenome 列表
        """
        genomes: list[CreativeGenome] = []
        for i, dna in enumerate(dna_list):
            source_id = dna.get("creative_id", f"{prefix}_{i}")
            genome_id = f"{prefix}_{i:03d}"
            try:
                genome = self.map_winner_dna(dna, source_id=source_id, genome_id=genome_id)
                genomes.append(genome)
            except DNAMappingError:
                continue
        return genomes

    # ── 内部方法 ──────────────────────────────────────

    def _extract_genes(self, dna: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """从 DNA 字典提取基因槽位。"""
        genes: dict[str, dict[str, Any]] = {
            slot: {} for slot in GENE_SLOTS
        }

        for src_field, (slot, sub_field, default) in self._FIELD_MAPPING.items():
            if src_field in dna and dna[src_field] not in (None, "", 0.0):
                genes[slot][sub_field] = dna[src_field]

        # 填充默认值
        for slot, sub_fields in GENE_SLOTS.items():
            for sf in sub_fields:
                if sf not in genes[slot]:
                    genes[slot][sf] = ""

        return genes

    def _extract_fitness(self, dna: dict[str, Any]) -> dict[str, float]:
        """从 DNA 字典提取性能指标。"""
        fitness: dict[str, float] = {}
        for src_field, target_field in self._FITNESS_MAPPING.items():
            if src_field in dna:
                val = dna[src_field]
                if isinstance(val, (int, float)) and val != 0:
                    fitness[target_field] = float(val)
        return fitness

    @property
    def mapped_count(self) -> int:
        """已映射的 DNA 数量。"""
        return self._mapped_count