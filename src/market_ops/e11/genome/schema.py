"""E11.1 Creative Genome Schema — 创意基因基础数据结构。

CreativeGenome: 可被进化与组合的创意遗传单位
Gene: 统一基因表达单元
GenomeLineage: 谱系追踪记录

Genome 是 DNA 的进化形态：
  DNA（固定）→ Genome（可突变）→ Mutation → New Genome
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════
# Gene — 统一基因表达单元
# ═══════════════════════════════════════════════════════════

@dataclass
class Gene:
    """单个创意基因，统一表达一个创意维度。

    例如：
        Gene(name="hook", value="rescue", confidence=0.91, source="winner_analysis")
    """
    name: str
    value: Any
    confidence: float = 0.0
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Gene:
        return cls(
            name=data["name"],
            value=data["value"],
            confidence=data.get("confidence", 0.0),
            source=data.get("source", "unknown"),
        )


# ═══════════════════════════════════════════════════════════
# GenomeLineage — 谱系追踪
# ═══════════════════════════════════════════════════════════

@dataclass
class GenomeLineage:
    """Genome 谱系元数据，记录来源与创建者。

    追踪链：
        winner_001 → genome_001 → mutation → genome_001_v2
    """
    source: str = ""          # 原始来源标识（如 winner_001）
    created_by: str = ""      # 创建者标识（如 dna_mapper, mutation_engine）
    created_at: str = ""      # ISO 8601 时间戳

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomeLineage:
        return cls(
            source=data.get("source", ""),
            created_by=data.get("created_by", ""),
            created_at=data.get("created_at", ""),
        )


# ═══════════════════════════════════════════════════════════
# GeneSlot — 基因槽位定义
# ═══════════════════════════════════════════════════════════

# E11.1 定义的五个核心基因槽位及其子字段
GENE_SLOTS = {
    "hook": ["type", "strength"],
    "visual": ["style", "composition"],
    "reward": ["type", "intensity"],
    "emotion": ["primary"],
    "gameplay": ["mechanic"],
}


# ═══════════════════════════════════════════════════════════
# CreativeGenome — 创意基因组
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeGenome:
    """可被进化与组合的创意遗传单位。

    CreativeGenome 是 E11 进化体系的核心对象：
      - 从 DNA 初始化（generation=0）
      - 可被 Mutation Engine 克隆与变异（generation++）
      - 携带 fitness 指标用于选择与淘汰
      - 通过 lineage 追踪完整谱系

    Usage:
        genome = CreativeGenome(
            genome_id="genome_001",
            genes={...},
            fitness={"ctr": 0.12, "cpi": 0.45, "roas_d7": 0.32},
            lineage=GenomeLineage(source="winner_001", created_by="dna_mapper"),
        )
    """
    genome_id: str = ""
    parent_id: str | None = None
    generation: int = 0

    # 基因槽位：五个核心维度，每个槽位是 dict[str, Any]
    genes: dict[str, dict[str, Any]] = field(default_factory=dict)

    # 性能指标
    fitness: dict[str, float] = field(default_factory=dict)

    # 谱系
    lineage: GenomeLineage = field(default_factory=GenomeLineage)

    def __post_init__(self) -> None:
        if not self.lineage.created_at:
            self.lineage.created_at = datetime.now(timezone.utc).isoformat()

    # ── 基因访问 ──────────────────────────────────────

    def get_gene(self, slot: str) -> dict[str, Any] | None:
        """获取指定基因槽位的值。"""
        return self.genes.get(slot)

    def set_gene(self, slot: str, value: dict[str, Any]) -> None:
        """设置基因槽位值。"""
        self.genes[slot] = value

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "genes": self.genes,
            "fitness": self.fitness,
            "lineage": self.lineage.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeGenome:
        lineage_data = data.get("lineage", {})
        return cls(
            genome_id=data.get("genome_id", ""),
            parent_id=data.get("parent_id"),
            generation=data.get("generation", 0),
            genes=data.get("genes", {}),
            fitness=data.get("fitness", {}),
            lineage=GenomeLineage.from_dict(lineage_data) if isinstance(lineage_data, dict) else GenomeLineage(),
        )

    # ── 比较 ──────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CreativeGenome):
            return NotImplemented
        return self.genome_id == other.genome_id

    def __hash__(self) -> int:
        return hash(self.genome_id)

    def __repr__(self) -> str:
        return (
            f"CreativeGenome(id={self.genome_id!r}, "
            f"gen={self.generation}, "
            f"parent={self.parent_id!r})"
        )