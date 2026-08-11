"""E11.4.2 — Mutation Mapping Layer。

VisionDecision → Genome Gene → MutationPlan → V5 Mutation Engine。
"""
from .models import (
    MutationGeneChange,
    MutationConstraint,
    VisionMutationPlan,
)
from .gene_mapper import GeneMapper, GeneMapping, PATTERN_TO_GENOME
from .constraint import ConstraintEngine, DEFAULT_CONSTRAINTS
from .mutation_planner import MutationPlanner

__all__ = [
    "MutationGeneChange",
    "MutationConstraint",
    "VisionMutationPlan",
    "GeneMapper",
    "GeneMapping",
    "PATTERN_TO_GENOME",
    "ConstraintEngine",
    "DEFAULT_CONSTRAINTS",
    "MutationPlanner",
]