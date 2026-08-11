"""E13.7.8 Learning Orchestration Models — 学习循环编排协议.

Day 7.8:
  定义 LearningCycleOrchestrator 的 Contract 层，
  将现有的 Learning Components 升级为 Autonomous Learning Agent。

核心模型:
  1. CycleOrchestrationState  — 编排状态机
  2. OrchestratorConfig       — 编排器配置
  3. OrchestrationCycleResult — 编排周期输出

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 每个周期输出包含完整的状态转换记录
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. CycleOrchestrationState
# ═══════════════════════════════════════════════════════════════


class CycleOrchestrationState(str, Enum):
    """编排状态机 — 学习循环的完整生命周期.

    | 状态              | 说明                          | 下一状态             |
    |------------------|------------------------------|---------------------|
    | IDLE             | 未启动                        | OBSERVE             |
    | OBSERVE          | 观察当前状态                   | MEASURE_OUTCOME     |
    | MEASURE_OUTCOME  | 测量上一轮执行结果              | FEEDBACK_INGESTION  |
    | FEEDBACK_INGESTION| 分类并路由反馈 (Day 7.8 S4)   | CYCLE_GATE          |
    | CYCLE_GATE       | 门控评估 (Day 7.8 S5)         | EVALUATE / PAUSED   |
    | EVALUATE         | 评估学习有效性                 | POLICY_ADJUSTMENT   |
    | POLICY_ADJUSTMENT| 策略参数调整 (Day 7.8 S6)     | POLICY_DECISION     |
    | POLICY_DECISION  | 生成策略决策                   | EXECUTE             |
    | EXECUTE          | 执行策略决策                   | UPDATE_MEMORY       |
    | UPDATE_MEMORY    | 更新记忆/策略状态               | OPTIMIZE_STRATEGY   |
    | OPTIMIZE_STRATEGY| 优化策略参数                   | COMPLETED           |
    | COMPLETED        | 周期完成                       | NEXT_CYCLE / IDLE   |
    | PAUSED           | 暂停 (门控触发)                 | OBSERVE (resume)    |
    | FAILED           | 失败                          | IDLE (reset)        |
    """

    IDLE = "idle"
    OBSERVE = "observe"
    MEASURE_OUTCOME = "measure_outcome"
    FEEDBACK_INGESTION = "feedback_ingestion"
    CYCLE_GATE = "cycle_gate"
    EVALUATE = "evaluate"
    POLICY_ADJUSTMENT = "policy_adjustment"
    POLICY_DECISION = "policy_decision"
    EXECUTE = "execute"
    UPDATE_MEMORY = "update_memory"
    OPTIMIZE_STRATEGY = "optimize_strategy"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """是否为终态."""
        return self in {CycleOrchestrationState.COMPLETED, CycleOrchestrationState.FAILED}

    @property
    def is_running(self) -> bool:
        """是否为运行态."""
        return self not in {
            CycleOrchestrationState.IDLE,
            CycleOrchestrationState.COMPLETED,
            CycleOrchestrationState.FAILED,
            CycleOrchestrationState.PAUSED,
        }


# ═══════════════════════════════════════════════════════════════
# 2. OrchestratorConfig
# ═══════════════════════════════════════════════════════════════


@dataclass
class OrchestratorConfig:
    """编排器配置 — 控制自主循环行为.

    Attributes:
        max_cycles: 最大循环次数 (0 = 无限)
        cycle_interval_seconds: 周期间隔 (秒, 0 = 无延迟)
        min_effectiveness_threshold: 最低有效性阈值 (低于此值暂停)
        auto_pause_on_negative: 学习增益为负时自动暂停
        failure_max_retries: 单周期最大重试次数
        enable_policy_gating: 是否启用策略门控
        enable_auto_optimization: 是否启用自动策略优化
        metadata: 扩展配置
    """

    max_cycles: int = 0
    cycle_interval_seconds: float = 0.0
    min_effectiveness_threshold: float = 0.3
    auto_pause_on_negative: bool = True
    failure_max_retries: int = 3
    enable_policy_gating: bool = True
    enable_auto_optimization: bool = True
    enable_cycle_gate: bool = True
    enable_policy_adjustment: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_cycles": self.max_cycles,
            "cycle_interval_seconds": self.cycle_interval_seconds,
            "min_effectiveness_threshold": self.min_effectiveness_threshold,
            "auto_pause_on_negative": self.auto_pause_on_negative,
            "failure_max_retries": self.failure_max_retries,
            "enable_policy_gating": self.enable_policy_gating,
            "enable_auto_optimization": self.enable_auto_optimization,
            "enable_cycle_gate": self.enable_cycle_gate,
            "enable_policy_adjustment": self.enable_policy_adjustment,
            "metadata": self.metadata,
        }

    @classmethod
    def default(cls) -> OrchestratorConfig:
        """默认配置 — 保守模式."""
        return cls(
            max_cycles=100,
            cycle_interval_seconds=0.0,
            min_effectiveness_threshold=0.3,
            auto_pause_on_negative=True,
            failure_max_retries=3,
            enable_policy_gating=True,
            enable_auto_optimization=True,
        )

    @classmethod
    def aggressive(cls) -> OrchestratorConfig:
        """激进配置 — 最大化学习速度."""
        return cls(
            max_cycles=0,
            cycle_interval_seconds=0.0,
            min_effectiveness_threshold=0.1,
            auto_pause_on_negative=False,
            failure_max_retries=5,
            enable_policy_gating=False,
            enable_auto_optimization=True,
        )

    @classmethod
    def test_mode(cls) -> OrchestratorConfig:
        """测试配置 — 小规模运行."""
        return cls(
            max_cycles=10,
            cycle_interval_seconds=0.0,
            min_effectiveness_threshold=0.0,
            auto_pause_on_negative=False,
            failure_max_retries=1,
            enable_policy_gating=False,
            enable_auto_optimization=False,
        )


# ═══════════════════════════════════════════════════════════════
# 3. OrchestrationCycleResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class OrchestrationCycleResult:
    """编排周期结果 — 一次完整编排循环的输出.

    Day 7.8:
      区别于 LearningCycleResult (单次 LearningLoopController 输出)，
      本结果包含完整的编排周期:
        Observe → Measure → Evaluate → Policy → Execute → Memory → Optimize

    Attributes:
        cycle_id: 周期唯一标识
        cycle_number: 周期编号
        state: 最终状态
        effectiveness: 学习有效性评估结果 (LearningEffectiveness)
        policy_decision: 策略决策 (LearningPolicyDecision)
        execution_result: 执行结果 (LearningExecutionResult)
        memory_updates: 记忆更新记录
        strategy_adjusted: 策略是否被调整
        next_action: 下一步动作 (continue / pause / stop / retry)
        gating_reason: 门控原因 (如果被暂停)
        error: 错误信息
        state_transitions: 状态转换记录
        duration_ms: 周期耗时
        created_at: 创建时间
        metadata: 扩展元数据
    """

    cycle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    state: str = CycleOrchestrationState.IDLE.value
    effectiveness: Any = None  # LearningEffectiveness
    policy_decision: Any = None  # LearningPolicyDecision
    execution_result: Any = None  # LearningExecutionResult
    memory_updates: dict[str, Any] = field(default_factory=dict)
    strategy_adjusted: bool = False
    next_action: str = "continue"  # continue / pause / stop / retry
    gating_reason: str = ""
    gate_result: Any = None  # CycleGateResult (Day 7.8 Step 5)
    policy_adjustments: Any = None  # PolicyAdjustmentSet (Day 7.8 Step 6)
    error: str | None = None
    state_transitions: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_successful(self) -> bool:
        """周期是否成功完成."""
        return (
            self.state == CycleOrchestrationState.COMPLETED.value
            and self.error is None
        )

    @property
    def is_gated(self) -> bool:
        """是否被门控暂停."""
        return self.next_action == "pause" and bool(self.gating_reason)

    @property
    def should_continue(self) -> bool:
        """是否应继续下一轮."""
        return self.next_action == "continue"

    @property
    def should_stop(self) -> bool:
        """是否应停止."""
        return self.next_action == "stop"

    @property
    def has_effectiveness(self) -> bool:
        """是否有有效性评估."""
        return self.effectiveness is not None

    @property
    def has_policy_decision(self) -> bool:
        """是否有策略决策."""
        return self.policy_decision is not None

    @property
    def has_execution_result(self) -> bool:
        """是否有执行结果."""
        return self.execution_result is not None

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def idle_result(cls, cycle_number: int = 0) -> OrchestrationCycleResult:
        """创建 IDLE 状态结果."""
        return cls(
            cycle_number=cycle_number,
            state=CycleOrchestrationState.IDLE.value,
            next_action="continue",
        )

    @classmethod
    def completed_result(
        cls,
        cycle_number: int,
        effectiveness: Any = None,
        policy_decision: Any = None,
        execution_result: Any = None,
        memory_updates: dict[str, Any] | None = None,
        state_transitions: list[dict[str, Any]] | None = None,
        duration_ms: float = 0.0,
        **kwargs: Any,
    ) -> OrchestrationCycleResult:
        """创建 COMPLETED 状态结果."""
        return cls(
            cycle_number=cycle_number,
            state=CycleOrchestrationState.COMPLETED.value,
            effectiveness=effectiveness,
            policy_decision=policy_decision,
            execution_result=execution_result,
            memory_updates=memory_updates or {},
            next_action="continue",
            state_transitions=state_transitions or [],
            duration_ms=duration_ms,
            **kwargs,
        )

    @classmethod
    def paused_result(
        cls,
        cycle_number: int,
        gating_reason: str,
        state_transitions: list[dict[str, Any]] | None = None,
    ) -> OrchestrationCycleResult:
        """创建 PAUSED (门控) 结果."""
        return cls(
            cycle_number=cycle_number,
            state=CycleOrchestrationState.PAUSED.value,
            next_action="pause",
            gating_reason=gating_reason,
            state_transitions=state_transitions or [],
        )

    @classmethod
    def gated_result(
        cls,
        cycle_number: int,
        gate_result: Any = None,
        gating_reason: str = "",
        state_transitions: list[dict[str, Any]] | None = None,
    ) -> OrchestrationCycleResult:
        """创建门控结果 (Day 7.8 Step 5 — CycleGate).

        Args:
            cycle_number: 周期编号
            gate_result: CycleGateResult 实例
            gating_reason: 门控原因
            state_transitions: 状态转换记录

        Returns:
            OrchestrationCycleResult: 门控结果
        """
        # 映射 GateDecision → next_action
        decision = getattr(gate_result, "decision", "") if gate_result else ""
        next_action = {
            "pause": "pause",
            "rollback": "stop",
            "request_more_data": "continue",
        }.get(decision, "pause")

        state = CycleOrchestrationState.PAUSED.value
        if decision == "request_more_data":
            state = CycleOrchestrationState.COMPLETED.value

        return cls(
            cycle_number=cycle_number,
            state=state,
            next_action=next_action,
            gating_reason=gating_reason,
            gate_result=gate_result,
            state_transitions=state_transitions or [],
        )

    @classmethod
    def failed_result(
        cls,
        cycle_number: int,
        error: str,
        state: str = "",
        state_transitions: list[dict[str, Any]] | None = None,
    ) -> OrchestrationCycleResult:
        """创建 FAILED 结果."""
        return cls(
            cycle_number=cycle_number,
            state=state or CycleOrchestrationState.FAILED.value,
            next_action="retry",
            error=error,
            state_transitions=state_transitions or [],
        )

    @classmethod
    def stopped_result(
        cls,
        cycle_number: int,
        reason: str = "",
    ) -> OrchestrationCycleResult:
        """创建 STOP 结果."""
        return cls(
            cycle_number=cycle_number,
            state=CycleOrchestrationState.COMPLETED.value,
            next_action="stop",
            gating_reason=reason,
        )

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "state": self.state,
            "effectiveness": (
                self.effectiveness.to_dict()
                if hasattr(self.effectiveness, "to_dict")
                else None
            ),
            "policy_decision": (
                self.policy_decision.to_dict()
                if hasattr(self.policy_decision, "to_dict")
                else None
            ),
            "execution_result": (
                self.execution_result.to_dict()
                if hasattr(self.execution_result, "to_dict")
                else None
            ),
            "memory_updates": self.memory_updates,
            "strategy_adjusted": self.strategy_adjusted,
            "next_action": self.next_action,
            "gating_reason": self.gating_reason,
            "gate_result": (
                self.gate_result.to_dict()
                if hasattr(self.gate_result, "to_dict")
                else None
            ),
            "policy_adjustments": (
                self.policy_adjustments.to_dict()
                if hasattr(self.policy_adjustments, "to_dict")
                else None
            ),
            "error": self.error,
            "state_transitions": self.state_transitions,
            "duration_ms": self.duration_ms,
            "is_successful": self.is_successful,
            "is_gated": self.is_gated,
            "should_continue": self.should_continue,
            "should_stop": self.should_stop,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "CycleOrchestrationState",
    "OrchestratorConfig",
    "OrchestrationCycleResult",
]