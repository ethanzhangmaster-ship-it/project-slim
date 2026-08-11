"""E9.7: Creative Prediction Feedback Learning Engine — Data Models.

Core types for the prediction→feedback→learning closed loop:
  - PredictionRecord: frozen snapshot of an E9.6 prediction
  - CreativeActualPerformance: real campaign performance data
  - PredictionError: per-creative per-archetype per-metric error
  - DNAWeightConfig: learned weight adjustments for DNA features
  - LearningReport: summary of what the system learned
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ═══════════════════════════════════════════════════════════
# Prediction Record (frozen snapshot)
# ═══════════════════════════════════════════════════════════

@dataclass
class PredictionRecord:
    """A frozen snapshot of an E9.6 prediction at a point in time."""
    creative_id: str = ""
    creative_genome_name: str = ""
    prediction_time: str = ""  # ISO format

    # Per-archetype predicted probabilities
    archetype_prediction: dict[str, float] = field(default_factory=dict)

    # Predicted aggregate metrics
    predicted_metrics: dict[str, float] = field(default_factory=dict)

    # DNA features used for prediction
    dna_features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_genome_name": self.creative_genome_name,
            "prediction_time": self.prediction_time,
            "archetype_prediction": {
                arch: round(p, 3)
                for arch, p in self.archetype_prediction.items()
            },
            "predicted_metrics": {
                k: round(v, 3) if isinstance(v, float) else v
                for k, v in self.predicted_metrics.items()
            },
            "dna_features": self.dna_features,
        }


# ═══════════════════════════════════════════════════════════
# Creative Actual Performance
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeActualPerformance:
    """Real campaign performance data for a creative."""
    creative_id: str = ""
    data_source: str = ""  # "facebook", "adjust", "firebase", "mock"

    # Campaign metrics
    installs: int = 0
    spend: float = 0.0
    revenue: float = 0.0

    # Player metrics
    total_players: int = 0
    d30_retention: float = 0.0
    payer_rate: float = 0.0
    ltv_d7: float = 0.0
    ltv_d30: float = 0.0

    # Actual archetype distribution (from E9.5 re-run on real data)
    archetype_distribution: dict[str, float] = field(default_factory=dict)

    # Raw player events (for archetype reconstruction)
    raw_player_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "data_source": self.data_source,
            "installs": self.installs,
            "spend": round(self.spend, 2),
            "revenue": round(self.revenue, 2),
            "total_players": self.total_players,
            "d30_retention": round(self.d30_retention, 3),
            "payer_rate": round(self.payer_rate, 3),
            "ltv_d7": round(self.ltv_d7, 2),
            "ltv_d30": round(self.ltv_d30, 2),
            "archetype_distribution": {
                arch: round(p, 3)
                for arch, p in self.archetype_distribution.items()
            },
            "raw_player_count": self.raw_player_count,
        }

    @property
    def roas(self) -> float:
        if self.spend == 0:
            return 0.0
        return self.revenue / self.spend

    @property
    def cpi(self) -> float:
        if self.installs == 0:
            return 0.0
        return self.spend / self.installs


# ═══════════════════════════════════════════════════════════
# Prediction Error
# ═══════════════════════════════════════════════════════════

@dataclass
class ArchetypeError:
    """Error for a single archetype."""
    archetype: str = ""
    predicted: float = 0.0
    actual: float = 0.0
    absolute_error: float = 0.0
    relative_error: float = 0.0  # (actual - predicted) / max(predicted, 0.01)

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype": self.archetype,
            "predicted": round(self.predicted, 3),
            "actual": round(self.actual, 3),
            "absolute_error": round(self.absolute_error, 3),
            "relative_error": round(self.relative_error, 3),
        }


@dataclass
class MetricError:
    """Error for a single metric."""
    metric: str = ""
    predicted: float = 0.0
    actual: float = 0.0
    absolute_error: float = 0.0
    relative_error: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "predicted": round(self.predicted, 3),
            "actual": round(self.actual, 3),
            "absolute_error": round(self.absolute_error, 3),
            "relative_error": round(self.relative_error, 3),
        }


@dataclass
class PredictionError:
    """Full prediction error for one creative."""
    creative_id: str = ""
    creative_genome_name: str = ""

    archetype_errors: dict[str, ArchetypeError] = field(default_factory=dict)
    metric_errors: dict[str, MetricError] = field(default_factory=dict)

    # Overall error scores
    archetype_mae: float = 0.0   # Mean absolute error across archetypes
    metric_mae: float = 0.0      # Mean absolute error across metrics
    ltv_error: float = 0.0       # LTV prediction error (key metric)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_genome_name": self.creative_genome_name,
            "archetype_errors": {
                arch: e.to_dict()
                for arch, e in self.archetype_errors.items()
            },
            "metric_errors": {
                metric: e.to_dict()
                for metric, e in self.metric_errors.items()
            },
            "archetype_mae": round(self.archetype_mae, 3),
            "metric_mae": round(self.metric_mae, 3),
            "ltv_error": round(self.ltv_error, 2),
        }


# ═══════════════════════════════════════════════════════════
# DNA Weight Config
# ═══════════════════════════════════════════════════════════

@dataclass
class DNAWeightUpdate:
    """A single weight update for a DNA feature."""
    feature: str = ""
    archetype: str = ""
    old_weight: float = 0.0
    new_weight: float = 0.0
    delta: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "archetype": self.archetype,
            "old_weight": round(self.old_weight, 3),
            "new_weight": round(self.new_weight, 3),
            "delta": round(self.delta, 3),
            "reason": self.reason,
        }


@dataclass
class DNAWeightConfig:
    """Learned DNA feature weight configuration."""
    version: str = "1.0"
    updated_at: str = ""

    # {archetype: {feature: weight}}
    weights: dict[str, dict[str, float]] = field(default_factory=dict)

    # History of updates
    updates: list[DNAWeightUpdate] = field(default_factory=list)

    def get_weight(self, archetype: str, feature: str) -> float:
        return self.weights.get(archetype, {}).get(feature, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "weights": {
                arch: {
                    feat: round(w, 3)
                    for feat, w in features.items()
                }
                for arch, features in self.weights.items()
            },
            "updates": [u.to_dict() for u in self.updates],
        }


# ═══════════════════════════════════════════════════════════
# Learning Report
# ═══════════════════════════════════════════════════════════

@dataclass
class LearningReport:
    """Summary of what the system learned from feedback."""
    report_time: str = ""
    total_creatives: int = 0
    total_creatives_with_feedback: int = 0

    # Error summary
    avg_ltv_error_before: float = 0.0
    avg_ltv_error_after: float = 0.0
    ltv_error_improvement: float = 0.0  # percentage improvement

    avg_archetype_mae_before: float = 0.0
    avg_archetype_mae_after: float = 0.0
    archetype_mae_improvement: float = 0.0

    # Weight updates
    total_weight_updates: int = 0
    top_learnings: list[dict[str, Any]] = field(default_factory=list)

    # Archetype-level learning
    archetype_learnings: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_time": self.report_time,
            "total_creatives": self.total_creatives,
            "total_creatives_with_feedback": self.total_creatives_with_feedback,
            "error_summary": {
                "avg_ltv_error_before": round(self.avg_ltv_error_before, 2),
                "avg_ltv_error_after": round(self.avg_ltv_error_after, 2),
                "ltv_error_improvement_pct": round(self.ltv_error_improvement, 1),
                "avg_archetype_mae_before": round(self.avg_archetype_mae_before, 3),
                "avg_archetype_mae_after": round(self.avg_archetype_mae_after, 3),
                "archetype_mae_improvement_pct": round(self.archetype_mae_improvement, 1),
            },
            "total_weight_updates": self.total_weight_updates,
            "top_learnings": self.top_learnings,
            "archetype_learnings": self.archetype_learnings,
        }