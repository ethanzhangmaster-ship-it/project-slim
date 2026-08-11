"""E11.6.3 Creative Genome Attribution Engine — 创意 DNA 归因引擎。

将 Adjust 归因好的收入反推到 Creative DNA / Genome 层，
回答"什么创意 DNA 带来了高价值 IAP 用户？"

模块：
  - attribution_schema: CreativeRevenueAttribution, GeneRevenueImpact, GenomeAttributionResult
  - genome_attributor: GenomeAttributor (RevenueEvent → Genome Attribution)
  - dna_revenue_analyzer: DNARevenueAnalyzer (Winner DNA Pattern Detection)
  - attribution_repository: AttributionRepository (持久化)

数据流：
  RevenueEvent → GenomeAttributor → GenomeAttributionResult → DNARevenueAnalyzer → Winner DNA
"""

from .attribution_schema import (
    CreativeRevenueAttribution,
    GeneRevenueImpact,
    GenomeAttributionResult,
)
from .genome_attributor import GenomeAttributor
from .dna_revenue_analyzer import DNARevenueAnalyzer
from .attribution_repository import AttributionRepository

__all__ = [
    "CreativeRevenueAttribution",
    "GeneRevenueImpact",
    "GenomeAttributionResult",
    "GenomeAttributor",
    "DNARevenueAnalyzer",
    "AttributionRepository",
]