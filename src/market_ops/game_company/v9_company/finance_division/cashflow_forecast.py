from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List


class ScenarioType(Enum):
    BASE = "base"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    STRESS = "stress"


@dataclass
class CashflowProjection:
    date: str
    inflow: float
    outflow: float
    net_cashflow: float
    cumulative_cash: float

    def to_dict(self):
        return {
            "date": self.date,
            "inflow": self.inflow,
            "outflow": self.outflow,
            "net_cashflow": self.net_cashflow,
            "cumulative_cash": self.cumulative_cash,
        }


@dataclass
class BreakEvenAnalysis:
    fixed_costs: float
    variable_cost_ratio: float
    break_even_revenue: float
    days_to_break_even: int

    def to_dict(self):
        return {
            "fixed_costs": self.fixed_costs,
            "variable_cost_ratio": self.variable_cost_ratio,
            "break_even_revenue": self.break_even_revenue,
            "days_to_break_even": self.days_to_break_even,
        }


@dataclass
class RunwayEstimate:
    current_cash: float
    monthly_burn: float
    runway_months: float
    zero_cash_date: str

    def to_dict(self):
        return {
            "current_cash": self.current_cash,
            "monthly_burn": self.monthly_burn,
            "runway_months": self.runway_months,
            "zero_cash_date": self.zero_cash_date,
        }


class CashflowForecast:
    def __init__(self):
        self._projections: List[CashflowProjection] = []
        self._scenarios: Dict[ScenarioType, List[CashflowProjection]] = {}
        self._break_even = BreakEvenAnalysis(
            fixed_costs=800000.0,
            variable_cost_ratio=0.45,
            break_even_revenue=1454545.0,
            days_to_break_even=90,
        )
        self._runway = RunwayEstimate(
            current_cash=5000000.0,
            monthly_burn=450000.0,
            runway_months=11.1,
            zero_cash_date=(datetime.now() + timedelta(days=337)).isoformat(),
        )

    def forecast(self, days: int) -> List[CashflowProjection]:
        projections = []
        base_cash = 5000000.0
        for i in range(days):
            date = (datetime.now() + timedelta(days=i)).isoformat()
            inflow = 30000.0 + (i * 100)
            outflow = 15000.0 + (i * 50)
            net = inflow - outflow
            base_cash += net
            projections.append(CashflowProjection(
                date=date,
                inflow=inflow,
                outflow=outflow,
                net_cashflow=net,
                cumulative_cash=base_cash,
            ))
        self._projections = projections
        return projections

    def get_cashflow_projections(self) -> List[CashflowProjection]:
        if not self._projections:
            self.forecast(30)
        return self._projections

    def get_break_even_analysis(self) -> BreakEvenAnalysis:
        return self._break_even

    def get_runway_estimate(self) -> RunwayEstimate:
        return self._runway

    def simulate_scenario(self, scenario: ScenarioType) -> List[CashflowProjection]:
        multipliers = {
            ScenarioType.BASE: 1.0,
            ScenarioType.OPTIMISTIC: 1.3,
            ScenarioType.PESSIMISTIC: 0.7,
            ScenarioType.STRESS: 0.4,
        }
        mult = multipliers.get(scenario, 1.0)
        projections = []
        base_cash = 5000000.0
        for i in range(30):
            date = (datetime.now() + timedelta(days=i)).isoformat()
            inflow = (30000.0 + (i * 100)) * mult
            outflow = 15000.0 + (i * 50)
            net = inflow - outflow
            base_cash += net
            projections.append(CashflowProjection(
                date=date,
                inflow=inflow,
                outflow=outflow,
                net_cashflow=net,
                cumulative_cash=base_cash,
            ))
        self._scenarios[scenario] = projections
        return projections

    def get_stats(self) -> Dict:
        return {
            "total_projections": len(self._projections),
            "scenarios_simulated": len(self._scenarios),
            "break_even": self._break_even.to_dict(),
            "runway": self._runway.to_dict(),
        }
