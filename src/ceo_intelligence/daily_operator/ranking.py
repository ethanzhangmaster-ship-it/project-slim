"""E17.9 — 优先级排序（Priority Ranking）。

输入：E17.3 DecisionReport + E17.8 PortfolioSimulationReport
输出：List[GamePriority]（Top N，默认 10）

评分：Priority = |Impact| × Confidence × Urgency × SimulationScore
- SimulationScore 由 E17.8 闸门确定性映射：PASS=1.0 / REVIEW=0.6 / BLOCK=0.1；
  未模拟（OBSERVE / REJECT，本来不落地）= 0.5 中性分。
- 排序确定性：分数降序，同分按 game_id 升序、action 升序。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import GamePriority, priority_score

# E17.8 闸门 → 模拟得分（确定性查表）
GATE_SCORE: Dict[str, float] = {
    "pass": 1.0,
    "review": 0.6,
    "block": 0.1,
}
NO_SIMULATION_SCORE = 0.5


def _gate_of(decision, sim_by_audit_id: Dict[str, object]) -> str:
    sim = sim_by_audit_id.get(decision.audit_id)
    if sim is None:
        return ""
    status = sim.flag.status
    return status.value if hasattr(status, "value") else str(status)


def rank_priorities(
    dec_report,
    sim_report=None,
    top_n: int = 10,
) -> List[GamePriority]:
    """把决策 + 模拟闸门压成 CEO Top N 优先级清单。"""
    sim_by_id: Dict[str, object] = {}
    if sim_report is not None:
        for s in sim_report.simulations:
            if s.decision_audit_id:
                sim_by_id[s.decision_audit_id] = s

    rows: List[GamePriority] = []
    for d in dec_report.decisions:
        gate = _gate_of(d, sim_by_id)
        sim_score = GATE_SCORE.get(gate, NO_SIMULATION_SCORE)
        dtype = (
            d.decision_type.value
            if hasattr(d.decision_type, "value")
            else str(d.decision_type)
        )
        opp_type = d.opportunity_id.rsplit(":", 1)[-1] if d.opportunity_id else ""
        rows.append(
            GamePriority(
                rank=0,
                game_id=d.game_id,
                action=d.action,
                problem=d.reason or d.action,
                opportunity_type=opp_type,
                decision_type=dtype,
                gate=gate,
                priority_score_value=priority_score(
                    d.expected_value, d.confidence, d.urgency, sim_score
                ),
                impact=d.expected_value,
                confidence=d.confidence,
                urgency=d.urgency,
                sim_score=sim_score,
            )
        )

    rows.sort(
        key=lambda p: (-p.priority_score_value, p.game_id, p.action)
    )
    out = rows[: max(0, top_n)]
    for i, p in enumerate(out, start=1):
        p.rank = i
    return out


__all__ = ["rank_priorities", "GATE_SCORE", "NO_SIMULATION_SCORE"]
