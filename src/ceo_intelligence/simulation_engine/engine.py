"""E17.8 — DeterministicSimulator：固定种子抖动网格采样的确定性模拟器。

方法（无 LLM、无第三方库）：
- 采样：N 点抖动网格 u_i = (i + r_i) / N，r_i 来自 random.Random(seed)
  （固定种子 → 跨进程/跨平台可复现到 1e-6；低差异覆盖 [0,1)）
- 分布：对称三角分布逆 CDF，中心 = 先验均值，半宽 = 风险 ×（|均值| + 底宽）
  → 风险越高分布越宽，p10/p90 尾部越深
- 每决策独立子种子（crc32(opportunity_id)），组合分布 = 对齐样本逐点平均
- 情景（what-if）：对均值/风险施加确定性乘子后重新采样
- 执行前闸门：负期望 BLOCK；高风险/低置信/深下行 REVIEW；其余 PASS

SIM 纪律：本层纯计算，real_api_called 恒为 False。
"""
from __future__ import annotations

import math
import random
import zlib
from typing import Dict, List, Optional, Sequence

from .models import (
    DEFAULT_SCENARIOS,
    CounterfactualComparison,
    DecisionSimulation,
    OutcomeDistribution,
    PreFlightFlag,
    PreFlightStatus,
    ScenarioOutcome,
    SimulationPrior,
    SimulationScenario,
)

SEED = 20260729
SAMPLES = 201

# 分布半宽底数：均值为 0 时仍有不确定性
_REV_BASE_WIDTH = 0.10
_ROAS_BASE_WIDTH = 0.05

# 闸门阈值（确定性）
_GATE_RISK_REVIEW = 0.60       # 与 E17.3 Gate2 高风险线对齐
_GATE_CONF_REVIEW = 0.50
_GATE_DOWNSIDE_REVIEW = -0.10  # 基线情景 p10 低于 -10% → 复核


def _triangular_icdf(u: float, mean: float, width: float) -> float:
    """对称三角分布（[mean-width, mean+width]，众数 mean）的逆 CDF。"""
    if width <= 0.0:
        return mean
    if u <= 0.5:
        return mean - width + width * math.sqrt(2.0 * u)
    return mean + width - width * math.sqrt(2.0 * (1.0 - u))


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    """线性插值分位数（输入须升序）。"""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _distribution(samples: Sequence[float]) -> OutcomeDistribution:
    ordered = sorted(samples)
    mean = sum(ordered) / len(ordered) if ordered else 0.0
    return OutcomeDistribution(
        p10=round(_percentile(ordered, 0.10), 6),
        p50=round(_percentile(ordered, 0.50), 6),
        p90=round(_percentile(ordered, 0.90), 6),
        mean=round(mean, 6),
    )


class DeterministicSimulator:
    """组合级 what-if 模拟 + 反事实对比 + 执行前闸门（全确定性）。"""

    def __init__(
        self,
        samples: int = SAMPLES,
        seed: int = SEED,
        scenarios: Optional[List[SimulationScenario]] = None,
    ):
        self.samples = int(samples)
        self.seed = int(seed)
        self.scenarios = list(scenarios) if scenarios is not None else list(
            DEFAULT_SCENARIOS
        )

    # ------------------------------------------------------------------ #
    # 采样底层
    # ------------------------------------------------------------------ #
    def _grid(self, seed_key: str) -> List[float]:
        """固定子种子的抖动网格 u_i ∈ [0,1)。"""
        rng = random.Random(self.seed + zlib.crc32(seed_key.encode("utf-8")))
        n = self.samples
        return [(i + rng.random()) / n for i in range(n)]

    def _metric_samples(
        self, grid: Sequence[float], mean: float, risk: float, base_width: float
    ) -> List[float]:
        width = max(0.0, risk) * (abs(mean) + base_width)
        return [_triangular_icdf(u, mean, width) for u in grid]

    def _scenario_samples(
        self, prior: SimulationPrior, scenario: SimulationScenario, seed_key: str
    ) -> Dict[str, List[float]]:
        """一个先验在一个情景下的收入/ROAS 样本（确定性）。"""
        grid = self._grid(f"{seed_key}|{scenario.id}")
        risk = min(0.95, max(0.0, prior.risk * scenario.risk_multiplier))
        return {
            "revenue": self._metric_samples(
                grid,
                prior.expected_revenue_change * scenario.revenue_multiplier,
                risk,
                _REV_BASE_WIDTH,
            ),
            "roas": self._metric_samples(
                grid,
                prior.expected_roas_change * scenario.roas_multiplier,
                risk,
                _ROAS_BASE_WIDTH,
            ),
            "_risk": [risk],
        }

    # ------------------------------------------------------------------ #
    # 决策级模拟
    # ------------------------------------------------------------------ #
    def simulate_decision(
        self,
        decision,
        prior: SimulationPrior,
        scenarios: Optional[List[SimulationScenario]] = None,
    ) -> DecisionSimulation:
        """一个 GrowthDecision（E17.3）→ 各情景分布 + 执行前闸门。"""
        scen_list = scenarios if scenarios is not None else self.scenarios
        outcomes: List[ScenarioOutcome] = []
        for scenario in scen_list:
            raw = self._scenario_samples(prior, scenario, decision.opportunity_id)
            outcomes.append(ScenarioOutcome(
                scenario_id=scenario.id,
                revenue=_distribution(raw["revenue"]),
                roas=_distribution(raw["roas"]),
                confidence=round(prior.confidence, 6),
                risk=round(raw["_risk"][0], 6),
            ))
        sim = DecisionSimulation(
            game_id=decision.game_id,
            opportunity_id=decision.opportunity_id,
            action=decision.action,
            decision_type=(
                decision.decision_type.value
                if hasattr(decision.decision_type, "value")
                else str(decision.decision_type)
            ),
            prior=prior,
            outcomes=outcomes,
            decision_audit_id=getattr(decision, "audit_id", ""),
        )
        sim.flag = self.pre_flight(sim)
        return sim

    # ------------------------------------------------------------------ #
    # 执行前闸门
    # ------------------------------------------------------------------ #
    @staticmethod
    def pre_flight(sim: DecisionSimulation) -> PreFlightFlag:
        """基线情景闸门：BLOCK > REVIEW > PASS（确定性规则）。"""
        try:
            base = sim.outcome("baseline")
        except KeyError:
            return PreFlightFlag(
                PreFlightStatus.REVIEW, "no baseline scenario simulated"
            )
        if base.revenue.p50 < 0.0:
            return PreFlightFlag(
                PreFlightStatus.BLOCK,
                f"负期望：基线收入 p50 {base.revenue.p50:+.1%}",
            )
        reasons: List[str] = []
        if base.risk >= _GATE_RISK_REVIEW:
            reasons.append(f"高风险 {base.risk:.0%}")
        if base.confidence < _GATE_CONF_REVIEW:
            reasons.append(f"低置信 {base.confidence:.0%}")
        if base.revenue.p10 <= _GATE_DOWNSIDE_REVIEW:
            reasons.append(f"深下行 p10 {base.revenue.p10:+.1%}")
        if reasons:
            return PreFlightFlag(PreFlightStatus.REVIEW, "；".join(reasons))
        return PreFlightFlag(PreFlightStatus.PASS, "")

    # ------------------------------------------------------------------ #
    # 组合级分布：对齐样本逐点平均（每决策独立子种子）
    # ------------------------------------------------------------------ #
    def simulate_portfolio(
        self,
        sims: List[DecisionSimulation],
        scenarios: Optional[List[SimulationScenario]] = None,
    ) -> Dict[str, OutcomeDistribution]:
        """组合收入变化分布（各情景），BLOCK 的决策不计入。"""
        scen_list = scenarios if scenarios is not None else self.scenarios
        active = [s for s in sims if s.flag.status != PreFlightStatus.BLOCK]
        out: Dict[str, OutcomeDistribution] = {}
        for scenario in scen_list:
            if not active:
                out[scenario.id] = OutcomeDistribution()
                continue
            pooled = [0.0] * self.samples
            for sim in active:
                raw = self._scenario_samples(
                    sim.prior, scenario, sim.opportunity_id
                )["revenue"]
                for j, v in enumerate(raw):
                    pooled[j] += v
            n = float(len(active))
            out[scenario.id] = _distribution([v / n for v in pooled])
        return out

    # ------------------------------------------------------------------ #
    # 反事实 A/B 对比
    # ------------------------------------------------------------------ #
    @staticmethod
    def compare_counterfactual(
        sim: DecisionSimulation, scenario_a: str, scenario_b: str
    ) -> CounterfactualComparison:
        a = sim.outcome(scenario_a)
        b = sim.outcome(scenario_b)
        rev_delta = round(a.revenue.p50 - b.revenue.p50, 6)
        return CounterfactualComparison(
            game_id=sim.game_id,
            opportunity_id=sim.opportunity_id,
            scenario_a=scenario_a,
            scenario_b=scenario_b,
            revenue_p50_delta=rev_delta,
            roas_p50_delta=round(a.roas.p50 - b.roas.p50, 6),
            winner=scenario_a if rev_delta >= 0 else scenario_b,
        )


__all__ = ["DeterministicSimulator", "SEED", "SAMPLES"]
