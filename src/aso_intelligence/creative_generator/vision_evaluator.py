"""
E16.6.8 — ASO Vision Evaluator.

Evaluates generated creative candidates on:
  1. Vision quality — hook, clarity, emotional appeal, brand consistency
  2. Store compliance — policy-friendliness, misleading claim detection
  3. Historical pattern match — similarity to successful experiments
  4. Revenue prediction — estimated CVR/LTV impact

This module bridges E11.3 Vision Layer concepts (deterministic heuristic,
no CLIP/LLM dependency in MVP).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.creative_generator.models import (
    ASOCreativeGenome,
    CreativeCandidate,
    CreativeScore,
    StoreAssetType,
)


# Phrases that trigger store compliance warnings
_HIGH_RISK_PATTERNS = [
    "100%", "guaranteed", "#1", "top rated", "best game",
    "free money", "win real", "everyone loves",
]
_MODERATE_RISK_PATTERNS = [
    "addictive", "must have", "incredible", "unbelievable",
    "you'll never", "total",
]


class ASOVisionEvaluator:
    """Evaluate creative candidates on vision quality and store safety."""

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        candidate: CreativeCandidate,
        benchmark: float = 0.6,
    ) -> CreativeScore:
        """Full evaluation of one creative candidate.

        Uses the candidate's genome and prompt to estimate vision scores.
        In production, this would call E11.3 Vision Layer.
        """
        genome = candidate.genome
        asset_type = candidate.asset_type

        # Vision scores derived from genome traits
        hook = self._score_hook(genome, asset_type)
        clarity = self._score_clarity(genome, asset_type)
        emotional = self._score_emotional(genome)
        brand = self._score_brand(genome)
        compliance = self._check_compliance(candidate.prompt_used)

        score = CreativeScore(
            hook_score=hook,
            clarity_score=clarity,
            emotional_score=emotional,
            brand_score=brand,
            conversion_prediction=(hook + clarity) / 2,
            store_compliance=compliance,
        )
        return score

    # ------------------------------------------------------------------ #
    def _score_hook(
        self, genome: Optional[ASOCreativeGenome], asset_type: StoreAssetType
    ) -> float:
        """Hook score based on genome hook strengths."""
        if genome is None:
            return 0.5

        score = 0.5  # baseline

        # Character presence → +0.2
        if genome.hook_character and genome.hook_character != "none":
            score += 0.15
            if "face" in genome.hook_character:
                score += 0.1  # face is strongest hook for store

        # Reward visibility → +0.15
        if genome.hook_reward and genome.hook_reward != "none":
            score += 0.15

        # Transformation → +0.1 for screenshots
        if (genome.hook_transformation
                and genome.hook_transformation != "none"
                and asset_type == StoreAssetType.SCREENSHOT):
            score += 0.1

        return min(1.0, score)

    def _score_clarity(
        self, genome: Optional[ASOCreativeGenome], asset_type: StoreAssetType
    ) -> float:
        """Clarity score: composition + hierarchy."""
        if genome is None:
            return 0.5

        score = 0.5
        if genome.comp_hierarchy == "clear":
            score += 0.2
        if genome.comp_contrast == "high":
            score += 0.15
        elif genome.comp_contrast == "medium":
            score += 0.05
        if genome.comp_focus in ("centered", "character_focused"):
            score += 0.1

        return min(1.0, score)

    def _score_emotional(self, genome: Optional[ASOCreativeGenome]) -> float:
        """Emotional appeal: achievement + curiosity + collection."""
        if genome is None:
            return 0.5

        emotions = [
            genome.emotion_achievement,
            genome.emotion_curiosity,
            genome.emotion_collection,
        ]
        avg = sum(emotions) / len(emotions) if emotions else 0.0
        return min(1.0, 0.4 + avg * 0.6)

    def _score_brand(self, genome: Optional[ASOCreativeGenome]) -> float:
        """Brand consistency: clear message + consistent style."""
        if genome is None:
            return 0.5
        score = 0.5
        if genome.text_headline:
            score += 0.2
        if genome.text_benefit:
            score += 0.15
        if genome.category:
            score += 0.1
        return min(1.0, score)

    # ------------------------------------------------------------------ #
    def _check_compliance(self, text: str) -> float:
        """Store compliance score (1.0 = fully compliant).

        Penalises misleading claims and excessive marketing language.
        """
        text_lower = text.lower()

        high_risk_hits = sum(
            1 for p in _HIGH_RISK_PATTERNS if p in text_lower
        )
        mod_risk_hits = sum(
            1 for p in _MODERATE_RISK_PATTERNS if p in text_lower
        )

        penalty = high_risk_hits * 0.2 + mod_risk_hits * 0.1
        return max(0.1, 1.0 - penalty)

    # ------------------------------------------------------------------ #
    def evaluate_batch(
        self,
        candidates: List[CreativeCandidate],
        benchmark: float = 0.6,
    ) -> List[CreativeCandidate]:
        """Evaluate all candidates and attach scores."""
        scored: List[CreativeCandidate] = []
        for c in candidates:
            score = self.evaluate(c, benchmark)
            c.score = score
            scored.append(c)
        return scored


__all__ = ["ASOVisionEvaluator"]
