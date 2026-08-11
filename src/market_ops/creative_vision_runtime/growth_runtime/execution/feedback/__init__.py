"""E13.6.5 Feedback Loop + E15.5 Execution Result Bridge — 反馈闭环模块.

将执行结果转化为量化 Reward，驱动 Memory 系统更新，
形成完整的 Observe → Understand → Decide → Execute → Learn → Improve 闭环。

核心组件:
  - ExecutionFeedback: 执行反馈数据模型
  - RewardSignal: 四维 Reward 信号 (execution/efficiency/safety/outcome)
  - FeedbackResult: 反馈处理结果
  - FeedbackConfig: 反馈计算参数配置
  - ResultAnalyzer: 执行结果分析器
  - RewardCalculator: Reward 计算器
  - FeedbackProcessor: 反馈处理器 (写入 Memory)
  - FeedbackLoop: 主闭环控制器 (E13.6.5)
  - ExecutionResultBridge: 执行结果 → 业务结果桥接 (E15.5)

连接:
  E13.6.3 ExecutionEngine → E13.6.5 FeedbackLoop → E13.5.5 DecisionMemory → E13.4 MemoryEvolution
  E15 ExecutionEngine → E15.5 ExecutionResultBridge → E13.4.1 ExperienceStore → E13.4.2 PatternMemory
"""

from .execution_result_bridge import (
    BridgeEntry,
    BridgeResult,
    ExecutionResultBridge,
)
from .feedback_loop import FeedbackLoop
from .feedback_processor import FeedbackProcessor
from .models import (
    ExecutionFeedback,
    FeedbackConfig,
    FeedbackResult,
    RewardSignal,
    create_conservative_config,
    create_default_config,
    create_exploration_config,
)
from .result_analyzer import ResultAnalyzer
from .reward_calculator import RewardCalculator

__all__ = [
    # Models
    "ExecutionFeedback",
    "RewardSignal",
    "FeedbackResult",
    "FeedbackConfig",
    # Factory
    "create_default_config",
    "create_exploration_config",
    "create_conservative_config",
    # Core
    "ResultAnalyzer",
    "RewardCalculator",
    "FeedbackProcessor",
    "FeedbackLoop",
    # E15.5 Execution Result Bridge
    "ExecutionResultBridge",
    "BridgeEntry",
    "BridgeResult",
]