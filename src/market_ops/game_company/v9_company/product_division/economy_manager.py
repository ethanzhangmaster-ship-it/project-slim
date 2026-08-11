from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class EconomyMetrics:
    product_id: str
    currency_inflation_rate: float
    sink_to_faucet_ratio: float
    avg_wallet_size: float
    top_spenders_pct: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "currency_inflation_rate": self.currency_inflation_rate,
            "sink_to_faucet_ratio": self.sink_to_faucet_ratio,
            "avg_wallet_size": self.avg_wallet_size,
            "top_spenders_pct": self.top_spenders_pct,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CurrencyBalance:
    currency_name: str
    daily_faucet: float
    daily_sink: float
    reserve: float
    target_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "currency_name": self.currency_name,
            "daily_faucet": self.daily_faucet,
            "daily_sink": self.daily_sink,
            "reserve": self.reserve,
            "target_ratio": self.target_ratio,
        }


@dataclass
class RewardAdjustment:
    reward_id: str
    old_value: float
    new_value: float
    reason: str
    applied_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reward_id": self.reward_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "applied_at": self.applied_at.isoformat(),
        }


class EconomyManager:
    def __init__(self):
        self._currencies: Dict[str, CurrencyBalance] = {}
        self._adjustments: List[RewardAdjustment] = []

    def analyze_economy(self) -> List[EconomyMetrics]:
        return [
            EconomyMetrics("p1", 0.02, 1.15, 1250.0, 2.5),
            EconomyMetrics("p2", 0.08, 0.85, 890.0, 3.2),
            EconomyMetrics("p3", 0.05, 1.02, 560.0, 1.8),
        ]

    def balance_currency(self, currency_name: str) -> CurrencyBalance:
        balanced = CurrencyBalance(
            currency_name=currency_name,
            daily_faucet=10000.0,
            daily_sink=10500.0,
            reserve=500000.0,
            target_ratio=1.05,
        )
        self._currencies[currency_name] = balanced
        return balanced

    def adjust_rewards(self, reward_id: str, new_value: float, reason: str) -> RewardAdjustment:
        adjustment = RewardAdjustment(
            reward_id=reward_id,
            old_value=new_value * 0.9,
            new_value=new_value,
            reason=reason,
        )
        self._adjustments.append(adjustment)
        return adjustment

    def get_economy_metrics(self) -> List[EconomyMetrics]:
        return self.analyze_economy()

    def predict_economy_health(self) -> Dict[str, Any]:
        return {
            "health_score": 78.5,
            "risk_level": "medium",
            "projected_inflation_30d": 0.04,
            "recommended_actions": [
                "increase_gem_sink_in_shop",
                "reduce_daily_bonus_by_10pct",
            ],
        }

    def get_stats(self) -> Dict[str, Any]:
        metrics = self.analyze_economy()
        return {
            "total_currencies_tracked": len(self._currencies),
            "total_adjustments": len(self._adjustments),
            "avg_inflation_rate": round(sum(m.currency_inflation_rate for m in metrics) / len(metrics), 4) if metrics else 0,
            "avg_sink_faucet_ratio": round(sum(m.sink_to_faucet_ratio for m in metrics) / len(metrics), 4) if metrics else 0,
        }