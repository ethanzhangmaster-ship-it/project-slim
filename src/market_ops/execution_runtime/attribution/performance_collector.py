"""E10.2 Phase 4 — Performance Collector.

Aggregates campaign performance data from multiple attribution
sources into a unified PerformanceSnapshot. This is the central
orchestrator that bridges attribution data with the E10.1
Runtime feedback loop.

Flow:
    Campaign ID
        │
        ▼
    fetch from Adjust
        │
        ▼
    fetch from AppsFlyer
        │
        ▼
    normalize & merge
        │
        ▼
    PerformanceSnapshot
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.schemas import PerformanceSnapshot
from market_ops.execution_runtime.attribution.base_tracker import (
    AttributionTracker,
    AttributionMetrics,
)
from market_ops.execution_runtime.attribution.metric_normalizer import MetricNormalizer


class PerformanceCollector:
    """Collects and merges multi-platform attribution data.

    Queries all configured attribution trackers and merges
    their results into a single PerformanceSnapshot for
    the FeedbackLoop.

    Args:
        trackers: Dict of source_name → AttributionTracker.
        normalizer: MetricNormalizer instance.

    Usage:
        collector = PerformanceCollector({
            "adjust": AdjustTracker(),
            "appsflyer": AppsFlyerTracker(),
        })
        snapshot = collector.collect("camp_001", "2024-01-01", "2024-01-07")
    """

    def __init__(
        self,
        trackers: dict[str, AttributionTracker] | None = None,
        normalizer: MetricNormalizer | None = None,
    ) -> None:
        self._trackers: dict[str, AttributionTracker] = trackers or {}
        self._normalizer = normalizer or MetricNormalizer()

    def collect(
        self,
        campaign_id: str,
        start_date: str = "",
        end_date: str = "",
        task_id: str = "",
    ) -> PerformanceSnapshot:
        """Collect and merge attribution data from all sources.

        Args:
            campaign_id: Platform campaign ID.
            start_date: ISO date string (YYYY-MM-DD).
            end_date: ISO date string (YYYY-MM-DD).
            task_id: Optional ExecutionTask ID for correlation.

        Returns:
            PerformanceSnapshot with aggregated metrics.
        """
        all_metrics: list[AttributionMetrics] = []

        for source_name, tracker in self._trackers.items():
            try:
                metrics = tracker.get_campaign_metrics(
                    campaign_id, start_date, end_date
                )
                all_metrics.append(metrics)
            except Exception:
                continue  # Skip failed sources

        if not all_metrics:
            return PerformanceSnapshot(
                task_id=task_id,
                status="NO_DATA",
            )

        merged = self._normalizer.merge_metrics(all_metrics)

        return self._to_snapshot(merged, task_id)

    def collect_from_single(
        self,
        tracker: AttributionTracker,
        campaign_id: str,
        start_date: str = "",
        end_date: str = "",
        task_id: str = "",
    ) -> PerformanceSnapshot:
        """Collect from a single attribution source.

        Args:
            tracker: Single AttributionTracker instance.
            campaign_id: Platform campaign ID.
            start_date: ISO date string.
            end_date: ISO date string.
            task_id: Optional ExecutionTask ID.

        Returns:
            PerformanceSnapshot.
        """
        metrics = tracker.get_campaign_metrics(campaign_id, start_date, end_date)
        return self._to_snapshot(metrics, task_id)

    def _to_snapshot(self, metrics: AttributionMetrics, task_id: str) -> PerformanceSnapshot:
        """Convert AttributionMetrics to PerformanceSnapshot."""
        return PerformanceSnapshot(
            task_id=task_id,
            impressions=metrics.impressions,
            clicks=metrics.clicks,
            conversions=metrics.installs,
            spend=metrics.spend,
            revenue=metrics.revenue_d7,
            roas=metrics.roi_d7,
            ctr=metrics.ctr,
            cvr=metrics.cvr,
            status="COMPLETED",
        )

    def add_tracker(self, source_name: str, tracker: AttributionTracker) -> None:
        """Register a new attribution tracker."""
        self._trackers[source_name] = tracker

    def remove_tracker(self, source_name: str) -> None:
        """Remove an attribution tracker."""
        self._trackers.pop(source_name, None)

    @property
    def tracker_count(self) -> int:
        return len(self._trackers)

    @property
    def source_names(self) -> list[str]:
        return list(self._trackers.keys())