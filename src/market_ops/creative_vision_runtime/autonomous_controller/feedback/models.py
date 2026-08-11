"""E11.5.3 — Feedback Models。

PerformanceSignal:  实验性能数据
FitnessScore:       Genome 适应度评分
LearningDirection:  学习方向枚举
LearningSignal:     反馈给 Evolution 的学习信号
EvolutionFeedback:  统一反馈输出
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningDirection(str, Enum):
    """学习方向。"""
    IMPROVE = "improve"  # 改进（保留并优化）
    KEEP = "keep"        # 保持（无需变动）
    MUTATE = "mutate"    # 突变（需要改变）
    RETIRE = "retire"    # 退役（放弃该基因组）


@dataclass
class PerformanceSignal:
    """实验性能数据。

    表示一个 Creative Genome 在投放实验中的表现。

    Attributes:
        signal_id:   信号 ID
        genome_id:   Genome ID
        creative_id: Creative ID
        impressions: 曝光数
        clicks:      点击数
        installs:    安装数
        revenue:     收入
        spend:       花费
        ctr:         点击率 (clicks/impressions)
        cvr:         转化率 (installs/clicks)
        roi:         ROI (revenue/spend)
        period:      统计周期 (7d/14d/30d)
        created_at:  创建时间
    """

    signal_id: str = ""
    genome_id: str = ""
    creative_id: str = ""

    impressions: int = 0
    clicks: int = 0
    installs: int = 0

    revenue: float = 0.0
    spend: float = 0.0

    ctr: float = 0.0
    cvr: float = 0.0
    roi: float = 0.0

    period: str = "7d"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            self.signal_id = f"ps_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def has_sufficient_data(self) -> bool:
        """是否有足够数据用于评估。"""
        return self.impressions >= 100 and self.clicks > 0 and self.spend > 0

    @property
    def is_positive_roi(self) -> bool:
        return self.roi >= 1.0

    @property
    def is_high_roi(self) -> bool:
        return self.roi >= 1.5

    @property
    def cost_per_install(self) -> float:
        if self.installs == 0:
            return float("inf")
        return self.spend / self.installs

    @property
    def revenue_per_install(self) -> float:
        if self.installs == 0:
            return 0.0
        return self.revenue / self.installs

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "genome_id": self.genome_id,
            "creative_id": self.creative_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "revenue": self.revenue,
            "spend": self.spend,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "roi": self.roi,
            "period": self.period,
            "has_sufficient_data": self.has_sufficient_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PerformanceSignal:
        return cls(
            signal_id=data.get("signal_id", ""),
            genome_id=data.get("genome_id", ""),
            creative_id=data.get("creative_id", ""),
            impressions=int(data.get("impressions", 0)),
            clicks=int(data.get("clicks", 0)),
            installs=int(data.get("installs", 0)),
            revenue=float(data.get("revenue", 0.0)),
            spend=float(data.get("spend", 0.0)),
            ctr=float(data.get("ctr", 0.0)),
            cvr=float(data.get("cvr", 0.0)),
            roi=float(data.get("roi", 0.0)),
            period=data.get("period", "7d"),
        )

    def __repr__(self) -> str:
        return (
            f"PerformanceSignal({self.genome_id}, "
            f"ROI={self.roi:.2f}, "
            f"CTR={self.ctr:.4f})"
        )


@dataclass
class FitnessScore:
    """Genome 适应度评分。

    Attributes:
        genome_id:       Genome ID
        overall_score:   综合评分 (0-100)
        roi_score:       ROI 评分 (0-100)
        ctr_score:       CTR 评分 (0-100)
        cvr_score:       CVR 评分 (0-100)
        revenue_score:   收入评分 (0-100)
        rank:            排名
        evaluated_at:    评估时间
    """

    genome_id: str = ""
    overall_score: float = 0.0
    roi_score: float = 0.0
    ctr_score: float = 0.0
    cvr_score: float = 0.0
    revenue_score: float = 0.0
    rank: int = 0
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        if not self.evaluated_at:
            self.evaluated_at = _now()

    @property
    def is_winner(self) -> bool:
        return self.overall_score >= 80

    @property
    def is_average(self) -> bool:
        return 50 <= self.overall_score < 80

    @property
    def is_failed(self) -> bool:
        return self.overall_score < 50

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "overall_score": self.overall_score,
            "roi_score": self.roi_score,
            "ctr_score": self.ctr_score,
            "cvr_score": self.cvr_score,
            "revenue_score": self.revenue_score,
            "rank": self.rank,
        }

    def __repr__(self) -> str:
        return (
            f"FitnessScore({self.genome_id}, "
            f"overall={self.overall_score}, "
            f"rank=#{self.rank})"
        )


@dataclass
class LearningSignal:
    """反馈给 Evolution 的学习信号。

    Attributes:
        signal_id:             信号 ID
        genome_id:             Genome ID
        direction:             学习方向 (IMPROVE/KEEP/MUTATE/RETIRE)
        confidence:            置信度
        insights:              洞察列表
        recommended_mutations: 推荐突变列表
        consecutive_failures:  连续失败次数
        created_at:            创建时间
    """

    signal_id: str = ""
    genome_id: str = ""
    direction: LearningDirection = LearningDirection.KEEP
    confidence: float = 0.0
    insights: list[str] = field(default_factory=list)
    recommended_mutations: list[str] = field(default_factory=list)
    consecutive_failures: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            self.signal_id = f"ls_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def should_evolve(self) -> bool:
        return self.direction == LearningDirection.MUTATE

    @property
    def should_retire(self) -> bool:
        return self.direction == LearningDirection.RETIRE

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "genome_id": self.genome_id,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "insights": self.insights,
            "recommended_mutations": self.recommended_mutations,
            "consecutive_failures": self.consecutive_failures,
        }

    def __repr__(self) -> str:
        return (
            f"LearningSignal({self.genome_id}, "
            f"dir={self.direction.value}, "
            f"conf={self.confidence:.2f})"
        )


@dataclass
class EvolutionFeedback:
    """统一反馈输出。

    Attributes:
        feedback_id:     反馈 ID
        genome_id:       Genome ID
        fitness:         FitnessScore
        learning_signal: LearningSignal
        created_at:      创建时间
    """

    feedback_id: str = ""
    genome_id: str = ""
    fitness: FitnessScore | None = None
    learning_signal: LearningSignal | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.feedback_id:
            self.feedback_id = f"ef_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_winner(self) -> bool:
        return self.fitness is not None and self.fitness.is_winner

    @property
    def needs_evolution(self) -> bool:
        if self.learning_signal is None:
            return False
        return self.learning_signal.direction in (
            LearningDirection.MUTATE,
            LearningDirection.IMPROVE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "genome_id": self.genome_id,
            "fitness": self.fitness.to_dict() if self.fitness else None,
            "learning_signal": self.learning_signal.to_dict() if self.learning_signal else None,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionFeedback({self.genome_id}, "
            f"fitness={self.fitness.overall_score if self.fitness else 'N/A'})"
        )