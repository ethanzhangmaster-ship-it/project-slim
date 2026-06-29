"""Creative Intelligence Layer - 图片素材智能分析层

模块组成:
- feature_engine (M1): Feature Intelligence Engine - 图片→Feature
- feature_db (M2): Creative Feature Database - DuckDB存储
- analytics_engine (M3): Feature Analytics Engine - 特效效果统计
- pattern_discovery (M4): Winner Pattern Discovery - 赢家规律发现
- knowledge_base (M5): Creative Knowledge Base - 统一知识库
- creative_planner (M6): Creative Planner - 知识驱动Prompt生成
- prediction_engine (M7): Creative Prediction - 预测CTR/CVR/CPI/ROAS
- feedback_learning (M8): Feedback Learning - 每日持续学习
- dashboard: Creative Intelligence Dashboard - 可视化

复用现有系统:
- Facebook Ads API (数据源)
- Creative DNA (标签推断)
- Creative Factory (图片生成)
- DuckDB creative_performance表 (性能数据)
- GeneMemory/WinnerMemory/LoserMemory (记忆层)
"""
from market_ops.creative_intelligence.feature_engine import FeatureIntelligenceEngine
from market_ops.creative_intelligence.feature_db import FeatureDatabase
from market_ops.creative_intelligence.analytics_engine import FeatureAnalyticsEngine
from market_ops.creative_intelligence.pattern_discovery import WinnerPatternDiscovery
from market_ops.creative_intelligence.knowledge_base import CreativeKnowledgeBase
from market_ops.creative_intelligence.creative_planner import CreativePlanner
from market_ops.creative_intelligence.prediction_engine import CreativePredictionEngine
from market_ops.creative_intelligence.feedback_learning import FeedbackLearning
from market_ops.creative_intelligence.dashboard import CreativeDashboard
from market_ops.creative_intelligence.models import CreativeFeature

__all__ = [
    "FeatureIntelligenceEngine",
    "FeatureDatabase",
    "FeatureAnalyticsEngine",
    "WinnerPatternDiscovery",
    "CreativeKnowledgeBase",
    "CreativePlanner",
    "CreativePredictionEngine",
    "FeedbackLearning",
    "CreativeDashboard",
    "CreativeFeature",
]
__version__ = "1.0"
