from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


@dataclass
class MonthlyStrategyResult:
    month: str
    objectives: List[Dict[str, Any]] = field(default_factory=list)
    strategy: Dict[str, Any] = field(default_factory=dict)
    budget_allocation: Dict[str, float] = field(default_factory=dict)
    kpi_targets: Dict[str, float] = field(default_factory=dict)
    risks: List[str] = field(default_factory=list)
    completed_at: Optional[datetime] = None


class MonthlyStrategy:
    def __init__(self):
        self._strategies: Dict[str, MonthlyStrategyResult] = {}

    def get_month_str(self, date: datetime = None) -> str:
        if date is None:
            date = datetime.now()
        return date.strftime("%Y-%m")

    def run_strategy_session(
        self,
        previous_month_data: Dict[str, Any] = None,
        month: str = None,
    ) -> MonthlyStrategyResult:
        if month is None:
            month = self.get_month_str()

        strategy = MonthlyStrategyResult(
            month=month,
        )

        if previous_month_data:
            strategy.strategy = self._build_strategy(previous_month_data)
        else:
            strategy.strategy = self._build_default_strategy()

        strategy.objectives = self._define_objectives(strategy.strategy)
        strategy.budget_allocation = self._allocate_budget(strategy.strategy)
        strategy.kpi_targets = self._set_kpi_targets(strategy.strategy)
        strategy.risks = self._identify_risks(strategy.strategy)
        strategy.completed_at = datetime.now()

        self._strategies[month] = strategy
        return strategy

    def _build_default_strategy(self) -> Dict[str, Any]:
        return {
            "focus": "scale_profitable_channels",
            "growth_target": 0.15,
            "market_focus": "US",
            "product_priority": "retention_improvement",
            "creative_volume": 50,
            "new_game_experiments": 1,
        }

    def _build_strategy(self, prev_data: Dict[str, Any]) -> Dict[str, Any]:
        strategy = self._build_default_strategy()

        revenue_growth = prev_data.get("revenue_growth", 0)
        if revenue_growth > 0.2:
            strategy["growth_target"] = 0.2
            strategy["creative_volume"] = 80
        elif revenue_growth < 0.05:
            strategy["growth_target"] = 0.08
            strategy["new_game_experiments"] = 2

        roi = prev_data.get("roi", 1.5)
        if roi > 2.0:
            strategy["budget_scale"] = 0.3
        elif roi < 1.2:
            strategy["budget_scale"] = -0.1

        return strategy

    def _define_objectives(self, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        growth = strategy.get("growth_target", 0.15) * 100
        return [
            {
                "id": "obj_001",
                "title": "Revenue Growth",
                "description": f"Achieve {growth:.0f}% revenue growth",
                "target_metric": "mrr",
                "target_value": f"{growth:.0f}% increase",
                "priority": 1,
            },
            {
                "id": "obj_002",
                "title": "Profitability",
                "description": "Maintain ROI above 1.8x",
                "target_metric": "roi",
                "target_value": ">1.8x",
                "priority": 2,
            },
            {
                "id": "obj_003",
                "title": "Product Improvement",
                "description": "Improve D7 retention by 2pp",
                "target_metric": "d7_retention",
                "target_value": "+2%",
                "priority": 3,
            },
        ]

    def _allocate_budget(self, strategy: Dict[str, Any]) -> Dict[str, float]:
        base_budget = 50000.0
        scale = strategy.get("budget_scale", 0.0)
        total = base_budget * (1 + scale)

        return {
            "ua": total * 0.5,
            "creative": total * 0.15,
            "product": total * 0.2,
            "as tools": total * 0.05,
            "experimentation": total * 0.1,
        }

    def _set_kpi_targets(self, strategy: Dict[str, Any]) -> Dict[str, float]:
        growth = strategy.get("growth_target", 0.15)
        return {
            "mrr_growth_rate": growth,
            "roi_min": 1.8,
            "d7_retention": 0.20,
            "d30_ltv": 4.5,
            "payback_days": 90,
            "new_game_pipeline": 2,
        }

    def _identify_risks(self, strategy: Dict[str, Any]) -> List[str]:
        risks = [
            "Market competition intensifying",
            "Platform policy changes",
            "Creative fatigue",
            "CPI increase",
        ]

        if strategy.get("new_game_experiments", 0) > 1:
            risks.append("Resource spread too thin across projects")

        if strategy.get("growth_target", 0) > 0.15:
            risks.append("Aggressive growth may impact profitability")

        return risks

    def get_strategy(self, month: str) -> Optional[MonthlyStrategyResult]:
        return self._strategies.get(month)

    def get_strategy_progress(self, month: str, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        strategy = self._strategies.get(month)
        if not strategy:
            return {}

        progress = {}
        for objective in strategy.objectives:
            metric = objective["target_metric"]
            current = current_metrics.get(metric, 0)
            progress[objective["id"]] = {
                "title": objective["title"],
                "target": objective["target_value"],
                "current": current,
                "status": "on_track" if current > 0 else "behind",
            }

        return progress

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_strategies": len(self._strategies),
            "latest_month": max(self._strategies.keys()) if self._strategies else None,
            "total_objectives": sum(len(s.objectives) for s in self._strategies.values()),
            "total_risks": sum(len(s.risks) for s in self._strategies.values()),
        }
