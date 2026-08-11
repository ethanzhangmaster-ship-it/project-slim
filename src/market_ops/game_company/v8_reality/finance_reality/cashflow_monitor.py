from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum


class CashflowType(Enum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class CashflowCategory(Enum):
    OPERATING = "operating"
    INVESTING = "investing"
    FINANCING = "financing"


@dataclass
class CashflowRecord:
    type: CashflowType
    category: CashflowCategory
    amount: float
    date: datetime
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "category": self.category.value,
            "amount": self.amount,
            "date": self.date.isoformat(),
            "description": self.description,
        }


@dataclass
class CashflowStatement:
    period_start: str
    period_end: str
    opening_balance: float
    closing_balance: float
    net_cashflow: float
    operating_cashflow: float
    investing_cashflow: float
    financing_cashflow: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "net_cashflow": self.net_cashflow,
            "operating_cashflow": self.operating_cashflow,
            "investing_cashflow": self.investing_cashflow,
            "financing_cashflow": self.financing_cashflow,
        }


@dataclass
class RunwayAnalysis:
    current_balance: float
    monthly_burn_rate: float
    runway_days: int
    runway_months: float
    warning_level: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_balance": self.current_balance,
            "monthly_burn_rate": self.monthly_burn_rate,
            "runway_days": self.runway_days,
            "runway_months": self.runway_months,
            "warning_level": self.warning_level,
        }


class CashflowMonitor:
    def __init__(self, initial_balance: float = 1000000.0):
        self._records: List[CashflowRecord] = []
        self._initial_balance = initial_balance

    def record_cashflow(self, type: str, category: str, amount: float, date: datetime,
                        description: Optional[str] = None) -> CashflowRecord:
        try:
            type_enum = CashflowType(type)
        except ValueError:
            type_enum = CashflowType.INFLOW if amount > 0 else CashflowType.OUTFLOW

        try:
            category_enum = CashflowCategory(category)
        except ValueError:
            category_enum = CashflowCategory.OPERATING

        record = CashflowRecord(
            type=type_enum,
            category=category_enum,
            amount=amount,
            date=date,
            description=description,
        )
        self._records.append(record)
        return record

    def get_cash_balance(self) -> float:
        balance = self._initial_balance
        for record in self._records:
            if record.type == CashflowType.INFLOW:
                balance += record.amount
            else:
                balance -= record.amount
        return balance

    def get_cashflow_statement(self, period: str = "month") -> CashflowStatement:
        now = datetime.now()
        if period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:
            start_date = now - timedelta(days=30)

        opening_balance = self._initial_balance
        for record in self._records:
            if record.date < start_date:
                if record.type == CashflowType.INFLOW:
                    opening_balance += record.amount
                else:
                    opening_balance -= record.amount

        period_records = [r for r in self._records if start_date <= r.date <= now]
        operating = 0.0
        investing = 0.0
        financing = 0.0

        for record in period_records:
            amount = record.amount if record.type == CashflowType.INFLOW else -record.amount
            if record.category == CashflowCategory.OPERATING:
                operating += amount
            elif record.category == CashflowCategory.INVESTING:
                investing += amount
            elif record.category == CashflowCategory.FINANCING:
                financing += amount

        net_cashflow = operating + investing + financing
        closing_balance = opening_balance + net_cashflow

        return CashflowStatement(
            period_start=start_date.date().isoformat(),
            period_end=now.date().isoformat(),
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            net_cashflow=net_cashflow,
            operating_cashflow=operating,
            investing_cashflow=investing,
            financing_cashflow=financing,
        )

    def forecast_cashflow(self, days: int) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        current_balance = self.get_cash_balance()
        daily_inflow = 50000.0
        daily_outflow = 45000.0
        daily_net = daily_inflow - daily_outflow

        forecast = []
        balance = current_balance

        for i in range(days):
            date = (today + timedelta(days=i)).isoformat()
            balance += daily_net
            forecast.append({
                "date": date,
                "balance": balance,
                "inflow": daily_inflow,
                "outflow": daily_outflow,
            })

        return forecast

    def check_runway(self) -> RunwayAnalysis:
        current_balance = self.get_cash_balance()
        monthly_burn_rate = 150000.0

        if monthly_burn_rate <= 0:
            return RunwayAnalysis(
                current_balance=current_balance,
                monthly_burn_rate=monthly_burn_rate,
                runway_days=-1,
                runway_months=-1,
                warning_level="positive",
            )

        runway_days = int(current_balance / (monthly_burn_rate / 30))
        runway_months = current_balance / monthly_burn_rate

        if runway_months < 3:
            warning_level = "critical"
        elif runway_months < 6:
            warning_level = "warning"
        elif runway_months < 12:
            warning_level = "caution"
        else:
            warning_level = "healthy"

        return RunwayAnalysis(
            current_balance=current_balance,
            monthly_burn_rate=monthly_burn_rate,
            runway_days=runway_days,
            runway_months=round(runway_months, 2),
            warning_level=warning_level,
        )

    def get_all_records(self) -> List[CashflowRecord]:
        return list(self._records)

    def get_stats(self) -> Dict[str, Any]:
        inflows = sum(r.amount for r in self._records if r.type == CashflowType.INFLOW)
        outflows = sum(r.amount for r in self._records if r.type == CashflowType.OUTFLOW)
        return {
            "current_balance": self.get_cash_balance(),
            "total_inflows": inflows,
            "total_outflows": outflows,
            "net_cashflow": inflows - outflows,
            "record_count": len(self._records),
        }