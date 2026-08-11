"""E11.8.3 — Evolution Evaluation Models。

EvaluationStatus:          评估结果状态
MetricComparison:          进化前后指标对比
EvolutionEvaluation:       完整进化评估
EvolutionRecommendation:   后续行动建议
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvaluationStatus(str, Enum):
    """评估结果状态。"""
    SUCCESS = "success"          # 全面成功
    PARTIAL = "partial"          # 部分成功
    FAILED = "failed"            # 失败
    INCONCLUSIVE = "inconclusive"  # 数据不足，无法判断


class EvolutionRecommendation(str, Enum):
    """后续行动建议。"""
    KEEP = "keep"          # 保留当前基因组
    SCALE = "scale"        # 扩大投放
    ITERATE = "iterate"    # 继续迭代优化
    ROLLBACK = "rollback"  # 回滚到进化前
    RETIRE = "retire"      # 退役基因组


@dataclass
class MetricComparison:
    """进化前后单一指标对比。

    Attributes:
        metric:      指标名称
        before:      进化前值
        after:       进化后值
        delta:       变化量
        delta_pct:   变化百分比
        improvement: 是否改善
        significance: 显著性标记 (significant / marginal / none)
    """

    metric: str = ""
    before: float = 0.0
    after: float = 0.0
    delta: float = 0.0
    delta_pct: float = 0.0
    improvement: bool = False
    significance: str = "none"

    def __post_init__(self) -> None:
        if self.delta == 0.0 and self.before != 0.0:
            self.delta = self.after - self.before
        if self.delta_pct == 0.0 and self.before != 0.0:
            self.delta_pct = self.delta / abs(self.before)

    @property
    def is_significant(self) -> bool:
        return self.significance == "significant"

    @property
    def is_marginal(self) -> bool:
        return self.significance == "marginal"

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "before": self.before,
            "after": self.after,
            "delta": self.delta,
            "delta_pct": self.delta_pct,
            "improvement": self.improvement,
            "significance": self.significance,
        }

    def __repr__(self) -> str:
        direction = "+" if self.improvement else ""
        return (
            f"MetricComparison({self.metric}: "
            f"{self.before:.3f}→{self.after:.3f} "
            f"({direction}{self.delta_pct:.1%}))"
        )


@dataclass
class EvolutionEvaluation:
    """完整进化评估。

    Attributes:
        evaluation_id:   评估 ID
        strategy_id:     关联策略 ID
        status:          评估结果
        score:           综合评分 (0-100)
        improvements:    指标对比列表
        recommendation:  后续行动建议
        confidence:      置信度 (0-1)
        reason:          评估理由
        created_at:      创建时间
        metadata:        附加元数据
    """

    evaluation_id: str = ""
    strategy_id: str = ""
    status: EvaluationStatus = EvaluationStatus.INCONCLUSIVE
    score: float = 0.0
    improvements: list[MetricComparison] = field(default_factory=list)
    recommendation: EvolutionRecommendation = EvolutionRecommendation.KEEP
    confidence: float = 0.0
    reason: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evaluation_id:
            self.evaluation_id = f"eval_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_success(self) -> bool:
        return self.status == EvaluationStatus.SUCCESS

    @property
    def is_partial(self) -> bool:
        return self.status == EvaluationStatus.PARTIAL

    @property
    def is_failed(self) -> bool:
        return self.status == EvaluationStatus.FAILED

    @property
    def is_inconclusive(self) -> bool:
        return self.status == EvaluationStatus.INCONCLUSIVE

    @property
    def improved_count(self) -> int:
        return sum(1 for m in self.improvements if m.improvement)

    @property
    def degraded_count(self) -> int:
        return sum(1 for m in self.improvements if not m.improvement)

    @property
    def total_metrics(self) -> int:
        return len(self.improvements)

    @property
    def avg_improvement(self) -> float:
        if not self.improvements:
            return 0.0
        return sum(m.delta_pct for m in self.improvements) / len(self.improvements)

    @property
    def is_actionable(self) -> bool:
        """是否可执行后续动作。"""
        return self.recommendation in (
            EvolutionRecommendation.SCALE,
            EvolutionRecommendation.ITERATE,
            EvolutionRecommendation.ROLLBACK,
            EvolutionRecommendation.RETIRE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "score": self.score,
            "improvements": [m.to_dict() for m in self.improvements],
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionEvaluation({self.status.value}, "
            f"score={self.score:.1f}, "
            f"rec={self.recommendation.value}, "
            f"improved={self.improved_count}/{self.total_metrics})"
        )