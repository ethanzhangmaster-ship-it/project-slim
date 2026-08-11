"""
P3.5.2 — Operator Layer 决策学习反馈适配器。

把既有决策入口的产物（``PortfolioOptimizationResult`` / ``StrategyLoopResult``）
转成 ``DecisionKnowledgeRecord`` 并交给 ``KnowledgeFeedbackRecorder`` 写入
Knowledge Graph。

定位（用户 P3.5.2 契约冻结点 6/7）：

- ``PortfolioOptimizer`` / ``StrategyLoop`` **不**感知 Knowledge storage——
  业务计算层纯净（Optimizer 只编排、Loop 只产策略）；
- 反馈由 **Operator Layer**（本模块 / pipeline 阶段）消费 Result 后统一写入，
  Graph Writer 唯一入口仍是 ``KnowledgeFeedbackRecorder.record()``。

fail-open：recorder 为 None / result 为空 → 静默返回 0，不中断主链。
"""
from __future__ import annotations

from typing import Any

from src.ceo_intelligence.growth_memory_graph.feedback import DecisionKnowledgeRecord


def record_portfolio_feedback(recorder: Any, result: Any) -> int:
    """把 ``PortfolioOptimizationResult`` 的每个候选写成一条 CEO_DECISION。

    返回写入条数；recorder 为 None / result 为空 → 0（fail-open）。
    ``outcome`` 留空——realized 结果由后续 monitor 钩子 ``attach_outcome`` 回流。
    """
    if recorder is None or result is None:
        return 0
    ranked = list(getattr(result, "ranked_games", []) or [])
    n = 0
    for cand in ranked:
        action = (
            cand.recommended_action.value
            if hasattr(cand.recommended_action, "value")
            else str(cand.recommended_action)
        )
        rec = DecisionKnowledgeRecord(
            game_id=cand.game_id,
            decision_type="portfolio",
            source="PORTFOLIO",
            decision_payload={
                "action": action,
                "priority": float(getattr(cand, "priority", 0.0) or 0.0),
                "rank": int(getattr(cand, "rank", 0) or 0),
                "confidence": float(getattr(cand, "confidence", 0.0) or 0.0),
                "action_state": str(getattr(cand, "action_state", "") or ""),
            },
            knowledge_signal=cand.knowledge_signal,
            outcome=None,
        )
        recorder.record(rec)
        n += 1
    return n


def record_strategy_feedback(
    recorder: Any, result: Any, game_id: str = ""
) -> int:
    """把 ``StrategyLoopResult`` 的每个提案写成一条 CEO_DECISION。

    ``outcome`` 用提案有效置信（模拟，已知）；realized 结果由后续钩子回流。
    ``game_id`` 由调用方注入（pipeline 阶段通常为 fleet 级 → 传空串）。
    """
    if recorder is None or result is None:
        return 0
    proposals = list(getattr(result, "proposals", []) or [])
    n = 0
    for p in proposals:
        action = getattr(p, "proposed_change", "") or getattr(
            p, "current_strategy", ""
        )
        sim_sr = getattr(p, "knowledge_confidence", None)
        if sim_sr is None:
            sim_sr = getattr(p, "confidence", 0.0)
        rec = DecisionKnowledgeRecord(
            game_id=game_id,
            decision_type="strategy",
            source="STRATEGY",
            decision_payload={
                "action": str(action),
                "current_strategy": str(getattr(p, "current_strategy", "") or ""),
                "expected_impact": str(getattr(p, "expected_impact", "") or ""),
                "confidence": float(getattr(p, "confidence", 0.0) or 0.0),
                "knowledge_confidence": getattr(p, "knowledge_confidence", None),
                "requires_simulation": bool(
                    getattr(p, "requires_simulation", True)
                ),
            },
            knowledge_signal=getattr(p, "knowledge_signal", None),
            outcome={"success_rate": float(sim_sr or 0.0), "simulated": True},
        )
        recorder.record(rec)
        n += 1
    return n


__all__ = ["record_portfolio_feedback", "record_strategy_feedback"]
