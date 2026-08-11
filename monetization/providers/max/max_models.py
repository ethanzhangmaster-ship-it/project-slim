"""
E14.3.2 — Module 2: MAX Adapter Models
=======================================

Data contracts for the AppLovin MAX adapter. These describe the *MAX world*
(operations, floors, waterfall order, revenue metrics, health) and are the
vocabulary the mapper (max_mapper.py) translates the internal `Change` into.

The simulated backend (`MaxGameState`) is what the MockMaxClient mutates, so
apply/rollback behave like a real MAX backend without any network call. The
RealMaxClient (max_client.py) is the future network seam.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MaxOperationType(str, Enum):
    UPDATE_BID_FLOOR = "UPDATE_BID_FLOOR"
    UPDATE_WATERFALL_PRIORITY = "UPDATE_WATERFALL_PRIORITY"
    READ_REVENUE = "READ_REVENUE"


@dataclass
class MaxOperation:
    """A concrete, MAX-shaped operation derived from an internal Change."""
    operation: str
    app_id: str
    country: str = ""
    ad_unit: str = ""
    network: str = ""
    placement: str = ""
    date: str = ""
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    multiplier: Optional[float] = None          # new/old for bid floor
    old_order: List[str] = field(default_factory=list)
    new_order: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RevenueMetrics:
    """Ad revenue observation for one (date, geo, placement) cell."""
    date: str
    geo: str
    placement: str
    impressions: int
    revenue: float
    ecpm: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MaxHealth:
    status: str                 # healthy | degraded | down
    credential_valid: bool
    api_available: bool

    def to_dict(self) -> dict:
        return asdict(self)


# Simulated MAX backend state (one per game, never shared).
@dataclass
class BidFloor:
    country: str
    ad_unit: str
    floor: float


@dataclass
class MaxGameState:
    app_id: str
    floors: Dict[str, float] = field(default_factory=dict)        # "country|ad_unit" -> floor
    waterfalls: Dict[str, List[str]] = field(default_factory=dict)  # placement -> network order
    revenue: Dict[str, RevenueMetrics] = field(default_factory=dict)  # "date|geo|placement"

    @staticmethod
    def fkey(country: str, ad_unit: str) -> str:
        return f"{country}|{ad_unit}"

    def get_floor(self, country: str, ad_unit: str) -> Optional[float]:
        return self.floors.get(self.fkey(country, ad_unit))

    def set_floor(self, country: str, ad_unit: str, floor: float) -> None:
        self.floors[self.fkey(country, ad_unit)] = floor

    def get_waterfall(self, placement: str) -> List[str]:
        return list(self.waterfalls.get(placement, []))

    def set_waterfall(self, placement: str, order: List[str]) -> None:
        self.waterfalls[placement] = list(order)

    def set_revenue(self, rm: RevenueMetrics) -> None:
        self.revenue[f"{rm.date}|{rm.geo}|{rm.placement}"] = rm


class MaxMappingError(ValueError):
    """Raised when a Change cannot be mapped to a MAX operation (e.g. bad geo)."""
