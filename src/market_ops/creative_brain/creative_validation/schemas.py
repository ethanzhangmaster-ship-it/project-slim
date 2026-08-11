"""V4.2 Validation Schemas — shared data structures for validation modules.

All validation results, metrics, and reports use these schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════

class SplitType(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    HOLDOUT = "holdout"


class DriftType(str, Enum):
    CREATIVE = "creative"
    TREND = "trend"
    COUNTRY = "country"
    GENRE = "genre"
    PLATFORM = "platform"
    NETWORK = "network"


class OptimizerMethod(str, Enum):
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"
    MULTI_ARMED_BANDIT = "multi_armed_bandit"


class ErrorType(str, Enum):
    """Root cause classification for prediction errors."""
    RETRIEVER = "retriever"           # Retriever returned wrong/missing creatives
    PATTERN = "pattern"               # Pattern outdated or misclassified
    TREND = "trend"                   # Trend drift caused misprediction
    GRAPH = "graph"                   # Knowledge graph missing relationships
    LEARNING = "learning"             # Learning loop not updated
    CONSTRAINT = "constraint"         # Constraint optimization failure
    CONFIDENCE = "confidence"         # Confidence score miscalibrated


# ═══════════════════════════════════════════════
# Core Data Schemas
# ═══════════════════════════════════════════════

@dataclass
class HistoricalCreative:
    """A single historical creative with time-tagged data."""
    creative_id: str = ""
    dna: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    country: str = ""
    platform: str = "facebook"
    date: str = ""               # ISO date when this creative was active
    campaign_id: str = ""
    labels: list[str] = field(default_factory=list)
    split: SplitType = SplitType.TRAIN

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "dna": self.dna,
            "performance": self.performance,
            "country": self.country,
            "date": self.date,
            "split": self.split.value,
        }

    @property
    def is_winner(self) -> bool:
        return self.performance.get("roas_d7", 0) >= 0.5


@dataclass
class ReplayRecord:
    """A single replay record — prediction + ground truth."""
    creative_id: str = ""
    date: str = ""
    predicted_decision: str = ""   # GO/TEST/EXPLORE/ADAPT/AVOID
    actual_decision: str = ""      # ground truth decision
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)
    actual_roas: float = 0.0
    predicted_roas: float = 0.0
    is_correct: bool = False       # prediction matched reality

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "date": self.date,
            "predicted_decision": self.predicted_decision,
            "actual_decision": self.actual_decision,
            "confidence": round(self.confidence, 3),
            "actual_roas": round(self.actual_roas, 3),
            "predicted_roas": round(self.predicted_roas, 3),
            "is_correct": self.is_correct,
        }


# ═══════════════════════════════════════════════
# Evaluation Schemas
# ═══════════════════════════════════════════════

@dataclass
class EvaluationMetrics:
    """Complete set of evaluation metrics."""
    accuracy: float = 0.0
    balanced_accuracy: float = 0.0
    precision_macro: float = 0.0
    recall_macro: float = 0.0
    f1_macro: float = 0.0
    precision_weighted: float = 0.0
    recall_weighted: float = 0.0
    f1_weighted: float = 0.0
    roc_auc: float = 0.0
    pr_auc: float = 0.0
    per_class: dict[str, dict[str, float]] = field(default_factory=dict)
    total_samples: int = 0
    correct_samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "balanced_accuracy": round(self.balanced_accuracy, 4),
            "precision_macro": round(self.precision_macro, 4),
            "recall_macro": round(self.recall_macro, 4),
            "f1_macro": round(self.f1_macro, 4),
            "precision_weighted": round(self.precision_weighted, 4),
            "recall_weighted": round(self.recall_weighted, 4),
            "f1_weighted": round(self.f1_weighted, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "per_class": self.per_class,
            "total_samples": self.total_samples,
            "correct_samples": self.correct_samples,
        }


@dataclass
class PredictionMetrics:
    """Information Retrieval metrics."""
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    mrr: float = 0.0
    map_score: float = 0.0
    ndcg_at_10: float = 0.0
    ndcg_at_20: float = 0.0
    hit_rate: float = 0.0
    coverage: float = 0.0
    novelty: float = 0.0
    diversity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "recall@5": round(self.recall_at_5, 4),
            "recall@10": round(self.recall_at_10, 4),
            "recall@20": round(self.recall_at_20, 4),
            "mrr": round(self.mrr, 4),
            "map": round(self.map_score, 4),
            "ndcg@10": round(self.ndcg_at_10, 4),
            "ndcg@20": round(self.ndcg_at_20, 4),
            "hit_rate": round(self.hit_rate, 4),
            "coverage": round(self.coverage, 4),
            "novelty": round(self.novelty, 4),
            "diversity": round(self.diversity, 4),
        }


@dataclass
class ConfusionMatrix:
    """5x5 confusion matrix for GO/TEST/EXPLORE/ADAPT/AVOID."""
    classes: list[str] = field(default_factory=lambda: ["GO", "TEST", "EXPLORE", "ADAPT", "AVOID"])
    matrix: list[list[int]] = field(default_factory=lambda: [[0]*5 for _ in range(5)])
    tp: dict[str, int] = field(default_factory=dict)
    fp: dict[str, int] = field(default_factory=dict)
    fn: dict[str, int] = field(default_factory=dict)
    tn: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "classes": self.classes,
            "matrix": self.matrix,
        }
        for cls in self.classes:
            result[f"{cls}_tp"] = self.tp.get(cls, 0)
            result[f"{cls}_fp"] = self.fp.get(cls, 0)
            result[f"{cls}_fn"] = self.fn.get(cls, 0)
            result[f"{cls}_tn"] = self.tn.get(cls, 0)
        return result


@dataclass
class CalibrationResult:
    """Calibration evaluation results."""
    ece: float = 0.0               # Expected Calibration Error
    mce: float = 0.0               # Maximum Calibration Error
    brier_score: float = 0.0
    reliability_curve: list[dict[str, float]] = field(default_factory=list)
    num_bins: int = 10
    is_calibrated: bool = False    # ECE < 0.1 = calibrated

    def to_dict(self) -> dict[str, Any]:
        return {
            "ece": round(self.ece, 4),
            "mce": round(self.mce, 4),
            "brier_score": round(self.brier_score, 4),
            "num_bins": self.num_bins,
            "is_calibrated": self.is_calibrated,
            "reliability_curve": self.reliability_curve,
        }


# ═══════════════════════════════════════════════
# A/B Test Schema
# ═══════════════════════════════════════════════

@dataclass
class ABTestResult:
    """A/B test result comparing two decision engines."""
    baseline_name: str = "RuleEngine"
    treatment_name: str = "ReasoningEngine"
    baseline_accuracy: float = 0.0
    treatment_accuracy: float = 0.0
    winner_recall_baseline: float = 0.0
    winner_recall_treatment: float = 0.0
    roas_improvement: float = 0.0
    ctr_improvement: float = 0.0
    improvement: dict[str, float] = field(default_factory=dict)
    is_significant: bool = False
    p_value: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline_name,
            "treatment": self.treatment_name,
            "baseline_accuracy": round(self.baseline_accuracy, 4),
            "treatment_accuracy": round(self.treatment_accuracy, 4),
            "winner_recall_baseline": round(self.winner_recall_baseline, 4),
            "winner_recall_treatment": round(self.winner_recall_treatment, 4),
            "roas_improvement": round(self.roas_improvement, 4),
            "ctr_improvement": round(self.ctr_improvement, 4),
            "improvement": {k: round(v, 4) for k, v in self.improvement.items()},
            "is_significant": self.is_significant,
            "p_value": round(self.p_value, 4),
        }


# ═══════════════════════════════════════════════
# Drift & Feedback
# ═══════════════════════════════════════════════

@dataclass
class DriftResult:
    """Drift detection result."""
    drift_type: DriftType = DriftType.CREATIVE
    affected_dimension: str = ""
    affected_value: str = ""
    direction: str = ""            # "growing" or "declining"
    current_score: float = 0.0
    previous_score: float = 0.0
    change_pct: float = 0.0
    is_expired: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "drift_type": self.drift_type.value,
            "affected_dimension": self.affected_dimension,
            "affected_value": self.affected_value,
            "direction": self.direction,
            "current_score": round(self.current_score, 3),
            "previous_score": round(self.previous_score, 3),
            "change_pct": round(self.change_pct, 1),
            "is_expired": self.is_expired,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class FeedbackRecord:
    """Online feedback from Facebook."""
    creative_id: str = ""
    date: str = ""
    ctr: float = 0.0
    ipm: float = 0.0
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    ltv: float = 0.0
    spend: float = 0.0
    retention_d1: float = 0.0
    retention_d7: float = 0.0
    predicted_decision: str = ""
    actual_performance: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "date": self.date,
            "ctr": round(self.ctr, 4),
            "ipm": round(self.ipm, 2),
            "roas_d7": round(self.roas_d7, 3),
            "roas_d30": round(self.roas_d30, 3),
            "ltv": round(self.ltv, 2),
            "spend": round(self.spend, 2),
            "retention_d1": round(self.retention_d1, 3),
            "retention_d7": round(self.retention_d7, 3),
        }


# ═══════════════════════════════════════════════
# Weight Optimization
# ═══════════════════════════════════════════════

@dataclass
class WeightOptimizationResult:
    """Weight optimization result."""
    method: OptimizerMethod = OptimizerMethod.GRID_SEARCH
    initial_weights: dict[str, float] = field(default_factory=dict)
    optimized_weights: dict[str, float] = field(default_factory=dict)
    initial_score: float = 0.0
    optimized_score: float = 0.0
    improvement: float = 0.0
    trials: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method.value,
            "initial_weights": {k: round(v, 3) for k, v in self.initial_weights.items()},
            "optimized_weights": {k: round(v, 3) for k, v in self.optimized_weights.items()},
            "initial_score": round(self.initial_score, 4),
            "optimized_score": round(self.optimized_score, 4),
            "improvement": round(self.improvement, 4),
            "trials": self.trials,
        }


# ═══════════════════════════════════════════════
# Error Analysis
# ═══════════════════════════════════════════════

@dataclass
class ErrorDiagnosis:
    """Diagnosis of a single prediction error."""
    creative_id: str = ""
    predicted_decision: str = ""
    actual_decision: str = ""
    confidence: float = 0.0
    error_type: ErrorType = ErrorType.RETRIEVER
    root_cause: str = ""             # Human-readable root cause
    root_cause_detail: str = ""      # Detailed technical explanation
    contributing_modules: list[str] = field(default_factory=list)
    suggested_fix: str = ""          # How to fix this type of error
    severity: str = "medium"         # low/medium/high/critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "predicted_decision": self.predicted_decision,
            "actual_decision": self.actual_decision,
            "confidence": round(self.confidence, 3),
            "error_type": self.error_type.value,
            "root_cause": self.root_cause,
            "root_cause_detail": self.root_cause_detail,
            "contributing_modules": self.contributing_modules,
            "suggested_fix": self.suggested_fix,
            "severity": self.severity,
        }


@dataclass
class ErrorAnalysis:
    """Complete error analysis report."""
    total_errors: int = 0
    total_predictions: int = 0
    error_rate: float = 0.0
    diagnoses: list[ErrorDiagnosis] = field(default_factory=list)
    error_distribution: dict[str, int] = field(default_factory=dict)  # error_type → count
    error_distribution_pct: dict[str, float] = field(default_factory=dict)  # error_type → %
    top_error_types: list[dict[str, Any]] = field(default_factory=list)
    top_failure_creatives: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_errors": self.total_errors,
            "total_predictions": self.total_predictions,
            "error_rate": round(self.error_rate, 4),
            "error_distribution": self.error_distribution,
            "error_distribution_pct": self.error_distribution_pct,
            "top_error_types": self.top_error_types,
            "top_failure_creatives": self.top_failure_creatives,
            "recommendations": self.recommendations,
            "diagnoses": [d.to_dict() for d in self.diagnoses[:20]],
            "summary": self.summary,
        }


# ═══════════════════════════════════════════════
# Validation Report
# ═══════════════════════════════════════════════

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str = ""
    dataset_size: int = 0
    train_size: int = 0
    val_size: int = 0
    test_size: int = 0
    evaluation: EvaluationMetrics = field(default_factory=EvaluationMetrics)
    prediction: PredictionMetrics = field(default_factory=PredictionMetrics)
    confusion: ConfusionMatrix = field(default_factory=ConfusionMatrix)
    calibration: CalibrationResult = field(default_factory=CalibrationResult)
    ab_test: ABTestResult | None = None
    drift_results: list[DriftResult] = field(default_factory=list)
    weight_optimization: WeightOptimizationResult | None = None
    top_failure_cases: list[dict[str, Any]] = field(default_factory=list)
    top_success_cases: list[dict[str, Any]] = field(default_factory=list)
    error_analysis_text: str = ""
    error_analysis: ErrorAnalysis | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = {
            "timestamp": self.timestamp,
            "dataset": {
                "total": self.dataset_size,
                "train": self.train_size,
                "val": self.val_size,
                "test": self.test_size,
            },
            "evaluation": self.evaluation.to_dict(),
            "prediction_metrics": self.prediction.to_dict(),
            "confusion_matrix": self.confusion.to_dict(),
            "calibration": self.calibration.to_dict(),
        }
        if self.ab_test:
            result["ab_test"] = self.ab_test.to_dict()
        if self.weight_optimization:
            result["weight_optimization"] = self.weight_optimization.to_dict()
        result["drift_results"] = [d.to_dict() for d in self.drift_results]
        result["top_failure_cases"] = self.top_failure_cases[:10]
        result["top_success_cases"] = self.top_success_cases[:10]
        result["error_analysis"] = self.error_analysis.to_dict() if self.error_analysis else None
        result["summary"] = self.summary
        return result