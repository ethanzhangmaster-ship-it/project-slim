"""E13.7.7.3 Adaptive Confidence Models — 自适应置信度数据模型.

Day 7.7.3:
  定义 AdaptiveConfidenceEngine 的输入输出协议，
  将多个静态 confidence 统一升级为自适应 confidence。

核心模型:
  1. ConfidenceRecord       — 单次置信度预测记录 (用于追踪历史准确率)
  2. AdaptiveConfidenceResult — 自适应置信度计算结果
  3. ConfidenceDimension    — 置信度维度枚举

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 可序列化 (to_dict)，支持审计
  - 不修改现有 confidence 模块

用法:
  from growth_runtime.intelligence.learning.models.adaptive_confidence_models import (
      ConfidenceRecord,
      AdaptiveConfidenceResult,
      ConfidenceDimension,
  )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# ConfidenceDimension
# ═══════════════════════════════════════════════════════════════


class ConfidenceDimension(str, Enum):
    """置信度维度 — 自适应置信度的组成因子.

    | 维度                    | 含义                           | 数据来源              |
    |------------------------|-------------------------------|----------------------|
    | HISTORICAL_ACCURACY    | 历史预测准确率                    | ConfidenceRecord 历史 |
    | LEARNING_EFFECTIVENESS | 学习系统当前有效性                 | LearningEffectiveness |
    | CONTEXT_SIMILARITY     | 当前上下文与训练数据的相似度          | 上下文比较             |
    | FRESHNESS              | 支撑数据的时效性                   | 时间戳分析             |
    | BASE_CONFIDENCE        | 原始置信度 (来自上游模块)            | Enhancer/Predictor   |
    """
    HISTORICAL_ACCURACY = "historical_accuracy"
    LEARNING_EFFECTIVENESS = "learning_effectiveness"
    CONTEXT_SIMILARITY = "context_similarity"
    FRESHNESS = "freshness"
    BASE_CONFIDENCE = "base_confidence"


# ═══════════════════════════════════════════════════════════════
# ConfidenceRecord
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConfidenceRecord:
    """置信度预测记录 — 追踪一次置信度预测及其实际结果.

    用于计算 historical_accuracy:
      accuracy = 正确预测数 / 总预测数

    "正确预测"的定义:
      - 高置信度 (>= 0.70) + 实际成功 → 正确
      - 高置信度 (>= 0.70) + 实际失败 → 错误
      - 低置信度 (< 0.50) + 实际成功 → 中性 (保守预测)
      - 低置信度 (< 0.50) + 实际失败 → 正确

    Attributes:
        record_id: 记录唯一标识
        source: 置信度来源 (enhancer/predictor/confidence_engine)
        context_key: 上下文标识 (用于相似度计算)
        base_confidence: 原始置信度 (调整前)
        adjusted_confidence: 自适应置信度 (调整后)
        dimensions: 各维度因子值
        actual_outcome: 实际结果 (success/failure/partial)
        is_accurate: 预测是否准确
        created_at: 创建时间
        metadata: 扩展元数据
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    context_key: str = ""
    base_confidence: float = 0.0
    adjusted_confidence: float = 0.0
    dimensions: dict[str, float] = field(default_factory=dict)
    actual_outcome: str = "pending"
    is_accurate: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_resolved(self) -> bool:
        """是否已有实际结果."""
        return self.actual_outcome != "pending"

    @property
    def confidence_delta(self) -> float:
        """自适应调整量."""
        return round(self.adjusted_confidence - self.base_confidence, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source": self.source,
            "context_key": self.context_key,
            "base_confidence": round(self.base_confidence, 4),
            "adjusted_confidence": round(self.adjusted_confidence, 4),
            "dimensions": {k: round(v, 4) for k, v in self.dimensions.items()},
            "actual_outcome": self.actual_outcome,
            "is_accurate": self.is_accurate,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# AdaptiveConfidenceResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class AdaptiveConfidenceResult:
    """自适应置信度计算结果.

    包含:
      - 调整后的最终置信度
      - 各维度因子分解
      - 调整原因说明
      - 原始置信度 (用于对比)

    Attributes:
        result_id: 结果唯一标识
        base_confidence: 原始置信度 (上游模块输出)
        adjusted_confidence: 自适应调整后的置信度
        adjustment_factor: 综合调整因子 (adjusted / base)
        dimensions: 各维度分解
        dimension_weights: 各维度权重
        adjustments: 调整说明列表
        confidence_level: 置信度等级 (high/medium/low/insufficient)
        warnings: 警告信息
        created_at: 创建时间
        metadata: 扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    base_confidence: float = 0.0
    adjusted_confidence: float = 0.0
    adjustment_factor: float = 1.0
    dimensions: dict[str, float] = field(default_factory=dict)
    dimension_weights: dict[str, float] = field(default_factory=dict)
    adjustments: list[str] = field(default_factory=list)
    confidence_level: str = "insufficient"
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_adjusted(self) -> bool:
        """是否发生了调整."""
        return abs(self.adjusted_confidence - self.base_confidence) > 0.001

    @property
    def is_downgraded(self) -> bool:
        """是否被降级."""
        return self.adjusted_confidence < self.base_confidence - 0.001

    @property
    def is_upgraded(self) -> bool:
        """是否被升级."""
        return self.adjusted_confidence > self.base_confidence + 0.001

    @property
    def is_reliable(self) -> bool:
        """是否可靠 (HIGH 或 MEDIUM)."""
        return self.confidence_level in ("high", "medium")

    @property
    def dominant_factor(self) -> tuple[str, float]:
        """影响最大的维度."""
        if not self.dimensions:
            return ("base_confidence", self.base_confidence)
        # 排除 base_confidence，找偏离 1.0 最大的因子
        deviations = {
            k: abs(v - 1.0)
            for k, v in self.dimensions.items()
            if k != ConfidenceDimension.BASE_CONFIDENCE.value
        }
        if not deviations:
            return ("base_confidence", self.base_confidence)
        # 所有偏离为 0 → 无主导因子，返回 base_confidence
        if all(v == 0.0 for v in deviations.values()):
            return ("base_confidence", self.base_confidence)
        worst = max(deviations, key=deviations.get)
        return (worst, self.dimensions[worst])

    @property
    def confidence_level_score(self) -> float:
        """置信度等级对应的数值."""
        mapping = {"high": 0.85, "medium": 0.55, "low": 0.30, "insufficient": 0.10}
        return mapping.get(self.confidence_level, 0.0)

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "base_confidence": round(self.base_confidence, 4),
            "adjusted_confidence": round(self.adjusted_confidence, 4),
            "adjustment_factor": round(self.adjustment_factor, 4),
            "dimensions": {k: round(v, 4) for k, v in self.dimensions.items()},
            "dimension_weights": {k: round(v, 4) for k, v in self.dimension_weights.items()},
            "adjustments": self.adjustments,
            "confidence_level": self.confidence_level,
            "warnings": self.warnings,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "ConfidenceDimension",
    "ConfidenceRecord",
    "AdaptiveConfidenceResult",
]