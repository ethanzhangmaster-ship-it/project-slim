from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


@dataclass
class ProfitResult:
    date: str
    revenue: float
    cost_of_goods_sold: float
    operating_expenses: float
    gross_profit: float
    operating_profit: float
    net_profit: float
    profit_margin: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "revenue": self.revenue,
            "cost_of_goods_sold": self.cost_of_goods_sold,
            "operating_expenses": self.operating_expenses,
            "gross_profit": self.gross_profit,
            "operating_profit": self.operating_profit,
            "net_profit": self.net_profit,
            "profit_margin": self.profit_margin,
        }


@dataclass
class ProfitMargin:
    gross_margin: float
    operating_margin: float
    net_margin: float
    ebitda_margin: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gross_margin": self.gross_margin,
            "operating_margin": self.operating_margin,
            "net_margin": self.net_margin,
            "ebitda_margin": self.ebitda_margin,
        }


class ProfitCalculator:
    def __init__(self):
        self._cogs_ratio = 0.35
        self._operating_expense_ratio = 0.40
        self._tax_rate = 0.25

    def calculate_daily_profit(self, date: datetime) -> ProfitResult:
        date_str = date.date().isoformat()
        revenue = self._generate_mock_daily_revenue(date)
        cogs = revenue * self._cogs_ratio
        operating_expenses = revenue * self._operating_expense_ratio
        gross_profit = revenue - cogs
        operating_profit = gross_profit - operating_expenses
        net_profit = operating_profit * (1 - self._tax_rate)
        profit_margin = net_profit / revenue * 100 if revenue > 0 else 0

        return ProfitResult(
            date=date_str,
            revenue=revenue,
            cost_of_goods_sold=cogs,
            operating_expenses=operating_expenses,
            gross_profit=gross_profit,
            operating_profit=operating_profit,
            net_profit=net_profit,
            profit_margin=profit_margin,
        )

    def calculate_monthly_profit(self, month: int, year: Optional[int] = None) -> ProfitResult:
        target_year = year or datetime.now().year
        date_str = f"{target_year}-{month:02d}"
        revenue = self._generate_mock_monthly_revenue(month, target_year)
        cogs = revenue * self._cogs_ratio
        operating_expenses = revenue * self._operating_expense_ratio
        gross_profit = revenue - cogs
        operating_profit = gross_profit - operating_expenses
        net_profit = operating_profit * (1 - self._tax_rate)
        profit_margin = net_profit / revenue * 100 if revenue > 0 else 0

        return ProfitResult(
            date=date_str,
            revenue=revenue,
            cost_of_goods_sold=cogs,
            operating_expenses=operating_expenses,
            gross_profit=gross_profit,
            operating_profit=operating_profit,
            net_profit=net_profit,
            profit_margin=profit_margin,
        )

    def get_profit_margin(self) -> ProfitMargin:
        return ProfitMargin(
            gross_margin=(1 - self._cogs_ratio) * 100,
            operating_margin=(1 - self._cogs_ratio - self._operating_expense_ratio) * 100,
            net_margin=(1 - self._cogs_ratio - self._operating_expense_ratio) * (1 - self._tax_rate) * 100,
            ebitda_margin=(1 - self._cogs_ratio - self._operating_expense_ratio + 0.08) * 100,
        )

    def calculate_net_profit(self, revenue: float, costs: Dict[str, float]) -> float:
        total_costs = sum(costs.values())
        operating_profit = revenue - total_costs
        return operating_profit * (1 - self._tax_rate)

    def get_profit_trend(self, days: int) -> List[ProfitResult]:
        today = datetime.now().date()
        trend = []

        for i in range(days - 1, -1, -1):
            date = datetime.combine(today - timedelta(days=i), datetime.min.time())
            trend.append(self.calculate_daily_profit(date))

        return trend

    def _generate_mock_daily_revenue(self, date: datetime) -> float:
        base_revenue = 50000.0
        day_of_week = date.weekday()
        weekend_multiplier = 1.3 if day_of_week >= 5 else 1.0
        month_multiplier = 1.2 if date.month in [11, 12] else 1.0
        return base_revenue * weekend_multiplier * month_multiplier

    def _generate_mock_monthly_revenue(self, month: int, year: int) -> float:
        base_monthly = 1500000.0
        seasonal_multiplier = 1.4 if month in [11, 12] else 1.0
        return base_monthly * seasonal_multiplier