"""E13.1.4 MAX Connector — AppLovin MAX 广告变现 Reality Connector.

将 MAX 的广告收入、eCPM、ARPDAU、Waterfall 数据接入 Growth OS，
为 IAA / Hybrid 产品提供完整的广告变现视图。

模块:
  - models:         MAX 数据标准模型
  - client:         MAXClient API 客户端 (模拟/真实双模式)
  - revenue_mapper: MAX 原始数据 → Growth OS 标准指标映射
  - validator:      数据质量校验
  - exceptions:     MAX 专用异常
  - adapter:        MAXConnector 对接 E13.1.1 BaseConnector
"""

from .adapter import MAXConnector
from .client import MAXClient
from .exceptions import (
    MAXAPIError,
    MAXAuthError,
    MAXConfigError,
    MAXConnectionError,
    MAXDataNotFoundError,
    MAXError,
    MAXRateLimitError,
    MAXValidationError,
)
from .models import (
    MAXAccount,
    MAXAdFormat,
    MAXAdUnit,
    MAXAPIResponse,
    MAXNetwork,
    MAXPerformance,
    MAXRevenueEvent,
    MAXRevenueSnapshot,
    MAXRevenueType,
    MAXWaterfallEntry,
)
from .revenue_mapper import MAXRevenueMapper
from .validator import (
    MAXAdUnitValidator,
    MAXPerformanceValidator,
    MAXRevenueEventValidator,
    MAXRevenueSnapshotValidator,
    MAXWaterfallValidator,
    ValidationResult,
)

__all__ = [
    # Enums
    "MAXAdFormat",
    "MAXNetwork",
    "MAXRevenueType",
    # Models
    "MAXAccount",
    "MAXAdUnit",
    "MAXRevenueEvent",
    "MAXPerformance",
    "MAXRevenueSnapshot",
    "MAXAPIResponse",
    "MAXWaterfallEntry",
    # Client
    "MAXClient",
    # Mapper
    "MAXRevenueMapper",
    # Validator
    "ValidationResult",
    "MAXRevenueEventValidator",
    "MAXPerformanceValidator",
    "MAXRevenueSnapshotValidator",
    "MAXWaterfallValidator",
    "MAXAdUnitValidator",
    # Adapter
    "MAXConnector",
    # Exceptions
    "MAXError",
    "MAXAuthError",
    "MAXAPIError",
    "MAXRateLimitError",
    "MAXValidationError",
    "MAXDataNotFoundError",
    "MAXConnectionError",
    "MAXConfigError",
]