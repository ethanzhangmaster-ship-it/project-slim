"""Creative Mapping Engine — 统一多维度创意资产映射层。"""

from .delivery_bridge import (
    AutoStructureResult,
    BatchDeliveryResult,
    CIRCUIT_BREAKER_THRESHOLD,
    MAX_DELIVERIES_PER_RUN,
    DeliveryBridge,
    DeliveryResult,
)
from .eagle_tagger import (
    AssetTag,
    AssetTagResult,
    EagleAssetTagger,
    EagleTagStore,
    get_eagle_tagger,
    get_eagle_tag_store,
    reset_eagle_tag_store,
    reset_eagle_tagger,
)
from .engine import CreativeMappingEngine
from .facebook_ingester import FacebookCreativeIngester, IngestionResult
from .frame_similarity import FrameSimilarityComputer
from .insights_ingester import (
    CreativePerformance,
    FacebookInsightsIngester,
    InsightsIngestionResult,
)
from .models import (
    CreativeMappingRecord,
    MappingDeliveryStatus,
    MappingScores,
    MappingStatus,
    ReviewTask,
    now_iso,
)
from .review_queue import ReviewQueue
from .scanner import EagleScanner
from .scorers import MappingScorer
from .store import MappingStore
from .strategy_optimizer import (
    ArchiveResult,
    DeliveryStrategyOptimizer,
)

__all__ = [
    "CreativeMappingEngine",
    "DeliveryBridge",
    "DeliveryResult",
    "BatchDeliveryResult",
    "AutoStructureResult",
    "MAX_DELIVERIES_PER_RUN",
    "CIRCUIT_BREAKER_THRESHOLD",
    "EagleAssetTagger",
    "EagleScanner",
    "EagleTagStore",
    "FacebookCreativeIngester",
    "FacebookInsightsIngester",
    "CreativePerformance",
    "InsightsIngestionResult",
    "DeliveryStrategyOptimizer",
    "ArchiveResult",
    "FrameSimilarityComputer",
    "IngestionResult",
    "MappingScorer",
    "MappingStore",
    "ReviewQueue",
    "AssetTag",
    "AssetTagResult",
    "CreativeMappingRecord",
    "MappingDeliveryStatus",
    "MappingScores",
    "MappingStatus",
    "ReviewTask",
    "get_eagle_tag_store",
    "get_eagle_tagger",
    "now_iso",
    "reset_eagle_tag_store",
    "reset_eagle_tagger",
]
