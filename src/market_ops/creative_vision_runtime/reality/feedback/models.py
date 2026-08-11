"""E12.4 — Reality Feedback Models。

定义 Reality Feedback Layer 核心数据模型：

Phase 1:
  FeedbackSignalType:   反馈信号类型（5种）
  RealityFeedbackSignal: 核心反馈信号
  PredictionOutcome:    预测结果与实际结果对比

Phase 2:
  MutationIntent:       突变意图（5种）
  MutationRequest:      突变请求
  ExperimentStatus:     实验状态（6阶段）
  ExperimentRun:        实验运行记录
  ExperimentEvaluation: 实验结果评估
  EvolutionLearningRecord: 进化学习记录
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enums ──────────────────────────────────────────────────


class FeedbackSignalType(str, Enum):
    """反馈信号类型。

    每种类型对应一种 E11 Evolution Action。
    """

    FATIGUE_WARNING = "fatigue_warning"           # 疲劳预警 → 创建 Mutation
    ROAS_DECLINE = "roas_decline"                 # ROAS 下降 → DNA 分析 + Mutation
    SCALE_OPPORTUNITY = "scale_opportunity"        # 放量机会 → 增加探索
    CREATIVE_REPLACEMENT = "creative_replacement"  # 素材替换 → 归档 + 替换
    DATA_COLLECTION = "data_collection"            # 数据不足 → 继续收集


# ── RealityFeedbackSignal ──────────────────────────────────


@dataclass
class RealityFeedbackSignal:
    """E12.4 核心输出 —— 反馈信号。

    将 E12.3 Prediction 转换为可执行的反馈信号，
    供 E11 Evolution Orchestrator 消费。

    Attributes:
        signal_id:          信号 ID
        creative_id:        创意 ID
        signal_type:        信号类型
        severity:           严重程度（0-1）
        confidence:         置信度（0-1）
        reason:             原因列表
        recommended_action: 建议行动
        source_prediction_id: 来源预测 ID
        metadata:           额外元数据
        created_at:         创建时间
    """

    signal_id: str = ""
    creative_id: str = ""
    signal_type: FeedbackSignalType = FeedbackSignalType.DATA_COLLECTION

    severity: float = 0.0
    confidence: float = 0.0

    reason: list[str] = field(default_factory=list)
    recommended_action: str = ""

    source_prediction_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            self.signal_id = f"fs_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_actionable(self) -> bool:
        """是否需要行动。"""
        return self.severity >= 0.7 and self.confidence >= 0.7

    @property
    def priority(self) -> float:
        """综合优先级 = severity × 0.6 + confidence × 0.4。"""
        return self.severity * 0.6 + self.confidence * 0.4

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "creative_id": self.creative_id,
            "signal_type": self.signal_type.value,
            "severity": round(self.severity, 4),
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "source_prediction_id": self.source_prediction_id,
            "is_actionable": self.is_actionable,
            "priority": round(self.priority, 4),
            "created_at": self.created_at,
        }

    def to_evolution_opportunity(self) -> dict[str, Any]:
        """转换为 E11.9 EvolutionOpportunity 格式。"""
        return {
            "type": self.signal_type.value,
            "score": self.priority,
            "evidence": self.reason,
            "metrics": {
                "severity": self.severity,
                "confidence": self.confidence,
            },
            "metadata": {
                "signal_id": self.signal_id,
                "creative_id": self.creative_id,
                "recommended_action": self.recommended_action,
                "source": "e12.4_feedback",
                **self.metadata,
            },
        }

    def __repr__(self) -> str:
        return (
            f"RealityFeedbackSignal({self.signal_type.value}, "
            f"creative={self.creative_id}, "
            f"sev={self.severity:.2f}, conf={self.confidence:.2f})"
        )


# ── PredictionOutcome ──────────────────────────────────────


@dataclass
class PredictionOutcome:
    """预测结果与实际结果对比。

    用于闭环学习：记录预测值 vs 实际值，计算误差。

    Attributes:
        outcome_id:      结果 ID
        prediction_id:   关联的预测 ID
        creative_id:     创意 ID
        metric:          指标名称
        predicted_value: 预测值
        actual_value:    实际值
        horizon_days:    预测时间范围
        error:           绝对误差
        error_pct:       误差百分比
        is_success:      预测是否成功（误差 < 20%）
        evaluated_at:    评估时间
    """

    outcome_id: str = ""
    prediction_id: str = ""
    creative_id: str = ""
    metric: str = ""

    predicted_value: float = 0.0
    actual_value: float = 0.0
    horizon_days: int = 7

    error: float = 0.0
    error_pct: float = 0.0
    is_success: bool = False

    evaluated_at: str = ""

    def __post_init__(self) -> None:
        if not self.outcome_id:
            self.outcome_id = f"po_{uuid.uuid4().hex[:12]}"
        if not self.evaluated_at:
            self.evaluated_at = _now()
        if self.predicted_value != 0 or self.actual_value != 0:
            self.error = abs(self.actual_value - self.predicted_value)
            self.error_pct = (
                self.error / abs(self.predicted_value)
                if self.predicted_value != 0
                else 0.0
            )
            self.is_success = self.error_pct < 0.20

    @property
    def error_direction(self) -> str:
        """误差方向。

        - overestimate: 预测值 > 实际值（预测偏乐观）
        - underestimate: 预测值 < 实际值（预测偏悲观）
        """
        if self.predicted_value > self.actual_value:
            return "overestimate"
        elif self.predicted_value < self.actual_value:
            return "underestimate"
        return "exact"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "prediction_id": self.prediction_id,
            "creative_id": self.creative_id,
            "metric": self.metric,
            "predicted_value": round(self.predicted_value, 4),
            "actual_value": round(self.actual_value, 4),
            "horizon_days": self.horizon_days,
            "error": round(self.error, 4),
            "error_pct": round(self.error_pct, 4),
            "is_success": self.is_success,
            "error_direction": self.error_direction,
            "evaluated_at": self.evaluated_at,
        }

    def __repr__(self) -> str:
        return (
            f"PredictionOutcome({self.creative_id}, "
            f"{self.metric}: {self.predicted_value:.4f}→{self.actual_value:.4f}, "
            f"err={self.error_pct:.0%}, "
            f"success={self.is_success})"
        )


# ═══════════════════════════════════════════════════════════
# Phase 2: Experiment Models
# ═══════════════════════════════════════════════════════════


class MutationIntent(str, Enum):
    """突变意图 —— 告诉 Creative DNA Engine 改什么。"""

    REFRESH_HOOK = "refresh_hook"           # 刷新 Hook（开头 3 秒）
    VISUAL_VARIATION = "visual_variation"   # 视觉风格变化
    GAMEPLAY_CLARITY = "gameplay_clarity"   # 玩法展示优化
    OFFER_CHANGE = "offer_change"           # 付费/奖励调整
    FULL_REBUILD = "full_rebuild"           # 全面重建


# 反馈信号类型 → 突变意图映射
SIGNAL_TO_INTENT: dict[FeedbackSignalType, MutationIntent] = {
    FeedbackSignalType.FATIGUE_WARNING: MutationIntent.REFRESH_HOOK,
    FeedbackSignalType.ROAS_DECLINE: MutationIntent.OFFER_CHANGE,
    FeedbackSignalType.SCALE_OPPORTUNITY: MutationIntent.VISUAL_VARIATION,
    FeedbackSignalType.CREATIVE_REPLACEMENT: MutationIntent.FULL_REBUILD,
    FeedbackSignalType.DATA_COLLECTION: MutationIntent.REFRESH_HOOK,
}

# 突变意图 → 保留基因 + 修改基因
INTENT_DNA_CONSTRAINTS: dict[MutationIntent, dict[str, list[str]]] = {
    MutationIntent.REFRESH_HOOK: {
        "keep": ["gameplay", "monetization", "audience"],
        "change": ["hook", "visual_style"],
    },
    MutationIntent.VISUAL_VARIATION: {
        "keep": ["hook", "gameplay", "monetization"],
        "change": ["visual_style", "context"],
    },
    MutationIntent.GAMEPLAY_CLARITY: {
        "keep": ["hook", "visual_style", "monetization"],
        "change": ["gameplay", "psychology"],
    },
    MutationIntent.OFFER_CHANGE: {
        "keep": ["hook", "visual_style", "gameplay"],
        "change": ["monetization", "context"],
    },
    MutationIntent.FULL_REBUILD: {
        "keep": ["audience"],
        "change": ["hook", "visual_style", "gameplay", "monetization", "context", "psychology"],
    },
}

# 突变意图 → 建议生成数量
INTENT_GENERATION_COUNT: dict[MutationIntent, int] = {
    MutationIntent.REFRESH_HOOK: 20,
    MutationIntent.VISUAL_VARIATION: 15,
    MutationIntent.GAMEPLAY_CLARITY: 10,
    MutationIntent.OFFER_CHANGE: 10,
    MutationIntent.FULL_REBUILD: 30,
}


@dataclass
class MutationRequest:
    """突变请求 —— 发送给 Creative DNA Engine。

    将 RealityFeedbackSignal 转换为 Creative DNA Engine 可执行的
    突变指令，包含意图、DNA 约束、生成数量。

    Attributes:
        request_id:         请求 ID
        creative_id:        创意 ID
        intent:             突变意图
        signal_id:          来源信号 ID
        reason:             原因列表
        confidence:         置信度
        dna_constraints:    DNA 约束（keep + change 基因列表）
        generation_count:   建议生成变体数量
        created_at:         创建时间
    """

    request_id: str = ""
    creative_id: str = ""
    intent: MutationIntent = MutationIntent.REFRESH_HOOK
    signal_id: str = ""
    reason: list[str] = field(default_factory=list)
    confidence: float = 0.0
    dna_constraints: dict[str, list[str]] = field(default_factory=dict)
    generation_count: int = 10
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.request_id:
            self.request_id = f"mr_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def keep_genes(self) -> list[str]:
        return self.dna_constraints.get("keep", [])

    @property
    def change_genes(self) -> list[str]:
        return self.dna_constraints.get("change", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "creative_id": self.creative_id,
            "intent": self.intent.value,
            "signal_id": self.signal_id,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "dna_constraints": self.dna_constraints,
            "keep_genes": self.keep_genes,
            "change_genes": self.change_genes,
            "generation_count": self.generation_count,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"MutationRequest({self.creative_id}, "
            f"intent={self.intent.value}, "
            f"gen={self.generation_count}, "
            f"conf={self.confidence:.2f})"
        )


# ── Experiment Models ──────────────────────────────────────


class ExperimentStatus(str, Enum):
    """实验状态（6 阶段生命周期）。"""

    CREATED = "created"         # 已创建，等待生成
    GENERATING = "generating"   # 正在生成变体
    READY = "ready"             # 变体就绪，等待部署
    RUNNING = "running"         # 实验中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败


# 有效状态转换
VALID_EXPERIMENT_TRANSITIONS: dict[ExperimentStatus, list[ExperimentStatus]] = {
    ExperimentStatus.CREATED: [ExperimentStatus.GENERATING, ExperimentStatus.FAILED],
    ExperimentStatus.GENERATING: [ExperimentStatus.READY, ExperimentStatus.FAILED],
    ExperimentStatus.READY: [ExperimentStatus.RUNNING, ExperimentStatus.FAILED],
    ExperimentStatus.RUNNING: [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED],
    ExperimentStatus.COMPLETED: [],
    ExperimentStatus.FAILED: [],
}


@dataclass
class ExperimentRun:
    """实验运行记录。

    跟踪单个 Mutation 实验的完整生命周期。

    Attributes:
        experiment_id:       实验 ID
        creative_id:         原始创意 ID
        mutation_request_id: 关联的突变请求 ID
        variants:            变体 ID 列表
        status:              实验状态
        start_time:          开始时间
        end_time:            结束时间
        metrics:             当前指标
        metadata:            额外元数据
    """

    experiment_id: str = ""
    creative_id: str = ""
    mutation_request_id: str = ""

    variants: list[str] = field(default_factory=list)
    status: ExperimentStatus = ExperimentStatus.CREATED

    start_time: str = ""
    end_time: str = ""

    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.experiment_id:
            self.experiment_id = f"exp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_active(self) -> bool:
        return self.status in (
            ExperimentStatus.CREATED,
            ExperimentStatus.GENERATING,
            ExperimentStatus.READY,
            ExperimentStatus.RUNNING,
        )

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ExperimentStatus.COMPLETED,
            ExperimentStatus.FAILED,
        )

    @property
    def variant_count(self) -> int:
        return len(self.variants)

    def can_transition_to(self, target: ExperimentStatus) -> bool:
        valid = VALID_EXPERIMENT_TRANSITIONS.get(self.status, [])
        return target in valid

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "creative_id": self.creative_id,
            "mutation_request_id": self.mutation_request_id,
            "variants": self.variants,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metrics": self.metrics,
            "variant_count": self.variant_count,
            "is_active": self.is_active,
            "is_terminal": self.is_terminal,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"ExperimentRun({self.creative_id}, "
            f"status={self.status.value}, "
            f"variants={self.variant_count})"
        )


@dataclass
class ExperimentEvaluation:
    """实验结果评估。

    比较原始创意 vs 突变创意，找出赢家。

    Attributes:
        evaluation_id:       评估 ID
        experiment_id:       实验 ID
        creative_id:         原始创意 ID
        winner_id:           赢家变体 ID（None 表示无赢家）
        improvement_score:   改善幅度（-1 到 1，正数表示改善）
        metrics_delta:       指标变化 ({metric: delta})
        raw_metrics:         原始 vs 变体指标对比
        learning_signal:     学习信号
        confidence:          评估置信度
        evaluated_at:        评估时间
    """

    evaluation_id: str = ""
    experiment_id: str = ""
    creative_id: str = ""

    winner_id: str = ""
    improvement_score: float = 0.0
    metrics_delta: dict[str, float] = field(default_factory=dict)
    raw_metrics: dict[str, dict[str, float]] = field(default_factory=dict)

    learning_signal: str = ""
    confidence: float = 0.0
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        if not self.evaluation_id:
            self.evaluation_id = f"ev_{uuid.uuid4().hex[:12]}"
        if not self.evaluated_at:
            self.evaluated_at = _now()

    @property
    def has_winner(self) -> bool:
        return bool(self.winner_id) and self.improvement_score > 0

    @property
    def is_significant_improvement(self) -> bool:
        return self.improvement_score > 0.15

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "experiment_id": self.experiment_id,
            "creative_id": self.creative_id,
            "winner_id": self.winner_id,
            "improvement_score": round(self.improvement_score, 4),
            "metrics_delta": {k: round(v, 4) for k, v in self.metrics_delta.items()},
            "learning_signal": self.learning_signal,
            "confidence": round(self.confidence, 4),
            "has_winner": self.has_winner,
            "is_significant_improvement": self.is_significant_improvement,
            "evaluated_at": self.evaluated_at,
        }

    def __repr__(self) -> str:
        return (
            f"ExperimentEvaluation({self.creative_id}, "
            f"winner={self.winner_id or 'none'}, "
            f"improvement={self.improvement_score:+.2f})"
        )


@dataclass
class EvolutionLearningRecord:
    """进化学习记录 —— 完整闭环学习。

    记录从预测到实验结果的完整链路，用于跨实验学习。

    Attributes:
        record_id:            记录 ID
        prediction_id:        预测 ID
        mutation_request_id:  突变请求 ID
        experiment_id:        实验 ID
        prediction_accuracy:  预测准确率（0-1）
        mutation_success:     突变是否成功
        winner_dna:           赢家 DNA 特征
        insight:              学习洞察
        created_at:           创建时间
    """

    record_id: str = ""
    prediction_id: str = ""
    mutation_request_id: str = ""
    experiment_id: str = ""

    prediction_accuracy: float = 0.0
    mutation_success: bool = False

    winner_dna: dict[str, Any] = field(default_factory=dict)
    insight: str = ""

    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = f"elr_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "prediction_id": self.prediction_id,
            "mutation_request_id": self.mutation_request_id,
            "experiment_id": self.experiment_id,
            "prediction_accuracy": round(self.prediction_accuracy, 4),
            "mutation_success": self.mutation_success,
            "winner_dna": self.winner_dna,
            "insight": self.insight,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionLearningRecord(pred={self.prediction_accuracy:.0%}, "
            f"mutation_success={self.mutation_success}, "
            f"insight=\"{self.insight[:40]}...\")"
        )