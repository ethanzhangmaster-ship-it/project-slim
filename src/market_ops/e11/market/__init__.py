"""E11.5 Market — IAP 产品市场反馈层。

将外部平台的 UA 数据、用户行为数据和 IAP 付费数据
统一为 PerformanceFeedback，驱动 E11 进化。

E11.5.1 — Performance Feedback Adapter
  - PerformanceFeedback: 统一反馈对象
  - UAMetrics: UA 投放指标
  - EngagementMetrics: 用户行为指标
  - IAPMetrics: 商业化指标
  - PerformanceAdapter: 适配器抽象基类
  - UAPerformanceAdapter: UA 数据适配器
  - IAPPerformanceAdapter: IAP 数据适配器
  - AnalyticsPerformanceAdapter: 用户行为适配器
  - FeedbackRepository: 反馈存储
  - MarketError / MarketAdapterError / InvalidMetricsError / RepositoryError

E11.5.2 — Market Signal Processor
  - SignalType: 信号类型 (ACQUISITION / ENGAGEMENT / MONETIZATION / CREATIVE)
  - SignalStrength: 信号强度 (VERY_STRONG / STRONG / MEDIUM / WEAK / NONE)
  - MarketSignal: 市场信号 (creative_id + signals + confidence)
  - MarketSignalProcessor: 信号处理器

数据流：
  Facebook/Google Ads → UA Adapter →┐
  Firebase/GA → Analytics Adapter →├→ PerformanceFeedback → Repository
  RevenueCat/App Store → IAP Adapter→┘
                                        ↓
                              MarketSignalProcessor
                                        ↓
                                  MarketSignal
                                        ↓
                              E11.5.3 Fitness Engine
"""

from .feedback_schema import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
    PerformanceFeedback,
)
from .performance_adapter import PerformanceAdapter
from .ua_adapter import UAPerformanceAdapter
from .iap_adapter import IAPPerformanceAdapter
from .analytics_adapter import AnalyticsPerformanceAdapter
from .feedback_repository import FeedbackRepository
from .market_exceptions import (
    MarketError,
    MarketAdapterError,
    InvalidMetricsError,
    RepositoryError,
)
from .market_signal_schema import (
    SignalType,
    SignalStrength,
    MarketSignal,
)
from .signal_processor import MarketSignalProcessor
from .fitness_schema import (
    GenomeFitness,
    FitnessHistoryEntry,
    FitnessHistory,
)
from .fitness_calculator import FitnessCalculator
from .fitness_engine import FitnessEngine
from .feedback_loop_schema import (
    LoopStatus,
    EvolutionFeedbackEvent,
    FeedbackLoopState,
    EvolutionEventStore,
)
from .evolution_bridge import EvolutionBridge
from .feedback_loop import FeedbackLoopController

__all__ = [
    # E11.5.1 Schema
    "UAMetrics",
    "EngagementMetrics",
    "IAPMetrics",
    "PerformanceFeedback",
    # E11.5.1 Adapters
    "PerformanceAdapter",
    "UAPerformanceAdapter",
    "IAPPerformanceAdapter",
    "AnalyticsPerformanceAdapter",
    # E11.5.1 Repository
    "FeedbackRepository",
    # E11.5.1 Exceptions
    "MarketError",
    "MarketAdapterError",
    "InvalidMetricsError",
    "RepositoryError",
    # E11.5.2 Signal
    "SignalType",
    "SignalStrength",
    "MarketSignal",
    "MarketSignalProcessor",
    # E11.5.3 Fitness
    "GenomeFitness",
    "FitnessHistoryEntry",
    "FitnessHistory",
    "FitnessCalculator",
    "FitnessEngine",
    # E11.5.4 Feedback Loop
    "LoopStatus",
    "EvolutionFeedbackEvent",
    "FeedbackLoopState",
    "EvolutionEventStore",
    "EvolutionBridge",
    "FeedbackLoopController",
]