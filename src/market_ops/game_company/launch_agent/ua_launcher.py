from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class LaunchResult:
    launch_id: str
    platform: str = ""
    status: str = "pending"
    budget: float = 0.0
    installs: int = 0
    cpi: float = 0.0
    roas: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class UALauncher:
    def __init__(self):
        self.launches: Dict[str, LaunchResult] = {}

    def launch(self, platform: str, budget: float, creative_ids: List[str]) -> LaunchResult:
        status = "running"
        cpi_map = {"meta": 2.5, "google": 2.0, "tiktok": 1.8, "apple": 3.0}
        
        cpi = cpi_map.get(platform, 2.5)
        installs = int(budget / cpi)
        
        revenue = installs * 0.15 * 30 * 0.5
        roas = revenue / budget if budget > 0 else 0

        result = LaunchResult(
            launch_id=f"launch_{hash(platform + str(budget)) % 10000:04d}",
            platform=platform,
            status=status,
            budget=budget,
            installs=installs,
            cpi=cpi,
            roas=round(roas, 2),
            start_time=datetime.now(),
        )

        self.launches[result.launch_id] = result
        return result

    def launch_all(self, budget: float, creative_ids: List[str]) -> List[LaunchResult]:
        results = []
        platforms = ["meta", "google", "tiktok", "apple"]
        for platform in platforms:
            results.append(self.launch(platform, budget / len(platforms), creative_ids))
        return results

    def launch_demo(self) -> LaunchResult:
        return self.launch("meta", 50000, ["video_1", "video_2", "video_3"])
