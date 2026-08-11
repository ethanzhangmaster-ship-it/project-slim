"""L14 Full Stack Ads System v1 — 14_full_stack Package

Production Full Stack Ads System - 自主多平台广告交易系统

层级架构：
- L0: Creative Intelligence Layer（已有）
- L1: Asset Production Layer
- L2: Ad Platform Orchestrator
- L3: Traffic & Tracking Layer
- L4: Attribution Engine
- L5: Metrics Engine
- L6: Budget Intelligence Engine
- L7: Learning Loop（已有 P2 升级版）

核心文件：
- l1_asset_production.py：Image/Video Renderer + Variant Generator
- l2_ad_platform_orchestrator.py：Meta/TikTok/Google Ads 多平台支持
- l3_tracking_layer.py：Pixel/SDK/CAPI 真实数据回收
- l456_attribution_metrics_budget.py：Attribution + Metrics + Budget Intelligence
- full_stack_pipeline.py：13步生产版主执行器
"""
from __future__ import annotations

import importlib

_PKG = "market_ops.creative_growth_loop.14_full_stack"

_l1 = importlib.import_module(f"{_PKG}.l1_asset_production")
AssetProductionEngine = _l1.AssetProductionEngine
ImageRenderer = _l1.ImageRenderer
VariantGenerator = _l1.VariantGenerator

_l2 = importlib.import_module(f"{_PKG}.l2_ad_platform_orchestrator")
MultiPlatformOrchestrator = _l2.MultiPlatformOrchestrator
MetaAdsClient = _l2.MetaAdsClient
TikTokAdsClient = _l2.TikTokAdsClient
GoogleAdsClient = _l2.GoogleAdsClient

_l3 = importlib.import_module(f"{_PKG}.l3_tracking_layer")
EventStreamCollector = _l3.EventStreamCollector
PixelTracker = _l3.PixelTracker
ConversionAPIClient = _l3.ConversionAPIClient

_l456 = importlib.import_module(f"{_PKG}.l456_attribution_metrics_budget")
AttributionEngineV2 = _l456.AttributionEngineV2
MetricsEngine = _l456.MetricsEngine
BudgetIntelligenceEngine = _l456.BudgetIntelligenceEngine

_pipeline = importlib.import_module(f"{_PKG}.full_stack_pipeline")
FullStackAdsPipeline = _pipeline.FullStackAdsPipeline
FullStackReport = _pipeline.FullStackReport