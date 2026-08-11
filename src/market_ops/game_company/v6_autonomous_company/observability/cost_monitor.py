from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class CostRecord:
    record_id: str
    category: str
    amount: float
    description: str
    source: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostMonitor:
    def __init__(self):
        self._records: Dict[str, CostRecord] = []
        self._daily_costs: Dict[str, float] = defaultdict(float)
        self._category_costs: Dict[str, float] = defaultdict(float)
        self._daily_category: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._budgets: Dict[str, float] = {}

    def record_cost(
        self,
        category: str,
        amount: float,
        description: str,
        source: str = "unknown",
        metadata: Dict[str, Any] = None,
    ) -> CostRecord:
        record_id = f"cost_{hash(category + description + str(datetime.now())) % 100000:05d}"

        record = CostRecord(
            record_id=record_id,
            category=category,
            amount=amount,
            description=description,
            source=source,
            metadata=metadata or {},
        )

        if isinstance(self._records, dict):
            self._records = []
        self._records.append(record)

        date_str = record.timestamp.strftime("%Y-%m-%d")
        self._daily_costs[date_str] += amount
        self._category_costs[category] += amount
        self._daily_category[date_str][category] += amount

        return record

    def set_budget(self, category: str, amount: float):
        self._budgets[category] = amount

    def get_daily_cost(self, date_str: str = None) -> float:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        return self._daily_costs.get(date_str, 0.0)

    def get_weekly_cost(self, start_date: str = None) -> float:
        if start_date is None:
            start = datetime.now() - timedelta(days=6)
        else:
            start = datetime.strptime(start_date, "%Y-%m-%d")

        total = 0.0
        for i in range(7):
            date_str = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            total += self._daily_costs.get(date_str, 0.0)
        return total

    def get_monthly_cost(self, year_month: str = None) -> float:
        if year_month is None:
            year_month = datetime.now().strftime("%Y-%m")

        total = 0.0
        for date_str, cost in self._daily_costs.items():
            if date_str.startswith(year_month):
                total += cost
        return total

    def get_cost_by_category(self, date_str: str = None) -> Dict[str, float]:
        if date_str is None:
            return dict(self._category_costs)
        return dict(self._daily_category.get(date_str, {}))

    def get_budget_usage(self, category: str) -> Dict[str, Any]:
        budget = self._budgets.get(category, 0)
        spent = self._category_costs.get(category, 0)
        usage = (spent / budget * 100) if budget > 0 else 0
        return {
            "category": category,
            "budget": budget,
            "spent": round(spent, 2),
            "remaining": round(budget - spent, 2),
            "usage_percent": round(usage, 2),
            "over_budget": spent > budget,
        }

    def get_all_budget_usage(self) -> List[Dict[str, Any]]:
        return [self.get_budget_usage(cat) for cat in self._budgets.keys()]

    def get_cost_trend(self, days: int = 7) -> List[Dict[str, Any]]:
        trend = []
        today = datetime.now()
        for i in range(days - 1, -1, -1):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            trend.append({
                "date": date_str,
                "total": round(self._daily_costs.get(date_str, 0), 2),
                "by_category": {
                    cat: round(costs, 2)
                    for cat, costs in self._daily_category.get(date_str, {}).items()
                },
            })
        return trend

    def get_top_costs(self, category: str = None, limit: int = 10) -> List[CostRecord]:
        records = self._records if isinstance(self._records, list) else list(self._records.values())
        if category:
            records = [r for r in records if r.category == category]
        records.sort(key=lambda r: r.amount, reverse=True)
        return records[:limit]

    def get_summary(self) -> Dict[str, Any]:
        total = sum(self._category_costs.values())
        today = self.get_daily_cost()
        this_month = self.get_monthly_cost()

        return {
            "total_cost": round(total, 2),
            "daily_cost": round(today, 2),
            "monthly_cost": round(this_month, 2),
            "by_category": {k: round(v, 2) for k, v in self._category_costs.items()},
            "categories_tracked": len(self._category_costs),
            "total_records": len(self._records) if isinstance(self._records, list) else len(self._records),
            "budgets": {cat: self.get_budget_usage(cat) for cat in self._budgets},
        }
