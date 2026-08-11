from dataclasses import dataclass
from typing import Dict


@dataclass
class ProfitabilityAnalysis:
    revenue: float
    costs: float
    gross_profit: float
    net_profit: float
    period: str

    def to_dict(self):
        return {
            "revenue": self.revenue,
            "costs": self.costs,
            "gross_profit": self.gross_profit,
            "net_profit": self.net_profit,
            "period": self.period,
        }


@dataclass
class UnitEconomics:
    arpu: float
    cac: float
    marginal_cost: float
    contribution_margin: float

    def to_dict(self):
        return {
            "arpu": self.arpu,
            "cac": self.cac,
            "marginal_cost": self.marginal_cost,
            "contribution_margin": self.contribution_margin,
        }


@dataclass
class LTVCAC:
    ltv: float
    cac: float
    ratio: float
    payback_months: float

    def to_dict(self):
        return {
            "ltv": self.ltv,
            "cac": self.cac,
            "ratio": self.ratio,
            "payback_months": self.payback_months,
        }


class ProfitabilityEngine:
    def __init__(self):
        self._analysis = ProfitabilityAnalysis(
            revenue=2500000.0,
            costs=1800000.0,
            gross_profit=700000.0,
            net_profit=320000.0,
            period="monthly",
        )
        self._unit_economics = UnitEconomics(
            arpu=45.0,
            cac=12.5,
            marginal_cost=8.0,
            contribution_margin=37.0,
        )
        self._ltv_cac = LTVCAC(
            ltv=180.0,
            cac=12.5,
            ratio=14.4,
            payback_months=3.5,
        )

    def analyze_profitability(self) -> ProfitabilityAnalysis:
        return self._analysis

    def get_profit_margins(self) -> Dict:
        rev = self._analysis.revenue
        return {
            "gross_margin": self._analysis.gross_profit / rev if rev else 0.0,
            "net_margin": self._analysis.net_profit / rev if rev else 0.0,
        }

    def get_unit_economics(self) -> UnitEconomics:
        return self._unit_economics

    def get_ltv_cac_ratio(self) -> LTVCAC:
        return self._ltv_cac

    def get_payback_period(self) -> float:
        return self._ltv_cac.payback_months

    def get_stats(self) -> Dict:
        return {
            "profitability": self._analysis.to_dict(),
            "unit_economics": self._unit_economics.to_dict(),
            "ltv_cac": self._ltv_cac.to_dict(),
            "margins": self.get_profit_margins(),
        }
