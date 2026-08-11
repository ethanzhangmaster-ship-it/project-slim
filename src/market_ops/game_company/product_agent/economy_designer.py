from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GameEconomy:
    economy_id: str
    currencies: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    progression: Dict[str, Any] = field(default_factory=dict)
    reward_system: Dict[str, Any] = field(default_factory=dict)
    balancing: Dict[str, float] = field(default_factory=dict)


class EconomyDesigner:
    def __init__(self):
        self.economies: Dict[str, GameEconomy] = {}

    def design(self, genre: str, target_audience: str = "Female 25-44", **kwargs) -> GameEconomy:
        target_arpdau = kwargs.get("target_arpdau", None)
        economy = GameEconomy(
            economy_id=f"eco_{hash(genre + target_audience) % 10000:04d}",
            currencies=self._design_currencies(genre),
            resources=self._design_resources(genre),
            progression=self._design_progression(genre),
            reward_system=self._design_rewards(genre),
            balancing=self._design_balancing(target_audience),
        )
        
        if target_arpdau:
            economy.balancing["target_arpdau"] = target_arpdau

        self.economies[economy.economy_id] = economy
        return economy

    def _design_currencies(self, genre: str) -> List[Dict[str, Any]]:
        return [
            {"name": "Coins", "type": "soft", "earn_rate": 10, "spend_rate": 50},
            {"name": "Gems", "type": "hard", "earn_rate": 1, "spend_rate": 100},
        ]

    def _design_resources(self, genre: str) -> List[Dict[str, Any]]:
        resources_map = {
            "Merge + Decoration": [
                {"name": "Energy", "max": 30, "regen_time": 180},
                {"name": "Materials", "type": "crafting"},
                {"name": "Merge Items", "type": "collection"},
            ],
            "Cozy Games": [
                {"name": "Energy", "max": 25, "regen_time": 200},
                {"name": "Seeds", "type": "farming"},
                {"name": "Materials", "type": "crafting"},
            ],
        }
        return resources_map.get(genre, [{"name": "Energy", "max": 30, "regen_time": 180}])

    def _design_progression(self, genre: str) -> Dict[str, Any]:
        return {
            "type": "level_based",
            "max_level": 100,
            "xp_curve": "exponential",
            "rewards_per_level": ["Coins", "Gems", "New Items"],
        }

    def _design_rewards(self, genre: str) -> Dict[str, Any]:
        return {
            "daily_reward": {"days": 7, "increasing": True},
            "achievement_rewards": ["Gems", "Exclusive Items"],
            "event_rewards": ["Limited Items", "Currency Boost"],
        }

    def _design_balancing(self, audience: str) -> Dict[str, float]:
        if "Female" in audience:
            return {"difficulty": 0.3, "reward_multiplier": 1.2, "energy_efficiency": 0.8}
        return {"difficulty": 0.5, "reward_multiplier": 1.0, "energy_efficiency": 1.0}

    def design_demo(self) -> GameEconomy:
        return self.design("Merge + Decoration", "US Female 25-44")
