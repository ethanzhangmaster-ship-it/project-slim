"""Video Creative Intelligence Layer - V4.2.2

Facebook 创意系统的大脑层（Brain Layer）。
所有模块统一调用此层，不再各自维护知识和规则。

模块组成：
- memory_engine: 长期创意记忆（DuckDB 存储）
- feature_store: 统一特征定义和标准化
- knowledge_graph: 创意知识图谱（networkx）
- predictor_engine: 统一预测入口（插件架构）
- portfolio_engine: 创意组合管理（Safe/Growth/Explore）
- learning_engine: 增量学习引擎
- rule_engine: 统一规则管理
- intelligence_api: 统一 API 入口
- dashboard: 可视化报告
"""
from src.market_ops.video_intelligence.memory_engine import VideoMemoryEngine
from src.market_ops.video_intelligence.feature_store import VideoFeatureStore
from src.market_ops.video_intelligence.knowledge_graph import CreativeKnowledgeGraph
from src.market_ops.video_intelligence.predictor_engine import PredictorEngine
from src.market_ops.video_intelligence.portfolio_engine import PortfolioEngine
from src.market_ops.video_intelligence.learning_engine import VideoLearningEngine
from src.market_ops.video_intelligence.rule_engine import RuleEngine
from src.market_ops.video_intelligence.intelligence_api import CreativeIntelligence, get_intelligence
from src.market_ops.video_intelligence.dashboard import IntelligenceDashboard

__all__ = [
    "VideoMemoryEngine",
    "VideoFeatureStore",
    "CreativeKnowledgeGraph",
    "PredictorEngine",
    "PortfolioEngine",
    "VideoLearningEngine",
    "RuleEngine",
    "CreativeIntelligence",
    "IntelligenceDashboard",
    "get_intelligence",
]

__version__ = "4.2.2"
