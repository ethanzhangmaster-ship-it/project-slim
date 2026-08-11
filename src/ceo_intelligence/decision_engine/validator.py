"""E17.3 — 决策验证器 / 路由（三道门执行层）。

复用既有生产基础设施（不重造）：
- E16.1.1 JsonlApprovalQueue：人工审批信箱（直接 import 复用）
- EP0 AuditTrail：每条决策不可变落盘（record_decision / record_approval）

流程：
    Opportunity
      → simulate (SimulationResult)
      → memory.confidence_adjust (历史加成)
      → policy.decide (三道门 → DecisionType)
      → 路由：
            EXECUTE  → action_sink.submit（SIM 下无 sink，不触发真实 API）
            APPROVE  → JsonlApprovalQueue.enqueue（人工审批）
            OBSERVE  → 仅审计
            REJECT   → 仅审计
      → AuditTrail.record_decision（始终写入，全链路可追溯）
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from audit.trail import ApprovalRecord, AuditTrail, DecisionRecord
from src.revenue_intelligence.decision.validator import JsonlApprovalQueue

from src.ceo_intelligence.opportunity_engine.models import GrowthOpportunity

from .memory import DecisionMemory
from .models import DecisionSink, DecisionType, GrowthDecision, action_label
from .policy import CompanyDecisionPolicy
from .scoring import score_decision
from .simulator import MemoryStats, OpportunitySimulator


class DecisionValidator:
    """公司级三道门执行器：把机会转成可追溯的决策。"""

    def __init__(
        self,
        *,
        policy: Optional[CompanyDecisionPolicy] = None,
        approval_queue_path: str = "data/ceo/approval_queue.jsonl",
        audit_dir: str = "data/ceo/audit",
        memory: Optional[DecisionMemory] = None,
        action_sink: Optional[DecisionSink] = None,
    ):
        self.policy = policy or CompanyDecisionPolicy()
        self.simulator = OpportunitySimulator()
        self.memory = memory
        self.action_sink = action_sink
        self.queue = JsonlApprovalQueue(approval_queue_path)
        self.audit = AuditTrail(audit_dir)

    # ------------------------------------------------------------------ #
    def validate(
        self, opp: GrowthOpportunity, *, segment: str = "global"
    ) -> GrowthDecision:
        # 1) 模拟
        mem_stats: Optional[MemoryStats] = None
        if self.memory is not None:
            mem_stats = self.memory.stats(opp.game_id, opp.type.value)
        sim = self.simulator.simulate(opp.type.value, mem_stats)

        # 2) 记忆置信度加成
        conf = opp.confidence
        if self.memory is not None:
            conf = self.memory.confidence_adjust(conf, opp.game_id, opp.type.value)
        conf = round(conf, 4)

        # 3) 三道门
        decision_type, reason = self.policy.decide(
            game_id=opp.game_id,
            opportunity_type=opp.type.value,
            expected_value=opp.expected_impact,
            confidence=conf,
            risk=sim.risk,
        )

        # 4) 组装决策
        decision = GrowthDecision(
            game_id=opp.game_id,
            opportunity_id=f"{opp.game_id}:{opp.type.value}",
            action=action_label(opp.type.value, opp.game_id),
            decision_type=decision_type,
            expected_value=opp.expected_impact,
            confidence=conf,
            risk=sim.risk,
            urgency=opp.urgency,
            reason=reason,
            simulation=sim,
        )

        # 5) 路由 + 审计
        self._route(decision)
        self._audit(decision, opp, segment)
        return decision

    # ------------------------------------------------------------------ #
    def _route(self, decision: GrowthDecision) -> None:
        if decision.decision_type == DecisionType.EXECUTE:
            if self.action_sink is not None:
                decision.executed = bool(self.action_sink.submit(decision))
        elif decision.decision_type == DecisionType.APPROVE:
            decision.queued = True
            self.queue.enqueue(decision)
        # OBSERVE / REJECT：仅审计，不执行、不入队

    def _audit(
        self, decision: GrowthDecision, opp: GrowthOpportunity, segment: str
    ) -> None:
        score = score_decision(
            impact=decision.expected_value,
            confidence=decision.confidence,
            urgency=decision.urgency,
            risk=decision.risk,
        )
        self.audit.record_decision(
            DecisionRecord(
                agent="ceo_decision_engine",
                action=decision.action,
                game_id=decision.game_id,
                reason=f"[{decision.decision_type.value}] {decision.reason}",
                confidence=decision.confidence,
                decision_id=decision.audit_id,
                inputs={
                    "opportunity_id": decision.opportunity_id,
                    "opportunity_type": opp.type.value,
                    "expected_value": decision.expected_value,
                    "risk": decision.risk,
                    "urgency": decision.urgency,
                    "decision_score": round(score, 4),
                    "segment": segment,
                    "simulation": decision.simulation.to_dict()
                    if decision.simulation
                    else None,
                },
            )
        )

    # ------------------------------------------------------------------ #
    # 人工审批闭环（E17.6 执行前的人为闸门）
    # ------------------------------------------------------------------ #
    def approve(self, audit_id: str, *, approver: str = "human") -> bool:
        entry = self.queue.get(audit_id)
        if entry is None or entry.get("status") != "pending":
            return False
        if self.queue.has_resolution(audit_id):
            return False
        executed = False
        if self.action_sink is not None:
            # 取出原决策重新提交执行
            stored = self._load_queued(audit_id)
            if stored is not None:
                executed = bool(self.action_sink.submit(stored))
        self.queue.resolve(audit_id, "approved", executed=executed)
        self.audit.record_approval(
            ApprovalRecord(
                decision_id=audit_id,
                approver=approver,
                approved=True,
                reason="human approved",
            )
        )
        return True

    def reject(self, audit_id: str, *, approver: str = "human") -> bool:
        entry = self.queue.get(audit_id)
        if entry is None or entry.get("status") != "pending":
            return False
        if self.queue.has_resolution(audit_id):
            return False
        self.queue.resolve(audit_id, "rejected", executed=False)
        self.audit.record_approval(
            ApprovalRecord(
                decision_id=audit_id,
                approver=approver,
                approved=False,
                reason="human rejected",
            )
        )
        return True

    def _load_queued(self, audit_id: str) -> Optional[GrowthDecision]:
        entry = self.queue.get(audit_id)
        if entry is None:
            return None
        try:
            return GrowthDecision.from_dict(entry)
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    @property
    def pending_approvals(self) -> list:
        # 复用 JsonlApprovalQueue，但其 pending() 不剔除已决议项；
        # 此处过滤已由 has_resolution 标记的 audit_id，得到真实待办。
        return [
            e
            for e in self.queue.pending()
            if not self.queue.has_resolution(e.get("audit_id", ""))
        ]
