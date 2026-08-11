"""E13.3.4 Decision Engine — 核心决策编排器.

核心职责: 编排 Growth Intelligence → Opportunity Detector → Creative Ranker
的完整决策流程，输出 DecisionReport。

决策流程:
  1. GrowthIntelligence.analyze(vectors) → GrowthInsight[]
  2. OpportunityDetector.detect(insights) → GrowthOpportunity[]
  3. CreativeRanker.rank(vectors) → CreativeRanking[]
  4. ActionMapper.map(opportunities) → DecisionAction[]
  5. 输出 DecisionReport

输入: CreativeFitnessVector[]
输出: DecisionReport
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from ..pipeline.models import CreativeFitnessVector
from .action_mapper import ActionMapper
from .creative_ranker import CreativeRanker
from .intelligence import GrowthIntelligence
from .models import (
    ActionType,
    DecisionReport,
)
from .opportunity_detector import OpportunityDetector


# ═══════════════════════════════════════════════════════════════
# Decision Engine
# ═══════════════════════════════════════════════════════════════


class GrowthDecisionEngine:
    """E13.3.4 Growth Decision Engine — 核心决策编排器.

    功能:
      1. 编排完整决策流程
      2. 输出 DecisionReport
      3. 连接 E12 Feedback Controller 和 E11 Evolution Engine
    """

    def __init__(
        self,
        intelligence: GrowthIntelligence | None = None,
        detector: OpportunityDetector | None = None,
        ranker: CreativeRanker | None = None,
        mapper: ActionMapper | None = None,
    ):
        self._intelligence = intelligence or GrowthIntelligence()
        self._detector = detector or OpportunityDetector()
        self._ranker = ranker or CreativeRanker()
        self._mapper = mapper or ActionMapper()

        self._last_report: DecisionReport | None = None

    # ── Properties ────────────────────────────────────────────

    @property
    def intelligence(self) -> GrowthIntelligence:
        return self._intelligence

    @property
    def detector(self) -> OpportunityDetector:
        return self._detector

    @property
    def ranker(self) -> CreativeRanker:
        return self._ranker

    @property
    def last_report(self) -> DecisionReport | None:
        return self._last_report

    # ── Core Decision Flow ────────────────────────────────────

    def analyze(
        self, vectors: list[CreativeFitnessVector],
        product_id: str = "",
    ) -> DecisionReport:
        """执行完整决策分析.

        Args:
            vectors: 创意适应度向量列表
            product_id: 产品 ID

        Returns:
            DecisionReport: 决策报告
        """
        if not vectors:
            return DecisionReport(
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                product_id=product_id,
            )

        # Step 1: Growth Intelligence → Insights
        insights = self._intelligence.analyze(vectors)

        # Step 2: Opportunity Detector → Opportunities
        opportunities = self._detector.detect(insights)

        # Step 3: Creative Ranker → Rankings
        rankings = self._ranker.rank(vectors)

        # Step 4: Action Mapper → Decisions
        decisions = self._mapper.map_opportunities(opportunities)

        # Build Report
        report = self._build_report(
            vectors=vectors,
            insights=insights,
            opportunities=opportunities,
            rankings=rankings,
            decisions=decisions,
            product_id=product_id,
        )

        self._last_report = report
        return report

    def _build_report(
        self,
        vectors: list[CreativeFitnessVector],
        insights: list,
        opportunities: list,
        rankings: list,
        decisions: list,
        product_id: str,
    ) -> DecisionReport:
        """构建 DecisionReport."""
        return DecisionReport(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            product_id=product_id,
            total_creatives_analyzed=len(vectors),
            total_insights=len(insights),
            total_opportunities=len(opportunities),
            total_decisions=len(decisions),
            decisions=decisions,
            rankings=rankings,
            insights=insights,
            opportunities=opportunities,
            winners_count=sum(1 for r in rankings if r.is_winner),
            fatigued_count=sum(1 for r in rankings if r.is_fatigued),
            scale_actions=sum(1 for d in decisions if d.action in {ActionType.SCALE, ActionType.INCREASE_BUDGET}),
            stop_actions=sum(1 for d in decisions if d.action in {ActionType.STOP, ActionType.PAUSE}),
            mutate_actions=sum(1 for d in decisions if d.action == ActionType.MUTATE),
        )

    # ── Quick Analysis ────────────────────────────────────────

    def quick_analyze(
        self, vectors: list[CreativeFitnessVector],
    ) -> dict[str, Any]:
        """快速分析 (不生成完整报告)."""
        report = self.analyze(vectors)
        return {
            "total_creatives": report.total_creatives_analyzed,
            "winners": report.winners_count,
            "fatigued": report.fatigued_count,
            "decisions": {
                "scale": report.scale_actions,
                "stop": report.stop_actions,
                "mutate": report.mutate_actions,
            },
            "top_decisions": [
                {
                    "action": d.action.value,
                    "creative_id": d.creative_id,
                    "confidence": round(d.confidence, 2),
                    "reason": d.reason,
                }
                for d in report.decisions[:5]
            ],
        }

    # ── Decision Export ───────────────────────────────────────

    def export_for_feedback_controller(self) -> list[dict[str, Any]]:
        """导出给 E12 Feedback Controller 的格式."""
        if not self._last_report:
            return []

        result: list[dict[str, Any]] = []
        for d in self._last_report.decisions:
            result.append({
                "action": d.action.value,
                "creative_id": d.creative_id,
                "genome_id": d.genome_id,
                "product_id": d.product_id,
                "priority": d.priority,
                "confidence": d.confidence,
                "reason": d.reason,
                "requires_approval": d.requires_approval,
                "approval_level": d.approval_level,
                "budget": d.budget_action.to_dict() if d.budget_action else None,
            })
        return result

    def export_for_evolution_engine(self) -> list[dict[str, Any]]:
        """导出给 E11 Evolution Engine 的格式."""
        if not self._last_report:
            return []

        result: list[dict[str, Any]] = []
        for d in self._last_report.decisions:
            if d.action == ActionType.MUTATE:
                result.append({
                    "creative_id": d.creative_id,
                    "genome_id": d.genome_id,
                    "reason": d.reason,
                    "confidence": d.confidence,
                    "action": "mutate",
                })
        return result

    # ── Lifecycle ─────────────────────────────────────────────

    def reset(self) -> None:
        self._intelligence.reset()
        self._detector.reset()
        self._ranker.reset()
        self._mapper.reset()
        self._last_report = None

    def get_summary(self) -> dict[str, Any]:
        if not self._last_report:
            return {"status": "no analysis performed"}

        return {
            "report": self._last_report.to_dict()["summary"],
            "intelligence": self._intelligence.get_summary(),
            "opportunities": self._detector.get_summary(),
            "rankings": self._ranker.get_summary(),
        }