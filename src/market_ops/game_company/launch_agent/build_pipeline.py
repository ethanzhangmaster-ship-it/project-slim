from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class BuildResult:
    build_id: str
    platform: str
    status: str = "pending"
    version: str = ""
    file_size_mb: float = 0.0
    build_time_minutes: float = 0.0
    errors: List[str] = field(default_factory=list)


class BuildPipeline:
    def __init__(self):
        self.builds: Dict[str, BuildResult] = {}

    def build(self, project, platform: str = "android") -> BuildResult:
        status = "success"
        errors = []
        
        if len(project.get("scripts", [])) < 3:
            status = "failed"
            errors.append("Insufficient scripts")

        result = BuildResult(
            build_id=f"build_{hash(str(project)) % 10000:04d}",
            platform=platform,
            status=status,
            version="1.0.0",
            file_size_mb=self._calculate_size(project, platform),
            build_time_minutes=5.0,
            errors=errors,
        )

        self.builds[result.build_id] = result
        return result

    def build_all(self, project) -> List[BuildResult]:
        results = []
        for platform in ["android", "ios"]:
            results.append(self.build(project, platform))
        return results

    def _calculate_size(self, project, platform: str) -> float:
        base = 50.0
        if platform == "ios":
            base *= 1.5
        base += len(project.get("scripts", [])) * 0.5
        return round(base, 1)

    def build_demo(self) -> BuildResult:
        project = {"name": "Cozy Witch Garden", "scripts": ["a", "b", "c", "d", "e"]}
        return self.build(project, "android")
