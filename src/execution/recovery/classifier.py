"""P2.6.2 Failure Classifier — 故障分类器。

输入：P2.4 SafeExecutionOutcome（+ 可选 ExecutionRequest / P2.5 MonitorAlert），
输出：FailureClassification（failure_type + treatment + severity）。

分类规则（确定性，无 LLM）：

    1. Rollback Failure     -> ROLLBACK_FAILED  -> EMERGENCY_ESCALATE (CRITICAL)
       （outcome.escalated=True 或 verdict=ESCALATED：P2.4 Rule5 回滚也失败）
    2. Authentication (401) -> AUTH_FAILURE     -> ESCALATE (HIGH)
       —— token 失效不能自动修复，重试只会连续失败
    3. State Drift          -> STATE_DRIFT      -> RECONCILE (MEDIUM)
       （请求 PAUSE，平台实际 ACTIVE；来自 after_state 与期望不符或 Monitor 告警）
    4. Provider Timeout/5xx -> PROVIDER_TIMEOUT -> RETRY (LOW)
    5. 其他                  -> UNKNOWN          -> ESCALATE (HIGH, 低置信度)
       —— 不认识的故障宁可升级，不可乱试

规则优先级自上而下：回滚失败 > 认证 > 漂移 > 超时 > 未知。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.execution.recovery.models import (
    FAILURE_AUTH,
    FAILURE_ROLLBACK_FAILED,
    FAILURE_STATE_DRIFT,
    FAILURE_TIMEOUT,
    FAILURE_UNKNOWN,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    TREATMENT_EMERGENCY_ESCALATE,
    TREATMENT_ESCALATE,
    TREATMENT_RECONCILE,
    TREATMENT_RETRY,
    FailureClassification,
    RecoveryIncident,
    _as_str,
)

# ---------------------------------------------------------------------------
# 错误文本模式（大小写不敏感）
# ---------------------------------------------------------------------------

# 超时 / 服务端错误 / 限流：可重试
_TIMEOUT_PATTERNS = re.compile(
    r"(timeout|timed?\s*out|connection\s*(reset|refused|aborted)"
    r"|rate\s*limit|too\s*many\s*requests"
    r"|\b429\b|\b5\d{2}\b|server\s*error|service\s*unavailable"
    r"|temporarily\s*unavailable|gateway)",
    re.IGNORECASE,
)

# 认证失败：不可自动修复
_AUTH_PATTERNS = re.compile(
    r"(\b401\b|\b403\b|unauthorized|unauthenticated|forbidden"
    r"|invalid\s*(token|key|credential)|token\s*(expired|invalid|revoked)"
    r"|auth(entication|orization)?\s*(fail|error|denied)"
    r"|access\s*denied|permission\s*denied)",
    re.IGNORECASE,
)

# 状态漂移
_DRIFT_PATTERNS = re.compile(
    r"(state\s*drift|drift(ed)?|state\s*mismatch|unexpected\s*state"
    r"|inconsistent\s*state)",
    re.IGNORECASE,
)

# 回滚失败
_ROLLBACK_PATTERNS = re.compile(
    r"(rollback\s*(fail|error)|failed\s*to\s*roll\s*back)",
    re.IGNORECASE,
)


def _extract_error(outcome: Any) -> str:
    """从 SafeExecutionOutcome 中提取错误文本（result.error 优先）。"""
    result = getattr(outcome, "result", None)
    error = ""
    if result is not None:
        error = str(getattr(result, "error", "") or "")
    if not error:
        context = getattr(outcome, "context", None)
        error = str(getattr(context, "reason", "") or "")
    return error


def _detect_state_drift(outcome: Any, alert: Any = None) -> bool:
    """检测状态漂移：Monitor 告警声明漂移，或 after_state 与期望不符。"""
    # 1) P2.5 MonitorAlert / ExecutionSummary 声明 drifted
    if alert is not None:
        if bool(getattr(alert, "drifted", False)):
            return True
        kind = _as_str(getattr(alert, "kind", "") or getattr(alert, "type", ""))
        if "drift" in kind.lower():
            return True
        message = str(getattr(alert, "message", "") or "")
        if _DRIFT_PATTERNS.search(message):
            return True
    # 2) after_state 显式携带 drifted 标记 / expected vs actual 不一致
    result = getattr(outcome, "result", None)
    if result is not None:
        after = getattr(result, "after_state", None) or {}
        if isinstance(after, dict):
            if bool(after.get("drifted")):
                return True
            expected = after.get("expected_status")
            actual = after.get("status") or after.get("actual_status")
            if expected is not None and actual is not None:
                if _as_str(expected).lower() != _as_str(actual).lower():
                    return True
    return False


class FailureClassifier:
    """确定性故障分类器（无 I/O、无网络、无 LLM）。"""

    def classify(
        self,
        outcome: Any,
        request: Any = None,
        alert: Any = None,
        incident: Optional[RecoveryIncident] = None,
    ) -> FailureClassification:
        """对一次失败的执行进行分类。

        Args:
            outcome  : P2.4 SafeExecutionOutcome
            request  : 可选 P2.1 ExecutionRequest（补全 action/provider）
            alert    : 可选 P2.5 MonitorAlert / ExecutionSummary（漂移信号）
            incident : 可选已构建的 RecoveryIncident；不传则自动构建

        Returns:
            FailureClassification；同时将 incident（若传入）迁移到 CLASSIFIED
            并回填 failure_type / severity。
        """
        if incident is None:
            incident = RecoveryIncident.from_outcome(outcome, request)

        error = _extract_error(outcome)
        verdict = _as_str(getattr(outcome, "verdict", ""))
        escalated = bool(getattr(outcome, "escalated", False))
        provider = incident.provider
        action = incident.action

        failure_type, treatment, severity, message, confidence = (
            self._apply_rules(error, verdict, escalated, outcome, alert)
        )

        # 回填 incident 并推进状态机
        incident.failure_type = failure_type
        incident.severity = severity
        if not incident.error:
            incident.error = error
        if incident.status == "DETECTED":
            incident.transition("CLASSIFIED", reason=message)

        return FailureClassification(
            incident_id=incident.incident_id,
            failure_type=failure_type,
            treatment=treatment,
            severity=severity,
            provider=provider,
            action=action,
            message=message,
            confidence=confidence,
            metadata={"verdict": verdict, "error": error},
        )

    # ------------------------------------------------------------------
    # 分类规则（优先级自上而下）
    # ------------------------------------------------------------------

    def _apply_rules(
        self,
        error: str,
        verdict: str,
        escalated: bool,
        outcome: Any,
        alert: Any,
    ):
        # Rule 1 — 回滚失败（最高级）：P2.4 Rule5 升级信号
        if escalated or verdict == "ESCALATED" or _ROLLBACK_PATTERNS.search(error):
            return (
                FAILURE_ROLLBACK_FAILED,
                TREATMENT_EMERGENCY_ESCALATE,
                SEVERITY_CRITICAL,
                "rollback failed — emergency escalation, halt automation",
                1.0,
            )

        # Rule 2 — 认证失败：不能自动修复
        if _AUTH_PATTERNS.search(error):
            return (
                FAILURE_AUTH,
                TREATMENT_ESCALATE,
                SEVERITY_HIGH,
                "authentication failure — cannot self-heal, escalate to human",
                1.0,
            )

        # Rule 3 — 状态漂移：重读平台状态后重执行
        if _detect_state_drift(outcome, alert) or _DRIFT_PATTERNS.search(error):
            return (
                FAILURE_STATE_DRIFT,
                TREATMENT_RECONCILE,
                SEVERITY_MEDIUM,
                "state drift detected — reconcile platform state then re-execute",
                1.0,
            )

        # Rule 4 — 超时 / 5xx / 限流：可重试
        if _TIMEOUT_PATTERNS.search(error):
            return (
                FAILURE_TIMEOUT,
                TREATMENT_RETRY,
                SEVERITY_LOW,
                "provider timeout / transient error — retry with backoff",
                1.0,
            )

        # Rule 5 — 未知：宁可升级，不可乱试
        return (
            FAILURE_UNKNOWN,
            TREATMENT_ESCALATE,
            SEVERITY_HIGH,
            f"unknown failure — escalate (error={error[:120]!r})",
            0.3,
        )


__all__ = ["FailureClassifier"]
