"""E11 Phase 2 — Adjust Revenue Matching Layer。

将 Adjust 归因收入数据与 CreativeEntity 绑定，
形成"花费 vs 收入"的完整经济视图。

模块：
  - AdjustClient:            Adjust API 客户端
  - AdjustFetcher:           Adjust 数据抓取器
  - AdjustRevenueEntity:     Adjust 收入数据模型
  - AdjustCreativeMatcher:   4 级匹配逻辑
  - RevenueCalculator:       收入指标计算器（CPI/ARPU/ROAS/LTV）
  - AdjustSyncEngine:        完整同步流程编排器
  - AdjustStorage:           adjust.json 保存
  - AdjustDataQualityValidator: 数据质量检查

Usage:
    from market_ops.adjust_ingestion import (
        AdjustClient,
        AdjustFetcher,
        AdjustSyncEngine,
        AdjustRevenueEntity,
        AdjustCreativeMatcher,
        RevenueCalculator,
        AdjustStorage,
        AdjustDataQualityValidator,
    )

    # 完整同步流程
    client = AdjustClient(api_token="xxx", app_token="yyy")
    engine = AdjustSyncEngine(client, creative_storage)
    result = engine.sync(start_date="2026-07-01", end_date="2026-07-21")
    print(result.to_summary())
"""

from .adjust_client import AdjustClient, AdjustAPIError
from .adjust_fetcher import AdjustFetcher
from .models import AdjustRevenueEntity
from .matcher import AdjustCreativeMatcher, MatchResult, AdjustMatchReport
from .revenue_calculator import RevenueCalculator, RevenueMetrics
from .sync_engine import AdjustSyncEngine, AdjustSyncResult
from .storage import AdjustStorage
from .adjust_validator import AdjustDataQualityValidator, AdjustQualityReport

__all__ = [
    "AdjustClient",
    "AdjustAPIError",
    "AdjustFetcher",
    "AdjustRevenueEntity",
    "AdjustCreativeMatcher",
    "MatchResult",
    "AdjustMatchReport",
    "RevenueCalculator",
    "RevenueMetrics",
    "AdjustSyncEngine",
    "AdjustSyncResult",
    "AdjustStorage",
    "AdjustDataQualityValidator",
    "AdjustQualityReport",
]