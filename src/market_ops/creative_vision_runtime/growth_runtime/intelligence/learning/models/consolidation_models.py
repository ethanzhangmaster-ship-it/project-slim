"""E17.11.3 Consolidation Pipeline Models — 整合管线模型.

Day 7.11 Step 3:
  定义 ExperienceConsolidationPipeline 的协议模型:
    1. TriggerDecision          — 触发决策
    2. TriggerReason            — 触发原因枚举
    3. ConsolidationContext     — 整合上下文 (适配 MemoryConsolidationPipeline)
    4. ConsolidationResult      — 整合结果
    5. ConsolidationStatus      — 整合状态枚举

设计原则:
  - TriggerDecision 独立于 ConsolidationTrigger 配置，是运行时决策
  - ConsolidationContext 兼容 MemoryConsolidationPipeline 的输入协议
  - 纯数据模型，不包含业务逻辑
  - 可序列化 (to_dict)，支持审计
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class TriggerReason(str, Enum):
    """触发原因枚举."""
    COUNT_THRESHOLD = "count_threshold"           # 经验数量达到阈值
    IMPORTANCE_THRESHOLD = "importance_threshold"  # 高重要性经验比例达标
    REWARD_IMPROVEMENT = "reward_improvement"      # 奖励持续提升
    HIGH_VALUE_PATTERN = "high_value_pattern"      # 发现高价值模式
    MANUAL = "manual"                              # 手动触发
    COOLDOWN_EXPIRED = "cooldown_expired"          # 冷却期到期


class ConsolidationStatus(str, Enum):
    """整合状态."""
    EXECUTED = "executed"     # 成功执行整合
    SKIPPED = "skipped"       # 跳过 (触发条件不满足)
    FAILED = "failed"         # 执行失败


# ═══════════════════════════════════════════════════════════════
# 1. TriggerDecision
# ═══════════════════════════════════════════════════════════════


@dataclass
class TriggerDecision:
    """触发决策 — ConsolidationTrigger.check() 的返回值.

    Attributes:
        should_run: 是否应该执行整合
        reason: 触发原因
        confidence: 决策置信度 [0, 1]
        urgency: 紧急程度 [0, 1] (越高越需要立即执行)
        details: 详细说明
        timestamp: 决策时间
    """
    should_run: bool = False
    reason: TriggerReason = TriggerReason.COUNT_THRESHOLD
    confidence: float = 0.0
    urgency: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def skip(cls, reason: str = "conditions not met") -> TriggerDecision:
        """创建跳过决策."""
        return cls(
            should_run=False,
            reason=TriggerReason.COUNT_THRESHOLD,
            confidence=0.0,
            urgency=0.0,
            details={"skip_reason": reason},
        )

    @classmethod
    def approve(
        cls,
        reason: TriggerReason,
        confidence: float = 0.8,
        urgency: float = 0.5,
        **details,
    ) -> TriggerDecision:
        """创建批准决策."""
        return cls(
            should_run=True,
            reason=reason,
            confidence=confidence,
            urgency=urgency,
            details=details,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_run": self.should_run,
            "reason": self.reason.value,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "details": self.details,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# 2. ConsolidationContext (Duck-type compatible with OrchestrationCycleResult)
# ═══════════════════════════════════════════════════════════════


@dataclass
class _MockPolicyDecision:
    """Mock 策略决策 — 提供 from_cycle_result 所需的 getattr 接口."""
    action: str = ""
    decision_type: str = ""
    confidence: float = 0.0
    action_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class _MockExecutionResult:
    """Mock 执行结果."""
    success: bool = True
    action: str = ""


@dataclass
class _MockEffectiveness:
    """Mock 学习有效性."""
    learning_gain: float = 0.0
    effectiveness_score: float = 0.0
    metrics_delta: dict[str, float] = field(default_factory=dict)


@dataclass
class ConsolidationContext:
    """整合上下文 — 适配 MemoryConsolidationPipeline 的输入协议.

    将 GrowthExperience[] 聚合为与 OrchestrationCycleResult 兼容的上下文，
    使得 MemoryConsolidationPipeline 可以无修改地消费。

    关键设计:
      - 使用 getattr 兼容的字段名 (cycle_id, cycle_number, policy_decision 等)
      - 从 GrowthExperience 列表聚合出 policy_decision / execution_result / effectiveness
      - gate_result 和 policy_adjustments 为 None (经验写入路径不涉及门控)

    Attributes:
        cycle_id: 上下文唯一标识
        cycle_number: 整合批次编号
        source_experiences: 原始 GrowthExperience 列表
        experience_count: 经验数量
        policy_decision: 聚合的策略决策 (Mock)
        execution_result: 聚合的执行结果 (Mock)
        effectiveness: 聚合的学习有效性 (Mock)
        gate_result: 门控结果 (None)
        policy_adjustments: 策略调整 (None)
        metadata: 扩展元数据
    """
    cycle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    source_experiences: list[Any] = field(default_factory=list)  # list[GrowthExperience]
    experience_count: int = 0
    policy_decision: _MockPolicyDecision = field(default_factory=_MockPolicyDecision)
    execution_result: _MockExecutionResult = field(default_factory=_MockExecutionResult)
    effectiveness: _MockEffectiveness = field(default_factory=_MockEffectiveness)
    gate_result: Any = None
    policy_adjustments: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "experience_count": self.experience_count,
            "action": self.policy_decision.action,
            "confidence": self.policy_decision.confidence,
            "success": self.execution_result.success,
            "learning_gain": self.effectiveness.learning_gain,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 3. ConsolidationResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConsolidationResult:
    """整合结果 — ExperienceConsolidationPipeline.run() 的返回值.

    Attributes:
        status: 整合状态
        trigger_decision: 触发决策
        consolidation_report: 核心整合报告 (来自 MemoryConsolidationPipeline)
        experience_count: 输入的经验数量
        context_id: 使用的上下文 ID
        duration_ms: 总耗时
        error: 错误信息
        timestamp: 完成时间
    """
    status: ConsolidationStatus = ConsolidationStatus.SKIPPED
    trigger_decision: TriggerDecision = field(default_factory=TriggerDecision)
    consolidation_report: Any = None  # ConsolidationReport
    experience_count: int = 0
    context_id: str = ""
    duration_ms: float = 0.0
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def skipped(cls, trigger: TriggerDecision) -> ConsolidationResult:
        """创建跳过结果."""
        return cls(
            status=ConsolidationStatus.SKIPPED,
            trigger_decision=trigger,
        )

    @classmethod
    def executed(
        cls,
        trigger: TriggerDecision,
        report: Any,
        experience_count: int,
        context_id: str,
        duration_ms: float,
    ) -> ConsolidationResult:
        """创建成功执行结果."""
        return cls(
            status=ConsolidationStatus.EXECUTED,
            trigger_decision=trigger,
            consolidation_report=report,
            experience_count=experience_count,
            context_id=context_id,
            duration_ms=duration_ms,
        )

    @classmethod
    def failed(cls, trigger: TriggerDecision, error: str, duration_ms: float = 0.0) -> ConsolidationResult:
        """创建失败结果."""
        return cls(
            status=ConsolidationStatus.FAILED,
            trigger_decision=trigger,
            error=error,
            duration_ms=duration_ms,
        )

    @property
    def is_executed(self) -> bool:
        return self.status == ConsolidationStatus.EXECUTED

    @property
    def is_skipped(self) -> bool:
        return self.status == ConsolidationStatus.SKIPPED

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status.value,
            "trigger_decision": self.trigger_decision.to_dict(),
            "experience_count": self.experience_count,
            "context_id": self.context_id,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "timestamp": self.timestamp,
        }
        if self.consolidation_report is not None and hasattr(self.consolidation_report, "to_dict"):
            result["consolidation_report"] = self.consolidation_report.to_dict()
        return result


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "TriggerReason",
    "ConsolidationStatus",
    "TriggerDecision",
    "ConsolidationContext",
    "ConsolidationResult",
    "_MockPolicyDecision",
    "_MockExecutionResult",
    "_MockEffectiveness",
]