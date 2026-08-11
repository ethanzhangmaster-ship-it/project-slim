from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class BuildResult:
    build_id: str
    platform: str
    status: str = "pending"
    file_path: str = ""
    size_mb: float = 0.0
    build_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class BuildManager:
    def __init__(self):
        self.builds: Dict[str, BuildResult] = {}

    def build(self, project, platform: str = "android") -> BuildResult:
        if isinstance(project, dict):
            name = project.get("name", "project")
            scripts = project.get("scripts", [])
            ui_elements = project.get("ui_elements", [])
        else:
            name = project.name
            scripts = project.scripts
            ui_elements = project.ui_elements
        
        build_result = BuildResult(
            build_id=f"build_{hash(name + platform) % 10000:04d}",
            platform=platform,
            status="success" if len(scripts) >= 3 else "partial",
            file_path=f"{name}_{platform}.apk",
            size_mb=self._calculate_size(len(scripts), len(ui_elements), platform),
            build_time=120.0,
            errors=[],
        )

        self.builds[build_result.build_id] = build_result
        return build_result

    def _calculate_size(self, script_count: int, ui_count: int, platform: str) -> float:
        base_size = 50.0
        if platform == "ios":
            base_size *= 1.5
        base_size += script_count * 0.5
        base_size += ui_count * 0.2
        return round(base_size, 1)

    def build_all(self, project) -> List[BuildResult]:
        results = []
        for platform in ["android", "ios"]:
            results.append(self.build(project, platform))
        return results

    def build_demo(self) -> BuildResult:
        project = {"name": "Cozy Witch Garden", "scripts": ["a", "b", "c", "d", "e"], "ui_elements": ["x", "y"]}
        return self.build(project, "android")
