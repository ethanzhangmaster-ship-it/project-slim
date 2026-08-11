"""E14.3.2 UA Analyzer — UA 指标分析与异常检测.

将对原始 UA 数据进行分析，输出结构化分析结果:

  输入: UAMetrics (spend, revenue, roas, cpi, ctr, cvr, ltv, fatigue, ...)
  输出: UAAnalysisResult (anomalies, trends, health_score, insights)

设计原则:
  - 指标异常检测基于阈值规则
  - 趋势分析基于历史对比
  - 健康评分综合多维度
  - 所有结果可解释
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


class MetricStatus(str, Enum):
    """指标状态."""
    HEALTHY = "healthy"          # 正常
    WARNING = "warning"          # 警告
    CRITICAL = "critical"        # 严重
    IMPROVING = "improving"      # 改善中
    DETERIORATING = "deteriorating"  # 恶化中


@dataclass
class UAMetrics:
    """UA 指标快照.

    Attributes:
        product_id: 产品 ID
        campaign_id: 广告系列 ID
        spend: 花费 (USD)
        revenue: 收入 (USD)
        roas: 广告支出回报率
        cpi: 单次安装成本
        ctr: 点击率
        cvr: 转化率
        ltv: 用户生命周期价值 (D7)
        fatigue: 素材疲劳度 (0-1)
        frequency: 广告频次
        impressions: 展示量
        installs: 安装量
        payer_rate: 付费率
        arpu: 单用户平均收入
        d7_retention: D7 留存
        timestamp: 数据时间
        metadata: 扩展元数据
    """
    product_id: str = ""
    campaign_id: str = ""
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    cpi: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    ltv: float = 0.0
    fatigue: float = 0.0
    frequency: float = 0.0
    impressions: int = 0
    installs: int = 0
    payer_rate: float = 0.0
    arpu: float = 0.0
    d7_retention: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "campaign_id": self.campaign_id,
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": self.roas,
            "cpi": self.cpi,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "ltv": self.ltv,
            "fatigue": self.fatigue,
            "frequency": self.frequency,
            "impressions": self.impressions,
            "installs": self.installs,
            "payer_rate": self.payer_rate,
            "arpu": self.arpu,
            "d7_retention": self.d7_retention,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class MetricAnomaly:
    """指标异常.

    Attributes:
        metric: 指标名称
        current_value: 当前值
        expected_value: 预期值
        deviation: 偏差比例
        status: 异常状态
        explanation: 解释
        confidence: 置信度
    """
    metric: str = ""
    current_value: float = 0.0
    expected_value: float = 0.0
    deviation: float = 0.0
    status: MetricStatus = MetricStatus.HEALTHY
    explanation: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "deviation": round(self.deviation, 4),
            "status": self.status.value,
            "explanation": self.explanation,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class UAAnalysisResult:
    """UA 分析结果.

    Attributes:
        analysis_id: 分析 ID
        product_id: 产品 ID
        metrics: 原始指标
        anomalies: 异常列表
        health_score: 健康评分 (0-100)
        trend_direction: 趋势方向 (improving / stable / deteriorating)
        summary: 分析摘要
        insights: 洞察列表
        created_at: 分析时间
        metadata: 扩展元数据
    """
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    metrics: UAMetrics | None = None
    anomalies: list[MetricAnomaly] = field(default_factory=list)
    health_score: float = 100.0
    trend_direction: str = "stable"
    summary: str = ""
    insights: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "product_id": self.product_id,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "health_score": round(self.health_score, 1),
            "trend_direction": self.trend_direction,
            "summary": self.summary,
            "insights": self.insights,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Default Thresholds
# ═══════════════════════════════════════════════════════════════

DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "roas": {"warning": 1.0, "critical": 0.7, "healthy": 1.2},
    "cpi": {"warning": 3.0, "critical": 5.0, "healthy": 2.0},
    "ctr": {"warning": 0.5, "critical": 0.3, "healthy": 1.0},
    "cvr": {"warning": 2.0, "critical": 1.0, "healthy": 3.0},
    "fatigue": {"warning": 0.5, "critical": 0.7, "healthy": 0.3},
    "frequency": {"warning": 3.0, "critical": 5.0, "healthy": 2.0},
    "payer_rate": {"warning": 1.0, "critical": 0.5, "healthy": 2.0},
    "d7_retention": {"warning": 15.0, "critical": 10.0, "healthy": 20.0},
    "ltv": {"warning": 3.0, "critical": 2.0, "healthy": 5.0},
}


# ═══════════════════════════════════════════════════════════════
# UA Analyzer
# ═══════════════════════════════════════════════════════════════


class UAAnalyzer:
    """UA 指标分析器 — 检测异常、评估健康度、生成洞察.

    用法:
        analyzer = UAAnalyzer()
        result = analyzer.analyze(metrics)
        print(result.health_score, result.summary)
    """

    def __init__(self, thresholds: dict[str, dict[str, float]] | None = None):
        self._thresholds = thresholds or DEFAULT_THRESHOLDS
        self._history: list[UAAnalysisResult] = []

    # ── 核心分析 ──────────────────────────────────────────────

    def analyze(
        self,
        metrics: UAMetrics,
        previous_metrics: UAMetrics | None = None,
    ) -> UAAnalysisResult:
        """分析 UA 指标.

        Args:
            metrics: 当前指标
            previous_metrics: 历史指标 (用于趋势分析)

        Returns:
            UAAnalysisResult: 分析结果
        """
        anomalies = self._detect_anomalies(metrics)
        health_score = self._compute_health_score(metrics, anomalies)
        trend = self._compute_trend(metrics, previous_metrics)
        insights = self._generate_insights(anomalies, trend)
        summary = self._generate_summary(anomalies, health_score, trend)

        result = UAAnalysisResult(
            product_id=metrics.product_id,
            metrics=metrics,
            anomalies=anomalies,
            health_score=health_score,
            trend_direction=trend,
            summary=summary,
            insights=insights,
        )
        self._history.append(result)
        return result

    def analyze_from_dict(self, data: dict[str, Any]) -> UAAnalysisResult:
        """从字典创建指标并分析."""
        metrics = self._dict_to_metrics(data)
        return self.analyze(metrics)

    # ── 异常检测 ──────────────────────────────────────────────

    def _detect_anomalies(self, metrics: UAMetrics) -> list[MetricAnomaly]:
        """检测所有指标异常."""
        anomalies = []

        checks = [
            ("roas", metrics.roas, self._check_lower_is_bad),
            ("cpi", metrics.cpi, self._check_higher_is_bad),
            ("ctr", metrics.ctr, self._check_lower_is_bad),
            ("cvr", metrics.cvr, self._check_lower_is_bad),
            ("fatigue", metrics.fatigue, self._check_higher_is_bad),
            ("frequency", metrics.frequency, self._check_higher_is_bad),
            ("payer_rate", metrics.payer_rate, self._check_lower_is_bad),
            ("d7_retention", metrics.d7_retention, self._check_lower_is_bad),
            ("ltv", metrics.ltv, self._check_lower_is_bad),
        ]

        for metric_name, value, checker in checks:
            anomaly = checker(metric_name, value)
            if anomaly:
                anomalies.append(anomaly)

        return anomalies

    def _check_lower_is_bad(self, metric_name: str, value: float) -> MetricAnomaly | None:
        """检查值越低越差的指标."""
        t = self._thresholds.get(metric_name, {})
        if not t:
            return None

        healthy = t.get("healthy", 0)
        warning = t.get("warning", 0)
        critical = t.get("critical", 0)

        expected = healthy
        deviation = (expected - value) / expected if expected > 0 else 0

        if value <= critical:
            status = MetricStatus.CRITICAL
            confidence = 0.9
        elif value <= warning:
            status = MetricStatus.WARNING
            confidence = 0.7
        else:
            return None

        return MetricAnomaly(
            metric=metric_name,
            current_value=value,
            expected_value=expected,
            deviation=deviation,
            status=status,
            explanation=f"{metric_name}={value} (expected>{warning})",
            confidence=confidence,
        )

    def _check_higher_is_bad(self, metric_name: str, value: float) -> MetricAnomaly | None:
        """检查值越高越差的指标 (CPI, fatigue, frequency)."""
        t = self._thresholds.get(metric_name, {})
        if not t:
            return None

        healthy = t.get("healthy", 0)
        warning = t.get("warning", 0)
        critical = t.get("critical", 0)

        expected = healthy
        deviation = (value - expected) / expected if expected > 0 else 0

        if value >= critical:
            status = MetricStatus.CRITICAL
            confidence = 0.9
        elif value >= warning:
            status = MetricStatus.WARNING
            confidence = 0.7
        else:
            return None

        return MetricAnomaly(
            metric=metric_name,
            current_value=value,
            expected_value=expected,
            deviation=deviation,
            status=status,
            explanation=f"{metric_name}={value} (expected<{warning})",
            confidence=confidence,
        )

    # ── 健康评分 ──────────────────────────────────────────────

    def _compute_health_score(
        self,
        metrics: UAMetrics,
        anomalies: list[MetricAnomaly],
    ) -> float:
        """计算综合健康评分 (0-100)."""
        if not anomalies:
            return 100.0

        # 每个异常扣分
        deductions = {
            MetricStatus.CRITICAL: 15.0,
            MetricStatus.WARNING: 8.0,
        }

        total_deduction = sum(
            deductions.get(a.status, 0) * a.confidence
            for a in anomalies
        )
        return max(100.0 - total_deduction, 0.0)

    # ── 趋势分析 ──────────────────────────────────────────────

    def _compute_trend(
        self,
        current: UAMetrics,
        previous: UAMetrics | None = None,
    ) -> str:
        """计算趋势方向."""
        if not previous:
            return "stable"

        # 比较关键指标
        roas_change = (current.roas - previous.roas) / previous.roas if previous.roas > 0 else 0
        cpi_change = (current.cpi - previous.cpi) / previous.cpi if previous.cpi > 0 else 0
        fatigue_change = current.fatigue - previous.fatigue

        # 正变化: ROAS上升 / CPI下降 / 疲劳下降
        positive = roas_change > 0.05 or cpi_change < -0.05 or fatigue_change < -0.05
        negative = roas_change < -0.05 or cpi_change > 0.05 or fatigue_change > 0.05

        if positive:
            return "improving"
        elif negative:
            return "deteriorating"
        return "stable"

    # ── 洞察生成 ──────────────────────────────────────────────

    def _generate_insights(
        self,
        anomalies: list[MetricAnomaly],
        trend: str,
    ) -> list[str]:
        """生成可读洞察."""
        insights = []

        for a in anomalies:
            if a.status == MetricStatus.CRITICAL:
                insights.append(f"[CRITICAL] {a.metric} 严重异常: {a.explanation}")
            elif a.status == MetricStatus.WARNING:
                insights.append(f"[WARNING] {a.metric} 偏差: {a.explanation}")

        if trend == "deteriorating":
            insights.append("整体趋势恶化，需要立即关注")
        elif trend == "improving":
            insights.append("整体趋势向好，可以继续观察")

        if not insights:
            insights.append("所有指标正常，无异常检测")

        return insights

    def _generate_summary(
        self,
        anomalies: list[MetricAnomaly],
        health_score: float,
        trend: str,
    ) -> str:
        """生成分析摘要."""
        criticals = [a for a in anomalies if a.status == MetricStatus.CRITICAL]
        warnings = [a for a in anomalies if a.status == MetricStatus.WARNING]

        parts = []
        if criticals:
            parts.append(f"{len(criticals)} 严重异常")
        if warnings:
            parts.append(f"{len(warnings)} 警告")
        if not parts:
            parts.append("无异常")

        return (
            f"健康评分: {health_score:.0f}/100 | "
            f"趋势: {trend} | "
            f"{', '.join(parts)}"
        )

    # ── 工具 ──────────────────────────────────────────────────

    def _dict_to_metrics(self, data: dict[str, Any]) -> UAMetrics:
        """从字典创建 UAMetrics."""
        return UAMetrics(
            product_id=data.get("product_id", ""),
            campaign_id=data.get("campaign_id", ""),
            spend=data.get("spend", 0.0),
            revenue=data.get("revenue", 0.0),
            roas=data.get("roas", 0.0),
            cpi=data.get("cpi", 0.0),
            ctr=data.get("ctr", 0.0),
            cvr=data.get("cvr", 0.0),
            ltv=data.get("ltv", 0.0),
            fatigue=data.get("fatigue", 0.0),
            frequency=data.get("frequency", 0.0),
            impressions=data.get("impressions", 0),
            installs=data.get("installs", 0),
            payer_rate=data.get("payer_rate", 0.0),
            arpu=data.get("arpu", 0.0),
            d7_retention=data.get("d7_retention", 0.0),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )

    def get_history(self, n: int = 10) -> list[UAAnalysisResult]:
        return self._history[-n:]

    def reset(self) -> None:
        self._history.clear()