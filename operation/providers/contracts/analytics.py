"""
E15.2.3 — Analytics Provider Contract

User analytics and retention data (Adjust, Firebase, custom).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetentionData:
    """Standardized retention metrics."""
    game_id: str
    date: str
    d1: float = 0.0
    d7: float = 0.0
    d30: float = 0.0
    dau: int = 0
    new_users: int = 0
    sessions: int = 0
    platform: str = ""
    country: str = ""


class AnalyticsProvider(ABC):
    """Provider contract for user analytics and retention."""

    name: str = "analytics"

    @abstractmethod
    def track_event(self, game_id: str, event_name: str,
                    properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Track a user event."""
        ...

    @abstractmethod
    def get_retention(self, game_id: str, date: str,
                      platform: str = "") -> RetentionData:
        """Get retention data for a date."""
        ...

    @abstractmethod
    def get_dau(self, game_id: str, date: str) -> int:
        """Get daily active users."""
        ...

    @abstractmethod
    def get_retention_range(self, game_id: str, start_date: str,
                            end_date: str) -> List[RetentionData]:
        """Get retention data for a date range."""
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check analytics source connectivity."""
        ...


__all__ = ["AnalyticsProvider", "RetentionData"]
