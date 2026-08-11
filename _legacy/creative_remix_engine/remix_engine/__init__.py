"""Remix Engine — V3.9 Creative Remix Evolution Engine

核心功能：
- Winner Structure Miner: 从真实UA数据挖掘Winner结构模式
- Remix Planner: 根据Winner结构生成剪辑方案
- Remix Mutation Engine: 剪辑策略变异
- Remix Quality Gate: 生成后自动评分
- Creative Remix Composer: 自动剪辑合成（ffmpeg）
"""

from .winner_structure_miner import WinnerStructureMiner, WinningStructure
from .remix_planner import RemixPlanner, RemixPlan
from .remix_mutation import RemixMutationEngine, MutationStrategy
from .remix_quality_gate import RemixQualityGate
from .creative_remix_composer import CreativeRemixComposer

__all__ = [
    "WinnerStructureMiner",
    "WinningStructure",
    "RemixPlanner",
    "RemixPlan",
    "RemixMutationEngine",
    "MutationStrategy",
    "RemixQualityGate",
    "CreativeRemixComposer",
]