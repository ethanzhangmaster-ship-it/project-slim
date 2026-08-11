"""Autonomous Product Studio package.

Exports all core classes for idea generation, game design, economy architecture,
level generation, prototype building, playtesting, and product management.
"""

from .idea_generator import IdeaGenerator, GameIdea, Opportunity
from .game_designer import GameDesigner, GameDesignDocument, CoreLoop, Mechanics
from .economy_architect import EconomyArchitect, Currency, RewardLoop, EconomyModel
from .level_generator import LevelGenerator, Level
from .prototype_builder import PrototypeBuilder, Feature, EffortEstimate
from .playtest_agent import PlaytestAgent, PlaySession, Feedback, Issue
from .product_manager import ProductManager, Milestone, ProductPackage

__all__ = [
    # Idea generation
    "IdeaGenerator",
    "GameIdea",
    "Opportunity",
    # Game design
    "GameDesigner",
    "GameDesignDocument",
    "CoreLoop",
    "Mechanics",
    # Economy
    "EconomyArchitect",
    "Currency",
    "RewardLoop",
    "EconomyModel",
    # Levels
    "LevelGenerator",
    "Level",
    # Prototype
    "PrototypeBuilder",
    "Feature",
    "EffortEstimate",
    # Playtest
    "PlaytestAgent",
    "PlaySession",
    "Feedback",
    "Issue",
    # Product management
    "ProductManager",
    "Milestone",
    "ProductPackage",
]
