from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class SelectionCriteria(Enum):
    PRIMARY_METRIC = "primary_metric"
    COMPOSITE_SCORE = "composite_score"
    STATISTICAL_SIGNIFICANCE = "statistical_significance"
    BUSINESS_IMPACT = "business_impact"
    RISK_ADJUSTED = "risk_adjusted"


class WinnerStatus(Enum):
    PENDING = "pending"
    SELECTED = "selected"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


@dataclass
class WinnerCandidate:
    candidate_id: str
    experiment_id: str
    variant_id: str
    primary_metric_value: float = 0.0
    composite_score: float = 0.0
    statistical_significance: float = 0.0
    business_impact: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.0
    is_winner: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "primary_metric_value": self.primary_metric_value,
            "composite_score": self.composite_score,
            "statistical_significance": self.statistical_significance,
            "business_impact": self.business_impact,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "is_winner": self.is_winner,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SelectionResult:
    result_id: str
    experiment_id: str
    winner_id: str
    selection_criteria: SelectionCriteria
    winner_score: float = 0.0
    runner_up_id: Optional[str] = None
    runner_up_score: float = 0.0
    margin: float = 0.0
    confidence: float = 0.0
    status: WinnerStatus = WinnerStatus.PENDING
    reasoning: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "experiment_id": self.experiment_id,
            "winner_id": self.winner_id,
            "selection_criteria": self.selection_criteria.value,
            "winner_score": self.winner_score,
            "runner_up_id": self.runner_up_id,
            "runner_up_score": self.runner_up_score,
            "margin": self.margin,
            "confidence": self.confidence,
            "status": self.status.value,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SelectionConfig:
    criteria: SelectionCriteria = SelectionCriteria.COMPOSITE_SCORE
    min_confidence: float = 0.95
    min_sample_size: int = 1000
    min_lift: float = 0.05
    consider_risk: bool = True
    weight_primary_metric: float = 0.4
    weight_statistical: float = 0.3
    weight_business: float = 0.3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criteria": self.criteria.value,
            "min_confidence": self.min_confidence,
            "min_sample_size": self.min_sample_size,
            "min_lift": self.min_lift,
            "consider_risk": self.consider_risk,
            "weight_primary_metric": self.weight_primary_metric,
            "weight_statistical": self.weight_statistical,
            "weight_business": self.weight_business,
        }


class WinnerSelector:
    def __init__(self):
        self._candidates: Dict[str, WinnerCandidate] = {}
        self._results: Dict[str, SelectionResult] = []
        self._config: SelectionConfig = SelectionConfig()
        self._selection_history: List[Dict[str, Any]] = []

    def register_candidate(
        self,
        experiment_id: str,
        variant_id: str,
        primary_metric_value: float,
        statistical_significance: float = None,
        business_impact: float = None
    ) -> WinnerCandidate:
        candidate_id = f"cand_{experiment_id}_{variant_id}"
        candidate = WinnerCandidate(
            candidate_id=candidate_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            primary_metric_value=primary_metric_value,
            statistical_significance=statistical_significance or random.uniform(0.85, 0.99),
            business_impact=business_impact or random.uniform(0.1, 0.5),
            risk_score=random.uniform(0.1, 0.4),
            confidence=random.uniform(0.85, 0.99),
        )
        candidate.composite_score = self._calculate_composite_score(candidate)
        self._candidates[candidate_id] = candidate
        return candidate

    def _calculate_composite_score(self, candidate: WinnerCandidate) -> float:
        score = (
            candidate.primary_metric_value * self._config.weight_primary_metric +
            candidate.statistical_significance * self._config.weight_statistical +
            candidate.business_impact * self._config.weight_business
        )
        if self._config.consider_risk:
            score = score * (1 - candidate.risk_score * 0.5)
        return score

    def select_winner(self, experiment_id: str, criteria: SelectionCriteria = None) -> Optional[SelectionResult]:
        criteria = criteria or self._config.criteria
        experiment_candidates = [c for c in self._candidates.values() if c.experiment_id == experiment_id]

        if not experiment_candidates:
            return None

        valid_candidates = [c for c in experiment_candidates if c.confidence >= self._config.min_confidence]
        if not valid_candidates:
            valid_candidates = experiment_candidates

        if criteria == SelectionCriteria.PRIMARY_METRIC:
            sorted_candidates = sorted(valid_candidates, key=lambda c: c.primary_metric_value, reverse=True)
        elif criteria == SelectionCriteria.COMPOSITE_SCORE:
            sorted_candidates = sorted(valid_candidates, key=lambda c: c.composite_score, reverse=True)
        elif criteria == SelectionCriteria.STATISTICAL_SIGNIFICANCE:
            sorted_candidates = sorted(valid_candidates, key=lambda c: c.statistical_significance, reverse=True)
        elif criteria == SelectionCriteria.BUSINESS_IMPACT:
            sorted_candidates = sorted(valid_candidates, key=lambda c: c.business_impact, reverse=True)
        else:
            sorted_candidates = sorted(valid_candidates, key=lambda c: c.composite_score, reverse=True)

        winner = sorted_candidates[0] if sorted_candidates else None
        runner_up = sorted_candidates[1] if len(sorted_candidates) > 1 else None

        if not winner:
            return None

        winner.is_winner = True
        winner_score = getattr(winner, criteria.value, winner.composite_score)
        runner_up_score = getattr(runner_up, criteria.value, 0) if runner_up else 0

        result_id = f"sel_{experiment_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = SelectionResult(
            result_id=result_id,
            experiment_id=experiment_id,
            winner_id=winner.variant_id,
            selection_criteria=criteria,
            winner_score=winner_score,
            runner_up_id=runner_up.variant_id if runner_up else None,
            runner_up_score=runner_up_score,
            margin=winner_score - runner_up_score,
            confidence=winner.confidence,
            reasoning=self._generate_reasoning(winner, runner_up, criteria),
        )

        self._results.append(result)
        self._selection_history.append({
            "experiment_id": experiment_id,
            "winner": winner.variant_id,
            "criteria": criteria.value,
            "timestamp": datetime.now().isoformat(),
        })
        return result

    def _generate_reasoning(self, winner: WinnerCandidate, runner_up: Optional[WinnerCandidate], criteria: SelectionCriteria) -> str:
        reasoning = f"Selected {winner.variant_id} based on {criteria.value}. "
        reasoning += f"Primary metric: {winner.primary_metric_value:.4f}, "
        reasoning += f"Confidence: {winner.confidence:.2%}, "
        if runner_up:
            reasoning += f"Margin over runner-up: {(winner.composite_score - runner_up.composite_score):.4f}"
        return reasoning

    def confirm_winner(self, result_id: str) -> Optional[SelectionResult]:
        for result in self._results:
            if result.result_id == result_id and result.status == WinnerStatus.PENDING:
                result.status = WinnerStatus.SELECTED
                return result
        return None

    def implement_winner(self, result_id: str) -> Optional[SelectionResult]:
        for result in self._results:
            if result.result_id == result_id and result.status == WinnerStatus.SELECTED:
                result.status = WinnerStatus.IMPLEMENTED
                return result
        return None

    def reject_winner(self, result_id: str) -> Optional[SelectionResult]:
        for result in self._results:
            if result.result_id == result_id and result.status in [WinnerStatus.PENDING, WinnerStatus.SELECTED]:
                result.status = WinnerStatus.REJECTED
                return result
        return None

    def get_candidate(self, candidate_id: str) -> Optional[WinnerCandidate]:
        return self._candidates.get(candidate_id)

    def get_candidates(self, experiment_id: str) -> List[WinnerCandidate]:
        return [c for c in self._candidates.values() if c.experiment_id == experiment_id]

    def get_result(self, result_id: str) -> Optional[SelectionResult]:
        for result in self._results:
            if result.result_id == result_id:
                return result
        return None

    def get_results(self, experiment_id: str = None) -> List[SelectionResult]:
        if experiment_id:
            return [r for r in self._results if r.experiment_id == experiment_id]
        return list(self._results)

    def set_config(self, config: SelectionConfig):
        self._config = config

    def get_config(self) -> SelectionConfig:
        return self._config

    def get_selection_history(self) -> List[Dict[str, Any]]:
        return list(self._selection_history)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_candidates": len(self._candidates),
            "total_selections": len(self._results),
            "selections_by_status": {
                status.value: sum(1 for r in self._results if r.status == status)
                for status in WinnerStatus
            },
            "selections_by_criteria": {
                criteria.value: sum(1 for r in self._results if r.selection_criteria == criteria)
                for criteria in SelectionCriteria
            },
            "history_count": len(self._selection_history),
        }