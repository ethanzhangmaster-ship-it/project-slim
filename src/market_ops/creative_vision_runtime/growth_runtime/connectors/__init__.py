"""E13.1.1 Growth Data Connector Framework — 所有真实数据接入的底座.

模块:
  - models:  统一数据模型 (CampaignMetrics, UserRevenueCurve, RetentionCurve, GameplayMetrics, GrowthDataEvent)
  - base:    BaseConnector 抽象基类 (连接/认证/健康检查/限流/重试)
  - registry: ConnectorRegistry 注册表 (注册/发现/生命周期/数据收集)
"""

from .base import BaseConnector
from .models import (
    CampaignMetrics,
    AdSetMetrics,
    CreativeMetrics,
    ConnectorConfig,
    ConnectorHealth,
    ConnectorInfo,
    ConnectorStatus,
    DataGranularity,
    DataSource,
    GameplayMetrics,
    GrowthDataEvent,
    MetricType,
    RetentionCurve,
    UserRevenueCurve,
)
from .registry import ConnectorRegistry

__all__ = [
    # Enums
    "DataSource",
    "MetricType",
    "DataGranularity",
    "ConnectorStatus",
    "ConnectorHealth",
    # Models
    "CampaignMetrics",
    "AdSetMetrics",
    "CreativeMetrics",
    "UserRevenueCurve",
    "RetentionCurve",
    "GameplayMetrics",
    "GrowthDataEvent",
    "ConnectorConfig",
    "ConnectorInfo",
    # Core
    "BaseConnector",
    "ConnectorRegistry",
]