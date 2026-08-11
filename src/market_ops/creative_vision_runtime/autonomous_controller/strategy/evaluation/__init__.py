"""E11.8.3 — Evolution Evaluation Engine。

自动判断进化是否成功，并决定保留、回滚、继续迭代。

模块：
  - models:               EvaluationStatus, MetricComparison, EvolutionEvaluation, EvolutionRecommendation
  - metric_evaluator:     进化前后指标对比
  - improvement_detector: 检测真正改善
  - strategy_judge:       策略评判 → 行动建议
  - evaluation_engine:    统一入口
"""

from .models import (
    EvaluationStatus,
    EvolutionEvaluation,
    EvolutionRecommendation,
    MetricComparison,
)
from .metric_evaluator import MetricEvaluator
from .improvement_detector import ImprovementDetector
from .strategy_judge import StrategyJudge
from .evaluation_engine import EvolutionEvaluationEngine

__all__ = [
    # Models
    "EvaluationStatus",
    "MetricComparison",
    "EvolutionEvaluation",
    "EvolutionRecommendation",
    # Engines
    "MetricEvaluator",
    "ImprovementDetector",
    "StrategyJudge",
    "EvolutionEvaluationEngine",
]