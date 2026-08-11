"""P2.6.5 Recovery Executor — 恢复动作执行器。

**纪律红线（用户契约）**：恢复动作绝不绕过 P2.3。

    正确： Recovery -> Authorization Check -> Safe Executor -> Provider
    禁止： Failure  -> 直接调用 Meta API

实现方式：本层唯一的执行出口是注入的 P2.4 SafeExecutor.execute(request)。
SafeExecutor 内部编排 授权(P2.3 AuthorizationGate)/风险/幂等/快照/执行/校验/审计
七步——recovery 层不拥有、也不可能拥有任何直连 Provider 的通道。

重试细节：
- 每次重试构造**新的 ExecutionRequest**（新 request_id，同 intent/mode/authorization）。
  若复用原 request_id，P2.4 幂等闸门会命中 RETURN_EXISTING 返回历史失败结果，
  重试将永远无效。
- PRODUCTION 模式下 P2.3 授权令牌单次消费（Rule 4）：重试前可经
  reauthorize_fn 重新获取授权；未提供且令牌已消费 -> SafeExecutor 会 BLOCK，
  这正是审批边界的正确行为（宁可失败也不绕过审批）。
- RECONCILE：先经 read_fn 重读平台真实状态；若已与期望一致则「无操作恢复」。
- ESCALATION 计划：不执行任何动作，直接交回引擎升级。
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from src.execution.recovery.models import (
    RECOVERY_ESCALATED,
    RECOVERY_NOT_RECOVERED,
    RECOVERY_RECOVERED,
    STRATEGY_RECONCILE,
    RecoveryAttempt,
    RecoveryIncident,
    RecoveryPlan,
    RecoveryResult,
    _as_str,
)
from src.execution.recovery.strategy import backoff_for


def _clone_request(request: Any) -> Any:
    """克隆 ExecutionRequest：新 request_id，同 intent/mode/authorization。

    延迟导入避免 import 环。
    """
    from src.execution.models import ExecutionRequest

    return ExecutionRequest(
        intent=request.intent,
        mode=request.mode,
        authorization=getattr(request, "authorization", None),
    )


class RecoveryExecutor:
    """恢复动作执行器——唯一出口是 SafeExecutor（P2.3 + P2.4 全链路）。

    Args:
        safe_executor  : P2.4 SafeExecutor（必需）；.execute(request)->outcome
        sleep_fn       : 退避等待函数（测试注入 fake，避免真 sleep）
        read_fn        : RECONCILE 用的只读状态读取 read_fn(target)->dict
        reauthorize_fn : 重试前重新授权 reauthorize_fn(request)->request
                         （PRODUCTION 令牌单次消费时按需注入）
    """

    def __init__(
        self,
        safe_executor: Any,
        sleep_fn: Callable[[float], None] = time.sleep,
        read_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
        reauthorize_fn: Optional[Callable[[Any], Any]] = None,
    ):
        if safe_executor is None:
            raise ValueError(
                "RecoveryExecutor requires a SafeExecutor — "
                "recovery MUST go through P2.3 authorization + P2.4 sandbox"
            )
        self.safe_executor = safe_executor
        self.sleep_fn = sleep_fn
        self.read_fn = read_fn
        self.reauthorize_fn = reauthorize_fn

    # ------------------------------------------------------------------

    def recover(
        self,
        incident: RecoveryIncident,
        plan: RecoveryPlan,
        request: Any,
    ) -> RecoveryResult:
        """按计划执行恢复。

        Returns:
            RecoveryResult：
            - RECOVERED     : 某次尝试 outcome.ok（验证由 Verifier 另行确认）
            - NOT_RECOVERED : 用尽 max_attempts 仍失败（引擎将升级）
            - ESCALATED     : escalate_only 计划，未执行任何动作
        """
        # ESCALATION 计划：不执行任何自动动作（incident 停在 PLANNED，
        # 由 EscalationManager 迁到 ESCALATED）
        if plan.escalate_only:
            return RecoveryResult(
                incident_id=incident.incident_id,
                plan_id=plan.plan_id,
                status=RECOVERY_ESCALATED,
                attempts=0,
                message="escalation-only plan — no automatic action taken",
            )

        if incident.status == "PLANNED":
            incident.transition("RECOVERING", reason=f"plan={plan.plan_id}")

        # RECONCILE：先重读平台真实状态
        if plan.strategy == STRATEGY_RECONCILE and self.read_fn is not None:
            observed = self.read_fn(plan.target) or {}
            if self._state_matches(plan.expected_state, observed):
                # 平台实际已处于期望状态——无操作恢复
                return RecoveryResult(
                    incident_id=incident.incident_id,
                    plan_id=plan.plan_id,
                    status=RECOVERY_RECOVERED,
                    attempts=0,
                    outcome=None,
                    message=(
                        "reconcile: platform already in expected state, "
                        "no re-execution needed"
                    ),
                )

        attempt_log: List[RecoveryAttempt] = []
        last_outcome: Any = None

        for attempt in range(1, plan.max_attempts + 1):
            wait = backoff_for(attempt, plan.backoff)
            if wait > 0:
                self.sleep_fn(wait)

            retry_request = _clone_request(request)
            if self.reauthorize_fn is not None:
                retry_request = self.reauthorize_fn(retry_request)

            # 唯一执行出口：SafeExecutor（P2.3 授权门 + P2.4 七步沙箱）
            outcome = self.safe_executor.execute(retry_request)
            last_outcome = outcome
            ok = bool(getattr(outcome, "ok", False))
            attempt_log.append(
                RecoveryAttempt(
                    attempt=attempt,
                    waited_seconds=wait,
                    verdict=_as_str(getattr(outcome, "verdict", "")),
                    ok=ok,
                    error=self._outcome_error(outcome),
                )
            )
            if ok:
                return RecoveryResult(
                    incident_id=incident.incident_id,
                    plan_id=plan.plan_id,
                    status=RECOVERY_RECOVERED,
                    attempts=attempt,
                    attempt_log=attempt_log,
                    outcome=self._outcome_dict(outcome),
                    message=f"recovered on attempt {attempt}/{plan.max_attempts}",
                )

        # 用尽尝试仍失败——交回引擎升级
        return RecoveryResult(
            incident_id=incident.incident_id,
            plan_id=plan.plan_id,
            status=RECOVERY_NOT_RECOVERED,
            attempts=len(attempt_log),
            attempt_log=attempt_log,
            outcome=self._outcome_dict(last_outcome),
            message=(
                f"exhausted {plan.max_attempts} attempt(s) without recovery"
            ),
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _state_matches(expected: Dict[str, Any], observed: Dict[str, Any]) -> bool:
        """expected 的每个键值都能在 observed 中匹配（大小写不敏感字符串比较）。"""
        if not expected:
            return False
        for key, value in expected.items():
            actual = observed.get(key)
            if _as_str(value).lower() != _as_str(actual).lower():
                return False
        return True

    @staticmethod
    def _outcome_error(outcome: Any) -> str:
        result = getattr(outcome, "result", None)
        if result is not None and getattr(result, "error", None):
            return str(result.error)
        context = getattr(outcome, "context", None)
        return str(getattr(context, "reason", "") or "")

    @staticmethod
    def _outcome_dict(outcome: Any) -> Optional[Dict[str, Any]]:
        if outcome is None:
            return None
        if hasattr(outcome, "to_dict"):
            return outcome.to_dict()
        return None


__all__ = ["RecoveryExecutor"]
