"""Idea generation module for autonomous product studio."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import random
import uuid


@dataclass
class GameIdea:
    """Represents a generated game idea."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    genre: str = ""
    target_platform: str = ""
    core_hook: str = ""
    estimated_market_potential: float = 0.0
    risk_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class Opportunity:
    """Market opportunity data."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    market_segment: str = ""
    trend: str = ""
    audience_size: int = 0
    competition_level: str = "medium"
    monetization_potential: float = 0.0


class IdeaGenerator:
    """Generates and evaluates game ideas based on market opportunities."""

    GENRES = ["RPG", "Strategy", "Puzzle", "Action", "Simulation", "Roguelike", "Idle"]
    PLATFORMS = ["Mobile", "PC", "Console", "Web", "VR"]
    HOOKS = [
        "innovative combat system",
        "procedural storytelling",
        "social co-op mechanics",
        "AI-driven NPCs",
        "cross-platform progression",
        "player-created content",
    ]

    def __init__(self):
        self._ideas: List[GameIdea] = []
        self._opportunity: Opportunity | None = None

    def generate(self, opportunity: Opportunity) -> GameIdea:
        """Generate a game idea tailored to a market opportunity."""
        self._opportunity = opportunity
        idea = GameIdea(
            title=f"Project {random.choice(['Nova', 'Apex', 'Zenith', 'Echo', 'Pulse'])} {random.randint(1, 99)}",
            genre=random.choice(self.GENRES),
            target_platform=random.choice(self.PLATFORMS),
            core_hook=random.choice(self.HOOKS),
            estimated_market_potential=round(random.uniform(0.5, 1.0) * opportunity.monetization_potential, 2),
            risk_score=round(random.uniform(0.1, 0.9), 2),
            tags=[opportunity.market_segment, opportunity.trend],
            description=f"A {random.choice(self.GENRES).lower()} game leveraging {opportunity.trend} for {opportunity.market_segment}.",
        )
        self._ideas.append(idea)
        return idea

    def brainstorm(self, count: int) -> List[GameIdea]:
        """Brainstorm multiple game ideas."""
        if self._opportunity is None:
            self._opportunity = Opportunity(
                market_segment="general",
                trend="emerging",
                audience_size=1_000_000,
                monetization_potential=0.7,
            )
        results: List[GameIdea] = []
        for _ in range(count):
            results.append(self.generate(self._opportunity))
        return results

    def evaluate_idea(self, idea: GameIdea) -> Dict[str, Any]:
        """Evaluate a game idea and return scoring metrics."""
        innovation = round(random.uniform(0.5, 1.0), 2)
        feasibility = round(1.0 - idea.risk_score, 2)
        market_fit = round(idea.estimated_market_potential, 2)
        overall = round((innovation + feasibility + market_fit) / 3, 2)
        return {
            "idea_id": idea.id,
            "innovation_score": innovation,
            "feasibility_score": feasibility,
            "market_fit_score": market_fit,
            "overall_score": overall,
            "recommendation": "proceed" if overall >= 0.7 else "revise" if overall >= 0.5 else "reject",
        }
