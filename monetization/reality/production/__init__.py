"""
E14.7.1 — Reality Production Layer (Shadow Mode, READ-ONLY)

Connects real game data (Adjust / Meta Ads / MAX) to the E13 Monetization
Agent in SHADOW mode. Validates that the Autonomous Game Operation OS can understand
real business signals without ever writing to production.

Modules:
    adjust_reader    — Adjust analytics (installs, revenue, cohorts)
    meta_reader      — Meta Ads creative + campaign performance
    max_reader       — MAX monetization (eCPM, fill rate, revenue)
    normalizer       — unifies all three into one RealitySnapshot
    p04_connector    — orchestrator: data → detect → shadow agent → report
    shadow_validator — zero-write + decision completeness verification
"""
from monetization.reality.production.adjust_reader import (
    AdjustReader, AdjustDailySnapshot, AdjustCohort, AdjustTrends,
)
from monetization.reality.production.meta_reader import (
    MetaReader, MetaCreative, MetaCampaign,
)
from monetization.reality.production.max_reader import (
    MaxReader, MaxAdUnitSnapshot, MaxTrend,
)
from monetization.reality.production.normalizer import (
    RealityNormalizer, RealitySnapshot, RealitySegment,
)
from monetization.reality.production.p04_connector import (
    P04Connector, P04ShadowReport,
)
from monetization.reality.production.shadow_validator import ShadowValidator

__all__ = [
    "AdjustReader", "AdjustDailySnapshot", "AdjustCohort", "AdjustTrends",
    "MetaReader", "MetaCreative", "MetaCampaign",
    "MaxReader", "MaxAdUnitSnapshot", "MaxTrend",
    "RealityNormalizer", "RealitySnapshot", "RealitySegment",
    "P04Connector", "P04ShadowReport", "ShadowValidator",
]
