"""E11.5.3 Fitness Schema — 真实市场适应度数据模型。

定义 Genome 在真实市场中的最终价值评分。

  GenomeFitness — 单个 Genome 的多维度适应度评分
  FitnessHistory — 适应度历史记录（追踪趋势）

数据流：
  MarketSignal → FitnessCalculator → GenomeFitness → FitnessEngine → Genome.fitness
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════
# GenomeFitness — 多维度适应度评分
# ═══════════════════════════════════════════════════════════

@dataclass
class GenomeFitness:
    """一个 Creative Genome 在真实市场中的最终价值评分。

    组成：
      - Monetization (40%): 商业价值
      - Retention (30%): 长期价值
      - Acquisition (20%): 获取效率
      - Confidence (10%): 数据可靠性

    例如：
        GenomeFitness(
            genome_id="genome_001",
            fitness_score=0.91,
            monetization_score=0.95,
            retention_score=0.85,
            acquisition_score=0.88,
            ltv_score=0.92,
            confidence=0.95,
        )
    """
    fitness_id: str = field(default_factory=lambda: f"fit_{uuid.uuid4().hex[:8]}")
    genome_id: str = ""
    creative_id: str = ""
    signal_id: str = ""

    # 综合评分
    fitness_score: float = 0.0

    # 各维度评分
    monetization_score: float = 0.0
    retention_score: float = 0.0
    acquisition_score: float = 0.0
    ltv_score: float = 0.0

    # 数据可靠性
    confidence: float = 0.0
    sample_size: int = 0

    # 权重明细
    weight_breakdown: dict[str, float] = field(default_factory=dict)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_elite(self) -> bool:
        """是否精英（fitness >= 0.85）。"""
        return self.fitness_score >= 0.85

    @property
    def is_strong(self) -> bool:
        """是否强（fitness >= 0.70）。"""
        return self.fitness_score >= 0.70

    @property
    def is_weak(self) -> bool:
        """是否弱（fitness < 0.40）。"""
        return self.fitness_score < 0.40

    def dominant_dimension(self) -> str:
        """返回得分最高的维度名称。"""
        dims = {
            "monetization": self.monetization_score,
            "retention": self.retention_score,
            "acquisition": self.acquisition_score,
            "ltv": self.ltv_score,
        }
        return max(dims, key=dims.get)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "fitness_id": self.fitness_id,
            "genome_id": self.genome_id,
            "creative_id": self.creative_id,
            "signal_id": self.signal_id,
            "fitness_score": self.fitness_score,
            "monetization_score": self.monetization_score,
            "retention_score": self.retention_score,
            "acquisition_score": self.acquisition_score,
            "ltv_score": self.ltv_score,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "weight_breakdown": self.weight_breakdown,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomeFitness:
        created_at = data.get("created_at")
        return cls(
            fitness_id=data.get("fitness_id", ""),
            genome_id=data.get("genome_id", ""),
            creative_id=data.get("creative_id", ""),
            signal_id=data.get("signal_id", ""),
            fitness_score=data.get("fitness_score", 0.0),
            monetization_score=data.get("monetization_score", 0.0),
            retention_score=data.get("retention_score", 0.0),
            acquisition_score=data.get("acquisition_score", 0.0),
            ltv_score=data.get("ltv_score", 0.0),
            confidence=data.get("confidence", 0.0),
            sample_size=data.get("sample_size", 0),
            weight_breakdown=data.get("weight_breakdown", {}),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"GenomeFitness(id={self.fitness_id!r}, "
            f"genome={self.genome_id!r}, "
            f"score={self.fitness_score}, "
            f"elite={self.is_elite})"
        )


# ═══════════════════════════════════════════════════════════
# FitnessHistory — 适应度历史
# ═══════════════════════════════════════════════════════════

@dataclass
class FitnessHistoryEntry:
    """单次适应度评估记录。"""
    date: str = ""
    fitness_score: float = 0.0
    monetization_score: float = 0.0
    retention_score: float = 0.0
    acquisition_score: float = 0.0
    ltv_score: float = 0.0
    sample_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "fitness_score": self.fitness_score,
            "monetization_score": self.monetization_score,
            "retention_score": self.retention_score,
            "acquisition_score": self.acquisition_score,
            "ltv_score": self.ltv_score,
            "sample_size": self.sample_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessHistoryEntry:
        return cls(
            date=data.get("date", ""),
            fitness_score=data.get("fitness_score", 0.0),
            monetization_score=data.get("monetization_score", 0.0),
            retention_score=data.get("retention_score", 0.0),
            acquisition_score=data.get("acquisition_score", 0.0),
            ltv_score=data.get("ltv_score", 0.0),
            sample_size=data.get("sample_size", 0),
        )


@dataclass
class FitnessHistory:
    """Genome 适应度历史记录。

    追踪一个 Genome 的适应度随时间变化，用于判断：
      - DNA 是否持续有效
      - 是否衰退

    例如：
        history = FitnessHistory(genome_id="genome_001")
        history.add_entry(FitnessHistoryEntry(date="2026-07", fitness_score=0.72))
        history.add_entry(FitnessHistoryEntry(date="2026-08", fitness_score=0.89))
        history.trend  # "improving"
    """
    history_id: str = field(default_factory=lambda: f"fh_{uuid.uuid4().hex[:8]}")
    genome_id: str = ""
    entries: list[FitnessHistoryEntry] = field(default_factory=list)

    # ── 查询 ──────────────────────────────────────────

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def latest_score(self) -> float:
        """最新适应度评分。"""
        if not self.entries:
            return 0.0
        return self.entries[-1].fitness_score

    @property
    def best_score(self) -> float:
        """历史最高评分。"""
        if not self.entries:
            return 0.0
        return max(e.fitness_score for e in self.entries)

    @property
    def score_progression(self) -> list[float]:
        return [e.fitness_score for e in self.entries]

    @property
    def trend(self) -> str:
        """趋势判断：improving, stable, declining, insufficient。

        Returns:
            "improving" | "stable" | "declining" | "insufficient"
        """
        if len(self.entries) < 2:
            return "insufficient"
        scores = self.score_progression
        first = scores[0]
        last = scores[-1]

        if last - first >= 0.05:
            return "improving"
        elif last - first <= -0.05:
            return "declining"
        else:
            return "stable"

    def is_declining(self) -> bool:
        """是否衰退中。"""
        return self.trend == "declining"

    def is_improving(self) -> bool:
        """是否改善中。"""
        return self.trend == "improving"

    # ── 写入 ──────────────────────────────────────────

    def add_entry(self, entry: FitnessHistoryEntry) -> None:
        self.entries.append(entry)

    def add_from_fitness(self, genome_fitness: GenomeFitness, date: str = "") -> None:
        """从 GenomeFitness 创建一条记录。

        Args:
            genome_fitness: 适应度评分
            date: 日期（默认使用当前日期）
        """
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m")

        entry = FitnessHistoryEntry(
            date=date,
            fitness_score=genome_fitness.fitness_score,
            monetization_score=genome_fitness.monetization_score,
            retention_score=genome_fitness.retention_score,
            acquisition_score=genome_fitness.acquisition_score,
            ltv_score=genome_fitness.ltv_score,
            sample_size=genome_fitness.sample_size,
        )
        self.entries.append(entry)

    def clear(self) -> None:
        self.entries.clear()

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "genome_id": self.genome_id,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessHistory:
        return cls(
            history_id=data.get("history_id", ""),
            genome_id=data.get("genome_id", ""),
            entries=[FitnessHistoryEntry.from_dict(e) for e in data.get("entries", [])],
        )

    def __repr__(self) -> str:
        return (
            f"FitnessHistory(genome={self.genome_id!r}, "
            f"entries={self.entry_count}, "
            f"trend={self.trend})"
        )