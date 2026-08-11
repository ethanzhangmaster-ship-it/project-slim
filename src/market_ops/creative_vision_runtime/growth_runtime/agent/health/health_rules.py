"""E13.7.4.3 Health Rules — 健康规则集.

定义系统自身健康评估规则，类似 Policy 的 RiskRule 但针对系统健康:
  - ExecutionFailureRule: 执行失败率过高 → SAFE_MODE
  - ToolFailureRule: 工具连续失败 → DEGRADED
  - DecisionDriftRule: 决策置信度下降 → WARNING
  - CycleTimeoutRule: 循环超时 → WARNING
  - ConsecutiveErrorRule: 连续错误 → SAFE_MODE
  - APITimeoutRule: API 超时过多 → DEGRADED
  - RateLimitRule: 限流频繁 → WARNING
  - HeartbeatLostRule: 心跳丢失 → FAILED
"""

from __future__ import annotations

from .health_models import (
    HealthMetricCategory,
    HealthRule,
    HealthRuleResult,
    HealthSnapshot,
    HealthStatus,
)


# ═══════════════════════════════════════════════════════════════
# 1. Execution Failure Rule
# ═══════════════════════════════════════════════════════════════

def _build_execution_failure_rule(
    max_failure_rate: float = 0.3,
    min_sample: int = 10,
) -> HealthRule:
    """执行失败率规则.

    条件: 过去足够样本中失败率 > 30%
    结果: SAFE_MODE
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        exec_health = snapshot.execution
        if exec_health.total_executions < min_sample:
            return False
        return exec_health.failure_rate > max_failure_rate

    return HealthRule(
        name="execution_failure",
        description=f"执行失败率超过 {max_failure_rate:.0%} (样本 ≥ {min_sample})",
        category=HealthMetricCategory.EXECUTION,
        priority=10,
        condition=condition,
        reason_template=f"执行失败率 {{failure_rate}} 超过 {max_failure_rate:.0%} 阈值",
        target_status=HealthStatus.SAFE_MODE,
    )


# ═══════════════════════════════════════════════════════════════
# 2. Tool Failure Rule
# ═══════════════════════════════════════════════════════════════

def _build_tool_failure_rule(
    max_consecutive_failures: int = 10,
    min_api_calls: int = 5,
) -> HealthRule:
    """工具连续失败规则.

    条件: API 调用足够样本且成功率 < 50%
    结果: DEGRADED
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        tool = snapshot.tool
        if tool.total_api_calls < min_api_calls:
            return False
        return tool.api_success_rate < 0.5

    return HealthRule(
        name="tool_failure",
        description=f"工具 API 成功率低于 50% (至少 {min_api_calls} 次调用)",
        category=HealthMetricCategory.TOOL,
        priority=20,
        condition=condition,
        reason_template="工具 API 成功率过低，切换到模拟模式",
        target_status=HealthStatus.DEGRADED,
    )


# ═══════════════════════════════════════════════════════════════
# 3. Decision Drift Rule
# ═══════════════════════════════════════════════════════════════

def _build_decision_drift_rule(
    min_confidence: float = 0.5,
    min_decisions: int = 5,
) -> HealthRule:
    """决策漂移规则.

    条件: 足够决策样本且平均置信度 < 50%
    结果: WARNING
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        dec = snapshot.decision
        if dec.decision_count < min_decisions:
            return False
        return dec.average_confidence < min_confidence

    return HealthRule(
        name="decision_drift",
        description=f"决策平均置信度低于 {min_confidence:.0%}",
        category=HealthMetricCategory.DECISION,
        priority=30,
        condition=condition,
        reason_template=f"决策平均置信度 {{average_confidence}} 低于 {min_confidence:.0%}",
        target_status=HealthStatus.WARNING,
    )


# ═══════════════════════════════════════════════════════════════
# 4. Cycle Timeout Rule
# ═══════════════════════════════════════════════════════════════

def _build_cycle_timeout_rule(
    max_duration_seconds: float = 300.0,
    min_cycles: int = 3,
) -> HealthRule:
    """循环超时规则.

    条件: 足够循环样本且平均耗时 > 300s
    结果: WARNING
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        rt = snapshot.runtime
        if rt.cycle_count < min_cycles:
            return False
        return rt.cycle_duration_avg > max_duration_seconds

    return HealthRule(
        name="cycle_timeout",
        description=f"循环平均耗时超过 {max_duration_seconds}s",
        category=HealthMetricCategory.RUNTIME,
        priority=25,
        condition=condition,
        reason_template=f"循环平均耗时 {{cycle_duration_avg}}s 超过 {max_duration_seconds}s 阈值",
        target_status=HealthStatus.WARNING,
    )


# ═══════════════════════════════════════════════════════════════
# 5. Consecutive Error Rule
# ═══════════════════════════════════════════════════════════════

def _build_consecutive_error_rule(
    max_consecutive: int = 5,
) -> HealthRule:
    """连续错误规则.

    条件: 连续错误 > 5 次
    结果: SAFE_MODE
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        return snapshot.execution.consecutive_errors > max_consecutive

    return HealthRule(
        name="consecutive_errors",
        description=f"连续执行错误超过 {max_consecutive} 次",
        category=HealthMetricCategory.EXECUTION,
        priority=5,
        condition=condition,
        reason_template=f"连续执行错误 {max_consecutive}+ 次，进入安全模式",
        target_status=HealthStatus.SAFE_MODE,
    )


# ═══════════════════════════════════════════════════════════════
# 6. API Timeout Rule
# ═══════════════════════════════════════════════════════════════

def _build_api_timeout_rule(
    max_timeouts: int = 10,
) -> HealthRule:
    """API 超时规则.

    条件: 超时次数 > 10
    结果: DEGRADED
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        return snapshot.tool.timeout_count > max_timeouts

    return HealthRule(
        name="api_timeout",
        description=f"API 超时超过 {max_timeouts} 次",
        category=HealthMetricCategory.TOOL,
        priority=15,
        condition=condition,
        reason_template=f"API 超时 {max_timeouts}+ 次，系统降级",
        target_status=HealthStatus.DEGRADED,
    )


# ═══════════════════════════════════════════════════════════════
# 7. Rate Limit Rule
# ═══════════════════════════════════════════════════════════════

def _build_rate_limit_rule(
    max_rate_limits: int = 5,
) -> HealthRule:
    """限流频繁规则.

    条件: 被限流 > 5 次
    结果: WARNING
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        return snapshot.tool.rate_limit_count > max_rate_limits

    return HealthRule(
        name="rate_limit",
        description=f"API 限流超过 {max_rate_limits} 次",
        category=HealthMetricCategory.TOOL,
        priority=35,
        condition=condition,
        reason_template=f"API 限流 {max_rate_limits}+ 次，需关注请求频率",
        target_status=HealthStatus.WARNING,
    )


# ═══════════════════════════════════════════════════════════════
# 8. Heartbeat Lost Rule
# ═══════════════════════════════════════════════════════════════

def _build_heartbeat_lost_rule(
    max_heartbeat_age_seconds: float = 600.0,
) -> HealthRule:
    """心跳丢失规则.

    条件: 最后心跳超过 600s 前
    结果: FAILED
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        if not snapshot.runtime.last_heartbeat:
            return False
        from datetime import datetime, timezone
        try:
            hb = datetime.fromisoformat(snapshot.runtime.last_heartbeat)
            age = (datetime.now(timezone.utc) - hb).total_seconds()
            return age > max_heartbeat_age_seconds
        except Exception:
            return False

    return HealthRule(
        name="heartbeat_lost",
        description=f"心跳丢失超过 {max_heartbeat_age_seconds}s",
        category=HealthMetricCategory.RUNTIME,
        priority=0,
        condition=condition,
        reason_template=f"Agent 心跳丢失超过 {max_heartbeat_age_seconds}s，可能已停止运行",
        target_status=HealthStatus.FAILED,
    )


# ═══════════════════════════════════════════════════════════════
# 9. Low Decision Confidence Rate
# ═══════════════════════════════════════════════════════════════

def _build_low_confidence_rate_rule(
    max_low_confidence_rate: float = 0.5,
    min_decisions: int = 5,
) -> HealthRule:
    """低置信度决策比例规则.

    条件: 足够决策样本且低置信度决策超过 50%
    结果: DEGRADED
    """
    def condition(snapshot: HealthSnapshot) -> bool:
        dec = snapshot.decision
        if dec.decision_count < min_decisions:
            return False
        return dec.low_confidence_rate > max_low_confidence_rate

    return HealthRule(
        name="low_confidence_rate",
        description=f"低置信度决策比例超过 {max_low_confidence_rate:.0%}",
        category=HealthMetricCategory.DECISION,
        priority=22,
        condition=condition,
        reason_template=f"低置信度决策比例 {{low_confidence_rate}} 超过 {max_low_confidence_rate:.0%}",
        target_status=HealthStatus.DEGRADED,
    )


# ═══════════════════════════════════════════════════════════════
# Default Rules Builder
# ═══════════════════════════════════════════════════════════════

def build_default_health_rules(
    max_failure_rate: float = 0.3,
    max_consecutive_errors: int = 5,
    max_cycle_duration: float = 300.0,
    max_timeouts: int = 10,
    max_rate_limits: int = 5,
    max_heartbeat_age: float = 600.0,
    min_confidence: float = 0.5,
    max_low_confidence_rate: float = 0.5,
) -> list[HealthRule]:
    """构建默认健康规则集.

    返回按 priority 排序的规则列表。
    优先级: 0(心跳) → 5(连续错误) → 10(执行失败) → 15(超时) →
             20(工具失败) → 22(低置信度比例) → 25(循环超时) →
             30(决策漂移) → 35(限流)

    Args:
        max_failure_rate: 最大执行失败率
        max_consecutive_errors: 最大连续错误数
        max_cycle_duration: 最大循环耗时 (秒)
        max_timeouts: 最大 API 超时次数
        max_rate_limits: 最大限流次数
        max_heartbeat_age: 最大心跳间隔 (秒)
        min_confidence: 最低平均置信度
        max_low_confidence_rate: 最大低置信度比例

    Returns:
        list[HealthRule]: 默认规则集
    """
    rules = [
        _build_heartbeat_lost_rule(max_heartbeat_age),
        _build_consecutive_error_rule(max_consecutive_errors),
        _build_execution_failure_rule(max_failure_rate),
        _build_api_timeout_rule(max_timeouts),
        _build_tool_failure_rule(),
        _build_low_confidence_rate_rule(max_low_confidence_rate),
        _build_cycle_timeout_rule(max_cycle_duration),
        _build_decision_drift_rule(min_confidence),
        _build_rate_limit_rule(max_rate_limits),
    ]
    return sorted(rules, key=lambda r: r.priority)