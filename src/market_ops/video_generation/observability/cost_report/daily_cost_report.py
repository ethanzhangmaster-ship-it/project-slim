"""Daily Cost Report - 每日成本报告"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class DailyCostReport:
    """每日成本报告"""
    date: str = ""
    generated: int = 0
    total_cost: float = 0.0
    avg_cost: float = 0.0
    success_cost: float = 0.0
    failed_cost: float = 0.0
    budget_used: float = 0.0
    budget_remaining: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "generated": self.generated,
            "total_cost": round(self.total_cost, 2),
            "avg_cost": round(self.avg_cost, 3),
            "success_cost": round(self.success_cost, 3),
            "failed_cost": round(self.failed_cost, 3),
            "budget_used": round(self.budget_used, 2),
            "budget_remaining": round(self.budget_remaining, 2),
        }
    
    def to_text(self) -> str:
        """文本格式报告"""
        lines = [
            f"=== Daily Generation Cost Report ===",
            f"",
            f"Date: {self.date}",
            f"Generated: {self.generated} videos",
            f"",
            f"Total Cost: ${self.total_cost:.2f}",
            f"Average: ${self.avg_cost:.3f}",
            f"Success Cost: ${self.success_cost:.3f}",
            f"Failed Cost: ${self.failed_cost:.3f}",
            f"",
            f"Budget Used: ${self.budget_used:.2f}",
            f"Budget Remaining: ${self.budget_remaining:.2f}",
        ]
        return "\n".join(lines)


class DailyCostReporter:
    """每日成本报告生成器"""
    
    def __init__(self, daily_budget: float = 1000.0):
        self.daily_budget = daily_budget
    
    def generate(
        self,
        generation_data: Dict[str, Any],
        cost_data: Dict[str, Any],
        date: str = None,
    ) -> DailyCostReport:
        """生成每日成本报告"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        total_cost = cost_data.get("total", 0.0)
        generated = generation_data.get("total", 0)
        
        return DailyCostReport(
            date=date,
            generated=generated,
            total_cost=total_cost,
            avg_cost=total_cost / generated if generated > 0 else 0.0,
            success_cost=cost_data.get("success_cost", 0.0),
            failed_cost=cost_data.get("failed_cost", 0.0),
            budget_used=total_cost,
            budget_remaining=max(0, self.daily_budget - total_cost),
        )
    
    def generate_demo(self) -> DailyCostReport:
        """生成演示报告"""
        generation_data = {"total": 1000}
        cost_data = {
            "total": 385.0,
            "success_cost": 0.41,
            "failed_cost": 0.08,
        }
        return self.generate(generation_data, cost_data, "2026-07-08")
