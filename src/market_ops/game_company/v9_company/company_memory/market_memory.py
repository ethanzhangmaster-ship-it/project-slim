from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict
import uuid


@dataclass
class MarketRecord:
    record_id: str
    metric_name: str
    value: float
    recorded_at: datetime = field(default_factory=datetime.now)
    segment: str = "global"

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "recorded_at": self.recorded_at.isoformat(),
            "segment": self.segment,
        }


@dataclass
class MarketTrend:
    trend_id: str
    trend_name: str
    direction: str
    strength: float
    start_date: datetime
    end_date: datetime

    def to_dict(self) -> Dict:
        return {
            "trend_id": self.trend_id,
            "trend_name": self.trend_name,
            "direction": self.direction,
            "strength": self.strength,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }


@dataclass
class CompetitorData:
    data_id: str
    competitor_name: str
    market_share: float
    key_products: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "data_id": self.data_id,
            "competitor_name": self.competitor_name,
            "market_share": self.market_share,
            "key_products": self.key_products,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PlayerBehavior:
    behavior_id: str
    behavior_type: str
    frequency: float
    avg_session_minutes: float
    segment: str = "all"

    def to_dict(self) -> Dict:
        return {
            "behavior_id": self.behavior_id,
            "behavior_type": self.behavior_type,
            "frequency": self.frequency,
            "avg_session_minutes": self.avg_session_minutes,
            "segment": self.segment,
        }


class MarketMemory:
    def __init__(self):
        self._market_data: Dict[str, MarketRecord] = {}
        self._competitors: Dict[str, CompetitorData] = {}
        self._behaviors: Dict[str, PlayerBehavior] = {}

    def record_market_data(self, data: MarketRecord) -> MarketRecord:
        self._market_data[data.record_id] = data
        return data

    def get_market_trends(self) -> List[MarketTrend]:
        return [
            MarketTrend(
                trend_id=str(uuid.uuid4()),
                trend_name="移动端增长",
                direction="up",
                strength=0.85,
                start_date=datetime.now().replace(month=1, day=1),
                end_date=datetime.now(),
            ),
            MarketTrend(
                trend_id=str(uuid.uuid4()),
                trend_name="PC端下滑",
                direction="down",
                strength=0.45,
                start_date=datetime.now().replace(month=1, day=1),
                end_date=datetime.now(),
            ),
        ]

    def get_competitor_data(self) -> List[CompetitorData]:
        if not self._competitors:
            self._competitors = {
                "c1": CompetitorData(
                    data_id="c1",
                    competitor_name="Alpha Games",
                    market_share=22.5,
                    key_products=["War Quest", "Puzzle King"],
                ),
                "c2": CompetitorData(
                    data_id="c2",
                    competitor_name="Beta Studio",
                    market_share=18.0,
                    key_products=["Racing Pro", "Farm World"],
                ),
            }
        return list(self._competitors.values())

    def get_player_behavior(self) -> List[PlayerBehavior]:
        if not self._behaviors:
            self._behaviors = {
                "b1": PlayerBehavior(
                    behavior_id="b1",
                    behavior_type="daily_login",
                    frequency=0.65,
                    avg_session_minutes=35.0,
                    segment="active",
                ),
                "b2": PlayerBehavior(
                    behavior_id="b2",
                    behavior_type="purchase",
                    frequency=0.08,
                    avg_session_minutes=45.0,
                    segment="payer",
                ),
            }
        return list(self._behaviors.values())

    def get_market_insights(self) -> Dict:
        trends = self.get_market_trends()
        competitors = self.get_competitor_data()
        return {
            "trend_count": len(trends),
            "dominant_direction": "up" if sum(1 for t in trends if t.direction == "up") > len(trends) / 2 else "down",
            "top_competitor": max(competitors, key=lambda c: c.market_share).competitor_name if competitors else None,
            "recorded_metrics": len(self._market_data),
        }

    def get_stats(self) -> Dict:
        return {
            "total_market_records": len(self._market_data),
            "competitors_tracked": len(self._competitors),
            "behavior_segments": len(self._behaviors),
        }
