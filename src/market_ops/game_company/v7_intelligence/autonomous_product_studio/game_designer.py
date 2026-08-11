"""Game design module for autonomous product studio."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import random
import uuid


@dataclass
class GameDesignDocument:
    """Game Design Document (GDD)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    genre: str = ""
    core_loop: str = ""
    mechanics: List[str] = field(default_factory=list)
    art_direction: str = ""
    narrative_outline: str = ""
    target_audience: str = ""
    platforms: List[str] = field(default_factory=list)
    estimated_playtime_hours: float = 0.0


@dataclass
class CoreLoop:
    """Core gameplay loop definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    steps: List[str] = field(default_factory=list)
    duration_minutes: float = 0.0
    reward_frequency: str = ""


@dataclass
class Mechanics:
    """Game mechanics definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    type: str = ""
    description: str = ""
    complexity: str = "medium"


class GameDesigner:
    """Designs games and produces design documents."""

    def __init__(self):
        self._gdd: GameDesignDocument | None = None
        self._core_loop: CoreLoop | None = None
        self._mechanics: List[Mechanics] = []

    def design_game(self, idea: Any) -> GameDesignDocument:
        """Design a full game based on an idea."""
        title = getattr(idea, "title", "Untitled Game")
        genre = getattr(idea, "genre", "Action")
        self._gdd = GameDesignDocument(
            title=title,
            genre=genre,
            core_loop="Explore → Collect → Upgrade → Challenge",
            mechanics=["progression", "resource_management", "combat"],
            art_direction=f"Stylized {random.choice(['low-poly', 'pixel art', 'realistic', 'cartoon'])}",
            narrative_outline=f"Player journey in a {genre.lower()} world full of discovery.",
            target_audience=getattr(idea, "target_platform", "Mobile") + " players",
            platforms=[getattr(idea, "target_platform", "Mobile")],
            estimated_playtime_hours=round(random.uniform(10, 100), 1),
        )
        return self._gdd

    def create_gdd(self) -> GameDesignDocument:
        """Create or return the current Game Design Document."""
        if self._gdd is None:
            self._gdd = GameDesignDocument(
                title="Untitled Project",
                genre="TBD",
                core_loop="TBD",
            )
        return self._gdd

    def design_core_loop(self) -> CoreLoop:
        """Design the core gameplay loop."""
        self._core_loop = CoreLoop(
            name="Primary Loop",
            steps=[
                "Player enters session",
                "Complete short objectives",
                "Earn rewards and XP",
                "Upgrade character/gear",
                "Face harder challenges",
            ],
            duration_minutes=round(random.uniform(5, 30), 1),
            reward_frequency=random.choice(["per session", "per minute", "per objective"]),
        )
        return self._core_loop

    def design_mechanics(self) -> List[Mechanics]:
        """Design detailed game mechanics."""
        mechanic_types = ["combat", "exploration", "crafting", "social", "economy", "narrative"]
        self._mechanics = [
            Mechanics(
                name=f"{mt.capitalize()} System",
                type=mt,
                description=f"Handles all {mt} interactions in the game.",
                complexity=random.choice(["low", "medium", "high"]),
            )
            for mt in mechanic_types
        ]
        return self._mechanics
