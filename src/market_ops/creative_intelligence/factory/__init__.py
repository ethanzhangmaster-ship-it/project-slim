"""P04 Creative Factory V2 — 统一生成管线（Phase 1 + Phase 2）。

主入口：
    from market_ops.creative_intelligence.factory import CreativeFactory
    factory = CreativeFactory()
    # Phase 1
    result = factory.generate("winner_001", count=50)
    # Phase 2（变异引擎 + CLIP 排序 + TOP10）
    result = factory.generate("winner_001", count=50, use_mutation=True, rank=True, top_k=10)
"""
from market_ops.creative_intelligence.factory.creative_factory import CreativeFactory
from market_ops.creative_intelligence.factory.generation_context import (
    GenerationContext,
    find_project_root,
)
from market_ops.creative_intelligence.factory.dna.dna_mutator import DNAMutator
from market_ops.creative_intelligence.factory.ranking.creative_ranker import CreativeRanker

__all__ = [
    "CreativeFactory",
    "GenerationContext",
    "find_project_root",
    "DNAMutator",
    "CreativeRanker",
]
