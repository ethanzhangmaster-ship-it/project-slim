"""V4.3.5 Knowledge Lifecycle Engine — schemas.

Knowledge governance layer between Validation and Policy.
Handles: promote, retire, update, refresh, version, lineage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════

class PatternStatus(str, Enum):
    """Pattern lifecycle status."""
    CANDIDATE = "candidate"       # Newly detected, not yet official
    ACTIVE = "active"             # Official, actively used
    DEPRECATED = "deprecated"     # Declined, kept for history
    RETIRED = "retired"           # Fully removed from active use
    PROMOTED = "promoted"         # Recently promoted from candidate


class KnowledgeEvent(str, Enum):
    """Types of knowledge lifecycle events."""
    PATTERN_PROMOTED = "pattern_promoted"
    PATTERN_RETIRED = "pattern_retired"
    GRAPH_UPDATED = "graph_updated"
    EMBEDDING_REFRESHED = "embedding_refreshed"
    RETRIEVER_REBUILT = "retriever_rebuilt"
    CONFIDENCE_REBUILT = "confidence_rebuilt"
    TREND_UPDATED = "trend_updated"
    VERSION_SNAPSHOT = "version_snapshot"
    VERSION_ROLLBACK = "version_rollback"


class TrendDirection(str, Enum):
    """Trend movement direction."""
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    DEAD = "dead"
    EMERGING = "emerging"


# ═══════════════════════════════════════════════════
# Core Schemas
# ═══════════════════════════════════════════════════

@dataclass
class PatternLifecycle:
    """A pattern's full lifecycle state."""
    pattern_id: str = ""
    name: str = ""
    status: PatternStatus = PatternStatus.CANDIDATE
    dna_dimensions: dict[str, Any] = field(default_factory=dict)
    # Performance metrics
    current_roas: float = 0.0
    peak_roas: float = 0.0
    roas_lift: float = 0.0          # % change from baseline
    consecutive_winner_days: int = 0
    consecutive_decline_days: int = 0
    confidence: float = 0.0
    # Lifecycle tracking
    created_at: str = ""
    promoted_at: str = ""
    deprecated_at: str = ""
    retired_at: str = ""
    # Evidence
    supporting_creatives: list[str] = field(default_factory=list)
    evidence_count: int = 0
    # Validation feedback
    last_validated: str = ""
    validation_accuracy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "status": self.status.value,
            "current_roas": round(self.current_roas, 3),
            "peak_roas": round(self.peak_roas, 3),
            "roas_lift": round(self.roas_lift, 3),
            "consecutive_winner_days": self.consecutive_winner_days,
            "consecutive_decline_days": self.consecutive_decline_days,
            "confidence": round(self.confidence, 3),
            "validation_accuracy": round(self.validation_accuracy, 3),
        }


@dataclass
class GraphUpdate:
    """A knowledge graph edge update."""
    source_node: str = ""
    target_node: str = ""
    relation: str = ""
    action: str = "add"              # add / remove / strengthen / weaken
    weight: float = 0.0
    weight_change: float = 0.0
    evidence: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_node,
            "target": self.target_node,
            "relation": self.relation,
            "action": self.action,
            "weight": round(self.weight, 3),
            "reason": self.reason,
        }


@dataclass
class EmbeddingUpdate:
    """Incremental embedding update for a creative."""
    creative_id: str = ""
    dna: dict[str, Any] = field(default_factory=dict)
    embedding_vector: list[float] = field(default_factory=list)
    action: str = "add"              # add / update / remove
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "action": self.action,
            "vector_dim": len(self.embedding_vector),
            "timestamp": self.timestamp,
        }


@dataclass
class ConfidenceCalibration:
    """Confidence recalibration result."""
    source: str = ""                 # pattern / retriever / graph / trend
    original_confidence: float = 0.0
    actual_accuracy: float = 0.0
    calibrated_confidence: float = 0.0
    gap: float = 0.0
    adjustment_factor: float = 1.0
    samples: int = 0
    recalibrated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "original_confidence": round(self.original_confidence, 3),
            "actual_accuracy": round(self.actual_accuracy, 3),
            "calibrated_confidence": round(self.calibrated_confidence, 3),
            "gap": round(self.gap, 3),
            "adjustment_factor": round(self.adjustment_factor, 3),
            "samples": self.samples,
        }


@dataclass
class LineageRecord:
    """Provenance record for a piece of knowledge."""
    knowledge_id: str = ""
    knowledge_type: str = ""         # pattern / graph_edge / trend / embedding
    source: str = ""                 # facebook / reasoning / validation
    source_creative_id: str = ""
    created_at: str = ""
    validated_at: str = ""
    validation_result: str = ""      # confirmed / rejected / updated
    version_added: str = ""
    version_retired: str = ""
    full_lineage: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "type": self.knowledge_type,
            "source": self.source,
            "source_creative": self.source_creative_id,
            "created": self.created_at,
            "validated": self.validated_at,
            "validation_result": self.validation_result,
            "version_added": self.version_added,
            "lineage": " → ".join(self.full_lineage),
        }


@dataclass
class KnowledgeSnapshot:
    """A point-in-time snapshot of the knowledge state."""
    version: str = ""
    timestamp: str = ""
    pattern_count: int = 0
    active_patterns: list[str] = field(default_factory=list)
    deprecated_patterns: list[str] = field(default_factory=list)
    graph_node_count: int = 0
    graph_edge_count: int = 0
    embedding_count: int = 0
    retriever_index_version: str = ""
    confidence_calibration: dict[str, float] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "patterns": {
                "total": self.pattern_count,
                "active": len(self.active_patterns),
                "deprecated": len(self.deprecated_patterns),
            },
            "graph": {
                "nodes": self.graph_node_count,
                "edges": self.graph_edge_count,
            },
            "embeddings": self.embedding_count,
            "retriever_version": self.retriever_index_version,
            "summary": self.summary,
        }


@dataclass
class LifecycleReport:
    """Complete lifecycle operation report."""
    timestamp: str = ""
    version_from: str = ""
    version_to: str = ""
    events: list[KnowledgeEvent] = field(default_factory=list)
    # Counts
    patterns_promoted: int = 0
    patterns_retired: int = 0
    graph_edges_updated: int = 0
    embeddings_refreshed: int = 0
    retriever_rebuilt: bool = False
    confidence_rebuilt: bool = False
    trends_updated: int = 0
    # Details
    promoted: list[PatternLifecycle] = field(default_factory=list)
    retired: list[PatternLifecycle] = field(default_factory=list)
    graph_updates: list[GraphUpdate] = field(default_factory=list)
    calibrations: list[ConfidenceCalibration] = field(default_factory=list)
    snapshot: KnowledgeSnapshot | None = None
    # Summary
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "version_from": self.version_from,
            "version_to": self.version_to,
            "events": [e.value for e in self.events],
            "counts": {
                "promoted": self.patterns_promoted,
                "retired": self.patterns_retired,
                "graph_edges": self.graph_edges_updated,
                "embeddings": self.embeddings_refreshed,
                "retriever_rebuilt": self.retriever_rebuilt,
                "confidence_rebuilt": self.confidence_rebuilt,
                "trends": self.trends_updated,
            },
            "summary": self.summary,
        }