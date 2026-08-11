"""E13.7.4.3 Health Policy — Safe Mode 行为策略.

定义 Agent 在不同健康状态下的行为约束:
  - HEALTHY: 全功能运行
  - WARNING: 全功能运行 + 告警
  - DEGRADED: 限制高风险操作，切换模拟模式
  - SAFE_MODE: 只读模式，禁止写操作
  - FAILED: 完全停止

与 E13.7.4.2 Policy 的关系:
  - Health Policy: 决定 Agent 运行模式 (整体降级)
  - Agent Policy: 决定单次动作能否执行 (逐动作检查)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .health_models import HealthStatus, SafeModePolicy


# ═══════════════════════════════════════════════════════════════
# Default Safe Mode Policy
# ═══════════════════════════════════════════════════════════════


DEFAULT_SAFE_MODE_POLICY = SafeModePolicy(
    allowed_actions=[
        "analyze",
        "generate_report",
        "monitor",
        "read_data",
        "observe",
        "reason",
        "plan",
        "learn",
    ],
    blocked_actions=[
        "create_campaign",
        "update_budget",
        "scale_budget",
        "change_targeting",
        "change_bidding",
        "pause_campaign",
        "resume_campaign",
        "create_creative",
        "mutate_creative",
        "batch_create",
    ],
    require_manual_approval=True,
)


# ═══════════════════════════════════════════════════════════════
# Health Policy
# ═══════════════════════════════════════════════════════════════


@dataclass
class HealthPolicy:
    """健康策略 — 定义各健康状态下的行为约束.

    Attributes:
        safe_mode_policy: 安全模式策略
        auto_recovery_enabled: 是否启用自动恢复
        auto_recovery_conditions: 自动恢复条件
        max_degraded_duration_seconds: 降级最长持续时间
    """
    safe_mode_policy: SafeModePolicy = field(default_factory=lambda: DEFAULT_SAFE_MODE_POLICY)
    auto_recovery_enabled: bool = False
    auto_recovery_conditions: list[str] = field(default_factory=lambda: [
        "consecutive_healthy_checks >= 3",
        "no_critical_alerts",
    ])
    max_degraded_duration_seconds: float = 3600.0  # 1 小时

    def get_allowed_actions(self, status: HealthStatus) -> list[str]:
        """获取指定状态下允许的动作."""
        if status == HealthStatus.HEALTHY:
            return self.safe_mode_policy.allowed_actions + self.safe_mode_policy.blocked_actions
        elif status == HealthStatus.WARNING:
            return self.safe_mode_policy.allowed_actions + self.safe_mode_policy.blocked_actions
        elif status in (HealthStatus.DEGRADED, HealthStatus.SAFE_MODE):
            return self.safe_mode_policy.allowed_actions
        elif status == HealthStatus.FAILED:
            return []
        return []

    def get_blocked_actions(self, status: HealthStatus) -> list[str]:
        """获取指定状态下被禁止的动作."""
        if status in (HealthStatus.HEALTHY, HealthStatus.WARNING):
            return []
        elif status in (HealthStatus.DEGRADED, HealthStatus.SAFE_MODE):
            return self.safe_mode_policy.blocked_actions
        elif status == HealthStatus.FAILED:
            return self.safe_mode_policy.allowed_actions + self.safe_mode_policy.blocked_actions
        return []

    def is_action_allowed(self, status: HealthStatus, action_type: str) -> bool:
        """检查指定状态下动作是否允许."""
        blocked = self.get_blocked_actions(status)
        return action_type not in blocked

    def can_auto_recover(
        self,
        current_status: HealthStatus,
        healthy_check_count: int,
        has_critical_alerts: bool,
    ) -> bool:
        """检查是否可以自动恢复.

        Args:
            current_status: 当前状态
            healthy_check_count: 连续健康检查次数
            has_critical_alerts: 是否有严重告警

        Returns:
            bool: 是否可以自动恢复
        """
        if not self.auto_recovery_enabled:
            return False
        if current_status == HealthStatus.HEALTHY:
            return True
        if healthy_check_count < 3:
            return False
        if has_critical_alerts:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe_mode_policy": self.safe_mode_policy.to_dict(),
            "auto_recovery_enabled": self.auto_recovery_enabled,
            "auto_recovery_conditions": self.auto_recovery_conditions,
            "max_degraded_duration_seconds": self.max_degraded_duration_seconds,
        }


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_health_policy(
    auto_recovery_enabled: bool = False,
) -> HealthPolicy:
    """创建健康策略的工厂函数."""
    return HealthPolicy(
        safe_mode_policy=DEFAULT_SAFE_MODE_POLICY,
        auto_recovery_enabled=auto_recovery_enabled,
    )