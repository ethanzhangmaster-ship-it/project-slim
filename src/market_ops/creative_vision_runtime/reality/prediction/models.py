"""E12.3 — Prediction Models。

定义 Reality Prediction Layer 核心数据模型：

Phase 1:
  PredictionType:          预测类型（4种）
  RiskLevel:               风险等级（4级）
  RealityPrediction:       核心输出
  RealityHistoryPoint:     历史数据点

Phase 2:
  CreativeLifecycleStage:  创意生命周期阶段（7阶段）
  LifecyclePrediction:     生命周期预测
  DecayPrediction:         衰减速度预测
  PredictionConfidence:    预测置信度
  PredictionExplanation:   预测解释
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


class PredictionType(str, Enum):
    """预测类型。"""

    CREATIVE_FATIGUE_RISK = "creative_fatigue_risk"   # 创意疲劳风险
    ROAS_DECAY_RISK = "roas_decay_risk"               # ROAS 衰减风险
    SCALE_OPPORTUNITY = "scale_opportunity"            # 放量机会
    BUDGET_BURN_RISK = "budget_burn_risk"              # 预算燃烧风险


class RiskLevel(str, Enum):
    """风险等级。"""

    LOW = "low"           # 低风险，持续监控
    MEDIUM = "medium"     # 中风险，准备预案
    HIGH = "high"         # 高风险，尽快行动
    CRITICAL = "critical" # 极高风险，立即行动


# ── RealityHistoryPoint ────────────────────────────────────


@dataclass
class RealityHistoryPoint:
    """单个时间点的现实数据快照。

    E12.3 的唯一输入来源。由 E12.1 RealitySnapshot 历史数据
    转换而来，不直接读取 Meta/Adjust API。

    Attributes:
        date:           数据日期
        creative_id:    Creative ID
        ctr:            点击率（0-1）
        cvr:            转化率（0-1）
        roas:           ROAS（如 0.8 表示 80%）
        spend:          花费（USD）
        revenue:        收入（USD）
        frequency:      曝光频次
        impressions:    展示量
        installs:       安装量
    """

    date: str = ""
    creative_id: str = ""

    ctr: float = 0.0
    cvr: float = 0.0
    roas: float = 0.0
    cpi: float = 0.0
    spend: float = 0.0
    revenue: float = 0.0
    frequency: float = 0.0
    impressions: int = 0
    installs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "creative_id": self.creative_id,
            "ctr": round(self.ctr, 4),
            "cvr": round(self.cvr, 4),
            "cpi": round(self.cpi, 2),
            "roas": round(self.roas, 4),
            "spend": round(self.spend, 2),
            "revenue": round(self.revenue, 2),
            "frequency": round(self.frequency, 2),
            "impressions": self.impressions,
            "installs": self.installs,
        }

    def __repr__(self) -> str:
        return (
            f"RealityHistoryPoint({self.date}, "
            f"creative={self.creative_id}, "
            f"ctr={self.ctr:.4f}, roas={self.roas:.4f})"
        )


# ── RealityPrediction ──────────────────────────────────────


@dataclass
class RealityPrediction:
    """E12.3 核心输出 —— 未来预测。

    预测未来 N 天的趋势和风险，为 E11 提供提前决策依据。

    Examples:
        >>> RealityPrediction(
        ...     prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
        ...     current_value=0.65,
        ...     predicted_value=0.91,
        ...     horizon_days=7,
        ...     probability=0.87,
        ...     risk_level=RiskLevel.HIGH,
        ...     recommended_action="MUTATE_HOOK",
        ... )

    Attributes:
        prediction_id:      预测 ID
        prediction_type:    预测类型
        target_id:          目标对象 ID（creative_id / campaign_id）
        current_value:      当前值（0-1）
        predicted_value:    预测值（0-1）
        horizon_days:       预测时间范围（天）
        probability:        预测概率（0-1）
        risk_level:         风险等级
        evidence:           证据列表
        recommended_action: 建议行动
        metadata:           额外元数据
        created_at:         创建时间
    """

    prediction_id: str = ""
    prediction_type: PredictionType = PredictionType.CREATIVE_FATIGUE_RISK
    target_id: str = ""

    current_value: float = 0.0
    predicted_value: float = 0.0
    horizon_days: int = 7

    probability: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW

    evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.prediction_id:
            self.prediction_id = f"rp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_actionable(self) -> bool:
        """是否需要行动。

        CRITICAL 或 HIGH 风险 + probability >= 0.7 才触发行动。
        """
        return self.risk_level in (
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
        ) and self.probability >= 0.7

    @property
    def delta(self) -> float:
        """预测变化量（predicted - current）。"""
        return self.predicted_value - self.current_value

    @property
    def delta_pct(self) -> float:
        """预测变化百分比。"""
        if self.current_value == 0:
            return 0.0
        return self.delta / self.current_value

    def _risk_level_from_probability(self) -> None:
        """根据 probability 自动设置 risk_level（如果未设置）。"""
        if self.probability >= 0.9:
            self.risk_level = RiskLevel.CRITICAL
        elif self.probability >= 0.75:
            self.risk_level = RiskLevel.HIGH
        elif self.probability >= 0.5:
            self.risk_level = RiskLevel.MEDIUM
        else:
            self.risk_level = RiskLevel.LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "prediction_type": self.prediction_type.value,
            "target_id": self.target_id,
            "current_value": round(self.current_value, 4),
            "predicted_value": round(self.predicted_value, 4),
            "horizon_days": self.horizon_days,
            "probability": round(self.probability, 4),
            "risk_level": self.risk_level.value,
            "evidence": self.evidence,
            "recommended_action": self.recommended_action,
            "is_actionable": self.is_actionable,
            "created_at": self.created_at,
        }

    def to_evolution_opportunity(self) -> dict[str, Any]:
        """转换为 E11.9 EvolutionOpportunity 格式。"""
        return {
            "type": self.prediction_type.value,
            "score": self.probability,
            "evidence": self.evidence,
            "metadata": {
                "prediction_id": self.prediction_id,
                "target_id": self.target_id,
                "current_value": self.current_value,
                "predicted_value": self.predicted_value,
                "horizon_days": self.horizon_days,
                "risk_level": self.risk_level.value,
                "recommended_action": self.recommended_action,
            },
        }

    def __repr__(self) -> str:
        return (
            f"RealityPrediction({self.prediction_type.value}, "
            f"target={self.target_id}, "
            f"{self.current_value:.2f}→{self.predicted_value:.2f}, "
            f"prob={self.probability:.2f}, "
            f"risk={self.risk_level.value})"
        )


# ═══════════════════════════════════════════════════════════
# Phase 2: Advanced Prediction Models
# ═══════════════════════════════════════════════════════════


class CreativeLifecycleStage(str, Enum):
    """创意生命周期阶段（7 阶段）。

    Launch → Learning → Peak → Stable → FatigueWarning → Fatigued → Dead
    """

    LAUNCH = "launch"                 # 刚上线，数据不足
    LEARNING = "learning"             # 学习期，CTR 波动
    PEAK = "peak"                     # 峰值期，CTR/ROAS 最高
    STABLE = "stable"                 # 稳定期，指标平稳
    FATIGUE_WARNING = "fatigue_warning"  # 疲劳预警，指标开始下降
    FATIGUED = "fatigued"             # 已疲劳，CTR/ROAS 显著下降
    DEAD = "dead"                     # 死亡，ROAS 不可接受


# 生命周期阶段 → 严重程度映射
LIFECYCLE_SEVERITY: dict[CreativeLifecycleStage, int] = {
    CreativeLifecycleStage.LAUNCH: 0,
    CreativeLifecycleStage.LEARNING: 0,
    CreativeLifecycleStage.PEAK: 0,
    CreativeLifecycleStage.STABLE: 1,
    CreativeLifecycleStage.FATIGUE_WARNING: 2,
    CreativeLifecycleStage.FATIGUED: 3,
    CreativeLifecycleStage.DEAD: 4,
}

# 有效生命周期阶段转换
VALID_LIFECYCLE_TRANSITIONS: dict[CreativeLifecycleStage, list[CreativeLifecycleStage]] = {
    CreativeLifecycleStage.LAUNCH: [
        CreativeLifecycleStage.LEARNING,
        CreativeLifecycleStage.PEAK,
    ],
    CreativeLifecycleStage.LEARNING: [
        CreativeLifecycleStage.PEAK,
        CreativeLifecycleStage.FATIGUE_WARNING,
    ],
    CreativeLifecycleStage.PEAK: [
        CreativeLifecycleStage.STABLE,
        CreativeLifecycleStage.FATIGUE_WARNING,
    ],
    CreativeLifecycleStage.STABLE: [
        CreativeLifecycleStage.FATIGUE_WARNING,
        CreativeLifecycleStage.PEAK,  # 可能通过 mutation 恢复
    ],
    CreativeLifecycleStage.FATIGUE_WARNING: [
        CreativeLifecycleStage.FATIGUED,
        CreativeLifecycleStage.STABLE,  # 可能通过 mutation 恢复
    ],
    CreativeLifecycleStage.FATIGUED: [
        CreativeLifecycleStage.DEAD,
        CreativeLifecycleStage.FATIGUE_WARNING,  # 可能通过 mutation 恢复
    ],
    CreativeLifecycleStage.DEAD: [
        CreativeLifecycleStage.LAUNCH,  # 重新生成 → 重启
    ],
}


@dataclass
class LifecyclePrediction:
    """创意生命周期预测。

    预测创意当前处于哪个生命周期阶段，以及何时会过渡到下一个阶段。

    Examples:
        >>> LifecyclePrediction(
        ...     creative_id="creative_001",
        ...     current_stage=CreativeLifecycleStage.STABLE,
        ...     predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
        ...     days_to_transition=8,
        ...     confidence=0.87,
        ... )

    Attributes:
        creative_id:         创意 ID
        current_stage:       当前生命周期阶段
        predicted_stage:     预测的下一个阶段
        days_to_transition:  距离过渡的天数
        confidence:          置信度（0-1）
        stage_scores:        各阶段得分（用于诊断）
        evidence:            证据列表
        recommended_action:  建议行动
        created_at:          创建时间
    """

    prediction_id: str = ""
    creative_id: str = ""

    current_stage: CreativeLifecycleStage = CreativeLifecycleStage.LAUNCH
    predicted_stage: CreativeLifecycleStage = CreativeLifecycleStage.LAUNCH
    days_to_transition: int = -1  # -1 表示无法预测

    confidence: float = 0.0

    stage_scores: dict[str, float] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""

    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.prediction_id:
            self.prediction_id = f"lp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_transitioning_soon(self) -> bool:
        """是否即将过渡（7 天内）。"""
        return 0 < self.days_to_transition <= 7

    @property
    def is_degrading(self) -> bool:
        """是否正在退化。"""
        return LIFECYCLE_SEVERITY.get(
            self.predicted_stage, 0
        ) > LIFECYCLE_SEVERITY.get(self.current_stage, 0)

    @property
    def is_improving(self) -> bool:
        """是否正在改善。"""
        return LIFECYCLE_SEVERITY.get(
            self.predicted_stage, 0
        ) < LIFECYCLE_SEVERITY.get(self.current_stage, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "creative_id": self.creative_id,
            "current_stage": self.current_stage.value,
            "predicted_stage": self.predicted_stage.value,
            "days_to_transition": self.days_to_transition,
            "confidence": round(self.confidence, 4),
            "stage_scores": {
                k: round(v, 4) for k, v in self.stage_scores.items()
            },
            "evidence": self.evidence,
            "recommended_action": self.recommended_action,
            "is_transitioning_soon": self.is_transitioning_soon,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"LifecyclePrediction({self.creative_id}, "
            f"{self.current_stage.value}→{self.predicted_stage.value}, "
            f"days={self.days_to_transition}, "
            f"conf={self.confidence:.2f})"
        )


@dataclass
class DecayPrediction:
    """单指标衰减速度预测。

    预测特定指标（CTR/ROAS/CVR/CPI）的衰减速度，
    用于精确量化创意退化趋势。

    Examples:
        >>> DecayPrediction(
        ...     creative_id="creative_001",
        ...     metric="ctr",
        ...     velocity=-0.0005,
        ...     current_value=0.025,
        ...     predicted_value=0.0215,
        ...     horizon_days=7,
        ... )

    Attributes:
        creative_id:         创意 ID
        metric:              指标名称（ctr/roas/cvr/cpi）
        velocity:            衰减速度（每天变化量，负值表示下降）
        current_value:       当前值
        predicted_value:     预测值
        horizon_days:        预测时间范围
        confidence:          置信度
        is_accelerating:     是否加速衰减
        evidence:            证据
    """

    prediction_id: str = ""
    creative_id: str = ""
    metric: str = ""

    velocity: float = 0.0
    current_value: float = 0.0
    predicted_value: float = 0.0
    horizon_days: int = 7

    confidence: float = 0.0
    is_accelerating: bool = False

    evidence: list[str] = field(default_factory=list)

    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.prediction_id:
            self.prediction_id = f"dp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def change_pct(self) -> float:
        """预测变化百分比。"""
        if self.current_value == 0:
            return 0.0
        return (self.predicted_value - self.current_value) / self.current_value

    @property
    def is_declining(self) -> bool:
        """是否在下降。"""
        return self.velocity < 0

    @property
    def decline_severity(self) -> str:
        """下降严重程度。"""
        if self.velocity >= 0:
            return "none"
        abs_v = abs(self.velocity)
        if abs_v > 0.005:
            return "critical"
        elif abs_v > 0.002:
            return "high"
        elif abs_v > 0.001:
            return "medium"
        return "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "creative_id": self.creative_id,
            "metric": self.metric,
            "velocity": round(self.velocity, 6),
            "current_value": round(self.current_value, 4),
            "predicted_value": round(self.predicted_value, 4),
            "horizon_days": self.horizon_days,
            "confidence": round(self.confidence, 4),
            "is_accelerating": self.is_accelerating,
            "change_pct": round(self.change_pct, 4),
            "evidence": self.evidence,
        }

    def __repr__(self) -> str:
        return (
            f"DecayPrediction({self.creative_id}, "
            f"{self.metric}: {self.current_value:.4f}→{self.predicted_value:.4f}, "
            f"v={self.velocity:.4f}/day)"
        )


@dataclass
class PredictionConfidence:
    """预测置信度评分。

    评估预测的可信程度，防止低质量预测触发 E11 误操作。

    confidence = data_volume × 0.35 + trend_consistency × 0.45 + metric_stability × 0.20

    Attributes:
        score:              综合置信度（0-1）
        data_volume:        数据量得分（install × days）
        trend_consistency:  趋势一致性（R²）
        metric_stability:   指标稳定性
        is_reliable:        是否可靠（score >= 0.7）
        is_highly_reliable: 是否高度可靠（score >= 0.85）
        breakdown:          各项得分明细
    """

    prediction_id: str = ""
    score: float = 0.0
    data_volume: float = 0.0
    trend_consistency: float = 0.0
    metric_stability: float = 0.0
    is_reliable: bool = False
    is_highly_reliable: bool = False
    breakdown: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.prediction_id:
            self.prediction_id = f"pc_{uuid.uuid4().hex[:12]}"
        self.is_reliable = self.score >= 0.7
        self.is_highly_reliable = self.score >= 0.85

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "score": round(self.score, 4),
            "data_volume": round(self.data_volume, 4),
            "trend_consistency": round(self.trend_consistency, 4),
            "metric_stability": round(self.metric_stability, 4),
            "is_reliable": self.is_reliable,
            "is_highly_reliable": self.is_highly_reliable,
            "breakdown": {k: round(v, 4) for k, v in self.breakdown.items()},
        }

    def __repr__(self) -> str:
        return (
            f"PredictionConfidence(score={self.score:.2f}, "
            f"reliable={self.is_reliable})"
        )


@dataclass
class PredictionExplanation:
    """预测解释。

    为每个 RealityPrediction 生成人类可读的解释，
    说明为什么系统做出这个预测，以及建议的行动。

    Attributes:
        prediction_id:      关联的预测 ID
        creative_id:        创意 ID
        summary:            一句话总结
        reasons:            原因列表
        similar_cases:      类似案例参考
        recommended_action: 建议行动
        action_detail:      行动详情
        urgency:            紧急程度
    """

    prediction_id: str = ""
    creative_id: str = ""
    summary: str = ""
    reasons: list[str] = field(default_factory=list)
    similar_cases: list[str] = field(default_factory=list)
    recommended_action: str = ""
    action_detail: str = ""
    urgency: str = ""

    explanation_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.explanation_id:
            self.explanation_id = f"pe_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "explanation_id": self.explanation_id,
            "prediction_id": self.prediction_id,
            "creative_id": self.creative_id,
            "summary": self.summary,
            "reasons": self.reasons,
            "similar_cases": self.similar_cases,
            "recommended_action": self.recommended_action,
            "action_detail": self.action_detail,
            "urgency": self.urgency,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"PredictionExplanation({self.creative_id}, "
            f"\"{self.summary[:50]}...\")"
        )