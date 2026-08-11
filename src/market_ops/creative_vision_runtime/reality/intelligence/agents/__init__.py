"""E12.3 — Business Intelligence Agents。

三个业务 Agent 消费 Reality 分析数据，输出可执行的优化决策：

  ProductIntelligenceAgent      → 产品优化建议 (调关卡/改教程/优化体验)
  MonetizationIntelligenceAgent → 收入提升方案 (Offer/定价/资源包)
  UAIntelligenceAgent           → 投放优化建议 (扩量/暂停/Lookalike)

数据流：
  Analyzers (Lifecycle/Funnel/Retention/Monetization)
       │
       ▼
  Business Intelligence Agents
       │
       ├── ProductOptimizationAction[]
       ├── RevenueOptimizationAction[]
       └── UAOptimizationAction[]
       │
       ▼
  Decision Engine (执行层)
"""

from .base_agent import BaseAgent, OptimizationAction, ActionPriority
from .product_agent import ProductIntelligenceAgent, ProductOptimizationAction
from .monetization_agent import (
    MonetizationIntelligenceAgent,
    RevenueOptimizationAction,
)
from .ua_agent import UAIntelligenceAgent, UAOptimizationAction

__all__ = [
    # Base
    "BaseAgent",
    "OptimizationAction",
    "ActionPriority",
    # Agents
    "ProductIntelligenceAgent",
    "ProductOptimizationAction",
    "MonetizationIntelligenceAgent",
    "RevenueOptimizationAction",
    "UAIntelligenceAgent",
    "UAOptimizationAction",
]
