from dataclasses import dataclass, field
from typing import List, Dict
import random


@dataclass
class PlayerBehavior:
    player_id: str
    session_length_minutes: float
    actions_per_session: int
    preferred_mode: str
    spending_usd: float
    social_interactions: int


class PlayerSimulator:
    """Simulate player behaviors for AI playtesting."""

    def __init__(self):
        self._behaviors: List[PlayerBehavior] = []
        self._completion_rate: float = 0.0

    def simulate(self, player_count: int) -> List[PlayerBehavior]:
        """Simulate a cohort of players."""
        self._behaviors = []
        for i in range(player_count):
            behavior = PlayerBehavior(
                player_id=f"player_{i+1:04d}",
                session_length_minutes=round(random.uniform(5.0, 120.0), 2),
                actions_per_session=random.randint(10, 500),
                preferred_mode=random.choice(["solo", "coop", "pvp", "exploration"]),
                spending_usd=round(random.uniform(0.0, 200.0), 2),
                social_interactions=random.randint(0, 50),
            )
            self._behaviors.append(behavior)
        self._completion_rate = round(random.uniform(0.3, 0.95), 4)
        return self._behaviors

    def get_behaviors(self) -> List[PlayerBehavior]:
        """Return simulated player behaviors."""
        return self._behaviors

    def get_completion_rate(self) -> float:
        """Return the level / task completion rate."""
        return self._completion_rate
