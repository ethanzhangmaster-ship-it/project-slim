"""P3.3 — Outcome Evaluator（结果评估器）。

把：
    Action + Execution Result + Business Outcome
转成：
    StrategyFeedback

纯函数式、零重算：不重新计算 ROAS，只把「已经发生的执行结果 + 业务结果」
归并成一条策略反馈。reward ∈ [-1, 1]，由业务改善幅度或执行成败推导。
"""
from __future__ import annotations

import math
from typing import Any, Optional

from .models import BusinessOutcome, StrategyFeedback


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _resolve_strategy_id(action: Any, strategy_id: Optional[str]) -> str:
    if strategy_id:
        return strategy_id
    for attr in ("strategy_id", "opportunity_type", "strategy_type"):
        v = getattr(action, attr, None)
        if v:
            return str(v)
    return "unknown_strategy"


def _resolve_action_id(action: Any, action_id: Optional[str]) -> str:
    if action_id:
        return action_id
    a = getattr(action, "action_id", None)
    if a:
        return str(a)
    game = getattr(action, "game_id", "") or ""
    act = getattr(action, "action", "") or ""
    return f"{game}:{act}" if (game or act) else "unknown_action"


def _execution_ok(execution_result: Optional[Any]) -> Optional[bool]:
    if execution_result is None:
        return None
    ok = getattr(execution_result, "ok", None)
    if ok is None:
        verdict = getattr(execution_result, "verdict", None)
        if verdict is not None:
            v = str(verdict).lower()
            # 被闸门拦截视作「保护生效」，非策略失败
            return "block" in v
        return None
    return bool(ok)


def _outcome_from(
    exec_ok: Optional[bool], business: Optional[BusinessOutcome]
) -> str:
    if exec_ok is True:
        return "SUCCESS"
    if exec_ok is False:
        return "FAILURE"
    if business is not None:
        return "SUCCESS" if business.after >= business.before else "FAILURE"
    return "NEUTRAL"


def _reward_from(
    exec_ok: Optional[bool], business: Optional[BusinessOutcome]
) -> float:
    if business is not None:
        return round(_clamp(business.delta_ratio()), 4)
    if exec_ok is True:
        return 1.0
    if exec_ok is False:
        return -1.0
    return 0.0


def _evidence(
    exec_ok: Optional[bool],
    business: Optional[BusinessOutcome],
    execution_result: Optional[Any],
) -> str:
    if business is not None:
        ratio = business.delta_ratio()
        pct = f"{ratio * 100:+.1f}%"
        return f"{business.metric} {business.before}→{business.after} ({pct})"
    if exec_ok is True:
        return "execution ok"
    if exec_ok is False:
        verdict = getattr(execution_result, "verdict", None)
        v = f" ({verdict})" if verdict is not None else ""
        return f"execution failed{v}"
    return "no execution outcome (pending / observe)"


def evaluate(
    action: Any,
    execution_result: Optional[Any] = None,
    business_outcome: Optional[BusinessOutcome] = None,
    *,
    strategy_id: Optional[str] = None,
    action_id: Optional[str] = None,
) -> StrategyFeedback:
    """Action + Execution Result + Business Outcome → StrategyFeedback。

    零重算：只把已有结果归并成一条反馈。
    """
    exec_ok = _execution_ok(execution_result)
    outcome = _outcome_from(exec_ok, business_outcome)
    reward = _reward_from(exec_ok, business_outcome)
    return StrategyFeedback(
        action_id=_resolve_action_id(action, action_id),
        strategy_id=_resolve_strategy_id(action, strategy_id),
        reward=reward,
        outcome=outcome,
        evidence=_evidence(exec_ok, business_outcome, execution_result),
        timestamp="",
    )


class OutcomeEvaluator:
    """可注入的策略评估器（与 StrategyLoop 同生命周期）。"""

    def evaluate(
        self,
        action: Any,
        execution_result: Optional[Any] = None,
        business_outcome: Optional[BusinessOutcome] = None,
        *,
        strategy_id: Optional[str] = None,
        action_id: Optional[str] = None,
    ) -> StrategyFeedback:
        return evaluate(
            action,
            execution_result=execution_result,
            business_outcome=business_outcome,
            strategy_id=strategy_id,
            action_id=action_id,
        )


__all__ = ["OutcomeEvaluator", "evaluate", "BusinessOutcome"]
