"""
E16.6.4 — ASO Pattern Scorer (cf. E13.4 / Growth Memory scoring).

Assigns an adoptability score to a mined ``ASOPattern``:

    Score = sample_size × success_rate × reward × confidence

Guarded by a minimum-sample threshold so a pattern proven only twice (no
matter how spectacular the lift) is NOT adopted — small samples are
unreliable. A pattern whose reward is negative (e.g. it lifted CVR but
harmed LTV) scores ≤ 0 and is likewise rejected.

Reference example (spec):
  Pattern A: n=20, 16/20 success, +18% reward, conf 0.9  → high score (adopt)
  Pattern B: n=2,  2/2  success, +50% reward, conf 1.0  → score 0 (reject)
"""

from __future__ import annotations

from typing import List

from src.aso_intelligence.experiment_memory.experiment_models import ASOPattern


class ASOPatternScorer:
    """Scores & ranks ASO patterns for adoption decisions."""

    def __init__(self, min_sample: int = 5):
        self.min_sample = min_sample

    # ------------------------------------------------------------------ #
    def score(self, pattern: ASOPattern) -> float:
        """Adoptability score. 0 if below the sample threshold or no reward."""
        if pattern.sample_size < self.min_sample:
            return 0.0
        if pattern.reward <= 0:
            return 0.0
        return round(
            pattern.sample_size
            * pattern.success_rate
            * pattern.reward
            * pattern.confidence,
            6,
        )

    def adoptable(self, pattern: ASOPattern) -> bool:
        """True only if the pattern clears the sample bar AND earns a positive
        score (i.e. real reward with enough evidence)."""
        return self.score(pattern) > 0 and pattern.sample_size >= self.min_sample

    def rank(self, patterns: List[ASOPattern]) -> List[ASOPattern]:
        """Return patterns sorted by score, highest first."""
        return sorted(patterns, key=lambda p: self.score(p), reverse=True)


__all__ = ["ASOPatternScorer"]
