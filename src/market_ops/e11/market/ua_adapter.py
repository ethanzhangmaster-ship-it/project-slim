"""E11.5.1 UA Adapter — UA 投放数据适配器。

将 Facebook Ads / Google Ads / ASA 等平台的投放数据
标准化为 UAMetrics。

输入格式：
  {
    "impressions": 100000,
    "clicks": 50000,
    "installs": 30000,
    "spend": 10000.0,
  }

输出：
  UAMetrics(impressions=100000, clicks=50000, installs=30000, spend=10000.0)

数据流：
  Facebook/Google Ads raw data → UA Adapter.normalize() → UAMetrics
"""

from __future__ import annotations

from typing import Any

from .feedback_schema import UAMetrics
from .market_exceptions import MarketAdapterError, InvalidMetricsError
from .performance_adapter import PerformanceAdapter


class UAPerformanceAdapter(PerformanceAdapter):
    """UA 投放数据适配器。

    支持 Facebook Ads、Google Ads、ASA 等平台的标准化。

    Usage:
        adapter = UAPerformanceAdapter()
        metrics = adapter.normalize({
            "impressions": 100000,
            "clicks": 50000,
            "installs": 30000,
            "spend": 10000.0,
        })
    """

    # 必要字段
    REQUIRED_FIELDS = {"impressions", "clicks", "installs", "spend"}

    def validate(self, raw_data: dict[str, Any]) -> bool:
        """验证是否包含所有必要字段。"""
        return self.REQUIRED_FIELDS.issubset(raw_data.keys())

    def normalize(self, raw_data: dict[str, Any]) -> UAMetrics:
        """将原始 UA 数据标准化为 UAMetrics。

        Args:
            raw_data: 包含 impressions, clicks, installs, spend 的字典

        Returns:
            UAMetrics 实例

        Raises:
            MarketAdapterError: 缺少必要字段
            InvalidMetricsError: 数值无效
        """
        if not self.validate(raw_data):
            missing = self.REQUIRED_FIELDS - set(raw_data.keys())
            raise MarketAdapterError(
                f"UA Adapter: missing required fields: {missing}"
            )

        # 提取并验证数值
        try:
            impressions = int(raw_data["impressions"])
            clicks = int(raw_data["clicks"])
            installs = int(raw_data["installs"])
            spend = float(raw_data["spend"])
        except (ValueError, TypeError) as e:
            raise InvalidMetricsError(
                f"UA Adapter: invalid numeric values: {e}"
            )

        # 基本合理性检查
        if impressions < 0 or clicks < 0 or installs < 0 or spend < 0:
            raise InvalidMetricsError(
                "UA Adapter: metrics cannot be negative"
            )
        if clicks > impressions:
            raise InvalidMetricsError(
                f"UA Adapter: clicks ({clicks}) > impressions ({impressions})"
            )
        if installs > clicks:
            raise InvalidMetricsError(
                f"UA Adapter: installs ({installs}) > clicks ({clicks})"
            )

        return UAMetrics(
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            spend=spend,
        )