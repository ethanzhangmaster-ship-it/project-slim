from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class LocalizationPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class LocalizationNeed:
    need_id: str
    game_id: str
    market: str
    language: str
    priority: LocalizationPriority
    estimated_cost: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "need_id": self.need_id,
            "game_id": self.game_id,
            "market": self.market,
            "language": self.language,
            "priority": self.priority.value,
            "estimated_cost": self.estimated_cost,
        }


@dataclass
class LocalizationPlan:
    plan_id: str
    game_id: str
    markets: List[str]
    start_date: datetime
    completion_date: datetime
    total_cost: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "game_id": self.game_id,
            "markets": self.markets,
            "start_date": self.start_date.isoformat(),
            "completion_date": self.completion_date.isoformat(),
            "total_cost": self.total_cost,
        }


@dataclass
class LocalizedAsset:
    asset_id: str
    game_id: str
    market: str
    asset_type: str
    url: str
    approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "game_id": self.game_id,
            "market": self.market,
            "asset_type": self.asset_type,
            "url": self.url,
            "approved": self.approved,
        }


class LocalizationManager:
    def __init__(self):
        self._plans: Dict[str, LocalizationPlan] = {}
        self._assets: Dict[str, LocalizedAsset] = {}

    def get_localization_needs(self) -> List[LocalizationNeed]:
        return [
            LocalizationNeed("ln1", "g1", "JP", "ja", LocalizationPriority.CRITICAL, 45000.0),
            LocalizationNeed("ln2", "g1", "KR", "ko", LocalizationPriority.HIGH, 32000.0),
            LocalizationNeed("ln3", "g1", "DE", "de", LocalizationPriority.MEDIUM, 28000.0),
            LocalizationNeed("ln4", "g1", "BR", "pt", LocalizationPriority.MEDIUM, 22000.0),
            LocalizationNeed("ln5", "g1", "FR", "fr", LocalizationPriority.LOW, 25000.0),
        ]

    def plan_localization(self, game_id: str, markets: List[str]) -> LocalizationPlan:
        now = datetime.now()
        plan = LocalizationPlan(
            plan_id=f"lp_{game_id}",
            game_id=game_id,
            markets=markets,
            start_date=now,
            completion_date=now + timedelta(days=60),
            total_cost=len(markets) * 30000.0,
        )
        self._plans[plan.plan_id] = plan
        return plan

    def get_localization_status(self) -> Dict[str, Any]:
        return {
            "in_progress": 2,
            "completed": 5,
            "pending_review": 1,
            "total_games": 3,
            "total_languages_covered": 12,
        }

    def get_localized_assets(self, game_id: str) -> List[LocalizedAsset]:
        assets = [
            LocalizedAsset("a1", game_id, "JP", "store_screenshots", f"/assets/{game_id}/jp/screenshots.zip", True),
            LocalizedAsset("a2", game_id, "JP", "app_description", f"/assets/{game_id}/jp/description.txt", True),
            LocalizedAsset("a3", game_id, "KR", "store_screenshots", f"/assets/{game_id}/kr/screenshots.zip", False),
            LocalizedAsset("a4", game_id, "KR", "app_description", f"/assets/{game_id}/kr/description.txt", True),
        ]
        for a in assets:
            self._assets[a.asset_id] = a
        return assets

    def get_stats(self) -> Dict[str, Any]:
        needs = self.get_localization_needs()
        priority_counts = {p.value: 0 for p in LocalizationPriority}
        for n in needs:
            priority_counts[n.priority.value] += 1
        return {
            "total_needs": len(needs),
            "priority_distribution": priority_counts,
            "active_plans": len(self._plans),
            "total_assets": len(self._assets),
        }