"""
E16.6.10 — Ranking Intelligence & Threat Scoring.

Analyzes competitor ranking movements and computes the Threat Score:
  ``Threat = Ranking Growth × Revenue Potential × Similarity × Momentum``

Also provides velocity computation, surge classification, and threat ranking.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.competitor.models import (
    CompetitorSnapshot,
    CompetitorChange,
    CompetitorChangeType,
    RankingVelocity,
    ThreatScore,
)


_SURGE_VELOCITY_THRESHOLD = 3.0  # ranks/day
_HIGH_THREAT_THRESHOLD = 0.5
_MEDIUM_THREAT_THRESHOLD = 0.2


class RankingIntelligence:
    """Compute ranking velocity, detect surges, and score threats."""

    # ------------------------------------------------------------------ #
    def compute_velocity(
        self,
        old: CompetitorSnapshot,
        new: CompetitorSnapshot,
        days: int = 7,
    ) -> Optional[RankingVelocity]:
        """Compute ranking velocity between two snapshots."""
        if old.ranking_position <= 0 or new.ranking_position <= 0:
            return None

        vel = RankingVelocity(
            app_id=new.app_id,
            previous_rank=old.ranking_position,
            current_rank=new.ranking_position,
            days=days,
        )
        vel.compute()
        return vel

    # ------------------------------------------------------------------ #
    def compute_threat(
        self,
        app_id: str,
        old: CompetitorSnapshot,
        new: CompetitorSnapshot,
        similarity: float = 0.5,
        revenue_potential: float = 0.5,
    ) -> ThreatScore:
        """Compute threat score from snapshot comparison.

        ``similarity``  — how similar the game is to yours (0–1)
        ``revenue_potential`` — estimated revenue overlap (0–1)
        """
        vel = self.compute_velocity(old, new)

        # Ranking growth (0–1): normalize velocity to 0–10 range, cap at 1
        growth = min(1.0, max(0.0, (vel.velocity if vel else 0) / 10.0))

        # Momentum: surge flag doubles the momentum component
        momentum = 0.3
        if vel and vel.is_surge(_SURGE_VELOCITY_THRESHOLD):
            momentum = 0.8
        if vel and vel.is_surge(5.0):
            momentum = 1.0

        threat = ThreatScore(
            app_id=app_id,
            ranking_growth=growth,
            revenue_potential=revenue_potential,
            similarity=similarity,
            momentum=momentum,
        )
        threat.compute()
        return threat

    # ------------------------------------------------------------------ #
    def rank_threats(
        self,
        snapshots: List[CompetitorSnapshot],
        similarities: Dict[str, float] = None,
        revenue_potentials: Dict[str, float] = None,
    ) -> List[Dict]:
        """Rank multiple competitors by threat score.

        Requires at least 2 snapshots per competitor (old + new).
        For MVP, uses latest two snapshots from each competitor.
        """
        sims = similarities or {}
        revs = revenue_potentials or {}

        # Group by app_id
        by_app: Dict[str, List[CompetitorSnapshot]] = {}
        for s in snapshots:
            by_app.setdefault(s.app_id, []).append(s)

        results: List[Dict] = []
        for app_id, snaps in by_app.items():
            if len(snaps) < 2:
                continue
            # Use last two
            old, new = snaps[-2], snaps[-1]

            threat = self.compute_threat(
                app_id=app_id,
                old=old,
                new=new,
                similarity=sims.get(app_id, 0.5),
                revenue_potential=revs.get(app_id, 0.5),
            )

            # Detect changes for the summary
            from src.aso_intelligence.competitor.change_detector import (
                ChangeDetectionEngine,
            )
            detector = ChangeDetectionEngine()
            changes = detector.detect_all(old, new)

            results.append({
                "app_id": app_id,
                "score": threat.score,
                "level": threat.level,
                "prev_rank": old.ranking_position,
                "curr_rank": new.ranking_position,
                "changes": [c.to_dict() for c in changes],
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # ------------------------------------------------------------------ #
    def classify_threats(
        self, threats: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Split threats into high/medium/low buckets."""
        classified: Dict[str, List[Dict]] = {
            "high": [], "medium": [], "low": [],
        }
        for t in threats:
            if t["score"] >= _HIGH_THREAT_THRESHOLD:
                classified["high"].append(t)
            elif t["score"] >= _MEDIUM_THREAT_THRESHOLD:
                classified["medium"].append(t)
            else:
                classified["low"].append(t)
        return classified


__all__ = ["RankingIntelligence"]
