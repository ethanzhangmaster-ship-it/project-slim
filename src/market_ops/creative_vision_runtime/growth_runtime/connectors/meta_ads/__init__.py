"""E13.1.2 Meta Ads Connector — Meta 广告平台真实数据连接器.

模块:
  - models:    Meta 数据标准模型
  - client:    MetaAdsClient API 客户端 (模拟/真实双模式)
  - adapter:   MetaAdsConnector 对接 E13.1.1 BaseConnector
  - metrics_mapper: Meta 原始字段 → Growth OS 标准字段映射
  - validator: 数据质量校验
  - exceptions: Meta 专用异常
"""

from .adapter import MetaAdsConnector
from .client import MetaAdsClient
from .exceptions import (
    MetaAdsError,
    MetaAPIError,
    MetaAuthError,
    MetaConfigError,
    MetaConnectionError,
    MetaDataNotFoundError,
    MetaRateLimitError,
    MetaValidationError,
)
from .metrics_mapper import MetaMetricsMapper
from .models import (
    CreativeFatigueSignal,
    MetaAccount,
    MetaAccountStatus,
    MetaAdSet,
    MetaAPIResponse,
    MetaCampaign,
    MetaCampaignObjective,
    MetaCampaignStatus,
    MetaCreative,
    MetaInsightAction,
    MetaInsightLevel,
    MetaPerformance,
    ScalingOpportunity,
)
from .validator import (
    CreativeFatigueValidator,
    MetaAccountValidator,
    MetaCampaignValidator,
    MetaCreativeValidator,
    MetaPerformanceValidator,
    ScalingOpportunityValidator,
    ValidationResult,
)

__all__ = [
    # Enums
    "MetaCampaignObjective",
    "MetaCampaignStatus",
    "MetaAccountStatus",
    "MetaInsightLevel",
    "MetaInsightAction",
    # Models
    "MetaAccount",
    "MetaCampaign",
    "MetaAdSet",
    "MetaCreative",
    "MetaPerformance",
    "MetaAPIResponse",
    "CreativeFatigueSignal",
    "ScalingOpportunity",
    # Client
    "MetaAdsClient",
    # Adapter
    "MetaAdsConnector",
    # Mapper
    "MetaMetricsMapper",
    # Validator
    "ValidationResult",
    "MetaPerformanceValidator",
    "MetaCampaignValidator",
    "MetaAccountValidator",
    "MetaCreativeValidator",
    "CreativeFatigueValidator",
    "ScalingOpportunityValidator",
    # Exceptions
    "MetaAdsError",
    "MetaAuthError",
    "MetaAPIError",
    "MetaRateLimitError",
    "MetaValidationError",
    "MetaDataNotFoundError",
    "MetaConnectionError",
    "MetaConfigError",
]