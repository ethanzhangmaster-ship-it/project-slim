"""E6.1: Knowledge layer — Category Memory + Trend Memory.

    category_memory.py — Tracks category evolution over time
    trend_memory.py — Tracks trend lifecycles from emergence to decline
"""

from .market_graph import MarketKnowledgeGraph, GraphNode, CategoryNode
from .category_memory import CategoryMemory
from .trend_memory import TrendMemory

__all__ = ["MarketKnowledgeGraph", "CategoryMemory", "TrendMemory",
           "GraphNode", "CategoryNode"]
