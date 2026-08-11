"""E11.5.2 — Opportunity Trigger Layer。

Raw Signals → OpportunityDetector → OpportunitySignal → TriggerEngine → TriggerDecision → Controller。

核心职责：
  - 检测市场/竞品/品类机会信号
  - 规则评估决定是否触发进化循环
  - 连接 E11.5.1 AutonomousCreativeController
"""
from .models import (
    OpportunitySignal,
    TriggerDecision,
    TriggerAction,
)
from .rules import (
    Rule,
    build_default_rules,
)
from .opportunity_detector import OpportunityDetector
from .trigger_engine import TriggerEngine

__all__ = [
    "OpportunitySignal",
    "TriggerDecision",
    "TriggerAction",
    "Rule",
    "build_default_rules",
    "OpportunityDetector",
    "TriggerEngine",
]