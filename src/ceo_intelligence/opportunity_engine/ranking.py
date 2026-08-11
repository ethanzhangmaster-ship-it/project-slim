"""E17.2 机会排序。

优先级分数（用户指定公式）：

    Priority = Impact × Confidence × Urgency ÷ Risk

风险在分母，故风险越高优先级越低。risk 下限保护 0.1 防除零。
"""
from __future__ import annotations

from typing import List

from .models import GrowthOpportunity


def priority_score(o: GrowthOpportunity) -> float:
    return (o.expected_impact * o.confidence * o.urgency) / max(o.risk, 0.1)


def rank(opportunities: List[GrowthOpportunity]) -> List[GrowthOpportunity]:
    for o in opportunities:
        o.priority = round(priority_score(o), 4)
    return sorted(opportunities, key=lambda x: x.priority, reverse=True)
