"""P3.3 — Strategy Mutation Engine（策略突变引擎）。

输入：历史策略绩效（StrategyState + StrategyInsight）。
输出：StrategyProposal（建议修改策略；requires_simulation 恒 True）。

铁律：
- 引擎**只产出建议**，绝不执行、绝不修改生产参数、绝不调 Provider。
- 任何生产变更都必须先过 Simulation 闸门（见 guard.py）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .models import (
    StrategyInsight,
    StrategyProposal,
    StrategyState,
    StrategyStatus,
)

# 已知策略 → 更稳妥的变体（参数降级，降低波动）
SAFER_VARIANT: Dict[str, tuple] = {
    "aggressive_scale": (
        "conservative_scale",
        {"budget_growth": 0.10},
        "高波动失败过多，降低预算增长以收敛风险",
    ),
    "ua_scale": (
        "conservative_scale",
        {"budget_growth": 0.10},
        "UA 放量波动过大，收敛预算以避免烧钱",
    ),
}

# 触发突变的阈值
_REDUCE_RATE = 0.40       # 历史成功率低于此值且样本足够 → 触发
_MIN_SAMPLES = 5
_CONSEC_FAIL_TRIGGER = 3  # 连续失败达到此数 → 触发


class StrategyMutationEngine:
    """把历史绩效转成策略调整建议。"""

    def __init__(self, safer_variant: Dict[str, tuple] = None) -> None:
        self._rules = safer_variant or SAFER_VARIANT

    def propose(
        self,
        states: Dict[str, StrategyState],
        insights: List[StrategyInsight],
    ) -> List[StrategyProposal]:
        rec_by_id = {i.strategy_id: i for i in insights}
        proposals: List[StrategyProposal] = []
        for sid, st in states.items():
            rule = self._rules.get(sid)
            if rule is None:
                continue  # 无更稳妥变体 → 不突变（保持）
            trigger, reason = self._should_mutate(st, rec_by_id.get(sid))
            if not trigger:
                continue
            target_sid, params, base_reason = rule
            change = (
                f"切换至 {target_sid}：" +
                "，".join(f"{k}={v}" for k, v in params.items())
            )
            proposals.append(StrategyProposal(
                current_strategy=sid,
                proposed_change=change,
                expected_impact="降低波动、保护下行；保留上行机会",
                confidence=round(min(0.9, 0.3 + 0.1 * st.samples), 4),
                requires_simulation=True,
            ))
        return proposals

    def _should_mutate(
        self, st: StrategyState, insight: Any
    ) -> (bool, str):
        consec = int(st.performance.get("consecutive_failures", 0))
        if st.status == StrategyStatus.DISABLED:
            return (True, "策略已停用，建议以更稳妥变体重启")
        if consec >= _CONSEC_FAIL_TRIGGER:
            return (True, f"连续失败 {consec} 次，触发降险")
        if (insight is not None
                and insight.recommendation == "reduce"
                and st.samples >= _MIN_SAMPLES):
            return (True, "历史成功率低于阈值，建议降权")
        return (False, "")


__all__ = ["StrategyMutationEngine", "SAFER_VARIANT"]
