"""E12.6.5 — Meta Portfolio Optimizer。

元组合优化器，实现产品组合级增长优化。

模块:
  - models:                  PortfolioSnapshot, ProductFitness, PortfolioDecision, etc.
  - portfolio_analyzer:      产品组合状态分析器
  - fitness_ranker:          产品适应度排名引擎
  - allocation_engine:       预算分配引擎
  - lifecycle_allocator:     生命周期分配器
  - experiment_allocator:    实验槽位分配器
  - portfolio_optimizer:     核心控制器
"""

from .models import (
    BudgetAllocation,
    ExperimentAllocation,
    PortfolioAction,
    PortfolioDecision,
    PortfolioResult,
    PortfolioSnapshot,
    ProductFitness,
    ProductLifecycleStage,
    get_default_action,
)
from .portfolio_analyzer import PortfolioAnalyzer
from .fitness_ranker import FitnessRanker
from .allocation_engine import AllocationEngine
from .lifecycle_allocator import LifecycleAllocator
from .experiment_allocator import ExperimentAllocator
from .portfolio_optimizer import PortfolioOptimizer

__all__ = [
    # Models
    "ProductLifecycleStage",
    "PortfolioAction",
    "PortfolioSnapshot",
    "ProductFitness",
    "BudgetAllocation",
    "ExperimentAllocation",
    "PortfolioDecision",
    "PortfolioResult",
    "get_default_action",
    # Engines
    "PortfolioAnalyzer",
    "FitnessRanker",
    "AllocationEngine",
    "LifecycleAllocator",
    "ExperimentAllocator",
    "PortfolioOptimizer",
]