from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


@dataclass
class KeyMetrics:
    revenue: float
    expenses: float
    net_profit: float
    profit_margin: float
    cash_balance: float
    burn_rate: float
    runway_days: int
    customer_acquisition_cost: float
    lifetime_value: float
    ltv_cac_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revenue": self.revenue,
            "expenses": self.expenses,
            "net_profit": self.net_profit,
            "profit_margin": self.profit_margin,
            "cash_balance": self.cash_balance,
            "burn_rate": self.burn_rate,
            "runway_days": self.runway_days,
            "customer_acquisition_cost": self.customer_acquisition_cost,
            "lifetime_value": self.lifetime_value,
            "ltv_cac_ratio": self.ltv_cac_ratio,
        }


@dataclass
class FinanceReport:
    report_type: str
    period_start: str
    period_end: str
    generated_at: str
    key_metrics: KeyMetrics
    revenue_breakdown: Dict[str, float]
    expense_breakdown: Dict[str, float]
    cashflow_summary: Dict[str, float]
    budget_summary: Dict[str, Any]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_type": self.report_type,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "generated_at": self.generated_at,
            "key_metrics": self.key_metrics.to_dict(),
            "revenue_breakdown": self.revenue_breakdown,
            "expense_breakdown": self.expense_breakdown,
            "cashflow_summary": self.cashflow_summary,
            "budget_summary": self.budget_summary,
            "notes": self.notes,
        }


class FinanceReportService:
    def __init__(self):
        self._mock_revenue_data = {
            "in_app_purchase": 250000.0,
            "ad_revenue": 150000.0,
            "subscription": 100000.0,
            "premium": 50000.0,
            "other": 25000.0,
        }
        self._mock_expense_data = {
            "advertising": 120000.0,
            "operations": 80000.0,
            "development": 100000.0,
            "marketing": 50000.0,
            "sales": 30000.0,
            "administration": 40000.0,
        }

    def generate_daily_report(self) -> FinanceReport:
        today = datetime.now()
        period_start = today.date().isoformat()
        period_end = today.date().isoformat()

        revenue = sum(self._mock_revenue_data.values()) / 30
        expenses = sum(self._mock_expense_data.values()) / 30
        net_profit = revenue - expenses
        profit_margin = net_profit / revenue * 100 if revenue > 0 else 0

        key_metrics = KeyMetrics(
            revenue=round(revenue, 2),
            expenses=round(expenses, 2),
            net_profit=round(net_profit, 2),
            profit_margin=round(profit_margin, 2),
            cash_balance=950000.0,
            burn_rate=5000.0,
            runway_days=190,
            customer_acquisition_cost=45.0,
            lifetime_value=450.0,
            ltv_cac_ratio=10.0,
        )

        return FinanceReport(
            report_type="daily",
            period_start=period_start,
            period_end=period_end,
            generated_at=today.isoformat(),
            key_metrics=key_metrics,
            revenue_breakdown={k: round(v / 30, 2) for k, v in self._mock_revenue_data.items()},
            expense_breakdown={k: round(v / 30, 2) for k, v in self._mock_expense_data.items()},
            cashflow_summary={
                "operating": 5000.0,
                "investing": -2000.0,
                "financing": 0.0,
                "net": 3000.0,
            },
            budget_summary={
                "total_budget": 500000.0,
                "total_spent": 180000.0,
                "remaining": 320000.0,
            },
            notes=["Daily report generated successfully"],
        )

    def generate_weekly_report(self) -> FinanceReport:
        today = datetime.now()
        period_start = (today - timedelta(days=7)).date().isoformat()
        period_end = today.date().isoformat()

        revenue = sum(self._mock_revenue_data.values()) * (7 / 30)
        expenses = sum(self._mock_expense_data.values()) * (7 / 30)
        net_profit = revenue - expenses
        profit_margin = net_profit / revenue * 100 if revenue > 0 else 0

        key_metrics = KeyMetrics(
            revenue=round(revenue, 2),
            expenses=round(expenses, 2),
            net_profit=round(net_profit, 2),
            profit_margin=round(profit_margin, 2),
            cash_balance=970000.0,
            burn_rate=35000.0,
            runway_days=186,
            customer_acquisition_cost=42.0,
            lifetime_value=460.0,
            ltv_cac_ratio=10.95,
        )

        return FinanceReport(
            report_type="weekly",
            period_start=period_start,
            period_end=period_end,
            generated_at=today.isoformat(),
            key_metrics=key_metrics,
            revenue_breakdown={k: round(v * (7 / 30), 2) for k, v in self._mock_revenue_data.items()},
            expense_breakdown={k: round(v * (7 / 30), 2) for k, v in self._mock_expense_data.items()},
            cashflow_summary={
                "operating": 35000.0,
                "investing": -15000.0,
                "financing": 0.0,
                "net": 20000.0,
            },
            budget_summary={
                "total_budget": 500000.0,
                "total_spent": 126000.0,
                "remaining": 374000.0,
            },
            notes=[
                "Weekly report generated successfully",
                "Revenue increased 5% compared to last week",
                "Marketing expenses slightly over budget",
            ],
        )

    def generate_monthly_report(self) -> FinanceReport:
        today = datetime.now()
        period_start = (today - timedelta(days=30)).date().isoformat()
        period_end = today.date().isoformat()

        revenue = sum(self._mock_revenue_data.values())
        expenses = sum(self._mock_expense_data.values())
        net_profit = revenue - expenses
        profit_margin = net_profit / revenue * 100 if revenue > 0 else 0

        key_metrics = KeyMetrics(
            revenue=round(revenue, 2),
            expenses=round(expenses, 2),
            net_profit=round(net_profit, 2),
            profit_margin=round(profit_margin, 2),
            cash_balance=1000000.0,
            burn_rate=150000.0,
            runway_days=200,
            customer_acquisition_cost=40.0,
            lifetime_value=480.0,
            ltv_cac_ratio=12.0,
        )

        return FinanceReport(
            report_type="monthly",
            period_start=period_start,
            period_end=period_end,
            generated_at=today.isoformat(),
            key_metrics=key_metrics,
            revenue_breakdown=self._mock_revenue_data,
            expense_breakdown=self._mock_expense_data,
            cashflow_summary={
                "operating": 150000.0,
                "investing": -50000.0,
                "financing": 0.0,
                "net": 100000.0,
            },
            budget_summary={
                "total_budget": 500000.0,
                "total_spent": 420000.0,
                "remaining": 80000.0,
                "utilization_rate": 84.0,
            },
            notes=[
                "Monthly report generated successfully",
                "Overall performance meets expectations",
                "Development budget fully utilized",
                "Cash runway healthy at 6+ months",
            ],
        )

    def get_key_metrics(self) -> KeyMetrics:
        return self.generate_daily_report().key_metrics

    def export_report(self, report: FinanceReport, format: str = "json") -> str:
        if format == "json":
            import json
            return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
        elif format == "csv":
            lines = ["Metric,Value"]
            for k, v in report.key_metrics.to_dict().items():
                lines.append(f"{k},{v}")
            return "\n".join(lines)
        elif format == "markdown":
            md = f"# {report.report_type.capitalize()} Finance Report\n\n"
            md += f"**Period:** {report.period_start} - {report.period_end}\n"
            md += f"**Generated:** {report.generated_at}\n\n"
            md += "## Key Metrics\n\n"
            md += "| Metric | Value |\n"
            md += "|--------|-------|\n"
            for k, v in report.key_metrics.to_dict().items():
                md += f"| {k.replace('_', ' ').title()} | {v} |\n"
            return md
        else:
            return str(report.to_dict())