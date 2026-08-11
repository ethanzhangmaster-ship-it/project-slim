"""E11.5.1 Analytics Adapter — 用户行为数据适配器。

将 Firebase / GameAnalytics 的用户行为数据
标准化为 EngagementMetrics。

输入格式：
  {
    "d1_retention": 0.45,
    "d7_retention": 0.35,
    "d30_retention": 0.15,
    "sessions": 12.5,
    "playtime": 42.0,
    "level_progress": 5.3,
  }

输出：
  EngagementMetrics(d1_retention=0.45, d7_retention=0.35, playtime=42.0, ...)

数据流：
  Firebase/GameAnalytics raw data → Analytics Adapter.normalize() → EngagementMetrics
"""

from __future__ import annotations

from typing import Any

from .feedback_schema import EngagementMetrics
from .market_exceptions import MarketAdapterError, InvalidMetricsError
from .performance_adapter import PerformanceAdapter


class AnalyticsPerformanceAdapter(PerformanceAdapter):
    """用户行为数据适配器。

    支持 Firebase、GameAnalytics 等平台的标准化。

    Usage:
        adapter = AnalyticsPerformanceAdapter()
        metrics = adapter.normalize({
            "d1_retention": 0.45,
            "d7_retention": 0.35,
            "d30_retention": 0.15,
            "sessions": 12.5,
            "playtime": 42.0,
            "level_progress": 5.3,
        })
    """

    # 必要字段
    REQUIRED_FIELDS = {"d1_retention", "d7_retention", "sessions"}

    def validate(self, raw_data: dict[str, Any]) -> bool:
        """验证是否包含所有必要字段。"""
        return self.REQUIRED_FIELDS.issubset(raw_data.keys())

    def normalize(self, raw_data: dict[str, Any]) -> EngagementMetrics:
        """将原始分析数据标准化为 EngagementMetrics。

        Args:
            raw_data: 包含 retention, sessions, playtime 的字典

        Returns:
            EngagementMetrics 实例

        Raises:
            MarketAdapterError: 缺少必要字段
            InvalidMetricsError: 数值无效
        """
        if not self.validate(raw_data):
            missing = self.REQUIRED_FIELDS - set(raw_data.keys())
            raise MarketAdapterError(
                f"Analytics Adapter: missing required fields: {missing}"
            )

        # 提取并验证数值
        try:
            d1_retention = float(raw_data["d1_retention"])
            d7_retention = float(raw_data["d7_retention"])
            d30_retention = float(raw_data.get("d30_retention", 0.0))
            sessions = float(raw_data["sessions"])
            playtime = float(raw_data.get("playtime", 0.0))
            level_progress = float(raw_data.get("level_progress", 0.0))
        except (ValueError, TypeError) as e:
            raise InvalidMetricsError(
                f"Analytics Adapter: invalid numeric values: {e}"
            )

        # 基本合理性检查
        for name, val in [
            ("d1_retention", d1_retention),
            ("d7_retention", d7_retention),
            ("d30_retention", d30_retention),
        ]:
            if val < 0 or val > 1:
                raise InvalidMetricsError(
                    f"Analytics Adapter: {name} must be between 0 and 1, got {val}"
                )
        if sessions < 0:
            raise InvalidMetricsError("Analytics Adapter: sessions cannot be negative")
        if playtime < 0:
            raise InvalidMetricsError("Analytics Adapter: playtime cannot be negative")
        if level_progress < 0:
            raise InvalidMetricsError("Analytics Adapter: level_progress cannot be negative")

        return EngagementMetrics(
            d1_retention=d1_retention,
            d7_retention=d7_retention,
            d30_retention=d30_retention,
            sessions=sessions,
            playtime=playtime,
            level_progress=level_progress,
        )