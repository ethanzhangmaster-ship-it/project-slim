"""P2.6.3 Recovery Strategy — 恢复策略定义。

四类策略（用户契约）：

- RetryPolicy         : timeout / 5xx / rate limit；最多 3 次，指数退避 1s/5s/30s
- ReconcilePolicy     : 状态漂移；重读平台真实状态后重执行（1 次）
- RollbackRetryPolicy : 回滚重试；max_retry=1（回滚是危险动作，只补试一次）
- EscalationPolicy    : 人工介入；不执行任何自动动作

策略是纯配置对象：定义「怎么试、试几次、等多久」，
真正的执行永远经 RecoveryExecutor -> P2.3 Authorization -> P2.4 SafeExecutor。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from src.execution.recovery.models import (
    STRATEGY_ESCALATION,
    STRATEGY_RECONCILE,
    STRATEGY_RETRY,
    STRATEGY_ROLLBACK_RETRY,
    TREATMENT_EMERGENCY_ESCALATE,
    TREATMENT_ESCALATE,
    TREATMENT_RECONCILE,
    TREATMENT_RETRY,
    TREATMENT_ROLLBACK_RETRY,
    _as_str,
)

# 默认指数退避（秒）：第 1 次重试前等 1s，第 2 次 5s，第 3 次 30s
DEFAULT_RETRY_BACKOFF: Tuple[float, ...] = (1.0, 5.0, 30.0)
DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_ROLLBACK_MAX_RETRY = 1


def backoff_for(attempt: int, backoff: List[float]) -> float:
    """第 attempt 次尝试（1-based）前应等待的秒数。

    attempt=1 -> backoff[0]，超出表长取最后一项；空表 -> 0。
    """
    if not backoff:
        return 0.0
    index = max(0, min(attempt - 1, len(backoff) - 1))
    return float(backoff[index])


@dataclass(frozen=True)
class RetryPolicy:
    """重试策略：适用瞬时故障（timeout / 5xx / rate limit）。"""

    strategy: str = STRATEGY_RETRY
    max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS
    backoff: Tuple[float, ...] = DEFAULT_RETRY_BACKOFF
    # 超过 max_attempts 仍失败 -> 升级
    escalate_on_exhaust: bool = True

    def wait_before(self, attempt: int) -> float:
        return backoff_for(attempt, list(self.backoff))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "max_attempts": self.max_attempts,
            "backoff": list(self.backoff),
            "escalate_on_exhaust": self.escalate_on_exhaust,
        }


@dataclass(frozen=True)
class ReconcilePolicy:
    """对账策略：状态漂移时重读平台真实状态，再决定是否重执行。

    reread_before_execute: 必须先读平台状态（RecoveryExecutor 会调用
    read_fn / provider 只读接口），避免在错误认知上二次操作。
    """

    strategy: str = STRATEGY_RECONCILE
    max_attempts: int = 1
    backoff: Tuple[float, ...] = ()
    reread_before_execute: bool = True
    escalate_on_exhaust: bool = True

    def wait_before(self, attempt: int) -> float:
        return backoff_for(attempt, list(self.backoff))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "max_attempts": self.max_attempts,
            "backoff": list(self.backoff),
            "reread_before_execute": self.reread_before_execute,
            "escalate_on_exhaust": self.escalate_on_exhaust,
        }


@dataclass(frozen=True)
class RollbackRetryPolicy:
    """回滚重试策略：回滚失败后只补试一次（回滚是危险动作）。

    补试仍失败 -> EMERGENCY escalation（CRITICAL，停止所有自动执行）。
    """

    strategy: str = STRATEGY_ROLLBACK_RETRY
    max_attempts: int = DEFAULT_ROLLBACK_MAX_RETRY
    backoff: Tuple[float, ...] = (1.0,)
    escalate_on_exhaust: bool = True
    emergency_on_exhaust: bool = True

    def wait_before(self, attempt: int) -> float:
        return backoff_for(attempt, list(self.backoff))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "max_attempts": self.max_attempts,
            "backoff": list(self.backoff),
            "escalate_on_exhaust": self.escalate_on_exhaust,
            "emergency_on_exhaust": self.emergency_on_exhaust,
        }


@dataclass(frozen=True)
class EscalationPolicy:
    """升级策略：MANUAL_INTERVENTION——不执行任何自动动作。"""

    strategy: str = STRATEGY_ESCALATION
    max_attempts: int = 1
    backoff: Tuple[float, ...] = ()
    escalate_on_exhaust: bool = True
    manual_intervention: bool = True

    def wait_before(self, attempt: int) -> float:  # pragma: no cover - 恒 0
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "max_attempts": self.max_attempts,
            "backoff": list(self.backoff),
            "escalate_on_exhaust": self.escalate_on_exhaust,
            "manual_intervention": self.manual_intervention,
        }


# ---------------------------------------------------------------------------
# treatment -> policy 映射
# ---------------------------------------------------------------------------

_TREATMENT_POLICY = {
    TREATMENT_RETRY: RetryPolicy(),
    TREATMENT_RECONCILE: ReconcilePolicy(),
    TREATMENT_ROLLBACK_RETRY: RollbackRetryPolicy(),
    TREATMENT_ESCALATE: EscalationPolicy(),
    TREATMENT_EMERGENCY_ESCALATE: EscalationPolicy(),
}


def policy_for_treatment(treatment: Any):
    """TREATMENT_* -> 对应策略实例；未知处置一律 EscalationPolicy（保守）。"""
    return _TREATMENT_POLICY.get(_as_str(treatment), EscalationPolicy())


__all__ = [
    "DEFAULT_RETRY_BACKOFF",
    "DEFAULT_RETRY_MAX_ATTEMPTS",
    "DEFAULT_ROLLBACK_MAX_RETRY",
    "backoff_for",
    "RetryPolicy",
    "ReconcilePolicy",
    "RollbackRetryPolicy",
    "EscalationPolicy",
    "policy_for_treatment",
]
