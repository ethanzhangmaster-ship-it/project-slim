"""V4.2 Pattern Classifier — classifies new creatives into known patterns.

Answers:
  - Which historical pattern does this new creative belong to?
  - Is this pattern worth trying?
  - What is the expected performance range?

Uses:
  - Combinatorial Pattern Miner (historical patterns)
  - Creative Retriever (similar creatives)
  - Performance data (expected outcomes)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatternMatch:
    pattern_id: str = ""
    match_dimensions: dict[str, str] = field(default_factory=dict)
    match_score: float = 0.0
    expected_roas: float = 0.0
    expected_ctr: float = 0.0
    expected_range: dict[str, tuple[float, float]] = field(default_factory=dict)
    historical_samples: int = 0
    confidence: float = 0.0
    is_winner_pattern: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "match_dimensions": self.match_dimensions,
            "match_score": round(self.match_score, 3),
            "expected_roas": round(self.expected_roas, 3),
            "expected_ctr": round(self.expected_ctr, 2),
            "historical_samples": self.historical_samples,
            "confidence": round(self.confidence, 3),
            "is_winner_pattern": self.is_winner_pattern,
        }


@dataclass
class ClassificationResult:
    creative_id: str = ""
    dna: dict[str, Any] = field(default_factory=dict)
    top_matches: list[PatternMatch] = field(default_factory=list)
    best_match: PatternMatch | None = None
    novelty_score: float = 0.0
    opportunity_assessment: str = ""
    worth_trying: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "dna": self.dna,
            "top_matches": [m.to_dict() for m in self.top_matches],
            "best_match": self.best_match.to_dict() if self.best_match else None,
            "novelty_score": round(self.novelty_score, 3),
            "opportunity_assessment": self.opportunity_assessment,
            "worth_trying": self.worth_trying,
        }


class PatternClassifier:
    """Classifies new creatives into known historical patterns.

    Determines:
      - Pattern match quality
      - Expected performance range
      - Novelty vs. known-pattern score
      - Whether it's worth trying
    """

    def __init__(self, retriever=None, pattern_miner=None) -> None:
        self._retriever = retriever
        self._pattern_miner = pattern_miner

    def classify(self, creative_id: str, dna: dict[str, Any],
                 performance: dict[str, Any] | None = None) -> ClassificationResult:
        """Classify a creative into known patterns."""
        # 1. Find similar creatives
        similar = self._find_similar(dna)

        # 2. Match against known patterns
        matches = self._match_patterns(dna, similar)

        # 3. Best match
        best = matches[0] if matches else None

        # 4. Novelty score
        novelty = self._compute_novelty(dna, similar)

        # 5. Opportunity assessment
        assessment, worth = self._assess_opportunity(best, novelty, similar)

        return ClassificationResult(
            creative_id=creative_id,
            dna=dna,
            top_matches=matches[:5],
            best_match=best,
            novelty_score=novelty,
            opportunity_assessment=assessment,
            worth_trying=worth,
        )

    def _find_similar(self, dna: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._retriever:
            return []
        query = " ".join(f"{k}:{v}" for k, v in dna.items() if v)
        results = self._retriever.retrieve(query, top_k=20)
        return [
            {"dna": r.dna, "performance": r.performance, "score": r.score}
            for r in results
        ]

    def _match_patterns(self, dna: dict[str, Any],
                        similar: list[dict[str, Any]]) -> list[PatternMatch]:
        """Match creative DNA against known patterns."""
        if not similar:
            return []

        matches = []
        # Group similar creatives by shared DNA dimensions
        pattern_groups: dict[str, list[dict[str, Any]]] = {}
        for s in similar:
            s_dna = s.get("dna", {})
            # Create a pattern key from the most important dimensions
            key_parts = []
            for dim in ["character", "reward", "hook", "gameplay", "style"]:
                v = s_dna.get(dim, "")
                if v:
                    key_parts.append(f"{dim}={v}")
            key = " | ".join(key_parts)
            pattern_groups.setdefault(key, []).append(s)

        for pattern_key, group in pattern_groups.items():
            if len(group) < 2:
                continue

            # Parse pattern key into dimensions
            match_dims = {}
            for part in pattern_key.split(" | "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    match_dims[k] = v

            # Compute overlap with query DNA
            overlap = 0
            total = 0
            for dim, val in dna.items():
                if val:
                    total += 1
                    if match_dims.get(dim) == val:
                        overlap += 1
            match_score = overlap / max(total, 1)

            # Expected performance
            roas_vals = [s.get("performance", {}).get("roas_d7", 0) for s in group]
            ctr_vals = [s.get("performance", {}).get("ctr", 0) for s in group]
            avg_roas = sum(roas_vals) / max(len(roas_vals), 1)
            avg_ctr = sum(ctr_vals) / max(len(ctr_vals), 1)

            matches.append(PatternMatch(
                pattern_id=f"pattern_{hash(pattern_key) % 10000:04d}",
                match_dimensions=match_dims,
                match_score=match_score,
                expected_roas=avg_roas,
                expected_ctr=avg_ctr,
                expected_range={
                    "roas_d7": (min(roas_vals), max(roas_vals)),
                    "ctr": (min(ctr_vals), max(ctr_vals)),
                },
                historical_samples=len(group),
                confidence=min(1.0, len(group) / 20),
                is_winner_pattern=avg_roas >= 0.5,
            ))

        matches.sort(key=lambda m: (m.match_score, m.confidence), reverse=True)
        return matches

    def _compute_novelty(self, dna: dict[str, Any],
                         similar: list[dict[str, Any]]) -> float:
        """Compute how novel this creative is vs. known patterns.

        High novelty = very different from existing creatives.
        """
        if not similar:
            return 1.0

        # Count how many dimensions match the most similar creative
        best_similar = similar[0] if similar else {}
        best_dna = best_similar.get("dna", {})

        matches = 0
        total = 0
        for dim, val in dna.items():
            if val:
                total += 1
                if best_dna.get(dim) == val:
                    matches += 1

        similarity = matches / max(total, 1)
        return 1.0 - similarity

    def _assess_opportunity(self, best_match: PatternMatch | None,
                            novelty: float,
                            similar: list[dict[str, Any]]) -> tuple[str, bool]:
        """Assess whether this creative is worth trying."""
        if not best_match and not similar:
            return (
                "INSUFFICIENT DATA — no reference creatives available. Cannot assess.",
                False,
            )

        if not best_match and novelty > 0.8:
            return (
                "HIGH NOVELTY — no known pattern match. This could be a breakthrough "
                "or a failure. Recommend small-budget test.",
                True,
            )

        if not best_match:
            return (
                "INSUFFICIENT DATA — cannot assess. Recommend conservative test.",
                False,
            )

        # Low DNA overlap → pattern match is too weak to be actionable
        if best_match.match_score < 0.35:
            return (
                f"LOW DNA OVERLAP — best pattern match score too low "
                f"({best_match.match_score:.0%}). "
                f"DNA does not sufficiently match proven patterns. "
                f"Recommend: AVOID or significantly modify DNA.",
                False,
            )

        if best_match.is_winner_pattern and best_match.confidence > 0.5:
            return (
                f"STRONG MATCH to winner pattern (ROAS: {best_match.expected_roas:.2f}). "
                f"Based on {best_match.historical_samples} similar creatives. "
                f"Recommend: SCALE.",
                True,
            )

        if best_match.is_winner_pattern and best_match.confidence <= 0.5:
            return (
                f"WEAK MATCH to winner pattern — low confidence ({best_match.confidence:.0%}). "
                f"Recommend: TEST with small budget.",
                True,
            )

        return (
            f"MATCHES LOSER PATTERN (ROAS: {best_match.expected_roas:.2f}). "
            f"Recommend: AVOID or significantly modify DNA.",
            False,
        )