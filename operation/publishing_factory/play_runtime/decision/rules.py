"""E15.2 决策规则 — 确定性规则, 不接 LLM.

规则按优先级顺序评估, 命中即返回 (先安全后增长):
1. auto_halt        — crash/anr 超阈值 → HALT_RELEASE
2. auto_increase    — 稳定性健康且灰度未满 → INCREASE_ROLLOUT
3. observe          — 其他情况 → HOLD_ROLLOUT (版本观察)

阈值口径: crash_rate/anr_rate 为百分比 (0-100),
与 GooglePlayRealClient.get_vitals / play_runtime 既有 HealthAgent 一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from .models import PlayAction, PlayDecision

# 与 HealthAgent / ReleaseAgent 既有健康门控保持同一数量级
CRASH_HALT_THRESHOLD = 0.5   # % — crash >= 0.5% 触发暂停
ANR_HALT_THRESHOLD = 0.2     # % — anr >= 0.2% 触发暂停
CRASH_HEALTHY_THRESHOLD = 0.5  # % — crash < 0.5% 视为健康
ANR_HEALTHY_THRESHOLD = 0.1    # % — anr < 0.1% 视为健康


@dataclass
class DecisionRule:
    name: str
    evaluate: Callable[["object"], Optional[PlayDecision]]


def _rule_auto_halt(snapshot) -> Optional[PlayDecision]:
    """规则: 自动暂停 — 稳定性恶化立即 HALT_RELEASE."""
    crash = snapshot.crash_rate
    anr = snapshot.anr_rate
    reasons = []
    if crash is not None and crash >= CRASH_HALT_THRESHOLD:
        reasons.append(f"crash_rate {crash:.2f}% >= {CRASH_HALT_THRESHOLD}%")
    if anr is not None and anr >= ANR_HALT_THRESHOLD:
        reasons.append(f"anr_rate {anr:.2f}% >= {ANR_HALT_THRESHOLD}%")
    if not reasons:
        return None
    return PlayDecision(
        package_name=snapshot.package_name,
        action=PlayAction.HALT_RELEASE,
        confidence=0.95,
        reason="; ".join(reasons),
        rule_name="auto_halt",
    )


def _rule_auto_increase(snapshot) -> Optional[PlayDecision]:
    """规则: 自动扩大灰度 — 稳定性健康且 rollout 未满."""
    crash = snapshot.crash_rate
    anr = snapshot.anr_rate
    rollout = snapshot.rollout_percentage
    if crash is None or anr is None:
        return None  # 数据不全, 不敢扩大
    if crash >= CRASH_HEALTHY_THRESHOLD or anr >= ANR_HEALTHY_THRESHOLD:
        return None
    if rollout is None or rollout >= 100.0:
        return None
    return PlayDecision(
        package_name=snapshot.package_name,
        action=PlayAction.INCREASE_ROLLOUT,
        confidence=0.9,
        reason=(
            f"healthy: crash_rate {crash:.2f}% < {CRASH_HEALTHY_THRESHOLD}%, "
            f"anr_rate {anr:.2f}% < {ANR_HEALTHY_THRESHOLD}%, "
            f"rollout {rollout:.1f}% < 100%"
        ),
        rule_name="auto_increase",
    )


def _rule_observe(snapshot) -> Optional[PlayDecision]:
    """规则: 版本观察 — 兜底 HOLD_ROLLOUT."""
    missing = snapshot.crash_rate is None or snapshot.anr_rate is None
    if missing:
        reason = "stability data unavailable; observing"
        confidence = 0.5
    else:
        reason = (
            f"no trigger matched: crash_rate {snapshot.crash_rate:.2f}%, "
            f"anr_rate {snapshot.anr_rate:.2f}%, "
            f"rollout {snapshot.rollout_percentage}"
        )
        confidence = 0.7
    return PlayDecision(
        package_name=snapshot.package_name,
        action=PlayAction.HOLD_ROLLOUT,
        confidence=confidence,
        reason=reason,
        rule_name="observe",
    )


DEFAULT_RULES: List[DecisionRule] = [
    DecisionRule(name="auto_halt", evaluate=_rule_auto_halt),
    DecisionRule(name="auto_increase", evaluate=_rule_auto_increase),
    DecisionRule(name="observe", evaluate=_rule_observe),
]
