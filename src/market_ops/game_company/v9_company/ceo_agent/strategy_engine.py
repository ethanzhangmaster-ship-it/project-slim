from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class StrategyType(Enum):
    GROWTH = "growth"
    EFFICIENCY = "efficiency"
    INNOVATION = "innovation"
    DEFENSE = "defense"


@dataclass
class MarketPosition:
    segment: str = "midcore"
    market_share: float = 0.05
    competitive_strength: float = 0.6
    brand_recognition: float = 0.4
    user_sentiment: float = 0.75

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment": self.segment,
            "market_share": self.market_share,
            "competitive_strength": self.competitive_strength,
            "brand_recognition": self.brand_recognition,
            "user_sentiment": self.user_sentiment,
        }


@dataclass
class StrategicInitiative:
    initiative_id: str
    name: str
    strategy_type: StrategyType
    description: str = ""
    target_metrics: Dict[str, float] = field(default_factory=dict)
    timeline_weeks: int = 12
    status: str = "planned"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initiative_id": self.initiative_id,
            "name": self.name,
            "strategy_type": self.strategy_type.value,
            "description": self.description,
            "target_metrics": self.target_metrics,
            "timeline_weeks": self.timeline_weeks,
            "status": self.status,
        }


@dataclass
class Strategy:
    strategy_id: str
    name: str
    strategy_type: StrategyType
    description: str = ""
    market_position: Optional[MarketPosition] = None
    initiatives: List[StrategicInitiative] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "strategy_type": self.strategy_type.value,
            "description": self.description,
            "market_position": self.market_position.to_dict() if self.market_position else None,
            "initiatives": [i.to_dict() for i in self.initiatives],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class StrategyEngine:
    def __init__(self):
        self._strategies: List[Strategy] = []
        self._current_strategy: Optional[Strategy] = None
        self._market_position: MarketPosition = MarketPosition()

    def formulate_strategy(self, market_data: Dict[str, Any]) -> Strategy:
        strategy_id = f"strategy_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        strategy_type = StrategyType.GROWTH

        initiatives = [
            StrategicInitiative(
                initiative_id=f"init_{strategy_id}_01",
                name="Expand into Tier-1 markets",
                strategy_type=strategy_type,
                description="Localize and UA push in US/UK/JP.",
                target_metrics={"dau": 100000, "revenue": 500000},
                timeline_weeks=16,
            ),
            StrategicInitiative(
                initiative_id=f"init_{strategy_id}_02",
                name="Improve monetization depth",
                strategy_type=StrategyType.EFFICIENCY,
                description="Add battle pass and seasonal offers.",
                target_metrics={"arpu": 3.5, "ltv": 45.0},
                timeline_weeks=8,
            ),
        ]

        strategy = Strategy(
            strategy_id=strategy_id,
            name="Q3 Growth & Efficiency",
            strategy_type=strategy_type,
            description="Balance user growth with monetization improvements.",
            market_position=self._market_position,
            initiatives=initiatives,
        )

        self._strategies.append(strategy)
        self._current_strategy = strategy
        return strategy

    def get_strategy(self) -> Optional[Strategy]:
        return self._current_strategy

    def update_strategy(self, updates: Dict[str, Any]) -> Optional[Strategy]:
        if not self._current_strategy:
            return None

        if "name" in updates:
            self._current_strategy.name = updates["name"]
        if "description" in updates:
            self._current_strategy.description = updates["description"]
        if "strategy_type" in updates:
            self._current_strategy.strategy_type = StrategyType(updates["strategy_type"])

        self._current_strategy.updated_at = datetime.now()
        return self._current_strategy

    def evaluate_strategy_fit(self) -> Dict[str, Any]:
        return {
            "market_fit_score": 0.82,
            "resource_fit_score": 0.75,
            "risk_score": 0.35,
            "recommendation": "Proceed with minor adjustments to resource allocation.",
            "timestamp": datetime.now().isoformat(),
        }

    def generate_initiatives(self) -> List[StrategicInitiative]:
        return [
            StrategicInitiative(
                initiative_id="init_001",
                name="Launch community events",
                strategy_type=StrategyType.INNOVATION,
                description="Weekly tournaments and creator program.",
                target_metrics={"engagement": 0.35, "retention_d7": 0.22},
                timeline_weeks=6,
            ),
            StrategicInitiative(
                initiative_id="init_002",
                name="Defend core user base",
                strategy_type=StrategyType.DEFENSE,
                description="Anti-churn emails and win-back offers.",
                target_metrics={"churn_rate": 0.05, "win_back_rate": 0.12},
                timeline_weeks=4,
            ),
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_strategies": len(self._strategies),
            "current_strategy_id": self._current_strategy.strategy_id if self._current_strategy else None,
            "total_initiatives": sum(len(s.initiatives) for s in self._strategies),
            "market_share": self._market_position.market_share,
        }
