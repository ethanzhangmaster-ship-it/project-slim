from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class UnityProject:
    project_id: str
    name: str
    scenes: List[str] = field(default_factory=list)
    scripts: List[str] = field(default_factory=list)
    ui_elements: List[str] = field(default_factory=list)
    economy_config: Dict[str, Any] = field(default_factory=dict)
    plugins: List[str] = field(default_factory=list)
    build_status: str = "pending"


class UnityAgent:
    def __init__(self):
        self.projects: Dict[str, UnityProject] = {}

    def create_project(self, gdd) -> UnityProject:
        if isinstance(gdd, dict):
            name = gdd.get("game_name", "Game")
            genre = gdd.get("genre", "Casual")
        else:
            name = gdd.game_name
            genre = gdd.genre

        project = UnityProject(
            project_id=f"unity_{hash(name) % 10000:04d}",
            name=name,
            scenes=self._generate_scenes(genre),
            scripts=self._generate_scripts(genre),
            ui_elements=self._generate_ui(genre),
            economy_config=self._generate_economy_config(genre),
            plugins=self._generate_plugins(),
            build_status="created",
        )

        self.projects[project.project_id] = project
        return project

    def _generate_scenes(self, genre: str) -> List[str]:
        base_scenes = ["MainMenu", "Gameplay", "Settings", "Shop"]
        
        if "Merge" in genre:
            base_scenes.append("MergeBoard")
        if "Decoration" in genre:
            base_scenes.append("DecorationMode")
        
        return base_scenes

    def _generate_scripts(self, genre: str) -> List[str]:
        base_scripts = ["GameManager.cs", "UIManager.cs", "AudioManager.cs"]
        
        if "Merge" in genre:
            base_scripts.extend(["MergeManager.cs", "ItemSystem.cs"])
        if "Decoration" in genre:
            base_scripts.extend(["DecorationManager.cs", "PlacementSystem.cs"])
        
        base_scripts.extend(["EconomyManager.cs", "SaveSystem.cs", "AnalyticsManager.cs"])
        
        return base_scripts

    def _generate_ui(self, genre: str) -> List[str]:
        return [
            "HUD", "Inventory", "CurrencyDisplay", "QuestLog",
            "SettingsPanel", "ShopPanel", "DailyRewards",
        ]

    def _generate_economy_config(self, genre: str) -> Dict[str, Any]:
        return {
            "currencies": ["Coins", "Gems"],
            "resources": ["Energy"],
            "max_energy": 30,
            "energy_regen_time": 180,
        }

    def _generate_plugins(self) -> List[str]:
        return [
            "Unity Ads", "Firebase Analytics", "Adjust",
            "Unity IAP", "Push Notifications",
        ]

    def create_project_demo(self) -> UnityProject:
        gdd = {"game_name": "Cozy Witch Garden", "genre": "Merge + Decoration"}
        return self.create_project(gdd)
