"""Selector Module — 素材选择器"""

from .dna_matcher import DNAMatcher
from .material_ranker import MaterialRanker
from .winner_selector import WinnerSelector
from .winner_dna_engine_v2 import WinnerDNAEngineV2
from .winner_dna_shot_selector_v38 import WinnerDNAShotSelectorV38, V38ShotCandidate

__all__ = [
    "DNAMatcher",
    "MaterialRanker",
    "WinnerSelector",
    "WinnerDNAEngineV2",
    "WinnerDNAShotSelectorV38",
    "V38ShotCandidate",
]
