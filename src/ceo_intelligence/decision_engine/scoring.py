"""E17.3 — 决策打分引擎。

公式（与 E17.2 机会优先级同构，公司级复用）：

    Decision Score = Impact × Confidence × Urgency ÷ Risk

- Impact：机会的业务影响（相对收益预期 expected_impact）
- Confidence：数据/历史置信度（可被 Decision Memory 加成）
- Urgency：问题紧迫度（收入下跌等越紧迫越高）
- Risk：风险（下限 0.1 防除零）

CEO 不看单一指标，看「收益 / 风险 / 成功概率」的均衡。
"""
from __future__ import annotations

from typing import List

from .models import CeoDecisionItem, GrowthDecision


def score_decision(
    *,
    impact: float,
    confidence: float,
    urgency: float,
    risk: float,
) -> float:
    """Decision Score = Impact × Confidence × Urgency ÷ Risk（risk 下限 0.1）。"""
    safe_risk = max(risk, 0.1)
    return (impact * confidence * urgency) / safe_risk


def ceo_priority_list(
    decisions: List[GrowthDecision], top_n: int = 10
) -> List[CeoDecisionItem]:
    """把决策按决策分排序，产出 CEO 优先级清单（Top N）。"""
    scored = []
    for d in decisions:
        sc = score_decision(
            impact=d.expected_value,
            confidence=d.confidence,
            urgency=d.urgency,
            risk=d.risk,
        )
        scored.append((sc, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    items: List[CeoDecisionItem] = []
    for i, (_, d) in enumerate(scored[:top_n], start=1):
        items.append(
            CeoDecisionItem(
                rank=i,
                game_id=d.game_id,
                action=d.action,
                expected_value=d.expected_value,
                confidence=d.confidence,
                decision_type=d.decision_type,
            )
        )
    return items
