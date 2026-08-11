from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class OutcomeType(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    INCONCLUSIVE = "inconclusive"


class AnalysisScope(Enum):
    ACTION = "action"
    CAMPAIGN = "campaign"
    PRODUCT = "product"
    STRATEGY = "strategy"


@dataclass
class Outcome:
    outcome_id: str
    action_id: str
    outcome_type: OutcomeType
    scope: AnalysisScope = AnalysisScope.ACTION
    metrics: Dict[str, float] = field(default_factory=dict)
    actual_impact: float = 0.0
    expected_impact: float = 0.0
    impact_deviation: float = 0.0
    duration: float = 0.0
    confidence: float = 0.0
    lessons: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "action_id": self.action_id,
            "outcome_type": self.outcome_type.value,
            "scope": self.scope.value,
            "metrics": self.metrics,
            "actual_impact": self.actual_impact,
            "expected_impact": self.expected_impact,
            "impact_deviation": self.impact_deviation,
            "duration": self.duration,
            "confidence": self.confidence,
            "lessons": self.lessons,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class OutcomeAnalysis:
    analysis_id: str
    outcome_ids: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    average_impact: float = 0.0
    prediction_accuracy: float = 0.0
    key_patterns: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "outcome_ids": self.outcome_ids,
            "success_rate": self.success_rate,
            "average_impact": self.average_impact,
            "prediction_accuracy": self.prediction_accuracy,
            "key_patterns": self.key_patterns,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PerformanceTrend:
    metric_name: str
    values: List[float] = field(default_factory=list)
    trend_direction: str = "stable"
    change_rate: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "values": self.values,
            "trend_direction": self.trend_direction,
            "change_rate": self.change_rate,
            "confidence": self.confidence,
        }


class OutcomeAnalyzer:
    def __init__(self):
        self._outcomes: Dict[str, Outcome] = {}
        self._analyses: Dict[str, OutcomeAnalysis] = []
        self._trends: Dict[str, PerformanceTrend] = {}
        self._history: List[Dict[str, Any]] = []

    def record_outcome(
        self,
        action_id: str,
        outcome_type: OutcomeType,
        metrics: Dict[str, float],
        expected_impact: float = 0.0
    ) -> Outcome:
        outcome_id = f"out_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        actual_impact = metrics.get("impact", random.uniform(-0.2, 0.5))
        deviation = actual_impact - expected_impact

        lessons = self._generate_lessons(outcome_type, actual_impact, deviation)

        outcome = Outcome(
            outcome_id=outcome_id,
            action_id=action_id,
            outcome_type=outcome_type,
            metrics=metrics,
            actual_impact=actual_impact,
            expected_impact=expected_impact,
            impact_deviation=deviation,
            duration=metrics.get("duration", random.uniform(1, 30)),
            confidence=random.uniform(0.7, 0.95),
            lessons=lessons,
        )
        self._outcomes[outcome_id] = outcome
        self._update_history(outcome)
        return outcome

    def _generate_lessons(self, outcome_type: OutcomeType, impact: float, deviation: float) -> List[str]:
        lessons = []
        if outcome_type == OutcomeType.SUCCESS:
            lessons.append("Action achieved expected results")
            if deviation > 0.1:
                lessons.append("Exceeded expectations - consider similar approaches")
        elif outcome_type == OutcomeType.PARTIAL:
            lessons.append("Partial success - review execution")
            if deviation < -0.1:
                lessons.append("Underperformed - investigate causes")
        elif outcome_type == OutcomeType.FAILURE:
            lessons.append("Action failed - avoid similar approach")
            lessons.append("Review preconditions and assumptions")
        return lessons

    def _update_history(self, outcome: Outcome):
        self._history.append({
            "outcome_id": outcome.outcome_id,
            "action_id": outcome.action_id,
            "outcome_type": outcome.outcome_type.value,
            "actual_impact": outcome.actual_impact,
            "timestamp": outcome.created_at.isoformat(),
        })

    def analyze_outcomes(self, scope: AnalysisScope = AnalysisScope.ACTION) -> OutcomeAnalysis:
        analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        outcomes = list(self._outcomes.values())

        if not outcomes:
            return OutcomeAnalysis(analysis_id=analysis_id)

        success_count = sum(1 for o in outcomes if o.outcome_type == OutcomeType.SUCCESS)
        success_rate = success_count / len(outcomes)

        avg_impact = sum(o.actual_impact for o in outcomes) / len(outcomes)

        predictions = [o for o in outcomes if o.expected_impact != 0]
        if predictions:
            accuracy = 1 - sum(abs(o.impact_deviation) for o in predictions) / len(predictions)
        else:
            accuracy = 0.0

        patterns = self._identify_patterns(outcomes)
        recommendations = self._generate_recommendations(success_rate, avg_impact, patterns)

        analysis = OutcomeAnalysis(
            analysis_id=analysis_id,
            outcome_ids=[o.outcome_id for o in outcomes],
            success_rate=success_rate,
            average_impact=avg_impact,
            prediction_accuracy=accuracy,
            key_patterns=patterns,
            recommendations=recommendations,
        )
        self._analyses.append(analysis)
        return analysis

    def _identify_patterns(self, outcomes: List[Outcome]) -> List[str]:
        patterns = []
        success_outcomes = [o for o in outcomes if o.outcome_type == OutcomeType.SUCCESS]
        if len(success_outcomes) > len(outcomes) * 0.7:
            patterns.append("High success rate - current approach is effective")
        elif len(success_outcomes) < len(outcomes) * 0.3:
            patterns.append("Low success rate - strategy needs revision")

        avg_deviation = sum(o.impact_deviation for o in outcomes) / len(outcomes) if outcomes else 0
        if avg_deviation > 0.1:
            patterns.append("Consistently exceeding predictions")
        elif avg_deviation < -0.1:
            patterns.append("Consistently underperforming expectations")
        return patterns

    def _generate_recommendations(self, success_rate: float, avg_impact: float, patterns: List[str]) -> List[str]:
        recommendations = []
        if success_rate > 0.7:
            recommendations.append("Continue current approach")
            recommendations.append("Scale successful actions")
        elif success_rate < 0.3:
            recommendations.append("Review and revise strategy")
            recommendations.append("Reduce risky actions")
        if avg_impact < 0:
            recommendations.append("Focus on high-impact actions")
        return recommendations

    def get_outcome(self, outcome_id: str) -> Optional[Outcome]:
        return self._outcomes.get(outcome_id)

    def get_outcomes(self, outcome_type: OutcomeType = None) -> List[Outcome]:
        if outcome_type:
            return [o for o in self._outcomes.values() if o.outcome_type == outcome_type]
        return list(self._outcomes.values())

    def get_analysis(self, analysis_id: str) -> Optional[OutcomeAnalysis]:
        for analysis in self._analyses:
            if analysis.analysis_id == analysis_id:
                return analysis
        return None

    def get_all_analyses(self) -> List[OutcomeAnalysis]:
        return list(self._analyses)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def get_stats(self) -> Dict[str, Any]:
        outcomes = list(self._outcomes.values())
        return {
            "total_outcomes": len(outcomes),
            "outcomes_by_type": {
                t.value: sum(1 for o in outcomes if o.outcome_type == t)
                for t in OutcomeType
            },
            "total_analyses": len(self._analyses),
            "history_count": len(self._history),
        }