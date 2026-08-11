"""V4.2 Models — domain models for reasoning operations.

Separates data models from schemas. Models represent domain entities
used across reasoning modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import DNASchema, PerformanceSchema, PatternType, TrendDirection


@dataclass
class CreativeModel:
    """Domain model for a creative asset."""
    creative_id: str = ""
    dna: DNASchema = field(default_factory=DNASchema)
    performance: PerformanceSchema = field(default_factory=PerformanceSchema)
    country: str = ""
    platform: str = ""
    network: str = "facebook"
    campaign_id: str = ""
    created_at: str = ""
    labels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "dna": self.dna.to_dict(),
            "performance": self.performance.to_dict(),
            "country": self.country,
            "platform": self.platform,
            "labels": self.labels,
        }


@dataclass
class PatternModel:
    """Domain model for a discovered pattern."""
    pattern_id: str = ""
    pattern_type: PatternType = PatternType.NOVEL
    dna: dict[str, Any] = field(default_factory=dict)
    sample_count: int = 0
    winner_count: int = 0
    avg_roas: float = 0.0
    avg_ctr: float = 0.0
    avg_cpi: float = 0.0
    support: float = 0.0
    confidence: float = 0.0
    lift: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "dna": self.dna,
            "sample_count": self.sample_count,
            "winner_count": self.winner_count,
            "avg_roas": round(self.avg_roas, 3),
            "avg_ctr": round(self.avg_ctr, 2),
            "avg_cpi": round(self.avg_cpi, 2),
            "support": round(self.support, 3),
            "confidence": round(self.confidence, 3),
            "lift": round(self.lift, 3),
        }


@dataclass
class TrendModel:
    """Domain model for a trend observation."""
    trend_id: str = ""
    dimension: str = ""          # e.g., "character", "hook", "reward"
    value: str = ""              # e.g., "dragon", "collection"
    direction: TrendDirection = TrendDirection.STABLE
    current_score: float = 0.0
    previous_score: float = 0.0
    change_pct: float = 0.0
    window_days: int = 7
    sample_count: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend_id": self.trend_id,
            "dimension": self.dimension,
            "value": self.value,
            "direction": self.direction.value,
            "current_score": round(self.current_score, 3),
            "previous_score": round(self.previous_score, 3),
            "change_pct": round(self.change_pct, 1),
            "window_days": self.window_days,
            "sample_count": self.sample_count,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class KnowledgeTransferModel:
    """Domain model for cross-game knowledge transfer."""
    transfer_id: str = ""
    source_game: str = ""
    target_game: str = ""
    transferable_dimensions: list[str] = field(default_factory=list)
    adaptation_required: list[str] = field(default_factory=list)
    transfer_score: float = 0.0
    expected_impact: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "source_game": self.source_game,
            "target_game": self.target_game,
            "transferable_dimensions": self.transferable_dimensions,
            "adaptation_required": self.adaptation_required,
            "transfer_score": round(self.transfer_score, 3),
            "expected_impact": self.expected_impact,
            "evidence": self.evidence,
        }