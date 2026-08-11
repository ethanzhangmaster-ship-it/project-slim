"""E14.8.2 Growth State Analyzer — 增长状态分析器.

E14.8 Autonomous Growth Agent 第二层:
  从 RealityData 中提取可操作的增长状态信号，为 Agent 决策提供依据.

输入: RealityData (来自 E12 Reality Intelligence / E13 Growth Runtime)
输出: GrowthState (结构化状态描述)

核心模型:
  - GrowthState: 当前增长状态
  - MetricStatus: 单个指标状态
  - StateAnalyzer: 状态分析器
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class MetricStatus(str, Enum):
    """指标状态."""
    ABOVE_TARGET = "above_target"
    ON_TARGET = "on_target"
    BELOW_TARGET = "below_target"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CreativeHealth(str, Enum):
    """创意健康状态."""
    HEALTHY = "healthy"
    FATIGUING = "fatiguing"
    FATIGUED = "fatigued"
    STALE = "stale"


class UAScaleStatus(str, Enum):
    """UA 放量状态."""
    SCALABLE = "scalable"
    STABLE = "stable"
    CONTRACTING = "contracting"
    PAUSED = "paused"


# ═══════════════════════════════════════════════════════════
# 模型
# ═══════════════════════════════════════════════════════════

@dataclass
class GrowthState:
    """增长状态 — 当前业务状态的完整快照.

    Attributes:
        state_id: 状态 ID
        timestamp: 时间戳
        roas_status: ROAS 状态
        roas_current: 当前 ROAS
        roas_target: 目标 ROAS
        creative_fatigue: 创意疲劳度 [0, 1]
        creative_health: 创意健康状态
        payer_conversion: 付费转化状态
        payer_rate: 当前付费率
        ua_scale: UA 放量状态
        campaign_count: 活跃广告系列数
        active_creative_count: 活跃创意数
        budget_utilization: 预算利用率
        trend_direction: 整体趋势 (improving / stable / declining)
        risk_signals: 风险信号列表
        opportunities: 机会列表
        metadata: 扩展数据
    """
    state_id: str = field(default_factory=lambda: f"gs_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    roas_status: MetricStatus = MetricStatus.UNKNOWN
    roas_current: float = 0.0
    roas_target: float = 1.0
    creative_fatigue: float = 0.0
    creative_health: CreativeHealth = CreativeHealth.HEALTHY
    payer_conversion: MetricStatus = MetricStatus.UNKNOWN
    payer_rate: float = 0.0
    ua_scale: UAScaleStatus = UAScaleStatus.STABLE
    campaign_count: int = 0
    active_creative_count: int = 0
    budget_utilization: float = 0.0
    trend_direction: str = "stable"
    risk_signals: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """系统是否健康."""
        return (
            self.roas_status in (MetricStatus.ON_TARGET, MetricStatus.ABOVE_TARGET)
            and self.creative_health == CreativeHealth.HEALTHY
            and self.trend_direction != "declining"
        )

    @property
    def needs_intervention(self) -> bool:
        """是否需要人工干预."""
        return (
            self.roas_status == MetricStatus.CRITICAL
            or self.creative_fatigue > 0.85
            or len(self.risk_signals) >= 3
        )

    @property
    def primary_opportunity(self) -> str:
        """主要机会类型."""
        if self.creative_fatigue > 0.7:
            return "creative_fatigue"
        if self.roas_status == MetricStatus.BELOW_TARGET:
            return "roas_drop"
        if self.ua_scale == UAScaleStatus.SCALABLE:
            return "scale_opportunity"
        if self.payer_conversion == MetricStatus.BELOW_TARGET:
            return "payer_conversion"
        return "general"

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "timestamp": self.timestamp,
            "roas_status": self.roas_status.value,
            "roas_current": self.roas_current,
            "roas_target": self.roas_target,
            "creative_fatigue": self.creative_fatigue,
            "creative_health": self.creative_health.value,
            "payer_conversion": self.payer_conversion.value,
            "payer_rate": self.payer_rate,
            "ua_scale": self.ua_scale.value,
            "campaign_count": self.campaign_count,
            "active_creative_count": self.active_creative_count,
            "budget_utilization": self.budget_utilization,
            "trend_direction": self.trend_direction,
            "risk_signals": self.risk_signals,
            "opportunities": self.opportunities,
            "is_healthy": self.is_healthy,
            "needs_intervention": self.needs_intervention,
            "primary_opportunity": self.primary_opportunity,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════
# StateAnalyzer
# ═══════════════════════════════════════════════════════════

class StateAnalyzer:
    """增长状态分析器 — 从 RealityData 生成 GrowthState.

    用法:
        analyzer = StateAnalyzer()
        state = analyzer.analyze(reality_data)
    """

    # 阈值配置
    ROAS_CRITICAL = 0.5
    ROAS_BELOW = 0.8
    ROAS_ABOVE = 1.2
    FATIGUE_THRESHOLD = 0.6
    FATIGUE_HIGH = 0.8
    PAYER_RATE_LOW = 0.02
    PAYER_RATE_GOOD = 0.05

    def __init__(
        self,
        roas_target: float = 1.0,
        fatigue_threshold: float = 0.6,
        fatigue_high: float = 0.8,
        payer_rate_low: float = 0.02,
        payer_rate_good: float = 0.05,
    ):
        self._roas_target = roas_target
        self._fatigue_threshold = fatigue_threshold
        self._fatigue_high = fatigue_high
        self._payer_rate_low = payer_rate_low
        self._payer_rate_good = payer_rate_good
        self._analysis_count: int = 0

    def analyze(self, reality_data: dict[str, Any] | None = None) -> GrowthState:
        """分析 RealityData 生成 GrowthState.

        Args:
            reality_data: Reality 数据字典. 支持:
                - roas: 当前 ROAS
                - roas_trend: ROAS 趋势
                - fatigue: 创意疲劳度
                - payer_rate: 付费率
                - campaign_count: 活跃广告系列数
                - creative_count: 活跃创意数
                - budget_utilization: 预算利用率
                - ctr: 点击率
                - cvr: 转化率
                - signals: 风险信号列表

        Returns:
            GrowthState: 结构化状态
        """
        self._analysis_count += 1
        data = reality_data or {}

        roas = float(data.get("roas", 0))
        roas_trend = data.get("roas_trend", "stable")
        fatigue = float(data.get("fatigue", 0))
        payer_rate = float(data.get("payer_rate", 0))
        campaign_count = int(data.get("campaign_count", 0))
        creative_count = int(data.get("creative_count", 0))
        budget_util = float(data.get("budget_utilization", 0))

        # ROAS 状态
        roas_status = self._classify_roas(roas)

        # 创意健康
        creative_health = self._classify_creative_health(fatigue)

        # 付费转化状态
        payer_status = self._classify_payer(payer_rate)

        # UA 放量状态
        ua_scale = self._classify_ua_scale(roas, fatigue, budget_util)

        # 趋势方向
        trend = self._classify_trend(roas_trend, roas, fatigue)

        # 风险信号
        risk_signals = self._detect_risks(
            data, roas, fatigue, payer_rate, roas_status
        )

        # 机会
        opportunities = self._detect_opportunities(
            roas, fatigue, payer_rate, roas_status, ua_scale
        )

        return GrowthState(
            roas_status=roas_status,
            roas_current=roas,
            roas_target=self._roas_target,
            creative_fatigue=fatigue,
            creative_health=creative_health,
            payer_conversion=payer_status,
            payer_rate=payer_rate,
            ua_scale=ua_scale,
            campaign_count=campaign_count,
            active_creative_count=creative_count,
            budget_utilization=budget_util,
            trend_direction=trend,
            risk_signals=risk_signals,
            opportunities=opportunities,
            metadata={"raw_data": data},
        )

    def _classify_roas(self, roas: float) -> MetricStatus:
        if roas <= 0:
            return MetricStatus.UNKNOWN
        if roas < self.ROAS_CRITICAL:
            return MetricStatus.CRITICAL
        if roas < self.ROAS_BELOW:
            return MetricStatus.BELOW_TARGET
        if roas >= self.ROAS_ABOVE:
            return MetricStatus.ABOVE_TARGET
        return MetricStatus.ON_TARGET

    def _classify_creative_health(self, fatigue: float) -> CreativeHealth:
        if fatigue >= self._fatigue_high:
            return CreativeHealth.FATIGUED
        if fatigue >= self._fatigue_threshold:
            return CreativeHealth.FATIGUING
        return CreativeHealth.HEALTHY

    def _classify_payer(self, payer_rate: float) -> MetricStatus:
        if payer_rate <= 0:
            return MetricStatus.UNKNOWN
        if payer_rate < self._payer_rate_low:
            return MetricStatus.CRITICAL
        if payer_rate < self._payer_rate_good:
            return MetricStatus.BELOW_TARGET
        return MetricStatus.ON_TARGET

    def _classify_ua_scale(
        self, roas: float, fatigue: float, budget_util: float
    ) -> UAScaleStatus:
        if budget_util <= 0:
            return UAScaleStatus.PAUSED
        if roas > 1.2 and fatigue < 0.4 and budget_util > 0.8:
            return UAScaleStatus.SCALABLE
        if roas < 0.5 or fatigue > 0.8:
            return UAScaleStatus.CONTRACTING
        return UAScaleStatus.STABLE

    def _classify_trend(
        self, roas_trend: str, roas: float, fatigue: float
    ) -> str:
        if roas_trend == "declining" or fatigue > self._fatigue_high:
            return "declining"
        if roas_trend == "improving" or roas > self.ROAS_ABOVE:
            return "improving"
        return "stable"

    def _detect_risks(
        self,
        data: dict[str, Any],
        roas: float,
        fatigue: float,
        payer_rate: float,
        roas_status: MetricStatus,
    ) -> list[str]:
        risks: list[str] = []
        if roas_status == MetricStatus.CRITICAL:
            risks.append("roas_critical")
        if fatigue > self._fatigue_high:
            risks.append("creative_high_fatigue")
        if payer_rate > 0 and payer_rate < self._payer_rate_low:
            risks.append("low_payer_rate")
        if data.get("ctr", 0) > 0 and data.get("ctr", 1) < 0.005:
            risks.append("low_ctr")
        if data.get("cvr", 0) > 0 and data.get("cvr", 1) < 0.01:
            risks.append("low_cvr")
        # 外部信号
        external = data.get("signals", [])
        if isinstance(external, list):
            risks.extend(external)
        return risks

    def _detect_opportunities(
        self,
        roas: float,
        fatigue: float,
        payer_rate: float,
        roas_status: MetricStatus,
        ua_scale: UAScaleStatus,
    ) -> list[str]:
        opportunities: list[str] = []
        if fatigue > self._fatigue_threshold:
            opportunities.append("creative_refresh")
        if roas_status == MetricStatus.BELOW_TARGET:
            opportunities.append("roas_improvement")
        if ua_scale == UAScaleStatus.SCALABLE:
            opportunities.append("scale_up")
        if payer_rate > 0 and payer_rate < self._payer_rate_good:
            opportunities.append("payer_optimization")
        if roas_status == MetricStatus.ABOVE_TARGET and fatigue < 0.3:
            opportunities.append("aggressive_scale")
        return opportunities

    @property
    def analysis_count(self) -> int:
        return self._analysis_count

    @property
    def roas_target(self) -> float:
        return self._roas_target


def create_state_analyzer(
    roas_target: float = 1.0,
    fatigue_threshold: float = 0.6,
    fatigue_high: float = 0.8,
) -> StateAnalyzer:
    """创建默认 StateAnalyzer."""
    return StateAnalyzer(
        roas_target=roas_target,
        fatigue_threshold=fatigue_threshold,
        fatigue_high=fatigue_high,
    )