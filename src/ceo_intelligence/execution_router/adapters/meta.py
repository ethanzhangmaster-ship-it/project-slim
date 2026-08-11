"""E17.6 — MetaAdapter：UA 域执行（Meta Ads）。

SIM-only：确定性模拟预算 / 实验 / 暂停操作，real_api_called 永远 False。
接真实 Meta Marketing API 时在此实现 live 子类（须走审批门 + 独立凭据库）。

支持 payload["simulate_failure"]=True 触发确定性失败（供 Failure Recovery 测试）。
"""
from __future__ import annotations

from ..models import AdapterOutcome, ExecutionAction, ExecutionDomain
from .base import BaseSimAdapter


class MetaAdapter(BaseSimAdapter):
    name = "meta_ads"
    domain = ExecutionDomain.UA.value

    def execute(self, action: ExecutionAction) -> AdapterOutcome:
        if action.payload.get("simulate_failure"):
            return AdapterOutcome(
                ok=False, real_api_called=False,
                error="meta api error (simulated)",
                detail=f"failed {action.action_type} on {action.target or action.game_id}",
            )
        p = action.payload
        if action.action_type == "increase_budget":
            pct = float(p.get("percent", 20))
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: would increase budget {pct:.0f}% "
                       f"on {action.target or action.game_id}",
                data={"budget_change_pct": pct},
            )
        if action.action_type == "pause_campaigns":
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: would pause losing campaigns of {action.game_id}",
            )
        if action.action_type == "reallocate_budget":
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: would reallocate budget to winners of {action.game_id}",
            )
        if action.action_type == "run_experiment":
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: would launch Meta creative experiment for {action.game_id}",
                data={"experiment": "creative_test"},
            )
        # 通用只读/监控类
        return AdapterOutcome(
            ok=True, real_api_called=False,
            detail=f"simulated: {action.action_type} on {action.game_id}",
        )


__all__ = ["MetaAdapter"]
