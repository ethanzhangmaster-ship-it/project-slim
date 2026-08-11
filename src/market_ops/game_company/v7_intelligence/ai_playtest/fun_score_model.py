from dataclasses import dataclass
from typing import Dict, Optional
import random


@dataclass
class FunFactors:
    novelty: float
    challenge: float
    reward: float
    autonomy: float
    social: float
    narrative: float


@dataclass
class FunScore:
    total_score: float
    factors: FunFactors
    verdict: str


class FunScoreModel:
    """Score the fun / engagement of a game."""

    def __init__(self):
        self._scores: Dict[str, FunScore] = {}

    def _random_factors(self) -> FunFactors:
        return FunFactors(
            novelty=round(random.uniform(0.4, 0.95), 4),
            challenge=round(random.uniform(0.4, 0.95), 4),
            reward=round(random.uniform(0.4, 0.95), 4),
            autonomy=round(random.uniform(0.4, 0.95), 4),
            social=round(random.uniform(0.4, 0.95), 4),
            narrative=round(random.uniform(0.4, 0.95), 4),
        )

    def score(self, game: str) -> FunScore:
        """Evaluate fun score for a given game identifier."""
        factors = self._random_factors()
        total = round(
            (
                factors.novelty
                + factors.challenge
                + factors.reward
                + factors.autonomy
                + factors.social
                + factors.narrative
            )
            / 6,
            4,
        )
        verdict = (
            "highly_fun"
            if total >= 0.8
            else "fun"
            if total >= 0.6
            else "moderate"
            if total >= 0.4
            else "low_fun"
        )
        fun_score = FunScore(total_score=total, factors=factors, verdict=verdict)
        self._scores[game] = fun_score
        return fun_score

    def get_fun_factors(self) -> FunFactors:
        """Return a sample set of fun factors."""
        return self._random_factors()

    def compare(self, fun_score_a: FunScore, fun_score_b: FunScore) -> Dict[str, str]:
        """Compare two fun scores."""
        winner = "A" if fun_score_a.total_score > fun_score_b.total_score else "B"
        diff = abs(fun_score_a.total_score - fun_score_b.total_score)
        return {
            "winner": winner,
            "difference": f"{diff:.4f}",
            "verdict_a": fun_score_a.verdict,
            "verdict_b": fun_score_b.verdict,
        }
