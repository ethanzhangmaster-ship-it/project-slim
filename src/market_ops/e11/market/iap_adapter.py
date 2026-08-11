"""E11.5.1 IAP Adapter — IAP 付费数据适配器。

将 App Store / Google Play / RevenueCat 的付费数据
标准化为 IAPMetrics。

输入格式：
  {
    "revenue": 50000.0,
    "iap_revenue": 48000.0,
    "payer_count": 500,
    "purchase_count": 1200,
    "installs": 30000,
    "d7_ltv": 1.2,
    "d30_ltv": 3.5,
    "d90_ltv": 8.0,
  }

输出：
  IAPMetrics(revenue=50000.0, payer_count=500, pay_rate=0.0167, ...)

数据流：
  RevenueCat/App Store raw data → IAP Adapter.normalize() → IAPMetrics
"""

from __future__ import annotations

from typing import Any

from .feedback_schema import IAPMetrics
from .market_exceptions import MarketAdapterError, InvalidMetricsError
from .performance_adapter import PerformanceAdapter


class IAPPerformanceAdapter(PerformanceAdapter):
    """IAP 付费数据适配器。

    支持 RevenueCat、App Store Connect、Google Play Console 的标准化。

    Usage:
        adapter = IAPPerformanceAdapter()
        metrics = adapter.normalize({
            "revenue": 50000.0,
            "iap_revenue": 48000.0,
            "payer_count": 500,
            "purchase_count": 1200,
            "installs": 30000,
            "d7_ltv": 1.2,
            "d30_ltv": 3.5,
            "d90_ltv": 8.0,
        })
    """

    # 必要字段
    REQUIRED_FIELDS = {"revenue", "payer_count", "purchase_count", "installs"}

    def validate(self, raw_data: dict[str, Any]) -> bool:
        """验证是否包含所有必要字段。"""
        return self.REQUIRED_FIELDS.issubset(raw_data.keys())

    def normalize(self, raw_data: dict[str, Any]) -> IAPMetrics:
        """将原始 IAP 数据标准化为 IAPMetrics。

        Args:
            raw_data: 包含 revenue, payer_count, purchase_count, installs 的字典

        Returns:
            IAPMetrics 实例

        Raises:
            MarketAdapterError: 缺少必要字段
            InvalidMetricsError: 数值无效
        """
        if not self.validate(raw_data):
            missing = self.REQUIRED_FIELDS - set(raw_data.keys())
            raise MarketAdapterError(
                f"IAP Adapter: missing required fields: {missing}"
            )

        # 提取并验证数值
        try:
            revenue = float(raw_data["revenue"])
            iap_revenue = float(raw_data.get("iap_revenue", 0.0))
            payer_count = int(raw_data["payer_count"])
            purchase_count = int(raw_data["purchase_count"])
            installs = int(raw_data["installs"])
            d7_ltv = float(raw_data.get("d7_ltv", 0.0))
            d30_ltv = float(raw_data.get("d30_ltv", 0.0))
            d90_ltv = float(raw_data.get("d90_ltv", 0.0))
        except (ValueError, TypeError) as e:
            raise InvalidMetricsError(
                f"IAP Adapter: invalid numeric values: {e}"
            )

        # 基本合理性检查
        if revenue < 0 or payer_count < 0 or purchase_count < 0 or installs < 0:
            raise InvalidMetricsError(
                "IAP Adapter: metrics cannot be negative"
            )
        if payer_count > installs and installs > 0:
            raise InvalidMetricsError(
                f"IAP Adapter: payer_count ({payer_count}) > installs ({installs})"
            )
        if purchase_count < payer_count:
            raise InvalidMetricsError(
                f"IAP Adapter: purchase_count ({purchase_count}) < payer_count ({payer_count})"
            )

        return IAPMetrics(
            revenue=revenue,
            iap_revenue=iap_revenue,
            payer_count=payer_count,
            purchase_count=purchase_count,
            installs=installs,
            d7_ltv=d7_ltv,
            d30_ltv=d30_ltv,
            d90_ltv=d90_ltv,
        )