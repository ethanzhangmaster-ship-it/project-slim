"""P3.3.3 — Adaptive Strategy Planner（提案 → GrowthDecision 生产级落地器）。

职责（薄层，不重写执行链）：
- 把 AdaptiveStrategyRequest 适配成 E17.3 GrowthDecision
- 提供首批 TEMPLATES（network_cleanup / campaign_pause；budget_scale 暂缓）
- 解析并合并 Provider 参数（network / ad_unit_id / campaign_id）

安全边界：
- 仅构造 GrowthDecision 与参数；**绝不** import 任何具体 Provider
- 只走已映射的安全动作
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.ceo_intelligence.decision_engine.models import (
    DecisionType,
    GrowthDecision,
)
from src.execution.models import ExecutionAction

from .models import (
    AdaptiveAction,
    AdaptiveStrategyRequest,
    AdaptiveStrategyTemplate,
)


class UnknownStrategyError(ValueError):
    """请求的 strategy_id 不在已注册模板中（或被暂缓）。"""


# ---------------------------------------------------------------------------
# 首批 TEMPLATES（仅安全动作）
# ---------------------------------------------------------------------------
# 先验来源（E17.8 get_prior）：
#   monetization  -> +0.18 / +0.15 / conf 0.70 / risk 0.50  -> 走 MANUAL（risk>=0.3）
#   ua_stop_loss  -> +0.08 / +0.20 / conf 0.85 / risk 0.25  -> PAUSE_CAMPAIGN 恒 MANUAL
DEFAULT_TEMPLATES: Dict[str, AdaptiveStrategyTemplate] = {
    "adaptive.network_cleanup": AdaptiveStrategyTemplate(
        strategy_id="adaptive.network_cleanup",
        display_name="关停僵尸广告网络",
        adaptive_action=AdaptiveAction.NETWORK_CLEANUP,
        decision_action="MAX_OPTIMIZE",
        opportunity_type="monetization",
        decision_type=DecisionType.EXECUTE,
        expected_value=0.18,
        confidence=0.70,
        risk=0.50,
        reason="低 eCPM 网络拖累整体变现，关停以回收填充",
        execution_action=ExecutionAction.DISABLE_NETWORK,
        dimension="ad_monetization",
        provider_params={"network": "zombie_network"},
    ),
    "adaptive.campaign_pause": AdaptiveStrategyTemplate(
        strategy_id="adaptive.campaign_pause",
        display_name="暂停亏损广告系列",
        adaptive_action=AdaptiveAction.CAMPAIGN_PAUSE,
        decision_action="UA_STOP",
        # 先验表含 ua_stop_loss（+0.08 / +0.20 / 0.85 / 0.25），UA_STOP 同样映射到 PAUSE_CAMPAIGN
        opportunity_type="ua_stop_loss",
        decision_type=DecisionType.EXECUTE,
        expected_value=0.08,
        confidence=0.85,
        risk=0.25,
        reason="系列 ROAS 持续低于阈值，止损暂停",
        execution_action=ExecutionAction.PAUSE_CAMPAIGN,
        dimension="ua",
        provider_params={"campaign_id": "bleeding_campaign"},
    ),
}


@dataclass
class PlannedAction:
    """Planner 的产物：可交给 Controller 的单个落地计划。"""

    template: AdaptiveStrategyTemplate
    decision: GrowthDecision
    provider_params: Dict[str, Any]
    opportunity_id: str
    expected_value: float


class AdaptiveStrategyPlanner:
    """StrategyProposal → GrowthDecision + Provider 参数。"""

    def __init__(self, templates: Optional[Dict[str, AdaptiveStrategyTemplate]] = None) -> None:
        self.templates = templates if templates is not None else dict(DEFAULT_TEMPLATES)

    # ------------------------------------------------------------------
    def get_template(self, strategy_id: str) -> AdaptiveStrategyTemplate:
        tpl = self.templates.get(str(strategy_id))
        if tpl is None:
            raise UnknownStrategyError(f"未知自适应策略：{strategy_id}")
        if not tpl.supported:
            raise UnknownStrategyError(f"策略 {strategy_id} 当前暂缓（budget_scale）")
        return tpl

    # ------------------------------------------------------------------
    def plan(self, request: AdaptiveStrategyRequest) -> PlannedAction:
        """把一个请求适配成可执行的 GrowthDecision + Provider 参数。"""
        tpl = self.get_template(request.strategy_id)
        params = dict(request.parameters or {})

        # opportunity_id = game_id:type（与 E17.4 / priors 解析一致）
        opportunity_id = f"{request.target}:{tpl.opportunity_type}"

        # expected_value 可被请求覆盖（支持 P3.3 反馈驱动的个性调整）
        expected_value = float(params.get("expected_value", tpl.expected_value))

        decision = GrowthDecision(
            game_id=request.target,
            opportunity_id=opportunity_id,
            action=tpl.decision_action,
            decision_type=tpl.decision_type,
            expected_value=expected_value,
            confidence=tpl.confidence,
            risk=tpl.risk,
            reason=tpl.reason or request.expected_change,
        )

        # Provider 参数：模板默认 + 请求覆盖（re-merge 进 expected_impact 的键）
        provider_params: Dict[str, Any] = dict(tpl.provider_params)
        for key in ("network", "ad_unit_id", "campaign_id", "networks"):
            if key in params:
                provider_params[key] = params[key]

        return PlannedAction(
            template=tpl,
            decision=decision,
            provider_params=provider_params,
            opportunity_id=opportunity_id,
            expected_value=expected_value,
        )

    def known_strategies(self) -> list:
        return [t.strategy_id for t in self.templates.values() if t.supported]


__all__ = [
    "AdaptiveStrategyPlanner",
    "PlannedAction",
    "UnknownStrategyError",
    "DEFAULT_TEMPLATES",
]
