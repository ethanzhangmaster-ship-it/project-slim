"""Level generation module for autonomous product studio."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import random
import uuid


@dataclass
class Level:
    """Represents a game level."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    level_number: int = 0
    name: str = ""
    difficulty: float = 0.0
    theme: str = ""
    objectives: List[str] = field(default_factory=list)
    enemies: List[str] = field(default_factory=list)
    rewards: Dict[str, float] = field(default_factory=dict)
    estimated_duration_minutes: float = 0.0
    layout_seed: int = 0


class LevelGenerator:
    """Generates and manages game levels."""

    THEMES = ["Forest", "Desert", "Ice", "Volcano", "City", "Space", "Underwater", "Dungeon"]
    ENEMY_POOL = ["Grunt", "Archer", "Mage", "Tank", "Assassin", "Boss", "Swarm", "Trap"]
    OBJECTIVES = ["defeat_all", "survive", "collect", "escort", "timed_run", "boss_fight"]

    def __init__(self):
        self._levels: Dict[str, Level] = {}
        self._level_list: List[Level] = []

    def generate_levels(self, count: int) -> List[Level]:
        """Generate a batch of levels."""
        start = len(self._level_list) + 1
        generated: List[Level] = []
        for i in range(count):
            level_num = start + i
            difficulty = min(1.0, round(0.1 + (level_num * 0.05) + random.uniform(-0.05, 0.05), 2))
            theme = random.choice(self.THEMES)
            level = Level(
                level_number=level_num,
                name=f"{theme} Level {level_num}",
                difficulty=difficulty,
                theme=theme,
                objectives=[random.choice(self.OBJECTIVES) for _ in range(random.randint(1, 3))],
                enemies=[random.choice(self.ENEMY_POOL) for _ in range(random.randint(2, 6))],
                rewards={
                    "xp": round(100 * difficulty, 2),
                    "gold": round(50 * difficulty, 2),
                    "loot_chance": round(difficulty * 0.8, 2),
                },
                estimated_duration_minutes=round(random.uniform(3, 15), 1),
                layout_seed=random.randint(1, 1_000_000),
            )
            self._levels[level.id] = level
            self._level_list.append(level)
            generated.append(level)
        return generated

    def get_level(self, level_id: str) -> Level | None:
        """Retrieve a level by its ID."""
        return self._levels.get(level_id)

    def adjust_difficulty(self, level_id: str, target: float) -> Dict[str, Any]:
        """Adjust a level's difficulty toward a target value."""
        level = self._levels.get(level_id)
        if level is None:
            return {"error": "Level not found", "level_id": level_id}
        old_difficulty = level.difficulty
        new_difficulty = round(max(0.0, min(1.0, target)), 2)
        level.difficulty = new_difficulty
        level.rewards["xp"] = round(100 * new_difficulty, 2)
        level.rewards["gold"] = round(50 * new_difficulty, 2)
        level.rewards["loot_chance"] = round(new_difficulty * 0.8, 2)
        return {
            "level_id": level_id,
            "old_difficulty": old_difficulty,
            "new_difficulty": new_difficulty,
            "adjusted": True,
        }
