"""E12.7.2 — Perception Layer。

Agent 感知层 —— 将原始信号转换为 GrowthObservation。

职责:
  1. 接收来自 Reality Layer / Meta Learning / Portfolio Optimizer 的信号
  2. 计算产品核心指标
  3. 评估创意状态
  4. 评估市场状态
  5. 检测异常信号
  6. 输出 GrowthObservation
"""

from __future__ import annotations

from typing import Any

from .models import (
    CreativeState,
    GrowthObservation,
    MarketState,
    ObservationSeverity,
    ProductMetrics,
    _now,
)


class PerceptionLayer:
    """Agent 感知层。

    将多源信号融合为统一的 GrowthObservation。
    """

    def __init__(self) -> None:
        self._observations: list[GrowthObservation] = []

    def perceive(
        self,
        product_id: str,
        metrics: dict[str, Any] | None = None,
        creative_data: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
        signals: list[str] | None = None,
    ) -> GrowthObservation:
        """感知产品当前状态。

        Args:
            product_id:    产品 ID
            metrics:       核心指标数据
            creative_data: 创意数据
            market_data:   市场数据
            signals:       已知信号列表

        Returns:
            GrowthObservation
        """
        metrics = metrics or {}
        creative_data = creative_data or {}
        market_data = market_data or {}

        # 构建指标
        product_metrics = ProductMetrics(
            roas=metrics.get("roas", 0.0),
            cpi=metrics.get("cpi", 0.0),
            ctr=metrics.get("ctr", 0.0),
            retention_d1=metrics.get("retention_d1", 0.0),
            retention_d7=metrics.get("retention_d7", 0.0),
            revenue=metrics.get("revenue", 0.0),
            spend=metrics.get("spend", 0.0),
            installs=metrics.get("installs", 0),
            impressions=metrics.get("impressions", 0),
        )

        # 构建创意状态
        creative_state = CreativeState(
            fatigue_score=creative_data.get("fatigue_score", 0.0),
            diversity_score=creative_data.get("diversity_score", 0.0),
            winner_ratio=creative_data.get("winner_ratio", 0.0),
            active_creatives=creative_data.get("active_creatives", 0),
            winning_creatives=creative_data.get("winning_creatives", 0),
            total_creatives=creative_data.get("total_creatives", 0),
        )

        # 构建市场状态
        market_state = MarketState(
            trend_score=market_data.get("trend_score", 0.5),
            competition_score=market_data.get("competition_score", 0.5),
            market_size=market_data.get("market_size", 0.0),
            growth_rate=market_data.get("growth_rate", 0.0),
        )

        # 检测信号
        detected_signals = signals or []
        detected_signals.extend(self._detect_signals(product_metrics, creative_state, market_state))

        # 计算严重程度
        severity = self._assess_severity(product_metrics, creative_state, market_state, detected_signals)

        # 生成摘要
        summary = self._generate_summary(product_metrics, creative_state, market_state, severity)

        observation = GrowthObservation(
            product_id=product_id,
            metrics=product_metrics,
            creative_state=creative_state,
            market_state=market_state,
            severity=severity,
            signals=detected_signals,
            summary=summary,
        )

        self._observations.append(observation)
        return observation

    def _detect_signals(
        self,
        metrics: ProductMetrics,
        creative: CreativeState,
        market: MarketState,
    ) -> list[str]:
        """检测异常信号。

        Returns:
            信号列表
        """
        signals: list[str] = []

        # ROAS 信号
        if metrics.roas < 0.50:
            signals.append("roas_critical")
        elif metrics.roas < 0.80:
            signals.append("roas_warning")

        # CTR 信号
        if metrics.ctr < 0.01:
            signals.append("ctr_low")

        # CPI 信号
        if metrics.cpi > 5.0:
            signals.append("cpi_high")

        # 创意疲劳
        if creative.is_highly_fatigued:
            signals.append("creative_highly_fatigued")
        elif creative.is_fatigued:
            signals.append("creative_fatigued")

        # 创意多样性
        if creative.diversity_score < 0.30:
            signals.append("creative_diversity_low")

        # 赢家比率
        if creative.winner_ratio < 0.10 and creative.total_creatives > 10:
            signals.append("winner_ratio_low")

        # 市场趋势
        if market.is_declining:
            signals.append("market_declining")

        # 竞争
        if market.is_highly_competitive:
            signals.append("market_highly_competitive")

        return signals

    def _assess_severity(
        self,
        metrics: ProductMetrics,
        creative: CreativeState,
        market: MarketState,
        signals: list[str],
    ) -> ObservationSeverity:
        """评估严重程度。

        Returns:
            ObservationSeverity
        """
        critical_count = len([
            s for s in signals if s in (
                "roas_critical", "creative_highly_fatigued",
                "market_declining",
            )
        ])
        warning_count = len([
            s for s in signals if s in (
                "roas_warning", "creative_fatigued", "ctr_low",
                "cpi_high", "creative_diversity_low",
                "winner_ratio_low", "market_highly_competitive",
            )
        ])

        if critical_count >= 2:
            return ObservationSeverity.FATAL
        if critical_count >= 1 or warning_count >= 3:
            return ObservationSeverity.CRITICAL
        if warning_count >= 2:
            return ObservationSeverity.WARNING
        if warning_count >= 1:
            return ObservationSeverity.WARNING
        return ObservationSeverity.NORMAL

    def _generate_summary(
        self,
        metrics: ProductMetrics,
        creative: CreativeState,
        market: MarketState,
        severity: ObservationSeverity,
    ) -> str:
        """生成观察摘要。"""
        parts: list[str] = []

        parts.append(f"Product metrics: ROAS={metrics.roas:.2f}")

        if creative.is_fatigued:
            parts.append(f"creative fatigue={creative.fatigue_score:.2f}")
        if market.is_declining:
            parts.append("market declining")
        if market.is_highly_competitive:
            parts.append("high competition")

        parts.append(f"severity={severity.value}")

        return " | ".join(parts)

    def get_latest_observation(
        self, product_id: str
    ) -> GrowthObservation | None:
        """获取产品最新观察。"""
        for obs in reversed(self._observations):
            if obs.product_id == product_id:
                return obs
        return None

    def get_history(
        self, product_id: str | None = None, limit: int = 100
    ) -> list[GrowthObservation]:
        """获取观察历史。"""
        results = self._observations
        if product_id:
            results = [o for o in results if o.product_id == product_id]
        return results[-limit:]

    def clear(self) -> None:
        """清除所有观察。"""
        self._observations.clear()

    @property
    def observation_count(self) -> int:
        return len(self._observations)

    def __repr__(self) -> str:
        return f"PerceptionLayer(observations={self.observation_count})"