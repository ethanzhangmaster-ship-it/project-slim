from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MarketStatus(Enum):
    UNEXPLORED = "unexplored"
    TESTING = "testing"
    SCALING = "scaling"
    MATURE = "mature"
    EXITING = "exiting"


@dataclass
class Market:
    market_id: str
    country_code: str
    language: str
    status: MarketStatus
    market_size_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_id": self.market_id,
            "country_code": self.country_code,
            "language": self.language,
            "status": self.status.value,
            "market_size_usd": self.market_size_usd,
        }


@dataclass
class MarketOpportunity:
    opportunity_id: str
    market_id: str
    score: float
    rationale: str
    estimated_cac: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "market_id": self.market_id,
            "score": self.score,
            "rationale": self.rationale,
            "estimated_cac": self.estimated_cac,
        }


@dataclass
class MarketEntry:
    market_id: str
    entry_date: datetime
    budget: float
    localization_required: bool
    channels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_id": self.market_id,
            "entry_date": self.entry_date.isoformat(),
            "budget": self.budget,
            "localization_required": self.localization_required,
            "channels": self.channels,
        }


class MarketStrategy:
    def __init__(self):
        self._markets: Dict[str, Market] = {}
        self._entries: Dict[str, MarketEntry] = {}

    def analyze_markets(self) -> List[Market]:
        return [
            Market("m1", "US", "en", MarketStatus.MATURE, 5000000000.0),
            Market("m2", "JP", "ja", MarketStatus.SCALING, 3200000000.0),
            Market("m3", "KR", "ko", MarketStatus.TESTING, 1800000000.0),
            Market("m4", "BR", "pt", MarketStatus.UNEXPLORED, 900000000.0),
            Market("m5", "DE", "de", MarketStatus.MATURE, 2100000000.0),
        ]

    def get_market_opportunities(self) -> List[MarketOpportunity]:
        return [
            MarketOpportunity("o1", "m4", 85.0, "High mobile penetration, low competition", 1.20),
            MarketOpportunity("o2", "m3", 78.0, "Strong gaming culture, favorable CPI", 2.50),
            MarketOpportunity("o3", "m2", 72.0, "High ARPU but saturated genre", 4.80),
        ]

    def enter_market(self, market_id: str) -> Optional[MarketEntry]:
        entry = MarketEntry(
            market_id=market_id,
            entry_date=datetime.now(),
            budget=100000.0,
            localization_required=True,
            channels=["paid_social", "aso", "influencer"],
        )
        self._entries[market_id] = entry
        return entry

    def exit_market(self, market_id: str) -> bool:
        if market_id in self._markets:
            self._markets[market_id].status = MarketStatus.EXITING
            return True
        return False

    def get_market_strategy(self) -> Dict[str, Any]:
        return {
            "priority_markets": ["US", "JP", "KR"],
            "expansion_mode": "test_then_scale",
            "localization_strategy": "full_localization_for_top3",
            "budget_allocation": {"mature": 0.5, "scaling": 0.3, "testing": 0.2},
        }

    def get_stats(self) -> Dict[str, Any]:
        markets = self.analyze_markets()
        status_counts = {s.value: 0 for s in MarketStatus}
        for m in markets:
            status_counts[m.status.value] += 1
        return {
            "total_markets": len(markets),
            "status_distribution": status_counts,
            "active_entries": len(self._entries),
            "total_addressable_market": round(sum(m.market_size_usd for m in markets), 2),
        }