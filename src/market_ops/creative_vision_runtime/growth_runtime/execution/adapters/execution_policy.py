"""E13.7 Execution Policy — 执行策略管理.

控制真实执行层的模式切换、降级策略和安全护栏。
核心职责:
  - 定义 ExecutionPolicy 模型 (real/mock/approval 切换规则)
  - 实现 Policy Engine 计算执行模式
  - 实现降级策略 (API 失败 → MOCK 退化)
  - 实现审批策略 (高风险 → APPROVAL_REQUIRED)

连接:
  E13.7 ExecutorGateway → ExecutionPolicy → ExecutionMode → Executor
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .adapter_models import ExecutionMode, PlatformType


# ═══════════════════════════════════════════════════════════════
# Policy Enums
# ═══════════════════════════════════════════════════════════════


class PolicyMode(str, Enum):
    """全局策略模式 — 控制整个系统的执行行为.

    | Mode              | 说明                              |
    |-------------------|----------------------------------|
    | FULL_MOCK         | 全部模拟 (开发/测试)               |
    | DRY_RUN_ONLY      | 仅干运行 (集成测试)               |
    | SAFE_REAL         | 安全真实执行 (低风险自动, 高风险审批)  |
    | FULL_REAL         | 全部真实执行 (生产, 无审批)         |
    | CUSTOM            | 自定义策略                         |
    """
    FULL_MOCK = "full_mock"
    DRY_RUN_ONLY = "dry_run_only"
    SAFE_REAL = "safe_real"
    FULL_REAL = "full_real"
    CUSTOM = "custom"


class ActionRiskLevel(str, Enum):
    """动作风险等级."""
    SAFE = "safe"           # 安全: 只读, 监控
    LOW = "low"             # 低风险: 暂停素材, 收集结果
    MEDIUM = "medium"       # 中风险: 调整预算 (±10%), 创建素材
    HIGH = "high"           # 高风险: 创建广告系列, 放量 (>20%)
    CRITICAL = "critical"   # 极高风险: 大规模放量, 批量修改


class DegradeReason(str, Enum):
    """降级原因."""
    API_UNAVAILABLE = "api_unavailable"
    AUTH_FAILURE = "auth_failure"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    RETRY_EXHAUSTED = "retry_exhausted"
    SAFETY_BLOCK = "safety_block"
    MANUAL_OVERRIDE = "manual_override"


# ═══════════════════════════════════════════════════════════════
# Action Risk Mapping
# ═══════════════════════════════════════════════════════════════

# 动作类型 → 风险等级 映射
ACTION_RISK_MAP: dict[str, ActionRiskLevel] = {
    # 安全动作
    "monitor": ActionRiskLevel.SAFE,
    "collect_result": ActionRiskLevel.SAFE,
    # 低风险
    "pause_creative": ActionRiskLevel.LOW,
    "pause_campaign": ActionRiskLevel.LOW,
    "freeze_campaign": ActionRiskLevel.LOW,
    # 中风险
    "update_budget": ActionRiskLevel.MEDIUM,
    "reduce_budget": ActionRiskLevel.MEDIUM,
    "create_creative": ActionRiskLevel.MEDIUM,
    "mutate_creative": ActionRiskLevel.MEDIUM,
    "upload_creative": ActionRiskLevel.MEDIUM,
    # 高风险
    "create_campaign": ActionRiskLevel.HIGH,
    "create_ad_set": ActionRiskLevel.HIGH,
    "update_campaign": ActionRiskLevel.HIGH,
    "scale_budget": ActionRiskLevel.HIGH,
    # 极高风险
    "batch_create": ActionRiskLevel.CRITICAL,
    "batch_scale": ActionRiskLevel.CRITICAL,
    "bulk_delete": ActionRiskLevel.CRITICAL,
}


# ═══════════════════════════════════════════════════════════════
# Execution Policy
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionPolicy:
    """执行策略 — 定义什么情况下用什么模式执行.

    Attributes:
        policy_id: 策略 ID
        name: 策略名称
        mode: 全局策略模式
        default_execution_mode: 默认执行模式
        risk_mode_map: 风险等级 → 执行模式 映射
        approval_threshold: 审批阈值 (risk_level >= threshold 需要审批)
        require_approval_for: 强制执行审批的风险等级集合
        max_retries: 最大重试次数
        retry_delay_seconds: 重试间隔
        degrade_on_failure: 失败时是否降级到 MOCK
        degrade_reasons: 允许降级的原因集合
        enabled: 策略是否启用
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "default"
    mode: PolicyMode = PolicyMode.SAFE_REAL
    default_execution_mode: ExecutionMode = ExecutionMode.REAL
    risk_mode_map: dict[ActionRiskLevel, ExecutionMode] = field(default_factory=dict)
    approval_threshold: ActionRiskLevel = ActionRiskLevel.HIGH
    require_approval_for: set[ActionRiskLevel] = field(default_factory=set)
    max_retries: int = 3
    retry_delay_seconds: int = 5
    degrade_on_failure: bool = True
    degrade_reasons: set[DegradeReason] = field(default_factory=lambda: {
        DegradeReason.API_UNAVAILABLE,
        DegradeReason.RATE_LIMITED,
        DegradeReason.TIMEOUT,
        DegradeReason.RETRY_EXHAUSTED,
    })
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_mode(
        self,
        action_type: str,
        risk_level: ActionRiskLevel | None = None,
    ) -> ExecutionMode:
        """根据动作类型和风险等级解析执行模式.

        Args:
            action_type: 动作类型
            risk_level: 风险等级 (如果未提供, 从 ACTION_RISK_MAP 推断)

        Returns:
            ExecutionMode: 应使用的执行模式
        """
        if not self.enabled:
            return ExecutionMode.DRY_RUN

        # 全局策略模式优先
        if self.mode == PolicyMode.FULL_MOCK:
            return ExecutionMode.MOCK
        if self.mode == PolicyMode.DRY_RUN_ONLY:
            return ExecutionMode.DRY_RUN
        if self.mode == PolicyMode.FULL_REAL:
            return ExecutionMode.REAL

        # 根据风险等级映射
        risk = risk_level or self._infer_risk(action_type)

        # 检查是否需要审批
        if risk in self.require_approval_for or self._meets_approval_threshold(risk):
            return ExecutionMode.APPROVAL_REQUIRED

        # 从风险映射表查找
        return self.risk_mode_map.get(risk, self.default_execution_mode)

    def needs_approval(self, action_type: str) -> bool:
        """判断动作是否需要审批."""
        risk = self._infer_risk(action_type)
        return risk in self.require_approval_for or self._meets_approval_threshold(risk)

    def should_degrade(self, reason: DegradeReason) -> bool:
        """判断是否应该降级."""
        if not self.degrade_on_failure:
            return False
        return reason in self.degrade_reasons

    def _infer_risk(self, action_type: str) -> ActionRiskLevel:
        """从动作类型推断风险等级."""
        return ACTION_RISK_MAP.get(action_type, ActionRiskLevel.MEDIUM)

    def _meets_approval_threshold(self, risk: ActionRiskLevel) -> bool:
        """判断风险等级是否达到审批阈值."""
        risk_order = [
            ActionRiskLevel.SAFE,
            ActionRiskLevel.LOW,
            ActionRiskLevel.MEDIUM,
            ActionRiskLevel.HIGH,
            ActionRiskLevel.CRITICAL,
        ]
        return risk_order.index(risk) >= risk_order.index(self.approval_threshold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "mode": self.mode.value,
            "default_execution_mode": self.default_execution_mode.value,
            "risk_mode_map": {k.value: v.value for k, v in self.risk_mode_map.items()},
            "approval_threshold": self.approval_threshold.value,
            "require_approval_for": [r.value for r in self.require_approval_for],
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "degrade_on_failure": self.degrade_on_failure,
            "degrade_reasons": [r.value for r in self.degrade_reasons],
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Policy Factory
# ═══════════════════════════════════════════════════════════════


def create_development_policy() -> ExecutionPolicy:
    """创建开发环境策略 — 全部模拟."""
    return ExecutionPolicy(
        name="development",
        mode=PolicyMode.FULL_MOCK,
        default_execution_mode=ExecutionMode.MOCK,
        require_approval_for=set(),
    )


def create_testing_policy() -> ExecutionPolicy:
    """创建测试环境策略 — 干运行."""
    return ExecutionPolicy(
        name="testing",
        mode=PolicyMode.DRY_RUN_ONLY,
        default_execution_mode=ExecutionMode.DRY_RUN,
        require_approval_for=set(),
    )


def create_safe_real_policy() -> ExecutionPolicy:
    """创建安全真实策略 — 低风险自动, 高风险审批.

    推荐用于: 生产环境 (人工在环)
    """
    return ExecutionPolicy(
        name="safe_real",
        mode=PolicyMode.SAFE_REAL,
        default_execution_mode=ExecutionMode.REAL,
        approval_threshold=ActionRiskLevel.HIGH,
        require_approval_for={ActionRiskLevel.CRITICAL},
        risk_mode_map={
            ActionRiskLevel.SAFE: ExecutionMode.REAL,
            ActionRiskLevel.LOW: ExecutionMode.REAL,
            ActionRiskLevel.MEDIUM: ExecutionMode.REAL,
            ActionRiskLevel.HIGH: ExecutionMode.APPROVAL_REQUIRED,
            ActionRiskLevel.CRITICAL: ExecutionMode.APPROVAL_REQUIRED,
        },
    )


def create_full_auto_policy() -> ExecutionPolicy:
    """创建全自动策略 — 全部真实, 无审批.

    推荐用于: 完全自主运行 (无人值守)
    """
    return ExecutionPolicy(
        name="full_auto",
        mode=PolicyMode.FULL_REAL,
        default_execution_mode=ExecutionMode.REAL,
        approval_threshold=ActionRiskLevel.CRITICAL,
        require_approval_for=set(),
        risk_mode_map={
            ActionRiskLevel.SAFE: ExecutionMode.REAL,
            ActionRiskLevel.LOW: ExecutionMode.REAL,
            ActionRiskLevel.MEDIUM: ExecutionMode.REAL,
            ActionRiskLevel.HIGH: ExecutionMode.REAL,
            ActionRiskLevel.CRITICAL: ExecutionMode.REAL,
        },
    )


def create_conservative_policy() -> ExecutionPolicy:
    """创建保守策略 — 除安全动作外全部审批.

    推荐用于: 高风险产品 / 新系统磨合期
    """
    return ExecutionPolicy(
        name="conservative",
        mode=PolicyMode.CUSTOM,
        default_execution_mode=ExecutionMode.APPROVAL_REQUIRED,
        approval_threshold=ActionRiskLevel.LOW,
        require_approval_for={
            ActionRiskLevel.LOW,
            ActionRiskLevel.MEDIUM,
            ActionRiskLevel.HIGH,
            ActionRiskLevel.CRITICAL,
        },
        risk_mode_map={
            ActionRiskLevel.SAFE: ExecutionMode.REAL,
            ActionRiskLevel.LOW: ExecutionMode.APPROVAL_REQUIRED,
            ActionRiskLevel.MEDIUM: ExecutionMode.APPROVAL_REQUIRED,
            ActionRiskLevel.HIGH: ExecutionMode.APPROVAL_REQUIRED,
            ActionRiskLevel.CRITICAL: ExecutionMode.APPROVAL_REQUIRED,
        },
    )


# ═══════════════════════════════════════════════════════════════
# Policy Engine
# ═══════════════════════════════════════════════════════════════


@dataclass
class PolicyDecision:
    """策略决策结果 — Policy Engine 的输出.

    Attributes:
        action_type: 动作类型
        resolved_mode: 解析后的执行模式
        needs_approval: 是否需要审批
        risk_level: 风险等级
        policy_name: 使用的策略名称
        degrade_reason: 降级原因 (如果降级了)
        degraded: 是否已降级
        timestamp: 决策时间
    """
    action_type: str = ""
    resolved_mode: ExecutionMode = ExecutionMode.MOCK
    needs_approval: bool = False
    risk_level: ActionRiskLevel = ActionRiskLevel.MEDIUM
    policy_name: str = ""
    degrade_reason: DegradeReason | None = None
    degraded: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PolicyEngine:
    """策略引擎 — 综合策略和实时状态计算执行模式.

    用法:
        engine = PolicyEngine(policy=create_safe_real_policy())
        decision = engine.evaluate("create_campaign")
        if decision.needs_approval:
            print("需要审批")
    """

    def __init__(self, policy: ExecutionPolicy | None = None):
        self._policy = policy or create_safe_real_policy()
        self._degraded_platforms: dict[PlatformType, DegradeReason] = {}
        self._decision_count: int = 0

    # ── 主入口 ────────────────────────────────────────────────

    def evaluate(
        self,
        action_type: str,
        platform: PlatformType = PlatformType.META,
        risk_level: ActionRiskLevel | None = None,
    ) -> PolicyDecision:
        """评估动作的执行策略.

        Args:
            action_type: 动作类型
            platform: 目标平台
            risk_level: 风险等级 (可选, 自动推断)

        Returns:
            PolicyDecision: 策略决策
        """
        self._decision_count += 1

        # 1. 解析基础模式
        risk = risk_level or ACTION_RISK_MAP.get(action_type, ActionRiskLevel.MEDIUM)
        resolved_mode = self._policy.resolve_mode(action_type, risk)

        # 2. 检查平台降级
        degrade_reason = self._degraded_platforms.get(platform)
        if degrade_reason and self._policy.should_degrade(degrade_reason):
            resolved_mode = ExecutionMode.MOCK
            return PolicyDecision(
                action_type=action_type,
                resolved_mode=resolved_mode,
                needs_approval=False,
                risk_level=risk,
                policy_name=self._policy.name,
                degrade_reason=degrade_reason,
                degraded=True,
            )

        # 3. 检查是否需要审批
        needs_approval = (
            resolved_mode == ExecutionMode.APPROVAL_REQUIRED
            or self._policy.needs_approval(action_type)
        )

        return PolicyDecision(
            action_type=action_type,
            resolved_mode=resolved_mode,
            needs_approval=needs_approval,
            risk_level=risk,
            policy_name=self._policy.name,
            degraded=False,
        )

    # ── 降级管理 ──────────────────────────────────────────────

    def degrade_platform(
        self,
        platform: PlatformType,
        reason: DegradeReason,
    ) -> None:
        """降级指定平台到 MOCK 模式."""
        self._degraded_platforms[platform] = reason

    def restore_platform(self, platform: PlatformType) -> None:
        """恢复平台."""
        self._degraded_platforms.pop(platform, None)

    def is_degraded(self, platform: PlatformType) -> bool:
        """检查平台是否已降级."""
        return platform in self._degraded_platforms

    def get_degraded_platforms(self) -> dict[PlatformType, DegradeReason]:
        """获取所有已降级的平台."""
        return dict(self._degraded_platforms)

    def clear_degraded(self) -> None:
        """清除所有降级状态."""
        self._degraded_platforms.clear()

    # ── 策略管理 ──────────────────────────────────────────────

    @property
    def policy(self) -> ExecutionPolicy:
        return self._policy

    @policy.setter
    def policy(self, value: ExecutionPolicy) -> None:
        self._policy = value

    def update_policy(self, policy: ExecutionPolicy) -> None:
        """更新策略."""
        self._policy = policy
        self._policy.updated_at = datetime.now(timezone.utc).isoformat()

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def decision_count(self) -> int:
        return self._decision_count

    def stats(self) -> dict[str, Any]:
        return {
            "policy_name": self._policy.name,
            "policy_mode": self._policy.mode.value,
            "decision_count": self._decision_count,
            "degraded_platforms": {k.value: v.value for k, v in self._degraded_platforms.items()},
            "approval_threshold": self._policy.approval_threshold.value,
        }