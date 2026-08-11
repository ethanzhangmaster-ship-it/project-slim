"""E13.3 Decision Strategies — 决策策略模块.

E13.3.2 Opportunity Mappers:
  将 GrowthSignal 转换为 GrowthOpportunity 的策略映射器.

E13.3.3 Executors:
  将 GrowthOpportunity 转换为 ExecutionAction 的执行器.
"""

from .creative_executor import CreativeExecutor
from .creative_opportunities import CreativeOpportunityMapper
from .revenue_executor import RevenueExecutor
from .revenue_opportunities import RevenueOpportunityMapper
from .ua_executor import UAExecutor
from .ua_opportunities import UAOpportunityMapper

__all__ = [
    # E13.3.2 Opportunity Mappers
    "CreativeOpportunityMapper",
    "UAOpportunityMapper",
    "RevenueOpportunityMapper",
    # E13.3.3 Executors
    "CreativeExecutor",
    "UAExecutor",
    "RevenueExecutor",
]