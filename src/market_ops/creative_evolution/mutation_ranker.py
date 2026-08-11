"""E9.8: Mutation Ranker — Scores and ranks mutation candidates.

Ranking formula:
  Mutation Score = DNA Alignment + Winner Similarity + Opportunity + Predicted LTV + Novelty

Each dimension weighted:
  - DNA Alignment: 0.25 (matches winner DNA patterns)
  - Winner Similarity: 0.20 (similar to historical winners)
  - Opportunity: 0.15 (market opportunity alignment)
  - Predicted LTV: 0.25 (E9.6 predicted LTV)
  - Novelty: 0.15 (different from existing creatives)
"""

from __future__ import annotations

from typing import Any

from market_ops.creative_evolution.schemas import (
    CreativeGenome, MutationRecord, MutationCandidate,
    WinnerPattern, MarketOpportunity,
)


class MutationRanker:
    """Ranks mutation candidates for production priority.

    Usage:
        ranker = MutationRanker()
        ranked = ranker.rank(candidates, winner_pattern, opportunities, existing_dna)
    """

    def __init__(self) -> None:
        # Scoring weights
        self._w_dna_alignment = 0.25
        self._w_winner_similarity = 0.20
        self._w_opportunity = 0.15
        self._w_predicted_ltv = 0.25
        self._w_novelty = 0.15

    # ── Main Ranking ──────────────────────────────────────

    def rank(
        self,
        candidates: list[tuple[CreativeGenome, list[MutationRecord]]],
        winner_pattern: WinnerPattern,
        opportunities: list[MarketOpportunity],
        existing_dna: list[dict[str, Any]],
        predicted_ltv_map: dict[str, dict[str, Any]] | None = None,
    ) -> list[MutationCandidate]:
        """Rank all mutation candidates.

        Args:
            candidates: (genome, mutations) tuples
            winner_pattern: Winner DNA patterns
            opportunities: Market opportunities
            existing_dna: All existing DNA entries
            predicted_ltv_map: {genome_id: {ltv, archetypes, ...}} from E9.6

        Returns:
            Ranked list of MutationCandidate objects
        """
        ranked: list[MutationCandidate] = []

        for genome, mutations in candidates:
            candidate = MutationCandidate(
                genome=genome,
                mutations=mutations,
            )

            # 1. DNA Alignment Score
            candidate.dna_alignment_score = self._score_dna_alignment(
                genome, winner_pattern,
            )

            # 2. Winner Similarity Score
            candidate.winner_similarity_score = self._score_winner_similarity(
                genome, winner_pattern,
            )

            # 3. Opportunity Score
            candidate.opportunity_score = self._score_opportunity(
                genome, opportunities,
            )

            # 4. Predicted LTV (from E9.6)
            if predicted_ltv_map and genome.genome_id in predicted_ltv_map:
                pred = predicted_ltv_map[genome.genome_id]
                candidate.predicted_ltv = pred.get("ltv", 0)
                candidate.predicted_archetypes = pred.get("archetypes", {})
                candidate.predicted_payer_rate = pred.get("payer_rate", 0)
                candidate.predicted_d30 = pred.get("d30", 0)
                candidate.confidence = pred.get("confidence", 0.5)
            else:
                # Estimate from winner pattern
                candidate.predicted_ltv = winner_pattern.avg_ltv * 0.9
                candidate.predicted_archetypes = winner_pattern.archetype_affinity
                candidate.confidence = 0.5

            # 5. Novelty Score
            candidate.novelty_score = self._score_novelty(genome, existing_dna)

            # Composite Score
            candidate.composite_score = (
                self._w_dna_alignment * candidate.dna_alignment_score +
                self._w_winner_similarity * candidate.winner_similarity_score +
                self._w_opportunity * candidate.opportunity_score +
                self._w_predicted_ltv * self._normalize_ltv(candidate.predicted_ltv) +
                self._w_novelty * candidate.novelty_score
            )

            # Risk assessment
            candidate.risk_level = self._assess_risk(candidate)

            ranked.append(candidate)

        # Sort by composite score descending
        ranked.sort(key=lambda c: c.composite_score, reverse=True)

        return ranked

    # ── Scoring Functions ──────────────────────────────────

    def _score_dna_alignment(
        self,
        genome: CreativeGenome,
        wp: WinnerPattern,
    ) -> float:
        """Score how well genome aligns with winner DNA patterns."""
        score = 0.0
        total = 0

        # Hook alignment
        winner_hooks = {h["value"] for h in wp.top_hooks[:3]}
        if genome.hook in winner_hooks:
            score += 1.0
        elif genome.hook:
            score += 0.3
        total += 1

        # Reward alignment
        winner_rewards = {r["value"] for r in wp.top_rewards[:3]}
        if genome.reward in winner_rewards:
            score += 1.0
        elif genome.reward:
            score += 0.3
        total += 1

        # Fantasy alignment
        winner_fantasies = {f["value"] for f in wp.top_fantasies[:3]}
        if genome.fantasy in winner_fantasies:
            score += 1.0
        elif genome.fantasy:
            score += 0.3
        total += 1

        return round(score / total, 3) if total > 0 else 0.0

    def _score_winner_similarity(
        self,
        genome: CreativeGenome,
        wp: WinnerPattern,
    ) -> float:
        """Score similarity to historical winners."""
        score = 0.0
        total = 0

        top_hooks = wp.top_hooks
        if top_hooks:
            hook_map = {h["value"]: h["pct"] / 100 for h in top_hooks}
            score += hook_map.get(genome.hook, 0.0)
            total += 1

        top_rewards = wp.top_rewards
        if top_rewards:
            reward_map = {r["value"]: r["pct"] / 100 for r in top_rewards}
            score += reward_map.get(genome.reward, 0.0)
            total += 1

        return round(score / total, 3) if total > 0 else 0.0

    def _score_opportunity(
        self,
        genome: CreativeGenome,
        opportunities: list[MarketOpportunity],
    ) -> float:
        """Score alignment with market opportunities."""
        max_score = 0.0
        for opp in opportunities:
            if opp.target_value == genome.hook:
                max_score = max(max_score, opp.confidence)
            elif opp.target_value == genome.reward:
                max_score = max(max_score, opp.confidence)
            elif opp.target_value == genome.fantasy:
                max_score = max(max_score, opp.confidence)
            elif opp.target_archetype == genome.target_archetype:
                max_score = max(max_score, opp.confidence)

        return round(max_score, 3)

    def _score_novelty(
        self,
        genome: CreativeGenome,
        existing_dna: list[dict[str, Any]],
    ) -> float:
        """Score how novel/different this genome is from existing."""
        if not existing_dna:
            return 1.0

        # Count existing creatives with same hook+reward combination
        same_count = 0
        for d in existing_dna:
            h = (d.get("hook", {}) or {}).get("type", "")
            r = (d.get("reward", {}) or {}).get("type", "")
            if h == genome.hook and r == genome.reward:
                same_count += 1

        # Novelty = 1 - (existing / total)
        novelty = 1.0 - (same_count / len(existing_dna))
        return round(max(0.0, min(1.0, novelty)), 3)

    # ── Risk Assessment ────────────────────────────────────

    def _assess_risk(self, candidate: MutationCandidate) -> str:
        """Assess risk level of a mutation candidate."""
        risk_score = 0

        # Low confidence = higher risk
        if candidate.confidence < 0.4:
            risk_score += 2
        elif candidate.confidence < 0.6:
            risk_score += 1

        # Low predicted LTV = higher risk
        if candidate.predicted_ltv < 15:
            risk_score += 2
        elif candidate.predicted_ltv < 18:
            risk_score += 1

        # Multiple mutations = higher risk
        if len(candidate.mutations) > 2:
            risk_score += 2
        elif len(candidate.mutations) > 1:
            risk_score += 1

        if risk_score >= 4:
            return "high"
        elif risk_score >= 2:
            return "medium"
        return "low"

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _normalize_ltv(ltv: float, max_ltv: float = 25.0) -> float:
        """Normalize LTV to 0-1 scale."""
        return round(min(1.0, max(0.0, ltv / max_ltv)), 3)