"""E10.2 Phase 4 — Base Attribution Interface.

Defines the unified AttributionTracker ABC and the shared
AttributionMetrics schema. All attribution platforms (Adjust,
AppsFlyer, etc.) must implement this interface.

Architecture:
    Campaign ID
        │
        ▼
    AttributionTracker.get_campaign_metrics()
        │
        ▼
    AttributionMetrics (normalized)
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AttributionMetrics:
    """Unified attribution metrics across all platforms.

    Normalized representation of campaign performance data
    regardless of source (Adjust, AppsFlyer, etc.).

    All monetary values in USD.
    """

    campaign_id: str = ""

    # Spend & engagement
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0

    # Conversions
    installs: int = 0
    conversions: int = 0

    # Revenue (D1/D7/D30 windows)
    revenue_d1: float = 0.0
    revenue_d7: float = 0.0
    revenue_d30: float = 0.0

    # Derived metrics
    roi_d7: float = 0.0
    roi_d30: float = 0.0
    cpi: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0

    # Metadata
    source: str = ""
    date_range: dict[str, str] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)

    # Identity
    metric_id: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id:
            self.metric_id = str(uuid.uuid4())
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()
        # Auto-calculate derived metrics if not explicitly set
        if self.spend > 0 and self.roi_d7 == 0.0:
            self.roi_d7 = round(self.revenue_d7 / self.spend, 4)
        if self.spend > 0 and self.roi_d30 == 0.0:
            self.roi_d30 = round(self.revenue_d30 / self.spend, 4)
        if self.installs > 0 and self.cpi == 0.0:
            self.cpi = round(self.spend / self.installs, 2)
        if self.impressions > 0 and self.ctr == 0.0:
            self.ctr = round(self.clicks / self.impressions, 4)
        if self.clicks > 0 and self.cvr == 0.0:
            self.cvr = round(self.installs / self.clicks, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "campaign_id": self.campaign_id,
            "spend": round(self.spend, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "conversions": self.conversions,
            "revenue_d1": round(self.revenue_d1, 2),
            "revenue_d7": round(self.revenue_d7, 2),
            "revenue_d30": round(self.revenue_d30, 2),
            "roi_d7": round(self.roi_d7, 4),
            "roi_d30": round(self.roi_d30, 4),
            "cpi": round(self.cpi, 2),
            "ctr": round(self.ctr, 4),
            "cvr": round(self.cvr, 4),
            "source": self.source,
            "date_range": self.date_range,
            "recorded_at": self.recorded_at,
        }


class AttributionTracker(ABC):
    """Abstract base for all attribution platform adapters.

    Every attribution platform (Adjust, AppsFlyer, etc.)
    must implement this interface to provide unified
    campaign metrics.

    Usage:
        tracker = AdjustTracker(config)
        metrics = tracker.get_campaign_metrics("camp_001", "2024-01-01", "2024-01-07")
    """

    @abstractmethod
    def get_campaign_metrics(
        self,
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> AttributionMetrics:
        """Fetch attribution metrics for a campaign.

        Args:
            campaign_id: Platform campaign ID.
            start_date: ISO date string (YYYY-MM-DD).
            end_date: ISO date string (YYYY-MM-DD).

        Returns:
            AttributionMetrics with normalized performance data.
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Attribution source identifier (e.g., 'adjust', 'appsflyer')."""
        ...