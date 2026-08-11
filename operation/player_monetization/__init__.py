"""
E15.2.7 — Player Monetization Intelligence.

When-who-what ad display optimization. Requires Unity SDK events (stub for now).

Architecture:  Events → PlayerProfile → Segment + ValuePrediction + Lifecycle
               → AdOpportunity → FrequencyRule → Experiment → Memory
"""
from operation.player_monetization.models import (
    PlayerEvent, AdEvent, GameEvent, PlayerProfile, PlayerSegment,
    ValuePrediction, AdOpportunity, FrequencyRule, PlayerLearningRecord,
)
from operation.player_monetization.events import (
    EventCollector, SDKProvider, SyntheticProvider, EventValidator,
)
from operation.player_monetization.user_profile import (
    PlayerSegmenter, ValuePredictor, LifecycleDetector,
)
from operation.player_monetization.ad_opportunity import (
    OpportunityDetector, RewardPredictor, InterstitialPredictor,
)
from operation.player_monetization.frequency import (
    FrequencyOptimizer, FatigueDetector, CooldownManager,
)
from operation.player_monetization.experiment import (
    ABAllocator, ResultAnalyzer,
)
from operation.player_monetization.memory import PlayerLearningMemory
from operation.player_monetization.normalize import (
    normalize_envelope, normalize_batch,
)
from operation.player_monetization.ingest_server import ingest as ingest_events, run_server

__all__ = [n for n in dir() if n[0].isupper()]
