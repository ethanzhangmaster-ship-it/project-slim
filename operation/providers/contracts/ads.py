"""
E15.2.3 — Ads Provider Contract

Abstract interface for ad network operations.
monetization_ops calls this, never imports max_sdk or admob directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AdUnitSpec:
    """Specification for creating/updating an ad unit."""
    game_id: str
    platform: str           # "android" | "ios"
    ad_type: str            # "rewarded" | "interstitial" | "banner" | "app_open"
    network: str            # "max" | "admob" | "levelplay"
    ad_unit_id: Optional[str] = None
    placement_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WaterfallConfig:
    """Waterfall network ordering configuration."""
    ad_unit_id: str
    networks: List[Dict[str, Any]]  # [{network, priority, floor, bidding}]
    country: str = "US"


@dataclass
class AdMetrics:
    """Standardized ad performance metrics."""
    ad_unit_id: str
    date: str
    impressions: int = 0
    revenue: float = 0.0
    ecpm: float = 0.0
    fill_rate: float = 0.0
    clicks: int = 0
    network: str = ""
    country: str = ""
    platform: str = ""


class AdsProvider(ABC):
    """Provider contract for ad network operations.

    monetization_ops calls this interface.
    Real implementations (MaxAdsProvider, AdMobAdsProvider) live in live/.
    """

    name: str = "ads"

    @abstractmethod
    def create_ad_unit(self, spec: AdUnitSpec) -> Dict[str, Any]:
        """Create an ad unit on the network. Returns {success, ad_unit_id, ...}."""
        ...

    @abstractmethod
    def update_waterfall(self, config: WaterfallConfig) -> Dict[str, Any]:
        """Update waterfall ordering for an ad unit."""
        ...

    @abstractmethod
    def update_bid_floor(self, ad_unit_id: str, floor: float,
                         ad_type: str = "rewarded") -> Dict[str, Any]:
        """Set the bid floor for an ad unit."""
        ...

    @abstractmethod
    def get_ad_metrics(self, ad_unit_id: str, date_range: str = "7d",
                       country: str = "US") -> List[AdMetrics]:
        """Fetch ad performance metrics."""
        ...

    @abstractmethod
    def list_ad_units(self, game_id: str) -> List[Dict[str, Any]]:
        """List all ad units for a game."""
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check connectivity to ad network."""
        ...


__all__ = ["AdsProvider", "AdUnitSpec", "WaterfallConfig", "AdMetrics"]
