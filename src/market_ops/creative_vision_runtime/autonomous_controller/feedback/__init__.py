"""E11.5.3 — Autonomous Feedback Loop。

Performance → Fitness → Learning → Controller Feedback。

完整闭环：
  Experiment Result
    → PerformanceCollector.collect()
    → Evaluator.evaluate()
    → LearningEngine.generate()
    → EvolutionFeedback
    → Controller.receive_feedback()
    → Next Evolution Cycle
"""
from .models import (
    PerformanceSignal,
    FitnessScore,
    LearningSignal,
    EvolutionFeedback,
    LearningDirection,
)
from .performance_collector import PerformanceCollector
from .evaluator import Evaluator
from .learning_engine import LearningEngine
from .feedback_engine import FeedbackEngine

__all__ = [
    "PerformanceSignal",
    "FitnessScore",
    "LearningSignal",
    "EvolutionFeedback",
    "LearningDirection",
    "PerformanceCollector",
    "Evaluator",
    "LearningEngine",
    "FeedbackEngine",
]