"""E11.7.3 — Population Evolution Manager。

种群级别进化管理：评估 → 多样性检测 → 选择 → 决策。

GenomePopulation → Evaluator → Diversity → Selector → PopulationDecision → Scheduler
"""
from .models import (
    GenomeIndividual,
    GenomeStatus,
    PopulationSnapshot,
    PopulationDecision,
    PopulationSummary,
)
from .evaluator import PopulationEvaluator
from .selector import PopulationSelector
from .diversity import DiversityEngine
from .population_manager import PopulationEvolutionManager

__all__ = [
    "GenomeIndividual",
    "GenomeStatus",
    "PopulationSnapshot",
    "PopulationDecision",
    "PopulationSummary",
    "PopulationEvaluator",
    "PopulationSelector",
    "DiversityEngine",
    "PopulationEvolutionManager",
]