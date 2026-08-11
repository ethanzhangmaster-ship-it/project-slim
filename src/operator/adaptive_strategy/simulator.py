"""P3.3.3 — Adaptive Strategy Simulator（复用 E17.8，薄封装）。

职责：
- 用 get_prior 取先验（可注入 prior_provider / graph）
- 用 DeterministicSimulator.simulate_decision 跑执行前闸门
- 返回 DecisionSimulation（含 .flag.status）

SIM 纪律：real_api_called 恒 False（纯计算，不触外部系统）。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from src.ceo_intelligence.decision_engine.simulator import OpportunitySimulator
from src.ceo_intelligence.simulation_engine.engine import DeterministicSimulator
from src.ceo_intelligence.simulation_engine.models import (
    DecisionSimulation,
    PreFlightStatus,
)
from src.ceo_intelligence.simulation_engine.priors import (
    get_prior,
    opportunity_type_of,
)


# prior_provider 契约：(opportunity_type: str) -> SimulationPrior
PriorProvider = Callable[[str], Any]


class AdaptiveStrategySimulator:
    """E17.8 模拟器的自适应封装。"""

    def __init__(
        self,
        *,
        graph: Any = None,
        simulator: Optional[OpportunitySimulator] = None,
        prior_provider: Optional[PriorProvider] = None,
        samples: int = 201,
        seed: int = 20260729,
    ) -> None:
        self.graph = graph
        self.simulator = simulator or OpportunitySimulator()
        self.prior_provider = prior_provider or self._default_prior
        self._engine = DeterministicSimulator(samples=samples, seed=seed)

    def _default_prior(self, opportunity_type: str):
        return get_prior(
            opportunity_type,
            self.graph,
            simulator=self.simulator,
        )

    def simulate(self, decision: Any) -> DecisionSimulation:
        """一个 GrowthDecision → 执行前闸门模拟。"""
        opportunity_type = opportunity_type_of(decision.opportunity_id)
        prior = self.prior_provider(opportunity_type)
        return self._engine.simulate_decision(decision, prior)

    # 便捷判定（供 Controller 使用，避免直接比较枚举）
    @staticmethod
    def passed(sim: DecisionSimulation) -> bool:
        return sim.flag.status == PreFlightStatus.PASS

    @staticmethod
    def status_of(sim: DecisionSimulation) -> str:
        return sim.flag.status.value

    @staticmethod
    def reason_of(sim: DecisionSimulation) -> str:
        return sim.flag.reason


__all__ = ["AdaptiveStrategySimulator", "PriorProvider"]
