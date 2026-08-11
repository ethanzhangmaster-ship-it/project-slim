from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class CampaignAction(Enum):
    SCALE = "scale"
    HOLD = "hold"
    REDUCE = "reduce"
    PAUSE = "pause"


@dataclass
class CampaignScore:
    campaign_id: str
    roas_score: float = 0.0
    retention_score: float = 0.0
    creative_score: float = 0.0
    cost_score: float = 0.0
    overall_score: float = 0.0
    action: CampaignAction = CampaignAction.HOLD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "roas_score": self.roas_score,
            "retention_score": self.retention_score,
            "creative_score": self.creative_score,
            "cost_score": self.cost_score,
            "overall_score": self.overall_score,
            "action": self.action.value,
        }


@dataclass
class OptimizationSuggestion:
    suggestion_id: str
    campaign_id: str
    category: str
    suggestion: str
    expected_impact: float = 0.0
    effort: float = 0.0
    confidence: float = 0.0
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "campaign_id": self.campaign_id,
            "category": self.category,
            "suggestion": self.suggestion,
            "expected_impact": self.expected_impact,
            "effort": self.effort,
            "confidence": self.confidence,
            "priority": self.priority,
        }


@dataclass
class CampaignAnalysis:
    campaign_id: str
    score: CampaignScore
    metrics: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[OptimizationSuggestion] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "score": self.score.to_dict(),
            "metrics": self.metrics,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class CampaignOptimizer:
    def __init__(self):
        self._analyses: Dict[str, CampaignAnalysis] = {}

    def analyze_campaign(self, campaign_id: str) -> CampaignAnalysis:
        roas = random.uniform(0.5, 3.0)
        retention = random.uniform(0.2, 0.6)
        creative = random.uniform(0.4, 1.0)
        cost = random.uniform(0.3, 1.0)

        roas_score = min(100, roas * 40)
        retention_score = retention * 100
        creative_score = creative * 100
        cost_score = cost * 100
        overall = (roas_score + retention_score + creative_score + cost_score) / 4

        if overall > 70:
            action = CampaignAction.SCALE
        elif overall > 40:
            action = CampaignAction.HOLD
        elif overall > 20:
            action = CampaignAction.REDUCE
        else:
            action = CampaignAction.PAUSE

        score = CampaignScore(
            campaign_id=campaign_id,
            roas_score=roas_score,
            retention_score=retention_score,
            creative_score=creative_score,
            cost_score=cost_score,
            overall_score=overall,
            action=action,
        )

        suggestions = self._generate_suggestions(campaign_id, score)

        analysis = CampaignAnalysis(
            campaign_id=campaign_id,
            score=score,
            metrics={"roas": roas, "retention": retention, "creative": creative, "cost": cost},
            suggestions=suggestions,
        )
        self._analyses[campaign_id] = analysis
        return analysis

    def _generate_suggestions(self, campaign_id: str, score: CampaignScore) -> List[OptimizationSuggestion]:
        suggestions = []

        if score.roas_score < 50:
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"sug_{campaign_id}_roas",
                campaign_id=campaign_id,
                category="roas",
                suggestion="Review targeting and creative to improve ROAS",
                expected_impact=0.3,
                effort=0.4,
                confidence=0.8,
                priority=1,
            ))

        if score.creative_score < 50:
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"sug_{campaign_id}_creative",
                campaign_id=campaign_id,
                category="creative",
                suggestion="Refresh ad creatives to combat fatigue",
                expected_impact=0.2,
                effort=0.3,
                confidence=0.75,
                priority=2,
            ))

        if score.cost_score < 50:
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"sug_{campaign_id}_cost",
                campaign_id=campaign_id,
                category="cost",
                suggestion="Optimize bidding strategy to reduce CPI",
                expected_impact=0.25,
                effort=0.3,
                confidence=0.7,
                priority=2,
            ))

        return suggestions

    def get_optimization_suggestions(self, campaign_id: str) -> List[OptimizationSuggestion]:
        analysis = self._analyses.get(campaign_id)
        return analysis.suggestions if analysis else []

    def scale_if_profitable(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        analysis = self._analyses.get(campaign_id)
        if analysis and analysis.score.action == CampaignAction.SCALE:
            return {
                "campaign_id": campaign_id,
                "action": "scale",
                "amount": random.uniform(20, 50),
                "reason": f"Overall score {analysis.score.overall_score:.1f}",
            }
        return None

    def pause_if_unprofitable(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        analysis = self._analyses.get(campaign_id)
        if analysis and analysis.score.action == CampaignAction.PAUSE:
            return {
                "campaign_id": campaign_id,
                "action": "pause",
                "reason": f"Overall score {analysis.score.overall_score:.1f} is too low",
            }
        return None

    def get_analysis(self, campaign_id: str) -> Optional[CampaignAnalysis]:
        return self._analyses.get(campaign_id)

    def get_all_analyses(self) -> List[CampaignAnalysis]:
        return list(self._analyses.values())

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._analyses)
        by_action = {}
        for analysis in self._analyses.values():
            action = analysis.score.action.value
            by_action[action] = by_action.get(action, 0) + 1

        return {
            "total_analyzed": total,
            "by_action": by_action,
            "avg_score": sum(a.score.overall_score for a in self._analyses.values()) / total if total > 0 else 0,
        }