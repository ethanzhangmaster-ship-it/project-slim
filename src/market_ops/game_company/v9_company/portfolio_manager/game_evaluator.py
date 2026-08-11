from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class GameHealth(Enum):
    THRIVING = "thriving"
    HEALTHY = "healthy"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL = "critical"


@dataclass
class GameEvaluation:
    game_id: str
    score: int
    health: GameHealth
    summary: str

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "score": self.score,
            "health": self.health.value,
            "summary": self.summary,
        }


@dataclass
class GameScore:
    game_id: str
    revenue_score: int
    retention_score: int
    engagement_score: int
    overall: int

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "revenue_score": self.revenue_score,
            "retention_score": self.retention_score,
            "engagement_score": self.engagement_score,
            "overall": self.overall,
        }


@dataclass
class EvaluationCriteria:
    criteria: List[str]
    weights: Dict[str, float]

    def to_dict(self):
        return {
            "criteria": self.criteria,
            "weights": self.weights,
        }


class GameEvaluator:
    def __init__(self):
        self._evaluations: Dict[str, GameEvaluation] = {}
        self._scores: Dict[str, GameScore] = {}

    def evaluate_game(self, game_id: str) -> GameEvaluation:
        score = 75 if game_id.startswith("g") else 55
        health = GameHealth.HEALTHY if score > 70 else GameHealth.STABLE
        evaluation = GameEvaluation(
            game_id=game_id,
            score=score,
            health=health,
            summary=f"Game {game_id} shows {health.value} performance.",
        )
        self._evaluations[game_id] = evaluation
        return evaluation

    def get_game_score(self, game_id: str) -> GameScore:
        score = GameScore(
            game_id=game_id,
            revenue_score=78,
            retention_score=72,
            engagement_score=80,
            overall=77,
        )
        self._scores[game_id] = score
        return score

    def get_game_health(self, game_id: str) -> GameHealth:
        eval_result = self.evaluate_game(game_id)
        return eval_result.health

    def compare_games(self) -> Dict:
        return {
            "evaluations": {k: v.to_dict() for k, v in self._evaluations.items()},
            "scores": {k: v.to_dict() for k, v in self._scores.items()},
        }

    def get_evaluation_criteria(self) -> EvaluationCriteria:
        return EvaluationCriteria(
            criteria=["revenue", "retention", "engagement", "monetization"],
            weights={
                "revenue": 0.3,
                "retention": 0.3,
                "engagement": 0.25,
                "monetization": 0.15,
            },
        )

    def get_stats(self) -> Dict:
        return {
            "evaluations_count": len(self._evaluations),
            "scores_count": len(self._scores),
            "criteria": self.get_evaluation_criteria().to_dict(),
        }
