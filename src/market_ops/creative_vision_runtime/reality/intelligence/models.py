"""E12.2 — Reality Intelligence Models。

定义 Reality Intelligence Layer 核心数据模型：

  InsightType:      洞察类型（6种）
  SeverityLevel:    严重程度（4级）
  RealityInsight:   核心输出（type + severity + confidence + evidence + recommendation）
  PerformanceInsight: 性能分析结果
  FatigueInsight:   创意疲劳检测结果
  AnomalyInsight:   异常检测结果
  TrendInsight:     趋势检测结果
  CombinedInsight:  多分析器融合结果
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


class InsightType(str, Enum):
    """洞察类型。"""

    CREATIVE_FATIGUE = "creative_fatigue"       # 创意疲劳
    PERFORMANCE_DROP = "performance_drop"       # 性能下降
    WINNING_PATTERN = "winning_pattern"         # 赢家模式
    MARKET_SHIFT = "market_shift"               # 市场变化
    SCALE_OPPORTUNITY = "scale_opportunity"     # 放量机会
    DATA_ANOMALY = "data_anomaly"               # 数据异常


class SeverityLevel(str, Enum):
    """严重程度。"""

    CRITICAL = "critical"   # 需要立即处理
    HIGH = "high"           # 需要尽快处理
    MEDIUM = "medium"       # 需要关注
    LOW = "low"             # 仅记录


# ── Core Insight ───────────────────────────────────────────


@dataclass
class RealityInsight:
    """E12.2 核心输出 —— 对现实的理解。

    这是 E12.2 的最终产物，包含：
      - 发生了什么（type, evidence）
      - 严重程度（severity）
      - 置信度（confidence）
      - 建议行动（recommended_action, target, priority）

    Attributes:
        insight_id:         洞察 ID
        type:               洞察类型
        severity:           严重程度
        confidence:         置信度（0-1）
        target:             目标对象（creative_id / genome_id）
        evidence:           证据列表
        recommended_action: 建议行动（MUTATE_HOOK / SCALE / PAUSE 等）
        priority:           优先级（0-1）
        metadata:           额外元数据
        source_snapshot_id: 来源快照 ID
        created_at:         创建时间
    """

    insight_id: str = ""
    type: InsightType = InsightType.PERFORMANCE_DROP
    severity: SeverityLevel = SeverityLevel.MEDIUM
    confidence: float = 0.0

    target: str = ""
    evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""
    priority: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)
    source_snapshot_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.insight_id:
            self.insight_id = f"ri_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    @property
    def is_actionable(self) -> bool:
        """是否需要行动。"""
        return self.severity in (
            SeverityLevel.CRITICAL,
            SeverityLevel.HIGH,
        ) and self.confidence >= 0.7

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "type": self.type.value,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 4),
            "target": self.target,
            "evidence": self.evidence,
            "recommended_action": self.recommended_action,
            "priority": round(self.priority, 4),
            "source_snapshot_id": self.source_snapshot_id,
            "is_actionable": self.is_actionable,
            "created_at": self.created_at,
        }

    def to_evolution_opportunity(self) -> dict[str, Any]:
        """转换为 E11.9 EvolutionOpportunity 格式。"""
        return {
            "type": self.type.value,
            "score": self.priority,
            "evidence": self.evidence,
            "metadata": {
                "insight_id": self.insight_id,
                "confidence": self.confidence,
                "severity": self.severity.value,
                "recommended_action": self.recommended_action,
                "target": self.target,
            },
        }

    def __repr__(self) -> str:
        return (
            f"RealityInsight({self.type.value}, "
            f"sev={self.severity.value}, "
            f"conf={self.confidence:.2f}, "
            f"pri={self.priority:.2f})"
        )


# ── Analyzer Outputs ───────────────────────────────────────


@dataclass
class PerformanceInsight:
    """Performance Analyzer 输出。

    检测单个 Campaign/Creative 的性能变化。

    Attributes:
        creative_id:         Creative/Campaign ID
        metric:              主要变化指标
        current_value:       当前值
        previous_value:      历史值
        change_pct:          变化百分比
        direction:           变化方向（+1 改善 / -1 恶化 / 0 持平）
        severity:            严重程度
        confidence:          置信度
        evidence:            证据
    """

    creative_id: str = ""
    metric: str = ""
    current_value: float = 0.0
    previous_value: float = 0.0
    change_pct: float = 0.0
    direction: int = 0  # +1=improved, -1=degraded, 0=stable
    severity: SeverityLevel = SeverityLevel.LOW
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "metric": self.metric,
            "current_value": round(self.current_value, 4),
            "previous_value": round(self.previous_value, 4),
            "change_pct": round(self.change_pct, 4),
            "direction": self.direction,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
        }

    def __repr__(self) -> str:
        return (
            f"PerformanceInsight({self.creative_id}, "
            f"{self.metric}: {self.change_pct:+.0%})"
        )


@dataclass
class FatigueInsight:
    """Creative Fatigue Detector 输出。

    检测创意是否疲劳。

    Attributes:
        creative_id:         Creative ID
        fatigue_score:       疲劳评分（0-1，越高越疲劳）
        ctr_decay:           CTR 衰减率
        roas_decay:          ROAS 衰减率
        frequency:           曝光频次
        days_since_launch:   上线天数
        evidence:            证据
        severity:            严重程度
        confidence:          置信度
    """

    creative_id: str = ""
    fatigue_score: float = 0.0
    ctr_decay: float = 0.0
    roas_decay: float = 0.0
    frequency: float = 0.0
    days_since_launch: int = 0
    evidence: list[str] = field(default_factory=list)
    severity: SeverityLevel = SeverityLevel.LOW
    confidence: float = 0.0

    @property
    def is_fatigued(self) -> bool:
        return self.fatigue_score >= 0.6

    @property
    def is_severely_fatigued(self) -> bool:
        return self.fatigue_score >= 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "fatigue_score": round(self.fatigue_score, 4),
            "ctr_decay": round(self.ctr_decay, 4),
            "roas_decay": round(self.roas_decay, 4),
            "frequency": round(self.frequency, 2),
            "days_since_launch": self.days_since_launch,
            "evidence": self.evidence,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 4),
        }

    def __repr__(self) -> str:
        return (
            f"FatigueInsight({self.creative_id}, "
            f"score={self.fatigue_score:.2f})"
        )


@dataclass
class AnomalyInsight:
    """Anomaly Detector 输出。

    检测数据异常（花费突变、收入异常等）。

    Attributes:
        campaign_id:         Campaign ID
        anomaly_type:        异常类型
        metric:              异常指标
        expected_value:      期望值
        actual_value:        实际值
        deviation_pct:       偏离百分比
        severity:            严重程度
        confidence:          置信度
        evidence:            证据
    """

    campaign_id: str = ""
    anomaly_type: str = ""
    metric: str = ""
    expected_value: float = 0.0
    actual_value: float = 0.0
    deviation_pct: float = 0.0
    severity: SeverityLevel = SeverityLevel.LOW
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

    @property
    def is_significant(self) -> bool:
        return abs(self.deviation_pct) >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "anomaly_type": self.anomaly_type,
            "metric": self.metric,
            "expected_value": round(self.expected_value, 2),
            "actual_value": round(self.actual_value, 2),
            "deviation_pct": round(self.deviation_pct, 4),
            "severity": self.severity.value,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
        }

    def __repr__(self) -> str:
        return (
            f"AnomalyInsight({self.campaign_id}, "
            f"{self.anomaly_type}: {self.deviation_pct:+.0%})"
        )


@dataclass
class TrendInsight:
    """Trend Detector 输出。

    检测市场趋势变化。

    Attributes:
        trend_type:         趋势类型
        metric:             趋势指标
        current_value:      当前值
        trend_direction:    趋势方向
        trend_strength:     趋势强度（0-1）
        confidence:         置信度
        evidence:           证据
    """

    trend_type: str = ""
    metric: str = ""
    current_value: float = 0.0
    trend_direction: int = 0  # +1=up, -1=down, 0=flat
    trend_strength: float = 0.0
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend_type": self.trend_type,
            "metric": self.metric,
            "current_value": round(self.current_value, 4),
            "trend_direction": self.trend_direction,
            "trend_strength": round(self.trend_strength, 4),
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
        }

    def __repr__(self) -> str:
        return (
            f"TrendInsight({self.trend_type}, "
            f"strength={self.trend_strength:.2f})"
        )


@dataclass
class CombinedInsight:
    """多分析器融合结果。

    InsightEngine 的输出：将多个分析器的结果融合为
    一个综合洞察。

    Attributes:
        combined_id:        融合结果 ID
        insights:           子洞察列表
        primary_type:       主要洞察类型
        aggregated_confidence: 聚合置信度
        aggregated_priority:  聚合优先级
        severity:           严重程度
        recommended_action: 建议行动
        evidence:           所有证据
    """

    combined_id: str = ""
    insights: list[RealityInsight] = field(default_factory=list)
    primary_type: InsightType = InsightType.PERFORMANCE_DROP
    aggregated_confidence: float = 0.0
    aggregated_priority: float = 0.0
    severity: SeverityLevel = SeverityLevel.MEDIUM
    recommended_action: str = ""
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.combined_id:
            self.combined_id = f"ci_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "combined_id": self.combined_id,
            "primary_type": self.primary_type.value,
            "aggregated_confidence": round(self.aggregated_confidence, 4),
            "aggregated_priority": round(self.aggregated_priority, 4),
            "severity": self.severity.value,
            "recommended_action": self.recommended_action,
            "evidence": self.evidence,
            "insight_count": len(self.insights),
        }

    def __repr__(self) -> str:
        return (
            f"CombinedInsight({self.primary_type.value}, "
            f"conf={self.aggregated_confidence:.2f}, "
            f"insights={len(self.insights)})"
        )