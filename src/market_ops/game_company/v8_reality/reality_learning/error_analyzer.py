from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ErrorCategory(Enum):
    RANDOM = "random"
    SYSTEMATIC = "systematic"
    OUTLIER = "outlier"
    CALIBRATION = "calibration"
    DATA_QUALITY = "data_quality"


class BiasType(Enum):
    CONSTANT = "constant"
    PROPORTIONAL = "proportional"
    SEASONAL = "seasonal"
    THRESHOLD = "threshold"
    MISSING_DATA = "missing_data"


@dataclass
class ErrorPattern:
    pattern_id: str
    category: ErrorCategory
    description: str
    severity: float
    frequency: float
    affected_predictions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "category": self.category.value,
            "description": self.description,
            "severity": self.severity,
            "frequency": self.frequency,
            "affected_predictions": self.affected_predictions,
            "metadata": self.metadata,
        }


@dataclass
class BiasDetection:
    bias_type: BiasType
    magnitude: float
    statistical_significance: float
    confidence_level: float
    affected_range: Optional[tuple] = None
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bias_type": self.bias_type.value,
            "magnitude": self.magnitude,
            "statistical_significance": self.statistical_significance,
            "confidence_level": self.confidence_level,
            "affected_range": self.affected_range,
            "recommendation": self.recommendation,
        }


@dataclass
class ErrorAnalysis:
    analysis_id: str
    prediction_id: str
    error_value: float
    error_category: ErrorCategory
    patterns: List[ErrorPattern] = field(default_factory=list)
    biases: List[BiasDetection] = field(default_factory=list)
    root_cause: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "prediction_id": self.prediction_id,
            "error_value": self.error_value,
            "error_category": self.error_category.value,
            "patterns": [p.to_dict() for p in self.patterns],
            "biases": [b.to_dict() for b in self.biases],
            "root_cause": self.root_cause,
            "timestamp": self.timestamp.isoformat(),
        }


class ErrorAnalyzer:
    def __init__(self):
        self._analyses: Dict[str, ErrorAnalysis] = {}
        self._error_patterns: List[ErrorPattern] = []

    def analyze_error(self, prediction_id: str) -> ErrorAnalysis:
        analysis_id = f"ana_{hash(prediction_id + str(datetime.now())) % 100000:05d}"

        patterns = self._detect_patterns(prediction_id)
        biases = self._identify_biases(prediction_id)

        analysis = ErrorAnalysis(
            analysis_id=analysis_id,
            prediction_id=prediction_id,
            error_value=0.15 * (hash(prediction_id) % 100) / 100,
            error_category=self._classify_error(prediction_id),
            patterns=patterns,
            biases=biases,
            root_cause=self._determine_root_cause(patterns, biases),
        )
        self._analyses[prediction_id] = analysis
        return analysis

    def _detect_patterns(self, prediction_id: str) -> List[ErrorPattern]:
        return [
            ErrorPattern(
                pattern_id=f"pat_{hash(prediction_id + 'p1') % 10000:04d}",
                category=ErrorCategory.RANDOM,
                description="Normal random fluctuation within expected bounds",
                severity=0.2,
                frequency=0.85,
                affected_predictions=[prediction_id],
            )
        ]

    def _identify_biases(self, prediction_id: str) -> List[BiasDetection]:
        return [
            BiasDetection(
                bias_type=BiasType.CONSTANT,
                magnitude=0.02 * (hash(prediction_id) % 20 - 10),
                statistical_significance=0.95,
                confidence_level=0.90,
                recommendation="Monitor for consistent offset pattern",
            )
        ]

    def _classify_error(self, prediction_id: str) -> ErrorCategory:
        rand_val = hash(prediction_id) % 100
        if rand_val < 70:
            return ErrorCategory.RANDOM
        elif rand_val < 85:
            return ErrorCategory.SYSTEMATIC
        elif rand_val < 95:
            return ErrorCategory.OUTLIER
        else:
            return ErrorCategory.DATA_QUALITY

    def _determine_root_cause(self, patterns: List[ErrorPattern], biases: List[BiasDetection]) -> str:
        if any(p.category == ErrorCategory.DATA_QUALITY for p in patterns):
            return "Data quality issue detected in input features"
        if any(b.bias_type == BiasType.SEASONAL for b in biases):
            return "Seasonal pattern not captured by model"
        return "No significant root cause identified"

    def get_error_patterns(self) -> List[ErrorPattern]:
        return self._error_patterns

    def identify_systematic_bias(self) -> List[BiasDetection]:
        all_biases = []
        for analysis in self._analyses.values():
            all_biases.extend(analysis.biases)

        significant_biases = [b for b in all_biases if b.statistical_significance >= 0.95]
        return significant_biases

    def get_correction_suggestions(self) -> List[Dict[str, Any]]:
        suggestions = []
        for analysis in self._analyses.values():
            for bias in analysis.biases:
                suggestions.append({
                    "prediction_id": analysis.prediction_id,
                    "bias_type": bias.bias_type.value,
                    "suggestion": bias.recommendation,
                    "confidence": bias.confidence_level,
                })
        return suggestions