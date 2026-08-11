"""E12.5.5 — Autonomous Meta Learning Loop Models。

定义自我学习循环的核心数据结构。

核心模型:
  MetaCycleStatus:     学习周期状态
  MetaLearningCycle:   学习周期
  LearningSchedule:    学习触发策略
  LearningTrigger:     触发条件
  StrategyFeedback:    策略反馈（预测 vs 实际）
  KnowledgeUpdate:     知识更新记录
  LearningSummary:     学习周期总结
  LoopMetrics:         循环运行指标
  MetaLearningResult:  控制器输出
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ──────────────────────────────────────────────────


class MetaCycleStatus(str, Enum):
    """学习周期状态。"""

    CREATED = "created"
    COLLECTING = "collecting"
    MINING = "mining"
    OPTIMIZING = "optimizing"
    EXECUTING = "executing"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerReason(str, Enum):
    """触发原因。"""

    EXPERIMENT_COUNT = "experiment_count"
    SPEND_THRESHOLD = "spend_threshold"
    TIME_INTERVAL = "time_interval"
    PERFORMANCE_DROP = "performance_drop"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


# ── MetaLearningCycle ──────────────────────────────────────


@dataclass
class MetaLearningCycle:
    """学习周期 —— 一次完整的 Meta Learning 迭代。

    Attributes:
        cycle_id:             周期 ID
        product_id:           产品 ID
        status:               周期状态
        start_time:           开始时间
        end_time:             结束时间
        trigger_reason:       触发原因
        experiments_analyzed: 分析的实验数
        patterns_discovered:  发现的 Pattern 数
        strategies_generated: 生成的策略数
        knowledge_updates:    知识更新次数
        feedbacks_collected:  收集的策略反馈数
        learning_gain:        学习增益 [0, 1]
        cycle_number:         周期序号
        errors:               错误列表
        summary:              周期总结
        metadata:             额外元数据
    """

    cycle_id: str = ""
    product_id: str = ""
    status: MetaCycleStatus = MetaCycleStatus.CREATED
    start_time: datetime = field(default_factory=_now)
    end_time: datetime | None = None
    trigger_reason: TriggerReason = TriggerReason.SCHEDULED

    experiments_analyzed: int = 0
    patterns_discovered: int = 0
    strategies_generated: int = 0
    knowledge_updates: int = 0
    feedbacks_collected: int = 0

    learning_gain: float = 0.0
    cycle_number: int = 0

    errors: list[str] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cycle_id:
            self.cycle_id = _gen_id("MLC")

    @property
    def is_active(self) -> bool:
        """周期是否活跃。"""
        return self.status not in (
            MetaCycleStatus.COMPLETED,
            MetaCycleStatus.FAILED,
        )

    @property
    def is_successful(self) -> bool:
        """周期是否成功。"""
        return self.status == MetaCycleStatus.COMPLETED

    @property
    def duration_seconds(self) -> float | None:
        """周期持续时间（秒）。"""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    def mark_completed(self, summary: str = "") -> None:
        """标记周期完成。"""
        self.status = MetaCycleStatus.COMPLETED
        self.end_time = _now()
        if summary:
            self.summary = summary

    def mark_failed(self, error: str) -> None:
        """标记周期失败。"""
        self.status = MetaCycleStatus.FAILED
        self.end_time = _now()
        self.errors.append(error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "product_id": self.product_id,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "trigger_reason": self.trigger_reason.value,
            "experiments_analyzed": self.experiments_analyzed,
            "patterns_discovered": self.patterns_discovered,
            "strategies_generated": self.strategies_generated,
            "knowledge_updates": self.knowledge_updates,
            "feedbacks_collected": self.feedbacks_collected,
            "learning_gain": round(self.learning_gain, 4),
            "cycle_number": self.cycle_number,
            "is_active": self.is_active,
            "is_successful": self.is_successful,
            "duration_seconds": round(self.duration_seconds, 2) if self.duration_seconds else None,
            "errors": self.errors,
            "summary": self.summary,
        }

    def __repr__(self) -> str:
        return (
            f"MetaLearningCycle({self.cycle_id[:15]}, "
            f"status={self.status.value}, "
            f"gain={self.learning_gain:.2f})"
        )


# ── LearningSchedule ───────────────────────────────────────


@dataclass
class LearningSchedule:
    """学习触发策略 —— 决定何时启动 Meta Learning。

    Attributes:
        min_experiments:        最小实验数
        min_spend:              最小花费
        learning_interval_days: 学习间隔（天）
        min_new_experiments:    最小新增实验数
        performance_drop:       性能下降阈值
        auto_trigger:           是否自动触发
        max_cycles_per_day:     每日最大周期数
    """

    min_experiments: int = 50
    min_spend: float = 5000.0
    learning_interval_days: int = 7
    min_new_experiments: int = 10
    performance_drop: float = 0.15
    auto_trigger: bool = True
    max_cycles_per_day: int = 24

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_experiments": self.min_experiments,
            "min_spend": self.min_spend,
            "learning_interval_days": self.learning_interval_days,
            "min_new_experiments": self.min_new_experiments,
            "performance_drop": self.performance_drop,
            "auto_trigger": self.auto_trigger,
            "max_cycles_per_day": self.max_cycles_per_day,
        }

    def __repr__(self) -> str:
        return (
            f"LearningSchedule(exp={self.min_experiments}, "
            f"spend=${self.min_spend:,.0f}, "
            f"interval={self.learning_interval_days}d)"
        )


# ── LearningTrigger ────────────────────────────────────────


@dataclass
class LearningTrigger:
    """学习触发信息。

    Attributes:
        reason:           触发原因
        experiment_count: 当前实验数
        total_spend:      当前总花费
        new_experiments:  新增实验数
        days_since_last:  距上次学习天数
        performance_drop: 性能下降幅度
        should_trigger:   是否应该触发
        triggered_at:     触发时间
        message:          触发消息
    """

    reason: TriggerReason = TriggerReason.SCHEDULED
    experiment_count: int = 0
    total_spend: float = 0.0
    new_experiments: int = 0
    days_since_last: float = 0.0
    performance_drop: float = 0.0
    should_trigger: bool = False
    triggered_at: datetime | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.should_trigger and self.triggered_at is None:
            self.triggered_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason.value,
            "experiment_count": self.experiment_count,
            "total_spend": self.total_spend,
            "new_experiments": self.new_experiments,
            "days_since_last": round(self.days_since_last, 2),
            "performance_drop": round(self.performance_drop, 4),
            "should_trigger": self.should_trigger,
            "message": self.message,
        }

    def __repr__(self) -> str:
        return (
            f"LearningTrigger(reason={self.reason.value}, "
            f"should={self.should_trigger})"
        )


# ── StrategyFeedback ───────────────────────────────────────


@dataclass
class StrategyFeedback:
    """策略反馈 —— 预测 vs 实际。

    Attributes:
        strategy_id:      策略 ID
        cycle_id:         所属周期 ID
        predicted_gain:   预测增益
        actual_gain:      实际增益
        prediction_error: 预测误差
        success:          是否成功
        confidence:       反馈置信度
        collected_at:     收集时间
        notes:            备注
    """

    strategy_id: str = ""
    cycle_id: str = ""
    predicted_gain: float = 0.0
    actual_gain: float = 0.0
    prediction_error: float = 0.0
    success: bool = False
    confidence: float = 0.0
    collected_at: datetime = field(default_factory=_now)
    notes: str = ""

    def __post_init__(self) -> None:
        if self.prediction_error == 0.0 and self.predicted_gain != 0:
            self.prediction_error = abs(self.actual_gain - self.predicted_gain)

    @property
    def prediction_accuracy(self) -> float:
        """预测准确度。

        1.0 = 完美预测，>1.0 = 低估，<1.0 = 高估。
        """
        if self.predicted_gain == 0:
            return 0.0
        return self.actual_gain / self.predicted_gain

    @property
    def is_overestimated(self) -> bool:
        """是否高估了效果。"""
        return self.prediction_accuracy < 1.0

    @property
    def is_underestimated(self) -> bool:
        """是否低估了效果。"""
        return self.prediction_accuracy > 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "cycle_id": self.cycle_id,
            "predicted_gain": round(self.predicted_gain, 4),
            "actual_gain": round(self.actual_gain, 4),
            "prediction_error": round(self.prediction_error, 4),
            "prediction_accuracy": round(self.prediction_accuracy, 4),
            "success": self.success,
            "confidence": round(self.confidence, 4),
            "is_overestimated": self.is_overestimated,
            "is_underestimated": self.is_underestimated,
            "notes": self.notes,
        }

    def __repr__(self) -> str:
        return (
            f"StrategyFeedback(pred={self.predicted_gain:.2f}, "
            f"actual={self.actual_gain:.2f}, "
            f"success={self.success})"
        )


# ── KnowledgeUpdate ────────────────────────────────────────


@dataclass
class KnowledgeUpdate:
    """知识更新记录。

    Attributes:
        node_id:          更新的知识节点 ID
        old_confidence:   旧置信度
        new_confidence:   新置信度
        evidence_count:   新增证据数
        cycle_id:         所属周期 ID
        updated_at:       更新时间
        update_reason:    更新原因
    """

    node_id: str = ""
    old_confidence: float = 0.0
    new_confidence: float = 0.0
    evidence_count: int = 0
    cycle_id: str = ""
    updated_at: datetime = field(default_factory=_now)
    update_reason: str = ""

    @property
    def confidence_delta(self) -> float:
        """置信度变化。"""
        return self.new_confidence - self.old_confidence

    @property
    def is_improved(self) -> bool:
        """置信度是否提升。"""
        return self.confidence_delta > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "old_confidence": round(self.old_confidence, 4),
            "new_confidence": round(self.new_confidence, 4),
            "confidence_delta": round(self.confidence_delta, 4),
            "evidence_count": self.evidence_count,
            "cycle_id": self.cycle_id,
            "is_improved": self.is_improved,
            "update_reason": self.update_reason,
        }

    def __repr__(self) -> str:
        return (
            f"KnowledgeUpdate({self.node_id}, "
            f"conf={self.old_confidence:.2f}→{self.new_confidence:.2f})"
        )


# ── LearningSummary ────────────────────────────────────────


@dataclass
class LearningSummary:
    """学习周期总结。

    Attributes:
        cycle_id:             周期 ID
        total_experiments:    总实验数
        total_patterns:       总 Pattern 数
        total_strategies:     总策略数
        total_feedbacks:      总反馈数
        average_prediction_accuracy: 平均预测准确度
        strategies_improved:  策略改进数
        knowledge_improved:   知识改进数
        overall_learning_gain: 综合学习增益
        summary_text:         文字总结
    """

    cycle_id: str = ""
    total_experiments: int = 0
    total_patterns: int = 0
    total_strategies: int = 0
    total_feedbacks: int = 0
    average_prediction_accuracy: float = 0.0
    strategies_improved: int = 0
    knowledge_improved: int = 0
    overall_learning_gain: float = 0.0
    summary_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "total_experiments": self.total_experiments,
            "total_patterns": self.total_patterns,
            "total_strategies": self.total_strategies,
            "total_feedbacks": self.total_feedbacks,
            "average_prediction_accuracy": round(self.average_prediction_accuracy, 4),
            "strategies_improved": self.strategies_improved,
            "knowledge_improved": self.knowledge_improved,
            "overall_learning_gain": round(self.overall_learning_gain, 4),
            "summary_text": self.summary_text,
        }

    def __repr__(self) -> str:
        return (
            f"LearningSummary(exp={self.total_experiments}, "
            f"gain={self.overall_learning_gain:.2f})"
        )


# ── LoopMetrics ────────────────────────────────────────────


@dataclass
class LoopMetrics:
    """循环运行指标。

    Attributes:
        total_cycles:         总周期数
        successful_cycles:    成功周期数
        failed_cycles:        失败周期数
        total_patterns_mined: 累计挖掘 Pattern 数
        total_knowledge_updated: 累计知识更新数
        total_strategies_generated: 累计策略数
        average_learning_gain: 平均学习增益
        average_cycle_duration: 平均周期时长（秒）
        uptime:               运行时长（秒）
    """

    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    total_patterns_mined: int = 0
    total_knowledge_updated: int = 0
    total_strategies_generated: int = 0
    average_learning_gain: float = 0.0
    average_cycle_duration: float = 0.0
    uptime: float = 0.0

    @property
    def success_rate(self) -> float:
        """周期成功率。"""
        if self.total_cycles == 0:
            return 0.0
        return self.successful_cycles / self.total_cycles

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cycles": self.total_cycles,
            "successful_cycles": self.successful_cycles,
            "failed_cycles": self.failed_cycles,
            "success_rate": round(self.success_rate, 4),
            "total_patterns_mined": self.total_patterns_mined,
            "total_knowledge_updated": self.total_knowledge_updated,
            "total_strategies_generated": self.total_strategies_generated,
            "average_learning_gain": round(self.average_learning_gain, 4),
            "average_cycle_duration": round(self.average_cycle_duration, 2),
            "uptime": round(self.uptime, 2),
        }

    def __repr__(self) -> str:
        return (
            f"LoopMetrics(cycles={self.total_cycles}, "
            f"success_rate={self.success_rate:.0%})"
        )


# ── MetaLearningResult ─────────────────────────────────────


@dataclass
class MetaLearningResult:
    """Meta Learning 控制器输出。

    Attributes:
        cycle:              学习周期
        trigger:            触发信息
        strategies:         生成的策略列表
        feedbacks:          策略反馈列表
        knowledge_updates:  知识更新列表
        summary:            学习总结
        metrics:            循环指标
        success:            是否成功
    """

    cycle: MetaLearningCycle = field(default_factory=MetaLearningCycle)
    trigger: LearningTrigger | None = None
    strategies: list = field(default_factory=list)
    feedbacks: list[StrategyFeedback] = field(default_factory=list)
    knowledge_updates: list[KnowledgeUpdate] = field(default_factory=list)
    summary: LearningSummary | None = None
    metrics: LoopMetrics | None = None
    success: bool = False

    def __post_init__(self) -> None:
        if self.summary is None:
            self.summary = LearningSummary(cycle_id=self.cycle.cycle_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle.to_dict(),
            "trigger": self.trigger.to_dict() if self.trigger else None,
            "strategies_count": len(self.strategies),
            "feedbacks_count": len(self.feedbacks),
            "knowledge_updates": [k.to_dict() for k in self.knowledge_updates],
            "summary": self.summary.to_dict() if self.summary else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "success": self.success,
        }

    def __repr__(self) -> str:
        return (
            f"MetaLearningResult(cycle={self.cycle.cycle_id[:15]}, "
            f"success={self.success})"
        )