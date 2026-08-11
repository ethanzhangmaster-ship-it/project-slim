"""
E15.2.3 — Revenue Provider Contract

Unified revenue data across all sources (MAX, AdMob, App Store, Google Play).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RevenueRecord:
    """Standardized daily revenue breakdown."""
    game_id: str
    date: str              # "2026-07-24"
    iaa: float = 0.0       # In-app advertising revenue
    iap: float = 0.0       # In-app purchase revenue
    total: float = 0.0
    currency: str = "USD"
    country: str = ""
    platform: str = ""
    source: str = ""       # "max" | "admob" | "app_store" | "google_play"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.total == 0.0:
            self.total = self.iaa + self.iap


class RevenueProvider(ABC):
    """Unified revenue data interface.

    Hides MAX/AdMob/Store-specific data models behind a single contract.
    """

    name: str = "revenue"

    @abstractmethod
    def get_daily_revenue(self, game_id: str, date: str,
                          country: str = "",
                          platform: str = "") -> RevenueRecord:
        """Get daily revenue breakdown for a game."""
        ...

    @abstractmethod
    def get_revenue_range(self, game_id: str, start_date: str,
                          end_date: str) -> List[RevenueRecord]:
        """Get revenue for a date range."""
        ...

    @abstractmethod
    def get_ecpm_trend(self, game_id: str, ad_type: str = "rewarded",
                       days: int = 7) -> List[Dict[str, Any]]:
        """Get eCPM trend for analysis."""
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check revenue source connectivity."""
        ...


__all__ = ["RevenueProvider", "RevenueRecord"]
