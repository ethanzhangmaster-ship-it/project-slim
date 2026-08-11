from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class SimulationResult:
    simulation_id: str
    days: int = 0
    total_users: int = 0
    active_users: int = 0
    revenue: float = 0.0
    total_revenue: float = 0.0
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    ltv: float = 0.0
    payback_days: float = 0.0
    roi: float = 0.0


class EconomySimulator:
    def __init__(self):
        self.simulations: Dict[str, SimulationResult] = {}

    def simulate(self, game_data: Dict[str, Any], budget: float) -> SimulationResult:
        days = 30
        d30 = game_data.get("d30", 0.09)
        arpdau = game_data.get("arpdau", 0.15)
        cpi = game_data.get("cpi", 2.5)

        installs_per_day = budget / cpi / days
        total_users = int(installs_per_day * days)
        
        active_users = int(total_users * d30)
        
        ad_revenue = active_users * arpdau * 0.6 * days
        iap_revenue = active_users * arpdau * 0.4 * days
        total_revenue = ad_revenue + iap_revenue

        ltv = total_revenue / total_users
        payback_days = budget / (total_revenue / days)

        result = SimulationResult(
            simulation_id=f"sim_{hash(str(game_data)) % 10000:04d}",
            days=days,
            total_users=total_users,
            active_users=active_users,
            revenue=round(total_revenue, 2),
            total_revenue=round(total_revenue, 2),
            iap_revenue=round(iap_revenue, 2),
            ad_revenue=round(ad_revenue, 2),
            ltv=round(ltv, 2),
            payback_days=round(payback_days, 1),
            roi=round((total_revenue - budget) / budget * 100, 1),
        )

        self.simulations[result.simulation_id] = result
        return result

    def simulate_long_term(self, game_data: Dict[str, Any], budget: float, days: int = 180) -> SimulationResult:
        d30 = game_data.get("d30", 0.09)
        arpdau = game_data.get("arpdau", 0.15)
        cpi = game_data.get("cpi", 2.5)

        installs_per_day = budget / cpi / 30
        total_users = int(installs_per_day * days)
        
        active_users = int(total_users * d30 * 0.5)
        
        ad_revenue = active_users * arpdau * 0.6 * days
        iap_revenue = active_users * arpdau * 0.4 * days
        total_revenue = ad_revenue + iap_revenue

        ltv = total_revenue / total_users

        result = SimulationResult(
            simulation_id=f"sim_long_{hash(str(game_data)) % 10000:04d}",
            days=days,
            total_users=total_users,
            active_users=active_users,
            revenue=round(total_revenue, 2),
            total_revenue=round(total_revenue, 2),
            iap_revenue=round(iap_revenue, 2),
            ad_revenue=round(ad_revenue, 2),
            ltv=round(ltv, 2),
            payback_days=round(budget / (total_revenue / days), 1),
            roi=round((total_revenue - budget) / budget * 100, 1),
        )

        return result

    def simulate_demo(self) -> SimulationResult:
        game_data = {
            "d30": 0.09,
            "arpdau": 0.15,
            "cpi": 2.5,
        }
        return self.simulate(game_data, 50000)
