"""E17.6 — AnalyticsAdapter：ANALYTICS 域（只读监控 / 评估，永远 SAFE）。

模板里大量 "Monitor ROAS / Evaluate ... / Validate ..." 步骤归此域：
真实数据由 E17.1 Growth Reality Hub 负责采集，这里只登记监控任务。
"""
from __future__ import annotations

from ..models import AdapterOutcome, ExecutionAction, ExecutionDomain
from .base import BaseSimAdapter


class AnalyticsAdapter(BaseSimAdapter):
    name = "analytics"
    domain = ExecutionDomain.ANALYTICS.value

    def execute(self, action: ExecutionAction) -> AdapterOutcome:
        if action.payload.get("simulate_failure"):
            return AdapterOutcome(
                ok=False, real_api_called=False,
                error="analytics error (simulated)",
                detail=f"failed {action.action_type} for {action.game_id}",
            )
        return AdapterOutcome(
            ok=True, real_api_called=False,
            detail=f"registered monitoring task: {action.action_type} for {action.game_id}"
                   " (data via Growth Reality Hub)",
            data={"monitor": action.action_type},
        )


__all__ = ["AnalyticsAdapter"]
