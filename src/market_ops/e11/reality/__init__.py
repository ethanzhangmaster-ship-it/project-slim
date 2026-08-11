"""E11.6 IAP Reality Integration Layer — 真实 IAP 商业数据层。

将游戏后台、Adjust、Firebase、Store 的真实收入数据
统一为 RevenueEvent，为 Genome 进化提供真实商业驱动。

E11.6.1 — Revenue Data Schema
  - AttributionSource: 归因来源
  - RevenueEvent: 单笔收入事件
  - UserValueProfile: 用户生命周期价值
  - RevenueSummary: Genome 聚合收入

数据流：
  Adjust/Firebase/AppStore → RevenueEvent → RevenueSummary → Fitness → Evolution
"""

from .revenue_schema import (
    AttributionSource,
    PayerType,
    RevenueEvent,
    UserValueProfile,
    RevenueSummary,
)
from .adjust import (
    AdjustRawEvent,
    RevenueType,
    AdjustAdapter,
    AdjustCreativeMapper,
)
from .attribution import (
    CreativeRevenueAttribution,
    GeneRevenueImpact,
    GenomeAttributionResult,
    GenomeAttributor,
    DNARevenueAnalyzer,
    AttributionRepository,
)
from .fitness import (
    ROASProfile,
    RetentionProfile,
    RevenueFitnessProfile,
    CalibratedFitness,
    FitnessWeights,
    RevenueFitnessCalculator,
    FitnessCalibrator,
)

__all__ = [
    "AttributionSource",
    "PayerType",
    "RevenueEvent",
    "UserValueProfile",
    "RevenueSummary",
    "AdjustRawEvent",
    "RevenueType",
    "AdjustAdapter",
    "AdjustCreativeMapper",
    "CreativeRevenueAttribution",
    "GeneRevenueImpact",
    "GenomeAttributionResult",
    "GenomeAttributor",
    "DNARevenueAnalyzer",
    "AttributionRepository",
    "ROASProfile",
    "RetentionProfile",
    "RevenueFitnessProfile",
    "CalibratedFitness",
    "FitnessWeights",
    "RevenueFitnessCalculator",
    "FitnessCalibrator",
]