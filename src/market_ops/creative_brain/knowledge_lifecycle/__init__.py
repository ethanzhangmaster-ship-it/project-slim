"""V4.3.5 Knowledge Lifecycle Engine — knowledge governance layer.

Sits between Validation (V4.2.1) and Policy (V4.3).
Handles: promote, retire, update, refresh, version, lineage.

This ensures knowledge evolves with the market, not remains static.
"""

from .schemas import (
    PatternStatus, KnowledgeEvent, TrendDirection,
    PatternLifecycle, GraphUpdate, EmbeddingUpdate,
    ConfidenceCalibration, LineageRecord, KnowledgeSnapshot,
    LifecycleReport,
)

from .pattern_promoter import PatternPromoter
from .pattern_retirer import PatternRetirer
from .graph_updater import GraphUpdater
from .trend_updater import TrendUpdater
from .embedding_refresher import EmbeddingRefresher
from .retriever_rebuilder import RetrieverRebuilder
from .confidence_rebuilder import ConfidenceRebuilder
from .knowledge_version import KnowledgeVersion
from .knowledge_snapshot import KnowledgeSnapshotter
from .lineage_tracker import LineageTracker
from .lifecycle_engine import LifecycleEngine

__all__ = [
    # Enums
    "PatternStatus", "KnowledgeEvent", "TrendDirection",
    # Schemas
    "PatternLifecycle", "GraphUpdate", "EmbeddingUpdate",
    "ConfidenceCalibration", "LineageRecord", "KnowledgeSnapshot",
    "LifecycleReport",
    # Modules
    "PatternPromoter", "PatternRetirer",
    "GraphUpdater", "TrendUpdater",
    "EmbeddingRefresher", "RetrieverRebuilder",
    "ConfidenceRebuilder", "KnowledgeVersion",
    "KnowledgeSnapshotter", "LineageTracker",
    "LifecycleEngine",
]