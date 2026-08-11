"""E11.6.2 Adjust Revenue Adapter — Adjust 收入数据适配层。

将 Adjust 原始归因事件映射为 E11 RevenueEvent，连接 P04 与 Reality Layer。

模块：
  - adjust_schema: AdjustRawEvent, RevenueType
  - adjust_adapter: AdjustAdapter (AdjustRawEvent → RevenueEvent)
  - adjust_mapper: AdjustCreativeMapper (creative_id → genome_id)

数据流：
  Adjust Raw Data → AdjustAdapter → RevenueEvent → Genome Attribution → Fitness
"""

from .adjust_schema import (
    AdjustRawEvent,
    RevenueType,
)
from .adjust_adapter import AdjustAdapter
from .adjust_mapper import AdjustCreativeMapper

__all__ = [
    "AdjustRawEvent",
    "RevenueType",
    "AdjustAdapter",
    "AdjustCreativeMapper",
]