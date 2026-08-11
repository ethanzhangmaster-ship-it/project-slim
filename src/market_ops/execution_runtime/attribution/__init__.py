"""E10.2 Phase 4 — Attribution Layer.

Unified attribution data collection across multiple platforms
(Adjust, AppsFlyer). Provides normalized metrics for the
E10.1 Runtime FeedbackLoop.

Modules:
  - base_tracker: AttributionTracker ABC + AttributionMetrics
  - adjust_adapter: Adjust reporting API adapter
  - appsflyer_adapter: AppsFlyer reporting API adapter
  - metric_normalizer: Cross-platform field normalization
  - performance_collector: Multi-source data aggregation
  - exceptions: Attribution-specific error types
"""

from .base_tracker import AttributionTracker, AttributionMetrics
from .adjust_adapter import AdjustTracker, AdjustConfig
from .appsflyer_adapter import AppsFlyerTracker, AppsFlyerConfig
from .metric_normalizer import MetricNormalizer
from .performance_collector import PerformanceCollector
from .exceptions import (
    AttributionError,
    AttributionAuthError,
    AttributionRateLimitError,
    AttributionTimeoutError,
    AttributionDataError,
    AttributionUnavailableError,
)

__all__ = [
    "AttributionTracker",
    "AttributionMetrics",
    "AdjustTracker",
    "AdjustConfig",
    "AppsFlyerTracker",
    "AppsFlyerConfig",
    "MetricNormalizer",
    "PerformanceCollector",
    "AttributionError",
    "AttributionAuthError",
    "AttributionRateLimitError",
    "AttributionTimeoutError",
    "AttributionDataError",
    "AttributionUnavailableError",
]