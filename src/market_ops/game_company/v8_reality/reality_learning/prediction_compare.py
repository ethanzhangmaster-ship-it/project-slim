from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class Prediction:
    prediction_id: str
    model_id: str
    target_variable: str
    predicted_value: float
    confidence_interval: tuple = field(default_factory=lambda: (0.0, 0.0))
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "model_id": self.model_id,
            "target_variable": self.target_variable,
            "predicted_value": self.predicted_value,
            "confidence_interval": self.confidence_interval,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ErrorMetrics:
    mae: float = 0.0
    mse: float = 0.0
    rmse: float = 0.0
    mape: float = 0.0
    bias: float = 0.0
    variance: float = 0.0
    correlation: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mae": self.mae,
            "mse": self.mse,
            "rmse": self.rmse,
            "mape": self.mape,
            "bias": self.bias,
            "variance": self.variance,
            "correlation": self.correlation,
        }


@dataclass
class ComparisonResult:
    prediction_id: str
    predicted_value: float
    actual_value: float
    absolute_error: float
    relative_error: float
    within_confidence: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error_metrics: Optional[ErrorMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "predicted_value": self.predicted_value,
            "actual_value": self.actual_value,
            "absolute_error": self.absolute_error,
            "relative_error": self.relative_error,
            "within_confidence": self.within_confidence,
            "timestamp": self.timestamp.isoformat(),
            "error_metrics": self.error_metrics.to_dict() if self.error_metrics else None,
        }


class PredictionCompare:
    def __init__(self):
        self._comparisons: List[ComparisonResult] = []

    def compare(self, prediction: Prediction, actual: float) -> ComparisonResult:
        absolute_error = abs(prediction.predicted_value - actual)
        relative_error = absolute_error / abs(actual) if actual != 0 else 0.0
        within_confidence = (
            prediction.confidence_interval[0] <= actual <= prediction.confidence_interval[1]
            if prediction.confidence_interval[0] < prediction.confidence_interval[1]
            else False
        )

        result = ComparisonResult(
            prediction_id=prediction.prediction_id,
            predicted_value=prediction.predicted_value,
            actual_value=actual,
            absolute_error=absolute_error,
            relative_error=relative_error,
            within_confidence=within_confidence,
        )
        self._comparisons.append(result)
        return result

    def get_comparison_report(self) -> Dict[str, Any]:
        if not self._comparisons:
            return {"total_comparisons": 0, "summary": "No comparisons recorded"}

        total = len(self._comparisons)
        within_confidence = sum(1 for c in self._comparisons if c.within_confidence)
        avg_abs_error = sum(c.absolute_error for c in self._comparisons) / total
        avg_rel_error = sum(c.relative_error for c in self._comparisons) / total

        return {
            "total_comparisons": total,
            "within_confidence_rate": within_confidence / total,
            "average_absolute_error": avg_abs_error,
            "average_relative_error": avg_rel_error,
            "last_comparison": self._comparisons[-1].to_dict() if self._comparisons else None,
            "report_timestamp": datetime.now().isoformat(),
        }

    def get_error_metrics(self) -> ErrorMetrics:
        if not self._comparisons:
            return ErrorMetrics()

        predictions = [c.predicted_value for c in self._comparisons]
        actuals = [c.actual_value for c in self._comparisons]

        n = len(predictions)
        mae = sum(abs(p - a) for p, a in zip(predictions, actuals)) / n
        mse = sum((p - a) ** 2 for p, a in zip(predictions, actuals)) / n
        rmse = mse ** 0.5
        mape = sum(abs((p - a) / a) * 100 for p, a in zip(predictions, actuals) if a != 0) / n
        bias = sum(p - a for p, a in zip(predictions, actuals)) / n
        variance = sum((p - sum(predictions) / n) ** 2 for p in predictions) / n

        avg_pred = sum(predictions) / n
        avg_act = sum(actuals) / n
        cov = sum((p - avg_pred) * (a - avg_act) for p, a in zip(predictions, actuals)) / n
        std_pred = (sum((p - avg_pred) ** 2 for p in predictions) / n) ** 0.5
        std_act = (sum((a - avg_act) ** 2 for a in actuals) / n) ** 0.5
        correlation = cov / (std_pred * std_act) if std_pred != 0 and std_act != 0 else 0.0

        return ErrorMetrics(
            mae=mae,
            mse=mse,
            rmse=rmse,
            mape=mape,
            bias=bias,
            variance=variance,
            correlation=correlation,
        )

    def get_bias_analysis(self) -> Dict[str, Any]:
        metrics = self.get_error_metrics()
        bias_direction = "none"
        if metrics.bias > 0:
            bias_direction = "overestimate"
        elif metrics.bias < 0:
            bias_direction = "underestimate"

        return {
            "bias_direction": bias_direction,
            "bias_magnitude": abs(metrics.bias),
            "bias_percentage": abs(metrics.bias) * 100 if self._comparisons else 0,
            "is_significant": abs(metrics.bias) > metrics.rmse * 0.1,
            "correlation": metrics.correlation,
            "sample_size": len(self._comparisons),
        }