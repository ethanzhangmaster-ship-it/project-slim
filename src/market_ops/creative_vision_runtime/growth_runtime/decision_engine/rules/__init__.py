"""E13.3.1 Rules Init — 规则模块导出."""

from .creative_rules import (
    CreativeFatigueDetector,
    CreativeUnderperformDetector,
    CreativeWinnerDetector,
)
from .revenue_rules import (
    LTVUpsideDetector,
    ROASDropDetector,
)
from .ua_rules import (
    BudgetWasteDetector,
    MonetizationIssueDetector,
    ScaleOpportunityDetector,
)

__all__ = [
    "CreativeFatigueDetector",
    "CreativeWinnerDetector",
    "CreativeUnderperformDetector",
    "ROASDropDetector",
    "LTVUpsideDetector",
    "ScaleOpportunityDetector",
    "BudgetWasteDetector",
    "MonetizationIssueDetector",
]