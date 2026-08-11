"""E17.6 — RemoteConfigAdapter：ECONOMY 域执行（定价 / 商品包，PAYMENT 权限域）。

SIM-only：分析与方案设计本地确定性完成；`apply_pricing` 属 CRITICAL，
Router 权限门会在到达本 Adapter 之前拦截（永不自动改价）。
接真实 Firebase Remote Config 时在此实现 live 子类。
"""
from __future__ import annotations

from ..models import AdapterOutcome, ExecutionAction, ExecutionDomain
from .base import BaseSimAdapter


class RemoteConfigAdapter(BaseSimAdapter):
    name = "remote_config"
    domain = ExecutionDomain.ECONOMY.value

    def execute(self, action: ExecutionAction) -> AdapterOutcome:
        if action.payload.get("simulate_failure"):
            return AdapterOutcome(
                ok=False, real_api_called=False,
                error="remote config error (simulated)",
                detail=f"failed {action.action_type} for {action.game_id}",
            )
        if action.action_type == "analyze_revenue":
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: analyzed revenue structure of {action.game_id}",
                data={"breakdown": "iap_vs_iaa"},
            )
        if action.action_type == "design_pricing":
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: designed pack/price adjustment for {action.game_id}",
            )
        if action.action_type == "ab_test_pricing":
            return AdapterOutcome(
                ok=True, real_api_called=False,
                detail=f"simulated: would start pricing A/B test for {action.game_id}",
            )
        if action.action_type == "apply_pricing":
            # 防御：即便权限门被绕过，本 Adapter 也绝不落真实改价
            return AdapterOutcome(
                ok=False, real_api_called=False,
                error="apply_pricing is CRITICAL: manual console operation only",
                detail="refused: pricing writes are never automated",
            )
        return AdapterOutcome(
            ok=True, real_api_called=False,
            detail=f"simulated: {action.action_type} for {action.game_id}",
        )


__all__ = ["RemoteConfigAdapter"]
