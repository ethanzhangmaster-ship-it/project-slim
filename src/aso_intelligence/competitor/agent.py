"""
E16.6.10 — ASO Competitor War Room Agent.

Main pipeline: collect snapshots → detect changes → analyze ranking →
diagnose → strategy → learn patterns → WarRoomReport.

This is the AI version of a game company's market research + ASO
competitive intelligence department.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.aso_intelligence.competitor.models import (
    CompetitorSnapshot,
    CompetitorChange,
    CompetitorChangeType,
    WarRoomReport,
)
from src.aso_intelligence.competitor.collector import CompetitorCollector
from src.aso_intelligence.competitor.change_detector import (
    ChangeDetectionEngine,
)
from src.aso_intelligence.competitor.ranking_analyzer import (
    RankingIntelligence,
)
from src.aso_intelligence.competitor.strategy_engine import StrategyEngine
from src.aso_intelligence.competitor.memory import CompetitorMemory
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOCompetitorAgent:
    """AI ASO Competitive Intelligence Analyst.

    Typical usage:

        agent = ASOCompetitorAgent.build(store)
        report = agent.run(
            game_category="merge",
            snapshots=[...old and new snapshots...],
        )
        print(report.to_markdown())
    """

    def __init__(
        self,
        collector: Optional[CompetitorCollector] = None,
        detector: Optional[ChangeDetectionEngine] = None,
        ranking: Optional[RankingIntelligence] = None,
        strategy: Optional[StrategyEngine] = None,
        memory: Optional[CompetitorMemory] = None,
    ):
        self.collector = collector or CompetitorCollector()
        self.detector = detector or ChangeDetectionEngine()
        self.ranking = ranking or RankingIntelligence()
        self.strategy = strategy or StrategyEngine()
        self.memory = memory or CompetitorMemory()

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOCompetitorAgent":
        return cls(memory=CompetitorMemory(store))

    # ------------------------------------------------------------------ #
    def run(
        self,
        game_category: str,
        old_snapshots: List[CompetitorSnapshot],
        new_snapshots: List[CompetitorSnapshot],
        similarities: Dict[str, float] = None,
        revenue_potentials: Dict[str, float] = None,
    ) -> WarRoomReport:
        """Run the full competitive intelligence cycle.

        1. Collect (accepts pre-collected snapshot pairs)
        2. Detect changes between old/new
        3. Analyze ranking velocity + compute threat scores
        4. Diagnose top threats
        5. Generate strategies and bridge to Creative/Keyword engines
        6. Learn patterns from observed competitor success
        7. Build report
        """
        # Step 1: Record snapshots
        for s in old_snapshots + new_snapshots:
            self.collector.record_snapshot(s)

        # Build lookup
        old_by_app: Dict[str, CompetitorSnapshot] = {
            s.app_id: s for s in old_snapshots
        }

        # Step 2: Detect all changes
        all_changes: List[CompetitorChange] = []
        for new_snap in new_snapshots:
            old_snap = old_by_app.get(new_snap.app_id)
            if old_snap:
                changes = self.detector.detect_all(old_snap, new_snap)
                all_changes.extend(changes)

        # Step 3: Rank threats
        all_snapshots = old_snapshots + new_snapshots
        ranked_threats = self.ranking.rank_threats(
            all_snapshots,
            similarities=similarities,
            revenue_potentials=revenue_potentials,
        )
        classified = self.ranking.classify_threats(ranked_threats)

        # Attach diagnoses for top threats
        diagnoses = []
        for t in ranked_threats[:5]:
            app_id = t["app_id"]
            new_snap = old_by_app.get(app_id)
            old_snap = old_by_app.get(app_id)
            # Find the matching snapshots
            old_match = next(
                (s for s in old_snapshots if s.app_id == app_id), None
            )
            new_match = next(
                (s for s in new_snapshots if s.app_id == app_id), None
            )
            if old_match and new_match:
                # Get changes for this competitor
                comp_changes = [
                    c for c in all_changes if c.app_id == app_id
                ]
                diagnosis = self.strategy.diagnose(
                    app_id, comp_changes, old_match, new_match
                )
                diagnoses.append(diagnosis)

                # Add recommended action to threat entry
                t["recommended_action"] = diagnosis.recommended_action

        # Step 4: Keyword movements from competitor title changes
        keyword_movements: List[Dict[str, Any]] = []
        for change in all_changes:
            kw_data = self.strategy.connect_to_keyword_intelligence(change)
            if kw_data:
                keyword_movements.append({
                    "keyword": ", ".join(kw_data.get("keyword", [])),
                    "opportunity": "HIGH" if change.impact == "high" else "MEDIUM",
                    "source": kw_data.get("source", ""),
                    "reason": kw_data.get("reason", ""),
                })

        # Step 5: Learn patterns from competitors with surge + icon/screenshot changes
        patterns_learned = 0
        for t in ranked_threats[:3]:
            if t["level"] != "high":
                continue
            # Determine if we can learn a pattern
            comp_changes = [
                c for c in all_changes if c.app_id == t["app_id"]
            ]
            for c in comp_changes:
                if c.change_type in (
                    CompetitorChangeType.ICON_CHANGE,
                    CompetitorChangeType.SCREENSHOT_CHANGE,
                ):
                    # Estimate rank improvement
                    rank_imp = t.get("prev_rank", 0) - t.get("curr_rank", 0)
                    if rank_imp > 0:
                        self.memory.observe(
                            category=game_category,
                            change_type=c.change_type,
                            rank_improvement=rank_imp,
                            confidence=c.confidence,
                            note=f"{t['app_id']} gained {rank_imp} ranks",
                        )

        # If we have enough observations, learn a pattern
        if self.memory.observations_count() >= 2:
            for ct in (CompetitorChangeType.ICON_CHANGE,
                       CompetitorChangeType.SCREENSHOT_CHANGE):
                obs_for_type = [
                    o for o in self.memory._observations
                    if o["change_type"] == ct.value
                ]
                if len(obs_for_type) >= 2:
                    avg_imp = sum(
                        o["rank_improvement"] for o in obs_for_type
                    ) / len(obs_for_type)
                    avg_conf = sum(
                        o["confidence"] for o in obs_for_type
                    ) / len(obs_for_type)
                    pat = self.memory.learn_pattern(
                        category=game_category,
                        change_type=ct,
                        num_observations=len(obs_for_type),
                        avg_rank_improvement=avg_imp,
                        confidence=avg_conf,
                    )
                    if pat:
                        patterns_learned += 1

        # Step 6: Build report
        report = WarRoomReport(
            game_category=game_category,
            date=_today_iso(),
            high_threat=classified.get("high", []),
            medium_threat=classified.get("medium", []),
            low_threat=classified.get("low", []),
            changes_detected=all_changes,
            diagnoses=diagnoses,
            keyword_movements=keyword_movements,
            patterns_learned=patterns_learned,
        )
        return report


__all__ = ["ASOCompetitorAgent"]
