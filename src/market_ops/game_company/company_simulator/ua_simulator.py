from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class UASimulation:
    simulation_id: str
    platform: str = ""
    budget: float = 0.0
    cpi: float = 0.0
    installs: int = 0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cvr: float = 0.0
    roas: float = 0.0


class UASimulator:
    def __init__(self):
        self.simulations: Dict[str, UASimulation] = {}

    def simulate(self, platform: str, budget: float, cpi: float = 2.5) -> UASimulation:
        installs = int(budget / cpi)
        clicks = int(installs / 0.03)
        impressions = int(clicks / 0.02)

        ctr = clicks / impressions
        cvr = installs / clicks

        revenue = installs * 0.15 * 30 * 0.5
        roas = revenue / budget if budget > 0 else 0

        simulation = UASimulation(
            simulation_id=f"ua_sim_{hash(platform + str(budget)) % 10000:04d}",
            platform=platform,
            budget=budget,
            cpi=cpi,
            installs=installs,
            impressions=impressions,
            clicks=clicks,
            ctr=round(ctr, 4),
            cvr=round(cvr, 4),
            roas=round(roas, 2),
        )

        self.simulations[simulation.simulation_id] = simulation
        return simulation

    def simulate_all_platforms(self, budget: float) -> List[UASimulation]:
        platforms = ["meta", "google", "tiktok", "apple"]
        cpis = {"meta": 2.5, "google": 2.0, "tiktok": 1.8, "apple": 3.0}
        
        results = []
        for platform in platforms:
            results.append(self.simulate(platform, budget / len(platforms), cpis[platform]))
        
        return results

    def simulate_demo(self) -> UASimulation:
        return self.simulate("meta", 50000)
