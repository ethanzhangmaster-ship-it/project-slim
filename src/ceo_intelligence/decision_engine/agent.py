"""E17.3 主入口：GrowthDecisionEngine。

输入：E17.2 的 OpportunityReport（或直接一批 GrowthOpportunity）
输出：DecisionReport（CEO 优先级清单 + 决策明细 + 出口分布摘要）

并提供 run_pipeline() 串联 E17.1→E17.2→E17.3（供端到端测试与每日自动运行）。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.ceo_intelligence.opportunity_engine.agent import GrowthOpportunityAgent
from src.ceo_intelligence.opportunity_engine.models import (
    GrowthOpportunity,
    OpportunityReport,
)
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.snapshot import CompanySnapshot

from .models import DecisionReport, DecisionType, GrowthDecision
from .scoring import ceo_priority_list
from .validator import DecisionValidator


class GrowthDecisionEngine:
    def __init__(self, validator: DecisionValidator):
        self.validator = validator

    # ------------------------------------------------------------------ #
    def analyze(
        self,
        report: OpportunityReport,
        *,
        segment: str = "global",
        top_n: int = 10,
    ) -> DecisionReport:
        return self.analyze_opportunities(
            report.top_priority, segment=segment, top_n=top_n
        )

    def analyze_opportunities(
        self,
        opportunities: List[GrowthOpportunity],
        *,
        segment: str = "global",
        top_n: int = 10,
    ) -> DecisionReport:
        decisions: List[GrowthDecision] = [
            self.validator.validate(o, segment=segment) for o in opportunities
        ]
        return self._build_report(decisions, top_n)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_report(
        decisions: List[GrowthDecision], top_n: int
    ) -> DecisionReport:
        counts = {t.value: 0 for t in DecisionType}
        total_expected = 0.0
        for d in decisions:
            counts[d.decision_type.value] += 1
            if d.decision_type in (DecisionType.EXECUTE, DecisionType.APPROVE):
                total_expected += d.expected_value
        ceo_list = ceo_priority_list(decisions, top_n)
        top = ceo_list[0].game_id if ceo_list else ""
        summary = {
            "execute": counts[DecisionType.EXECUTE.value],
            "approve": counts[DecisionType.APPROVE.value],
            "observe": counts[DecisionType.OBSERVE.value],
            "reject": counts[DecisionType.REJECT.value],
            "total_expected_value": round(total_expected, 4),
            "top_decision": top,
        }
        return DecisionReport(
            total_decisions=len(decisions),
            ceo_priority_list=ceo_list,
            decisions=decisions,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    # 人工审批闭环透传
    # ------------------------------------------------------------------ #
    def approve(self, audit_id: str, **kw) -> bool:
        return self.validator.approve(audit_id, **kw)

    def reject(self, audit_id: str, **kw) -> bool:
        return self.validator.reject(audit_id, **kw)

    @property
    def pending_approvals(self) -> list:
        return self.validator.pending_approvals


# --------------------------------------------------------------------------- #
# 端到端流水线：Reality Hub → Opportunity Engine → Decision Engine
# --------------------------------------------------------------------------- #
def run_pipeline(
    company: CompanySnapshot,
    *,
    store: Optional[GrowthFeatureStore] = None,
    opportunity_memory=None,
    decision_memory=None,
    action_sink=None,
    segment: str = "global",
    top_n: int = 10,
    approval_queue_path: str = "data/ceo/approval_queue.jsonl",
    audit_dir: str = "data/ceo/audit",
    created_at: str = "",
) -> Tuple[OpportunityReport, DecisionReport]:
    """串联 E17.1 → E17.2 → E17.3，产出机会报告与决策报告。"""
    opp_agent = GrowthOpportunityAgent(memory=opportunity_memory)
    opp_report = opp_agent.analyze(
        company, store=store, segment=segment, created_at=created_at, top_n=top_n
    )
    validator = DecisionValidator(
        memory=decision_memory,
        action_sink=action_sink,
        approval_queue_path=approval_queue_path,
        audit_dir=audit_dir,
    )
    engine = GrowthDecisionEngine(validator)
    dec_report = engine.analyze(opp_report, segment=segment, top_n=top_n)
    return opp_report, dec_report
