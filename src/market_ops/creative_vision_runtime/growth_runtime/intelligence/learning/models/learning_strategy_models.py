"""E13.7.7 Learning Strategy Models — 学习策略控制平面数据模型.

Day 7.7.1:
  定义 Adaptive Learning Optimization Layer 的共享协议，
  使系统从 "Learning System" 升级为 "Self-Optimizing Learning System"。

核心模型:
  1. LearningStrategyState    — 学习策略状态 (控制参数中心)
  2. LearningAdjustment       — 策略调整记录 (单次调整的完整信息)
  3. LearningPolicyDecision   — 策略决策 (控制器做出的决策)

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 所有模块 (Optimizer, Confidence, Policy, Exploration) 通过此协议通信
  - 可序列化 (to_dict)，支持持久化和审计
  - 不修改现有执行链 (Day 7.7.1 仅定义接口)

用法:
  from growth_runtime.intelligence.learning.models.learning_strategy_models import (
      LearningStrategyState,
      LearningAdjustment,
      LearningPolicyDecision,
      LearningMode,
      PolicyAction,
      AdjustmentSource,
  )

  state = LearningStrategyState()
  adjustment = LearningAdjustment(
      reason="learning_gain negative",
      parameter="pattern_weight",
      previous_value=0.7,
      new_value=0.4,
      source=AdjustmentSource.EVALUATION,
  )
  decision = LearningPolicyDecision(
      action=PolicyAction.INCREASE_EXPLORATION,
      evidence=["learning gain < 0", "trend declining"],
      confidence=0.85,
      previous_state_snapshot=state.to_dict(),
  )
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


class LearningMode(str, Enum):
    """学习模式 — 决定系统对 Pattern 和 Memory 的信任程度.

    | 模式         | Pattern 信任 | 探索率 | 衰减速度 | 适用场景             |
    |-------------|-------------|--------|---------|---------------------|
    | AGGRESSIVE   | 高          | 低     | 慢      | 稳定市场、已验证策略    |
    | BALANCED     | 中          | 中     | 中      | 正常运营 (默认)       |
    | CONSERVATIVE | 低          | 高     | 快      | 市场变化、学习失效     |
    """
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"


class PolicyAction(str, Enum):
    """策略动作 — LearningPolicyController 可执行的动作类型.

    | 动作                       | 含义                        | 触发条件示例              |
    |---------------------------|----------------------------|-------------------------|
    | INCREASE_EXPLORATION       | 提高探索比例                 | learning_gain < 0       |
    | REDUCE_PATTERN_WEIGHT      | 降低 Pattern 在决策中的权重    | pattern 连续失败         |
    | REFRESH_MEMORY             | 强制刷新记忆 (提高衰减速率)     | pattern_decay detected  |
    | STRENGTHEN_PATTERN         | 强化 Pattern 置信度          | 连续成功验证             |
    | DECAY_PATTERN              | 衰减 Pattern 置信度          | 近期表现下降             |
    | ADJUST_CONFIDENCE_THRESHOLD | 调整置信度阈值               | 整体置信度偏差           |
    | SWITCH_LEARNING_MODE       | 切换学习模式                 | 趋势方向改变             |
    """
    INCREASE_EXPLORATION = "increase_exploration"
    REDUCE_PATTERN_WEIGHT = "reduce_pattern_weight"
    REFRESH_MEMORY = "refresh_memory"
    STRENGTHEN_PATTERN = "strengthen_pattern"
    DECAY_PATTERN = "decay_pattern"
    ADJUST_CONFIDENCE_THRESHOLD = "adjust_confidence_threshold"
    SWITCH_LEARNING_MODE = "switch_learning_mode"


class AdjustmentSource(str, Enum):
    """调整来源 — 触发策略调整的数据来源.

    | 来源        | 含义                      |
    |------------|--------------------------|
    | EVALUATION | LearningEvaluator 评估结果 |
    | TREND      | ImprovementTrend 趋势检测  |
    | MANUAL     | 人工手动调整               |
    """
    EVALUATION = "evaluation"
    TREND = "trend"
    MANUAL = "manual"


class PolicyPriority(str, Enum):
    """策略优先级 — 决定调整的执行顺序和紧急程度."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PolicyDecisionType(str, Enum):
    """策略决策类型 — LearningPolicyController 的综合决策结果.

    | 类型                  | 含义                          | 触发条件              |
    |----------------------|------------------------------|----------------------|
    | ALLOW_LEARNING       | 允许学习系统更新                | 学习有效 + 置信度足够  |
    | BLOCK_LEARNING       | 阻止学习 (保护现有策略)          | 学习无效 + 置信度不足  |
    | REQUEST_MEMORY_REFRESH | 请求刷新记忆系统              | 记忆衰减 + 模式失效    |
    | ADJUST_MODE          | 调整学习模式                   | 趋势方向改变          |
    | MAINTAIN             | 保持当前策略不变                | 所有指标正常          |
    """
    ALLOW_LEARNING = "allow_learning"
    BLOCK_LEARNING = "block_learning"
    REQUEST_MEMORY_REFRESH = "request_memory_refresh"
    ADJUST_MODE = "adjust_mode"
    MAINTAIN = "maintain"


# ═══════════════════════════════════════════════════════════════
# 1. LearningStrategyState
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningStrategyState:
    """学习策略状态 — 整个学习系统的控制参数中心.

    Day 7.7.1:
      作为 Adaptive Layer 的共享协议，所有控制模块 (Optimizer, Confidence,
      Policy, Exploration) 通过此对象协调学习行为。

      类似 ML 系统中的超参数配置中心 / 强化学习中的 policy state。

    Attributes:
        state_id: 状态唯一标识
        confidence_threshold: 最小置信度阈值 [0, 1]
        pattern_weight: Pattern 在决策中的权重 [0, 1]
        memory_weight: Memory 在决策中的权重 [0, 1]
        exploration_rate: 探索比例 [0, 1]
        memory_decay_rate: 记忆衰减速率 λ (默认 0.01, 每天衰减约 1%)
        learning_mode: 学习模式 (aggressive/balanced/conservative)
        min_samples_for_confidence: 最小样本量 (不足时降低置信度)
        created_at: 创建时间
        updated_at: 更新时间
        version: 版本号 (每次调整 +1)
        metadata: 扩展元数据
    """

    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # 置信度控制
    confidence_threshold: float = 0.50
    # 权重控制
    pattern_weight: float = 0.70
    memory_weight: float = 0.30
    # 探索/利用
    exploration_rate: float = 0.20
    # 记忆衰减
    memory_decay_rate: float = 0.01
    # 学习模式
    learning_mode: str = LearningMode.BALANCED.value
    # 样本量
    min_samples_for_confidence: int = 10
    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Validation ──────────────────────────────────────────────

    def __post_init__(self) -> None:
        """验证参数范围."""
        self.confidence_threshold = max(0.0, min(1.0, self.confidence_threshold))
        self.pattern_weight = max(0.0, min(1.0, self.pattern_weight))
        self.memory_weight = max(0.0, min(1.0, self.memory_weight))
        self.exploration_rate = max(0.0, min(1.0, self.exploration_rate))
        self.memory_decay_rate = max(0.001, min(0.1, self.memory_decay_rate))
        self.min_samples_for_confidence = max(1, self.min_samples_for_confidence)

    # ── Properties ──────────────────────────────────────────────

    @property
    def exploitation_rate(self) -> float:
        """利用比例 (1 - exploration_rate)."""
        return round(1.0 - self.exploration_rate, 4)

    @property
    def is_aggressive(self) -> bool:
        return self.learning_mode == LearningMode.AGGRESSIVE.value

    @property
    def is_balanced(self) -> bool:
        return self.learning_mode == LearningMode.BALANCED.value

    @property
    def is_conservative(self) -> bool:
        return self.learning_mode == LearningMode.CONSERVATIVE.value

    @property
    def weights_normalized(self) -> bool:
        """权重是否归一化 (pattern + memory ≈ 1.0)."""
        total = self.pattern_weight + self.memory_weight
        return abs(total - 1.0) < 0.01

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def default(cls) -> LearningStrategyState:
        """创建默认平衡策略."""
        return cls(
            learning_mode=LearningMode.BALANCED.value,
            confidence_threshold=0.50,
            pattern_weight=0.70,
            memory_weight=0.30,
            exploration_rate=0.20,
            memory_decay_rate=0.01,
            min_samples_for_confidence=10,
        )

    @classmethod
    def aggressive(cls) -> LearningStrategyState:
        """创建激进策略 (高信任、低探索)."""
        return cls(
            learning_mode=LearningMode.AGGRESSIVE.value,
            confidence_threshold=0.40,
            pattern_weight=0.85,
            memory_weight=0.15,
            exploration_rate=0.05,
            memory_decay_rate=0.005,
            min_samples_for_confidence=5,
        )

    @classmethod
    def conservative(cls) -> LearningStrategyState:
        """创建保守策略 (低信任、高探索)."""
        return cls(
            learning_mode=LearningMode.CONSERVATIVE.value,
            confidence_threshold=0.65,
            pattern_weight=0.40,
            memory_weight=0.60,
            exploration_rate=0.50,
            memory_decay_rate=0.03,
            min_samples_for_confidence=20,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearningStrategyState:
        """从字典重建."""
        return cls(
            state_id=data.get("state_id", ""),
            confidence_threshold=data.get("confidence_threshold", 0.50),
            pattern_weight=data.get("pattern_weight", 0.70),
            memory_weight=data.get("memory_weight", 0.30),
            exploration_rate=data.get("exploration_rate", 0.20),
            memory_decay_rate=data.get("memory_decay_rate", 0.01),
            learning_mode=data.get("learning_mode", LearningMode.BALANCED.value),
            min_samples_for_confidence=data.get("min_samples_for_confidence", 10),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("version", 1),
            metadata=data.get("metadata", {}),
        )

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "confidence_threshold": self.confidence_threshold,
            "pattern_weight": self.pattern_weight,
            "memory_weight": self.memory_weight,
            "exploration_rate": self.exploration_rate,
            "memory_decay_rate": self.memory_decay_rate,
            "learning_mode": self.learning_mode,
            "min_samples_for_confidence": self.min_samples_for_confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "metadata": self.metadata,
        }

    def clone(self) -> LearningStrategyState:
        """深拷贝当前状态 (用于创建调整快照)."""
        return LearningStrategyState(
            confidence_threshold=self.confidence_threshold,
            pattern_weight=self.pattern_weight,
            memory_weight=self.memory_weight,
            exploration_rate=self.exploration_rate,
            memory_decay_rate=self.memory_decay_rate,
            learning_mode=self.learning_mode,
            min_samples_for_confidence=self.min_samples_for_confidence,
            metadata=dict(self.metadata),
        )

    def bump_version(self) -> None:
        """版本号 +1 并更新时间戳."""
        self.version += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════
# 2. LearningAdjustment
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningAdjustment:
    """学习策略调整记录 — 单次策略调整的完整信息.

    Day 7.7.1:
      记录每次 LearningStrategyState 参数变更的原因、幅度和预期影响，
      保证所有调整可追溯、可审计、可回滚。

    Attributes:
        adjustment_id: 调整唯一标识
        state_id: 关联的 LearningStrategyState ID
        reason: 调整原因 (human-readable)
        parameter: 被调整的参数名
        previous_value: 调整前的值
        new_value: 调整后的值
        delta: 变化量 (new - previous)
        delta_percentage: 变化百分比
        impact_prediction: 预期影响 (正=改善, 负=可能恶化)
        confidence: 调整决策的置信度 [0, 1]
        source: 触发来源 (evaluation/trend/manual)
        source_detail: 触发来源的详细信息
        reversible: 是否可回滚 (所有自动调整默认可回滚)
        created_at: 创建时间
        metadata: 扩展元数据
    """

    adjustment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state_id: str = ""
    reason: str = ""
    parameter: str = ""
    previous_value: float = 0.0
    new_value: float = 0.0
    impact_prediction: float = 0.0
    confidence: float = 0.0
    source: str = AdjustmentSource.EVALUATION.value
    source_detail: str = ""
    reversible: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def delta(self) -> float:
        """变化量."""
        return round(self.new_value - self.previous_value, 6)

    @property
    def delta_percentage(self) -> float:
        """变化百分比."""
        if self.previous_value == 0:
            return 0.0 if self.new_value == 0 else float("inf")
        return round((self.new_value - self.previous_value) / abs(self.previous_value) * 100, 2)

    @property
    def is_increase(self) -> bool:
        return self.new_value > self.previous_value

    @property
    def is_decrease(self) -> bool:
        return self.new_value < self.previous_value

    @property
    def is_significant(self) -> bool:
        """变化是否显著 (>= 10%)."""
        return abs(self.delta_percentage) >= 10.0 if self.delta_percentage != float("inf") else True

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "state_id": self.state_id,
            "reason": self.reason,
            "parameter": self.parameter,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "delta": self.delta,
            "delta_percentage": self.delta_percentage,
            "impact_prediction": round(self.impact_prediction, 4),
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "source_detail": self.source_detail,
            "reversible": self.reversible,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 3. LearningPolicyDecision
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningPolicyDecision:
    """学习策略决策 — 策略控制器做出的单次决策.

    Day 7.7.1:
      表示 LearningPolicyController 在分析评估结果后做出的策略调整决定。
      决策包含动作类型、支持证据、优先级和预期影响。

    Day 7.7.4:
      扩展为综合策略决策，回答四个核心问题:
        1. 是否应该学习？ (should_learn)
        2. 是否应该刷新记忆？ (should_update_memory)
        3. 是否调整策略模式？ (strategy_mode)
        4. 产生的决策类型是什么？ (decision_type)

    Attributes:
        decision_id: 决策唯一标识
        state_id: 关联的 LearningStrategyState ID
        decision_type: 决策类型 (PolicyDecisionType)
        should_learn: 是否允许学习系统更新
        should_update_memory: 是否应刷新记忆系统
        strategy_mode: 推荐的学习模式
        action: 策略动作类型 (保留 Day 7.7.1 兼容)
        priority: 优先级 (high/medium/low)
        evidence: 支持证据列表
        reasons: 决策原因 (human-readable)
        confidence: 决策置信度 [0, 1]
        adaptive_confidence: 自适应置信度 (来自 AdaptiveConfidenceEngine)
        learning_effectiveness_score: 学习有效性分数
        expected_impact: 预期影响 (正=改善)
        reversible: 是否可回滚
        previous_state_snapshot: 调整前的状态快照 (用于回滚)
        adjustments: 此决策触发的具体调整列表
        triggered_by: 触发来源 (evaluation_id / trend_id)
        created_at: 创建时间
        metadata: 扩展元数据
    """

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state_id: str = ""
    # Day 7.7.4 新增: 综合决策字段
    decision_type: str = PolicyDecisionType.MAINTAIN.value
    should_learn: bool = True
    should_update_memory: bool = False
    strategy_mode: str = LearningMode.BALANCED.value
    # Day 7.7.1 原有字段
    action: str = PolicyAction.INCREASE_EXPLORATION.value
    priority: str = PolicyPriority.MEDIUM.value
    evidence: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    adaptive_confidence: float = 0.0
    learning_effectiveness_score: float = 0.0
    expected_impact: float = 0.0
    reversible: bool = True
    previous_state_snapshot: dict[str, Any] | None = None
    adjustments: list[LearningAdjustment] = field(default_factory=list)
    triggered_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_high_priority(self) -> bool:
        return self.priority == PolicyPriority.HIGH.value

    @property
    def is_emergency(self) -> bool:
        """是否为紧急决策 (高优先级 + 高置信度)."""
        return self.is_high_priority and self.confidence >= 0.80

    @property
    def adjustment_count(self) -> int:
        return len(self.adjustments)

    @property
    def total_impact(self) -> float:
        """所有调整的预期影响总和."""
        if not self.adjustments:
            return self.expected_impact
        return round(sum(a.impact_prediction for a in self.adjustments), 4)

    # ── Methods ─────────────────────────────────────────────────

    def add_adjustment(self, adjustment: LearningAdjustment) -> None:
        """添加一个具体调整."""
        self.adjustments.append(adjustment)

    def can_rollback(self) -> bool:
        """是否可回滚 (需要快照 + reversible)."""
        return self.reversible and self.previous_state_snapshot is not None

    def rollback_state(self) -> LearningStrategyState | None:
        """从快照恢复状态."""
        if not self.can_rollback():
            return None
        return LearningStrategyState.from_dict(self.previous_state_snapshot)

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "state_id": self.state_id,
            "decision_type": self.decision_type,
            "should_learn": self.should_learn,
            "should_update_memory": self.should_update_memory,
            "strategy_mode": self.strategy_mode,
            "action": self.action,
            "priority": self.priority,
            "evidence": self.evidence,
            "reasons": self.reasons,
            "confidence": round(self.confidence, 4),
            "adaptive_confidence": round(self.adaptive_confidence, 4),
            "learning_effectiveness_score": round(self.learning_effectiveness_score, 4),
            "expected_impact": round(self.expected_impact, 4),
            "reversible": self.reversible,
            "previous_state_snapshot": self.previous_state_snapshot,
            "adjustments": [a.to_dict() for a in self.adjustments],
            "adjustment_count": self.adjustment_count,
            "triggered_by": self.triggered_by,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "LearningMode",
    "PolicyAction",
    "AdjustmentSource",
    "PolicyPriority",
    "PolicyDecisionType",
    "LearningStrategyState",
    "LearningAdjustment",
    "LearningPolicyDecision",
]