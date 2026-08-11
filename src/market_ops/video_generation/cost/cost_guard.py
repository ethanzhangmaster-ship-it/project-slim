"""Cost Guard"""
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .budget_manager import BudgetManager
from .cost_predictor import CostPredictor
from ..orchestrator.generation_task import GenerationTask


@dataclass
class CostGuardDecision:
    allowed: bool
    reason: str = ""
    suggested_priority: int = 0


class CostGuard:
    """成本守卫 - 基于预算控制生成任务"""

    def __init__(self, budget_manager: BudgetManager = None, warning_threshold: float = 0.8):
        self.budget_manager = budget_manager or BudgetManager()
        self.warning_threshold = warning_threshold

    def check_task(self, task: GenerationTask) -> CostGuardDecision:
        usage_percent = self.budget_manager.get_daily_usage_percent() / 100

        predicted_cost = CostPredictor.predict(
            platform=task.platform,
            duration=task.prompt.get("duration", 5),
        )["estimated_cost"]

        if not self.budget_manager.can_afford(predicted_cost):
            return CostGuardDecision(
                allowed=False,
                reason=f"Budget exceeded. Daily budget: ${self.budget_manager.daily_budget}, "
                       f"spent: ${self.budget_manager.get_daily_spent():.2f}, "
                       f"task cost: ${predicted_cost:.2f}",
            )

        if usage_percent >= self.warning_threshold:
            if task.priority < 8:
                return CostGuardDecision(
                    allowed=False,
                    reason=f"Budget usage at {usage_percent*100:.0f}%. "
                           f"Low priority tasks (priority < 8) are paused.",
                    suggested_priority=8,
                )

        return CostGuardDecision(allowed=True)

    def check_platform(self, platform: str, duration: float) -> CostGuardDecision:
        predicted_cost = CostPredictor.predict(platform, duration)["estimated_cost"]
        if not self.budget_manager.can_afford(predicted_cost):
            return CostGuardDecision(
                allowed=False,
                reason=f"Cannot afford {platform} generation (${predicted_cost:.2f})",
            )
        return CostGuardDecision(allowed=True)

    def get_cheapest_platform(self, duration: float, platforms: list = None) -> Optional[str]:
        comparisons = CostPredictor.compare_platforms(duration)
        if platforms:
            comparisons = {k: v for k, v in comparisons.items() if k in platforms}
        if not comparisons:
            return None
        return min(comparisons.keys(), key=lambda k: comparisons[k]["estimated_cost"])
