"""E15.3.4 Self Optimization — 模块导出.

自我优化模块为 Autonomous Operator 提供自我优化能力：
  - Performance Monitor:  监控 Operator 自身表现
  - Strategy Evaluator:   评估策略长期效果
  - Parameter Optimizer:  自动调整系统参数
  - Learning Optimizer:   优化记忆和学习系统
  - Self Diagnosis:       系统自我诊断
  - SelfOptimizer:        主入口，整合所有组件
"""

from .learning_optimizer import LearningOptimizer
from .models import (
    MetricSeverity,
    OptimizationAction,
    OptimizationArea,
    OptimizationMetric,
    OptimizationOpportunity,
    OptimizationPolicy,
    OptimizationResult,
    OptimizationStatus,
    StrategyPerformance,
    SystemDiagnosis,
    TrendDirection,
)
from .optimizer import SelfOptimizer
from .parameter_optimizer import PARAMETER_REGISTRY, ParameterOptimizer
from .performance_monitor import BUILTIN_METRICS, PerformanceMonitor
from .self_diagnosis import DIAGNOSIS_RULES, SelfDiagnosisEngine
from .strategy_evaluator import StrategyEvaluator

__all__ = [
    # Enums
    "MetricSeverity",
    "OptimizationArea",
    "OptimizationStatus",
    "TrendDirection",
    # Models
    "OptimizationMetric",
    "OptimizationOpportunity",
    "OptimizationAction",
    "OptimizationResult",
    "StrategyPerformance",
    "SystemDiagnosis",
    "OptimizationPolicy",
    # Constants
    "BUILTIN_METRICS",
    "PARAMETER_REGISTRY",
    "DIAGNOSIS_RULES",
    # Core
    "PerformanceMonitor",
    "StrategyEvaluator",
    "ParameterOptimizer",
    "LearningOptimizer",
    "SelfDiagnosisEngine",
    "SelfOptimizer",
]