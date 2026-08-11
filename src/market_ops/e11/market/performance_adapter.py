"""E11.5.1 Performance Adapter — 性能数据适配器抽象基类。

定义所有 Adapter 的统一接口。

每个 Adapter 负责将外部数据源（Facebook Ads, Firebase, RevenueCat 等）
标准化为 E11 内部数据模型。

接口：
  normalize(raw_data) → 标准化为内部指标对象

数据流：
  Raw Data (JSON) → Adapter.normalize() → Metrics Object
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PerformanceAdapter(ABC):
    """性能数据适配器抽象基类。

    所有 Adapter 必须实现 normalize() 方法。

    Usage:
        class UAPerformanceAdapter(PerformanceAdapter):
            def normalize(self, raw_data: dict) -> UAMetrics:
                ...
    """

    @abstractmethod
    def normalize(self, raw_data: dict[str, Any]) -> Any:
        """将原始数据标准化为内部指标对象。

        Args:
            raw_data: 外部数据源的原始数据

        Returns:
            标准化后的指标对象 (UAMetrics / EngagementMetrics / IAPMetrics)

        Raises:
            MarketAdapterError: 数据格式无效或缺失必要字段
        """
        ...

    @abstractmethod
    def validate(self, raw_data: dict[str, Any]) -> bool:
        """验证原始数据是否包含必要字段。

        Args:
            raw_data: 外部数据源的原始数据

        Returns:
            是否有效
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"