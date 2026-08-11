"""E15.1.1 — catalog: fleet registry, product profile, AI scheduler."""
from operation.publishing_factory.catalog.product_profile import (
    GameProduct, GameStatus, Platform, Genre, Monetization,
)
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.fleet_manager import (
    FleetManager, FleetTask, FleetScanReport, TaskType,
)

__all__ = [
    "GameProduct", "GameStatus", "Platform", "Genre", "Monetization",
    "GameRegistry", "FleetManager", "FleetTask", "FleetScanReport", "TaskType",
]
