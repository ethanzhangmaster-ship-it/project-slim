"""V4.2 Shared Schemas — unified data structures for all reasoning modules.

All reasoning modules use these schemas for input/output consistency.
This ensures evidence, confidence, and explanation formats are uniform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════

class DecisionType(str, Enum):
    GO = "go"            # Proven winner, full scale
    TEST = "test"         # Promising, test with budget
    EXPLORE = "explore"   # Novel, worth small test
    ADAPT = "adapt"       # Adapt for new market
    AVOID = "avoid"       # Proven loser, don't invest


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrendDirection(str, Enum):
    GROWING = "growing"
    DECLINING = "declining"
    STABLE = "stable"
    EMERGING = "emerging"
    DEAD = "dead"


class PatternType(str, Enum):
    WINNER = "winner"
    LOSER = "loser"
    NOVEL = "novel"
    MIXED = "mixed"


class EvidenceSource(str, Enum):
    MEMORY = "memory"
    RETRIEVER = "retriever"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    PATTERN_MINING = "pattern_mining"
    LEARNING_LOOP = "learning_loop"
    TREND = "trend"
    META = "meta"


# ═══════════════════════════════════════════════
# Core Schemas
# ═══════════════════════════════════════════════

@dataclass
class DNASchema:
    """Standard DNA representation for a creative."""
    character: str = ""
    reward: str = ""
    hook: str = ""
    gameplay: str = ""
    camera: str = ""
    style: str = ""
    palette: str = ""
    lighting: str = ""
    composition: str = ""
    background: str = ""
    emotion: str = ""
    typography: str = ""

    # Extra dimensions
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {}
        for field_name in self.__dataclass_fields__:
            if field_name == "extra":
                continue
            val = getattr(self, field_name)
            if val:
                result[field_name] = val
        result.update(self.extra)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DNASchema:
        known = {f.name for f in cls.__dataclass_fields__.keys() if f.name != "extra"}
        extra = {k: v for k, v in data.items() if k not in known}
        kwargs = {k: data.get(k, "") for k in known}
        kwargs["extra"] = extra
        return cls(**kwargs)


@dataclass
class PerformanceSchema:
    """Standard performance metrics for a creative."""
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    ctr: float = 0.0
    ipm: float = 0.0
    cpi: float = 0.0
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    country: str = ""
    platform: str = ""

    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "roas_d7": self.roas_d7,
            "roas_d30": self.roas_d30,
            "ctr": self.ctr,
            "ipm": self.ipm,
            "cpi": self.cpi,
            "spend": self.spend,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "country": self.country,
            "platform": self.platform,
            **self.extra,
        }


@dataclass
class EvidenceItem:
    """A single piece of evidence backing a decision or recommendation."""
    source: EvidenceSource = EvidenceSource.RETRIEVER
    source_id: str = ""          # e.g., "winner_0012", "pattern_0009"
    description: str = ""         # Human-readable evidence description
    strength: float = 0.0         # [0, 1] how strong this evidence is
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "source_id": self.source_id,
            "description": self.description,
            "strength": round(self.strength, 3),
            "data": self.data,
        }


@dataclass
class ConfidenceScore:
    """Weighted confidence score from multiple reasoning sources."""
    retriever_score: float = 0.0
    pattern_score: float = 0.0
    graph_score: float = 0.0
    learning_score: float = 0.0
    trend_score: float = 0.0
    overall: float = 0.0  # weighted combination

    weights: dict[str, float] = field(default_factory=lambda: {
        "retriever": 0.25,
        "pattern": 0.30,
        "graph": 0.15,
        "learning": 0.15,
        "trend": 0.15,
    })

    def compute_overall(self) -> float:
        self.overall = (
            self.retriever_score * self.weights["retriever"]
            + self.pattern_score * self.weights["pattern"]
            + self.graph_score * self.weights["graph"]
            + self.learning_score * self.weights["learning"]
            + self.trend_score * self.weights["trend"]
        )
        return self.overall

    def to_dict(self) -> dict[str, Any]:
        return {
            "retriever": round(self.retriever_score, 3),
            "pattern": round(self.pattern_score, 3),
            "graph": round(self.graph_score, 3),
            "learning": round(self.learning_score, 3),
            "trend": round(self.trend_score, 3),
            "overall": round(self.overall, 3),
        }


@dataclass
class ReasoningContext:
    """Input context for a reasoning request."""
    creative_id: str = ""
    dna: DNASchema = field(default_factory=DNASchema)
    performance: PerformanceSchema = field(default_factory=PerformanceSchema)
    source_country: str = ""
    target_country: str = ""
    budget: float = 0.0
    monetization: str = ""
    platform: str = ""
    timeline_days: int = 7
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "dna": self.dna.to_dict(),
            "performance": self.performance.to_dict(),
            "source_country": self.source_country,
            "target_country": self.target_country,
            "budget": self.budget,
            "monetization": self.monetization,
            "platform": self.platform,
            "timeline_days": self.timeline_days,
        }


@dataclass
class ReasoningResult:
    """Complete reasoning result with all components."""
    creative_id: str = ""
    decision_type: DecisionType = DecisionType.TEST
    confidence: ConfidenceScore = field(default_factory=ConfidenceScore)
    evidence: list[EvidenceItem] = field(default_factory=list)
    explanation: str = ""
    reason: str = ""
    recommended_dna: DNASchema = field(default_factory=DNASchema)
    risk: RiskLevel = RiskLevel.MEDIUM
    expected_roas: float = 0.0
    expected_cpi: float = 0.0
    priority: int = 0
    next_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "decision_type": self.decision_type.value,
            "confidence": self.confidence.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "explanation": self.explanation,
            "reason": self.reason,
            "recommended_dna": self.recommended_dna.to_dict(),
            "risk": self.risk.value,
            "expected_roas": round(self.expected_roas, 3),
            "expected_cpi": round(self.expected_cpi, 2),
            "priority": self.priority,
            "next_steps": self.next_steps,
            "warnings": self.warnings,
        }