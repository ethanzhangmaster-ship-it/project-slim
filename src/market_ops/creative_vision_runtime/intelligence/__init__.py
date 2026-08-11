"""E11.3.5 — Vision Intelligence Layer。

Pattern Mining + Hook Analysis + Composition + Winner DNA Extraction。
"""
from .models import (
    VisualPattern,
    HookAnalysis,
    CompositionAnalysis,
    VisionInsight,
    WinnerVisualDNA,
)
from .pattern_miner import PatternMiner
from .hook_analyzer import HookAnalyzer
from .dna_extractor import WinnerDNAExtractor
from .engine import VisionIntelligenceEngine

__all__ = [
    "VisualPattern",
    "HookAnalysis",
    "CompositionAnalysis",
    "VisionInsight",
    "WinnerVisualDNA",
    "PatternMiner",
    "HookAnalyzer",
    "WinnerDNAExtractor",
    "VisionIntelligenceEngine",
]