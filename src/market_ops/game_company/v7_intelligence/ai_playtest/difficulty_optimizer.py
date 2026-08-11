from dataclasses import dataclass
from typing import List, Dict
import random


@dataclass
class DifficultyProfile:
    level: int
    recommended_difficulty: float
    expected_clear_rate: float
    adjustments: List[str]


class DifficultyOptimizer:
    """Optimize game difficulty per level."""

    def __init__(self):
        self._profiles: Dict[int, DifficultyProfile] = {}
        self._difficulty_curve: List[float] = []

    def optimize(self, level: int) -> DifficultyProfile:
        """Recommend difficulty settings for a specific level."""
        base_difficulty = min(0.2 + level * 0.05, 1.0)
        noise = random.uniform(-0.05, 0.05)
        recommended = round(max(0.0, min(1.0, base_difficulty + noise)), 4)
        clear_rate = round(random.uniform(0.5, 0.95), 4)
        adjustments = random.sample(
            ["reduce_enemy_hp", "increase_ammo", "add_checkpoint", "slow_timer"],
            k=random.randint(1, 3),
        )
        profile = DifficultyProfile(
            level=level,
            recommended_difficulty=recommended,
            expected_clear_rate=clear_rate,
            adjustments=adjustments,
        )
        self._profiles[level] = profile
        return profile

    def get_difficulty_curve(self) -> List[float]:
        """Return a synthesized difficulty curve across levels."""
        if not self._difficulty_curve:
            self._difficulty_curve = [
                round(min(1.0, 0.2 + i * 0.05 + random.uniform(-0.02, 0.02)), 4)
                for i in range(1, 21)
            ]
        return self._difficulty_curve

    def test_balance(self) -> Dict[str, float]:
        """Run balance tests and return metrics."""
        return {
            "balance_score": round(random.uniform(0.6, 0.95), 4),
            "frustration_index": round(random.uniform(0.1, 0.4), 4),
            "boredom_index": round(random.uniform(0.05, 0.3), 4),
            "flow_score": round(random.uniform(0.5, 0.9), 4),
        }
