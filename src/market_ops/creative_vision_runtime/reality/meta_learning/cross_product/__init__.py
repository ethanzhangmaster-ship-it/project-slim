"""E12.6.4 — Cross Product Intelligence。

跨产品智能层，实现产品间的知识迁移。

模块:
  - models:                     ProductProfile, ProductFeature, UniversalPattern, TransferDecision, etc.
  - product_profiler:           产品画像构建器
  - similarity_engine:          产品相似度引擎
  - universal_pattern_library:  通用创意模式库
  - transfer_engine:            知识迁移决策引擎
  - cross_product_controller:   核心控制器
"""

from .models import (
    CrossLearningResult,
    KnowledgeTransfer,
    ProductCluster,
    ProductFeature,
    ProductProfile,
    SimilarityResult,
    TransferAction,
    TransferDecision,
    TransferRisk,
    UniversalPattern,
)
from .product_profiler import ProductProfiler
from .similarity_engine import SimilarityEngine
from .universal_pattern_library import UniversalPatternLibrary
from .transfer_engine import TransferEngine
from .cross_product_controller import CrossProductController

__all__ = [
    # Models
    "ProductFeature",
    "ProductProfile",
    "ProductCluster",
    "UniversalPattern",
    "TransferRisk",
    "TransferAction",
    "TransferDecision",
    "KnowledgeTransfer",
    "CrossLearningResult",
    "SimilarityResult",
    # Engines
    "ProductProfiler",
    "SimilarityEngine",
    "UniversalPatternLibrary",
    "TransferEngine",
    "CrossProductController",
]