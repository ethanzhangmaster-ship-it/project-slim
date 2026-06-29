"""Creative Loop - 素材闭环系统 (DEPRECATED - use creative_growth_loop instead)"""
from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop")

from .pattern_engine import PatternEngine, ImagePattern
from .mutation_engine import MutationEngine, Mutation, MutationType
from .prompt_builder import PromptBuilder, VariantPrompt
from .image_generator import ImageGenerator, GeneratedImage
from .image_validator import ImageValidator, ValidationResult
from .scoring_engine import ScoringEngine, ImageScore
from .library_manager import LibraryManager, WinnerRecord
from .creative_loop import CreativeLoop, LoopResult

__all__ = [
    "PatternEngine",
    "ImagePattern",
    "MutationEngine",
    "Mutation",
    "MutationType",
    "PromptBuilder",
    "VariantPrompt",
    "ImageGenerator",
    "GeneratedImage",
    "ImageValidator",
    "ValidationResult",
    "ScoringEngine",
    "ImageScore",
    "LibraryManager",
    "WinnerRecord",
    "CreativeLoop",
    "LoopResult",
]