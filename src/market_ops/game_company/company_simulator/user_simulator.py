from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class UserSimulation:
    simulation_id: str
    total_users: int = 0
    active_users: Dict[int, int] = field(default_factory=dict)
    retention: Dict[int, float] = field(default_factory=dict)
    sessions: Dict[int, int] = field(default_factory=dict)
    average_session_time: float = 0.0


class UserSimulator:
    def __init__(self):
        self.simulations: Dict[str, UserSimulation] = {}

    def simulate(self, game_data: Dict[str, Any], budget: float) -> UserSimulation:
        cpi = game_data.get("cpi", 2.5)
        d1 = game_data.get("d1", 0.4)
        d7 = game_data.get("d7", 0.2)
        d30 = game_data.get("d30", 0.1)
        days = 30

        total_users = int(budget / cpi)
        
        active_users = {}
        retention = {1: d1, 7: d7, 30: d30}
        
        for day in range(1, days + 1):
            if day == 1:
                active_users[day] = total_users
            elif day == 7:
                active_users[day] = int(total_users * d7)
            elif day == 30:
                active_users[day] = int(total_users * d30)
            else:
                decay = 0.98
                prev_day = day - 1
                active_users[day] = int(active_users.get(prev_day, total_users) * decay)

        sessions = {day: active_users[day] * 3 for day in range(1, days + 1)}

        simulation = UserSimulation(
            simulation_id=f"user_sim_{hash(str(game_data)) % 10000:04d}",
            total_users=total_users,
            active_users=active_users,
            retention=retention,
            sessions=sessions,
            average_session_time=8.5,
        )

        self.simulations[simulation.simulation_id] = simulation
        return simulation

    def simulate_demo(self) -> UserSimulation:
        game_data = {"cpi": 2.5, "d1": 0.4, "d7": 0.2, "d30": 0.09}
        return self.simulate(game_data, 50000)
