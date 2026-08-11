"""E12.3 — Reality Prediction Layer (Phase 2)。

基于 E12.1 历史数据 + E12.2 洞察，建立趋势预测能力。

Phase 1:
  - models:              预测数据模型
  - fatigue_predictor:   创意疲劳预测器
  - roas_predictor:      ROAS 趋势预测器
  - prediction_engine:   统一预测引擎

Phase 2:
  - lifecycle_predictor: 生命周期预测器
  - decay_predictor:     衰减速度预测器
  - confidence_engine:   预测置信度引擎
  - explanation_engine:  预测解释引擎
"""

from .models import (
    CreativeLifecycleStage,
    DecayPrediction,
    LifecyclePrediction,
    PredictionConfidence,
    PredictionExplanation,
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
)
from .fatigue_predictor import FatiguePredictor
from .roas_predictor import ROASPredictor
from .lifecycle_predictor import LifecyclePredictor
from .decay_predictor import DecayPredictor
from .confidence_engine import PredictionConfidenceEngine
from .explanation_engine import ExplanationEngine
from .prediction_engine import PredictionEngine, PredictionResult

__all__ = [
    # Phase 1
    "PredictionType",
    "RiskLevel",
    "RealityHistoryPoint",
    "RealityPrediction",
    "FatiguePredictor",
    "ROASPredictor",
    "PredictionEngine",
    "PredictionResult",
    # Phase 2
    "CreativeLifecycleStage",
    "LifecyclePrediction",
    "DecayPrediction",
    "PredictionConfidence",
    "PredictionExplanation",
    "LifecyclePredictor",
    "DecayPredictor",
    "PredictionConfidenceEngine",
    "ExplanationEngine",
]