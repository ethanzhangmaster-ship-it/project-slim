from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class HypothesisStatus(Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ConfidenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class Hypothesis:
    hypothesis_id: str
    title: str
    description: str
    category: str = "growth"
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    priority: int = 5
    expected_impact: float = 0.0
    risk_level: str = "medium"
    metrics_to_validate: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    validated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "status": self.status.value,
            "confidence": self.confidence.value,
            "priority": self.priority,
            "expected_impact": self.expected_impact,
            "risk_level": self.risk_level,
            "metrics_to_validate": self.metrics_to_validate,
            "assumptions": self.assumptions,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat(),
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
        }


@dataclass
class HypothesisEvidence:
    evidence_id: str
    hypothesis_id: str
    source: str
    data_type: str
    value: Any
    confidence: float = 0.0
    supports_hypothesis: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "hypothesis_id": self.hypothesis_id,
            "source": self.source,
            "data_type": self.data_type,
            "value": self.value,
            "confidence": self.confidence,
            "supports_hypothesis": self.supports_hypothesis,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HypothesisRecommendation:
    hypothesis_id: str
    action: str
    reason: str = ""
    confidence_score: float = 0.0
    next_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "action": self.action,
            "reason": self.reason,
            "confidence_score": self.confidence_score,
            "next_steps": self.next_steps,
        }


class HypothesisEngine:
    def __init__(self):
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._evidence: Dict[str, List[HypothesisEvidence]] = {}
        self._recommendations: List[HypothesisRecommendation] = []
        self._categories = ["growth", "retention", "monetization", "engagement", "viral", "product"]

    def create_hypothesis(
        self,
        title: str,
        description: str,
        category: str = "growth",
        expected_impact: float = 0.0,
        metrics: List[str] = None,
        assumptions: List[str] = None
    ) -> Hypothesis:
        hypothesis_id = f"hyp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        hypothesis = Hypothesis(
            hypothesis_id=hypothesis_id,
            title=title,
            description=description,
            category=category,
            expected_impact=expected_impact,
            metrics_to_validate=metrics or ["conversion_rate", "retention"],
            assumptions=assumptions or [],
        )
        self._hypotheses[hypothesis_id] = hypothesis
        return hypothesis

    def add_evidence(
        self,
        hypothesis_id: str,
        source: str,
        data_type: str,
        value: Any,
        supports: bool = True,
        confidence: float = 0.8
    ) -> HypothesisEvidence:
        evidence_id = f"ev_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        evidence = HypothesisEvidence(
            evidence_id=evidence_id,
            hypothesis_id=hypothesis_id,
            source=source,
            data_type=data_type,
            value=value,
            confidence=confidence,
            supports_hypothesis=supports,
        )

        if hypothesis_id not in self._evidence:
            self._evidence[hypothesis_id] = []
        self._evidence[hypothesis_id].append(evidence)

        hypothesis = self._hypotheses.get(hypothesis_id)
        if hypothesis:
            hypothesis.evidence.append(evidence_id)

        self._update_confidence(hypothesis_id)
        return evidence

    def _update_confidence(self, hypothesis_id: str):
        hypothesis = self._hypotheses.get(hypothesis_id)
        if not hypothesis:
            return

        evidence_list = self._evidence.get(hypothesis_id, [])
        if not evidence_list:
            return

        supporting = [e for e in evidence_list if e.supports_hypothesis]
        total_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)

        if len(supporting) >= len(evidence_list) * 0.8 and total_confidence > 0.8:
            hypothesis.confidence = ConfidenceLevel.VERY_HIGH
        elif len(supporting) >= len(evidence_list) * 0.6:
            hypothesis.confidence = ConfidenceLevel.HIGH
        elif len(supporting) >= len(evidence_list) * 0.4:
            hypothesis.confidence = ConfidenceLevel.MEDIUM
        else:
            hypothesis.confidence = ConfidenceLevel.LOW

    def validate_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        hypothesis = self._hypotheses.get(hypothesis_id)
        if not hypothesis:
            return None

        evidence_list = self._evidence.get(hypothesis_id, [])
        supporting = [e for e in evidence_list if e.supports_hypothesis]

        if len(supporting) >= len(evidence_list) * 0.7 and len(evidence_list) >= 3:
            hypothesis.status = HypothesisStatus.VALIDATED
        else:
            hypothesis.status = HypothesisStatus.REJECTED

        hypothesis.validated_at = datetime.now()
        return hypothesis

    def generate_recommendations(self) -> List[HypothesisRecommendation]:
        recommendations = []

        for hypothesis_id, hypothesis in self._hypotheses.items():
            if hypothesis.status == HypothesisStatus.PROPOSED:
                evidence_count = len(self._evidence.get(hypothesis_id, []))
                if evidence_count >= 3:
                    rec = HypothesisRecommendation(
                        hypothesis_id=hypothesis_id,
                        action="validate",
                        reason="Sufficient evidence collected for validation",
                        confidence_score=random.uniform(0.7, 0.95),
                        next_steps=["Run statistical analysis", "Document findings"],
                    )
                    recommendations.append(rec)
                else:
                    rec = HypothesisRecommendation(
                        hypothesis_id=hypothesis_id,
                        action="collect_evidence",
                        reason=f"Need more evidence ({evidence_count}/3 minimum)",
                        confidence_score=0.5,
                        next_steps=["Gather quantitative data", "Run A/B test"],
                    )
                    recommendations.append(rec)

            elif hypothesis.status == HypothesisStatus.VALIDATED:
                rec = HypothesisRecommendation(
                    hypothesis_id=hypothesis_id,
                    action="implement",
                    reason="Hypothesis validated - ready for implementation",
                    confidence_score=0.9,
                    next_steps=["Create implementation plan", "Allocate resources"],
                )
                recommendations.append(rec)

        self._recommendations.extend(recommendations)
        return recommendations

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        return self._hypotheses.get(hypothesis_id)

    def get_hypotheses_by_status(self, status: HypothesisStatus) -> List[Hypothesis]:
        return [h for h in self._hypotheses.values() if h.status == status]

    def get_hypotheses_by_category(self, category: str) -> List[Hypothesis]:
        return [h for h in self._hypotheses.values() if h.category == category]

    def get_all_hypotheses(self) -> List[Hypothesis]:
        return list(self._hypotheses.values())

    def get_evidence(self, hypothesis_id: str) -> List[HypothesisEvidence]:
        return self._evidence.get(hypothesis_id, [])

    def get_recommendations(self) -> List[HypothesisRecommendation]:
        return list(self._recommendations)

    def get_stats(self) -> Dict[str, Any]:
        hypotheses = list(self._hypotheses.values())
        return {
            "total_hypotheses": len(hypotheses),
            "hypotheses_by_status": {
                status.value: sum(1 for h in hypotheses if h.status == status)
                for status in HypothesisStatus
            },
            "hypotheses_by_category": {
                cat: sum(1 for h in hypotheses if h.category == cat)
                for cat in self._categories
            },
            "hypotheses_by_confidence": {
                conf.value: sum(1 for h in hypotheses if h.confidence == conf)
                for conf in ConfidenceLevel
            },
            "total_evidence_items": sum(len(e) for e in self._evidence.values()),
            "total_recommendations": len(self._recommendations),
        }