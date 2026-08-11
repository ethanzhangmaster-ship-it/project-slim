"""E12.5.2 — Pattern Mining Engine。

从 Experience Memory 中自动挖掘 Winner Pattern，形成可复用的 Creative Knowledge。

核心模块:
  - models:              Pattern 数据模型（PatternType, MetaPattern, GeneCluster 等）
  - gene_analyzer:       基因分析器（ExperienceRecord → ExtractedGene）
  - pattern_miner:       模式提取引擎（聚类 + 统计 + MetaPattern 构建）
  - correlation_engine:  相关性引擎（基因影响力量化）
  - pattern_ranker:      模式排序器（评分 + 筛选 + 排序）

Pipeline:
  ExperienceStore
       │
       ▼
  GeneAnalyzer.extract_genes()
       │
       ▼
  PatternExtractor.extract()
       │
       ▼
  CorrelationEngine.calculate_gene_impact()
       │
       ▼
  PatternRanker.rank()
       │
       ▼
  PatternMiningResult
"""

from .models import (
    ExtractedGene,
    GeneCluster,
    GeneImpactScore,
    MetaPattern,
    PatternMiningResult,
    PatternType,
)
from .gene_analyzer import GeneAnalyzer
from .pattern_miner import PatternExtractor
from .correlation_engine import CorrelationEngine
from .pattern_ranker import PatternRanker

__all__ = [
    # Models
    "PatternType",
    "ExtractedGene",
    "GeneCluster",
    "MetaPattern",
    "GeneImpactScore",
    "PatternMiningResult",
    # Engines
    "GeneAnalyzer",
    "PatternExtractor",
    "CorrelationEngine",
    "PatternRanker",
]