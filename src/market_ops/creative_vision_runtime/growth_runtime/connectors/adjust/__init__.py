"""E13.1.3 Adjust Connector — Adjust 用户生命周期 Reality Connector.

将 Adjust 的归因、用户行为、留存、收入事件接入 Growth OS，
为 IAA / IAP / Hybrid 产品提供统一用户价值视图。

模块:
  - models:      Adjust 数据标准模型
  - client:      AdjustClient API 客户端 (模拟/真实双模式)
  - event_parser: Adjust 原始事件 → AdjustUserEvent 解析器
  - attribution: 归因映射与网络关联
  - mapper:      事件/归因/留存 → UserValueSnapshot 聚合器
  - validator:   数据质量校验
  - connector:   AdjustConnector 对接 E13.1.1 BaseConnector
"""

from .attribution import AttributionMapper
from .client import AdjustClient
from .connector import AdjustConnector
from .event_parser import AdjustEventParser
from .mapper import AdjustValueMapper
from .models import (
    AdjustAPIResponse,
    AdjustEventType,
    AdjustNetwork,
    AdjustRevenueType,
    AdjustUserEvent,
    AttributionRecord,
    RetentionSnapshot,
    UserValueSnapshot,
)
from .validator import (
    APIResponseValidator,
    AdjustEventValidator,
    AttributionValidator,
    RetentionValidator,
    UserValueValidator,
    ValidationResult,
)

__all__ = [
    # Enums
    "AdjustEventType",
    "AdjustRevenueType",
    "AdjustNetwork",
    # Models
    "AdjustUserEvent",
    "AttributionRecord",
    "RetentionSnapshot",
    "UserValueSnapshot",
    "AdjustAPIResponse",
    # Client
    "AdjustClient",
    # Parser
    "AdjustEventParser",
    # Attribution
    "AttributionMapper",
    # Mapper
    "AdjustValueMapper",
    # Validator
    "ValidationResult",
    "AdjustEventValidator",
    "AttributionValidator",
    "RetentionValidator",
    "UserValueValidator",
    "APIResponseValidator",
    # Connector
    "AdjustConnector",
]