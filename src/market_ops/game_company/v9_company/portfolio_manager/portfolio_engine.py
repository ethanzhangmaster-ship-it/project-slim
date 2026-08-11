from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class Portfolio:
    games: List[Dict]
    total_value: float
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "games": self.games,
            "total_value": self.total_value,
            "last_updated": self.last_updated,
        }


@dataclass
class PortfolioHealth:
    overall_score: int
    diversification_index: float
    risk_level: str
    growth_trend: str

    def to_dict(self):
        return {
            "overall_score": self.overall_score,
            "diversification_index": self.diversification_index,
            "risk_level": self.risk_level,
            "growth_trend": self.growth_trend,
        }


@dataclass
class PortfolioBalance:
    allocations: Dict[str, float]
    target_allocations: Dict[str, float]
    drift: Dict[str, float]

    def to_dict(self):
        return {
            "allocations": self.allocations,
            "target_allocations": self.target_allocations,
            "drift": self.drift,
        }


class PortfolioEngine:
    def __init__(self):
        self._games: List[Dict] = [
            {"game_id": "g001", "name": "Fantasy Quest", "value": 1200000.0},
            {"game_id": "g002", "name": "Space Raiders", "value": 850000.0},
            {"game_id": "g003", "name": "Puzzle Master", "value": 450000.0},
        ]
        self._health = PortfolioHealth(
            overall_score=78,
            diversification_index=0.72,
            risk_level="medium",
            growth_trend="positive",
        )

    def get_portfolio(self) -> Portfolio:
        total = sum(g["value"] for g in self._games)
        return Portfolio(games=self._games, total_value=total)

    def add_game(self, game: Dict) -> None:
        self._games.append(game)

    def remove_game(self, game_id: str) -> bool:
        original_len = len(self._games)
        self._games = [g for g in self._games if g.get("game_id") != game_id]
        return len(self._games) < original_len

    def get_portfolio_health(self) -> PortfolioHealth:
        return self._health

    def rebalance_portfolio(self) -> PortfolioBalance:
        total = sum(g["value"] for g in self._games)
        allocations = {g["game_id"]: g["value"] / total for g in self._games} if total else {}
        targets = {g["game_id"]: 1.0 / len(self._games) for g in self._games}
        drift = {gid: allocations.get(gid, 0.0) - targets.get(gid, 0.0) for gid in allocations}
        return PortfolioBalance(
            allocations=allocations,
            target_allocations=targets,
            drift=drift,
        )

    def get_stats(self) -> Dict:
        total = sum(g["value"] for g in self._games)
        return {
            "game_count": len(self._games),
            "total_value": total,
            "health": self._health.to_dict(),
        }
