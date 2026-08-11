"""P2.6.6 Recovery Verification — 恢复后验证。

恢复不能只看「执行返回 ok」——必须验证业务状态真的回到期望值。

示例（用户契约）：
    原 DISABLE_NETWORK 失败 -> RETRY 成功 -> 读取平台状态 network:disabled
    -> RECOVERED；仍是 enabled -> NOT_RECOVERED（引擎将升级）

验证优先级：
    1. read_fn（平台只读接口）实读状态 —— 最强证据
    2. outcome.result.after_state —— 执行结果自带的后态
    3. 两者都没有 -> UNVERIFIABLE（保守：不算恢复成功）

DRY_RUN 纪律：dry_run outcome 的 after_state 是「期望后态」而非真实平台状态，
verify 仍可比对（用于测试链路），但 UNVERIFIABLE 优先级判断不变。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.execution.recovery.models import (
    VERIFY_NOT_RECOVERED,
    VERIFY_RECOVERED,
    VERIFY_UNVERIFIABLE,
    RecoveryPlan,
    VerificationResult,
    _as_str,
)


class RecoveryVerifier:
    """恢复后状态验证器。

    Args:
        read_fn : 平台只读状态读取 read_fn(target)->dict（可选；
                  不注入则退回 outcome.after_state）
    """

    def __init__(
        self, read_fn: Optional[Callable[[str], Dict[str, Any]]] = None
    ):
        self.read_fn = read_fn

    def verify(
        self,
        plan: RecoveryPlan,
        outcome: Any = None,
        expected_state: Optional[Dict[str, Any]] = None,
        read_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> VerificationResult:
        """验证恢复后的业务状态。

        Args:
            plan           : 恢复计划（expected_state 缺省来源）
            outcome        : 最后一次 SafeExecutionOutcome / 其 to_dict（可选）
            expected_state : 覆盖计划中的期望状态（可选）
            read_fn        : 覆盖构造时注入的 read_fn（可选）

        Returns:
            VerificationResult(RECOVERED / NOT_RECOVERED / UNVERIFIABLE)
        """
        expected = dict(expected_state or plan.expected_state or {})
        if not expected:
            return VerificationResult(
                incident_id=plan.incident_id,
                status=VERIFY_UNVERIFIABLE,
                message="no expected_state to verify against",
            )

        reader = read_fn or self.read_fn
        observed: Optional[Dict[str, Any]] = None
        source = ""

        # 1) 平台实读——最强证据
        if reader is not None:
            try:
                observed = reader(plan.target) or {}
                source = "platform_read"
            except Exception as exc:  # 读取失败不算恢复成功
                return VerificationResult(
                    incident_id=plan.incident_id,
                    status=VERIFY_UNVERIFIABLE,
                    expected_state=expected,
                    message=f"platform read failed: {exc}",
                )
        # 2) 执行结果后态
        elif outcome is not None:
            observed = self._after_state(outcome)
            source = "outcome_after_state"

        if not observed:
            return VerificationResult(
                incident_id=plan.incident_id,
                status=VERIFY_UNVERIFIABLE,
                expected_state=expected,
                message="no observed state available (conservative: not recovered)",
            )

        mismatches = {
            key: {"expected": value, "actual": observed.get(key)}
            for key, value in expected.items()
            if _as_str(value).lower() != _as_str(observed.get(key)).lower()
        }
        if mismatches:
            return VerificationResult(
                incident_id=plan.incident_id,
                status=VERIFY_NOT_RECOVERED,
                expected_state=expected,
                observed_state=observed,
                message=f"state mismatch via {source}: {sorted(mismatches)}",
            )
        return VerificationResult(
            incident_id=plan.incident_id,
            status=VERIFY_RECOVERED,
            expected_state=expected,
            observed_state=observed,
            message=f"state verified via {source}",
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _after_state(outcome: Any) -> Dict[str, Any]:
        """从 SafeExecutionOutcome / dict 提取 after_state。"""
        if isinstance(outcome, dict):
            result = outcome.get("result") or {}
            if isinstance(result, dict):
                return result.get("after_state") or {}
            return {}
        result = getattr(outcome, "result", None)
        if result is not None:
            after = getattr(result, "after_state", None)
            if isinstance(after, dict):
                return after
        context = getattr(outcome, "context", None)
        if context is not None:
            after = getattr(context, "after_state", None)
            if isinstance(after, dict):
                return after
        return {}


__all__ = ["RecoveryVerifier"]
