from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List


class KillReason(Enum):
    UNPROFITABLE = "unprofitable"
    LOW_RETENTION = "low_retention"
    HIGH_COST = "high_cost"
    STRATEGIC = "strategic"
    TECHNICAL = "technical"


@dataclass
class KillEvaluation:
    game_id: str
    should_kill: bool
    confidence: float
    primary_reason: KillReason

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "should_kill": self.should_kill,
            "confidence": self.confidence,
            "primary_reason": self.primary_reason.value,
        }


@dataclass
class KillTrigger:
    game_id: str
    reason: KillReason
    triggered_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "reason": self.reason.value,
            "triggered_at": self.triggered_at,
        }


@dataclass
class KillHistory:
    entries: List[KillTrigger]

    def to_dict(self):
        return {
            "entries": [e.to_dict() for e in self.entries],
            "total_killed": len(self.entries),
        }


class KillSwitch:
    def __init__(self):
        self._killed: List[KillTrigger] = []
        self._evaluations: Dict[str, KillEvaluation] = {}

    def evaluate_kill(self, game_id: str) -> KillEvaluation:
        evaluation = KillEvaluation(
            game_id=game_id,
            should_kill=False,
            confidence=0.15,
            primary_reason=KillReason.STRATEGIC,
        )
        self._evaluations[game_id] = evaluation
        return evaluation

    def trigger_kill(self, game_id: str, reason: KillReason) -> KillTrigger:
        trigger = KillTrigger(game_id=game_id, reason=reason)
        self._killed.append(trigger)
        return trigger

    def get_kill_recommendations(self) -> List[KillEvaluation]:
        return [e for e in self._evaluations.values() if e.should_kill]

    def get_killed_games(self) -> List[str]:
        return [k.game_id for k in self._killed]

    def get_kill_history(self) -> KillHistory:
        return KillHistory(entries=self._killed)

    def get_stats(self) -> Dict:
        return {
            "total_evaluations": len(self._evaluations),
            "total_killed": len(self._killed),
            "recommendations": len(self.get_kill_recommendations()),
        }
