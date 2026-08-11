"""P1.7.4 — 决策守卫（Reality Decision Gate）。

在 E17.3 决策引擎与执行层之间加一道可信门：
    RealityScore < 0.5  → BLOCKED（禁止 EXECUTE，降级为 OBSERVE）
    RealityScore 0.5–0.8 → APPROVE（允许人工审批）
    RealityScore > 0.8   → EXECUTE（允许自动执行）

可独立使用，也可覆盖到 DecisionReport 的每个决策项上。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import RealityScore

# 门控阈值
BLOCKED_THRESHOLD = 0.5
APPROVE_THRESHOLD = 0.8


def decide_level(composite: float) -> str:
    """根据 RealityScore.composite 判定决策等级。"""
    if composite < BLOCKED_THRESHOLD:
        return "BLOCKED"
    if composite < APPROVE_THRESHOLD:
        return "APPROVE"
    return "EXECUTE"


def apply_level(score: RealityScore) -> RealityScore:
    """原地为 RealityScore 注入 decision_level。"""
    score.decision_level = decide_level(score.composite)
    return score


class RealityGate:
    """决策门控制器。

    核心 API:
        gate.apply(decision_type, game_id, score) → (gated_type, reason)
        gate.gate_company_report(scores, decision_report) → modified report
    """

    @staticmethod
    def can_execute(score: float) -> bool:
        return score >= APPROVE_THRESHOLD

    @staticmethod
    def can_approve(score: float) -> bool:
        return score >= BLOCKED_THRESHOLD

    @staticmethod
    def apply(decision_type: str, game_id: str, score: float) -> tuple:
        """对单个决策应用门控。

        Args:
            decision_type: 原始决策类型（EXECUTE / APPROVE / REJECT / OBSERVE）
            game_id: 游戏 ID
            score: RealityScore.composite

        Returns:
            (gated_type, reason)
        """
        level = decide_level(score)
        # 升级：任何决策都受最高等级限制
        if decision_type in ("REJECT", "OBSERVE"):
            # 反向决策不受门控限制
            return (decision_type, "非正向决策，不受 RealityGate 限制")

        if level == "BLOCKED":
            return ("OBSERVE", f"RealityScore={score:.2f}<{BLOCKED_THRESHOLD}，禁止自动执行")
        if level == "APPROVE":
            if decision_type == "EXECUTE":
                return ("APPROVE", f"RealityScore={score:.2f} 在 APPROVE 区间，需人工审批")
            return (decision_type, f"RealityScore={score:.2f}，允许人工审批")
        # EXECUTE level
        return (decision_type, f"RealityScore={score:.2f}>={APPROVE_THRESHOLD}，允许自动执行")

    @staticmethod
    def gate_decisions(
        decisions: List[Dict[str, Any]],
        scores: Dict[str, RealityScore],
    ) -> List[Dict[str, Any]]:
        """对一批决策应用门控并返回打标后的副本。

        每个 decision dict 期望有 "game_id" 和 "decision_type" 键。
        """
        gated: List[Dict[str, Any]] = []
        for d in decisions:
            gid = d.get("game_id", "")
            dt = d.get("decision_type", "OBSERVE")
            score = scores.get(gid)
            sc = score.composite if score else 0.0
            gated_type, reason = RealityGate.apply(dt, gid, sc)
            gd = dict(d)
            gd["gated_type"] = gated_type
            gd["reality_score"] = sc
            gd["gate_reason"] = reason
            gd["gated"] = (gated_type != dt)
            gated.append(gd)
        return gated
