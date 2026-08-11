from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class OpportunityType(Enum):
    GROWTH = "growth"
    OPTIMIZATION = "optimization"
    RISK = "risk"
    EFFICIENCY = "efficiency"
    CREATIVE = "creative"
    PRODUCT = "product"


class OpportunityPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Opportunity:
    opportunity_id: str
    type: OpportunityType
    priority: OpportunityPriority
    title: str
    description: str = ""
    confidence: float = 0.0
    impact_score: float = 0.0
    effort_score: float = 0.0
    source: str = ""
    detected_at: datetime = field(default_factory=datetime.now)
    status: str = "new"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "impact_score": self.impact_score,
            "effort_score": self.effort_score,
            "source": self.source,
            "detected_at": self.detected_at.isoformat(),
            "status": self.status,
            "metadata": self.metadata,
        }

    @property
    def roi_score(self) -> float:
        if self.effort_score == 0:
            return 0
        return self.impact_score / self.effort_score


class OpportunityDetector:
    def __init__(self):
        self._opportunities: List[Opportunity] = []
        self._detection_rules: List[Dict[str, Any]] = []
        self._load_default_rules()

    def _load_default_rules(self):
        self._detection_rules = [
            {
                "name": "low_roas_campaign",
                "type": OpportunityType.OPTIMIZATION,
                "condition": lambda d: d.get("roas", 1) < 0.8,
                "title": "Campaign has low ROAS",
                "priority": OpportunityPriority.HIGH,
            },
            {
                "name": "high_fatigue_creative",
                "type": OpportunityType.CREATIVE,
                "condition": lambda d: d.get("fatigue_score", 0) > 0.7,
                "title": "Creative fatigue detected",
                "priority": OpportunityPriority.MEDIUM,
            },
            {
                "name": "retention_drop",
                "type": OpportunityType.PRODUCT,
                "condition": lambda d: d.get("d1_retention", 1) < 0.35,
                "title": "D1 retention below target",
                "priority": OpportunityPriority.HIGH,
            },
            {
                "name": "growth_opportunity",
                "type": OpportunityType.GROWTH,
                "condition": lambda d: d.get("market_growth", 0) > 0.2 and d.get("competition_level", "high") != "high",
                "title": "Market growth opportunity",
                "priority": OpportunityPriority.MEDIUM,
            },
        ]

    def add_rule(self, rule: Dict[str, Any]):
        self._detection_rules.append(rule)

    def detect_opportunities(self, data: Dict[str, Any]) -> List[Opportunity]:
        opportunities = []
        for rule in self._detection_rules:
            try:
                if rule["condition"](data):
                    opp_id = f"opp_{hash(rule['name'] + str(datetime.now())) % 100000:05d}"
                    opp = Opportunity(
                        opportunity_id=opp_id,
                        type=rule["type"],
                        priority=rule["priority"],
                        title=rule["title"],
                        confidence=random.uniform(0.7, 0.95),
                        impact_score=random.uniform(0.5, 1.0),
                        effort_score=random.uniform(0.2, 0.8),
                        source=rule["name"],
                    )
                    opportunities.append(opp)
                    self._opportunities.append(opp)
            except Exception:
                continue
        return opportunities

    def analyze_market_gap(self, market_data: Dict[str, Any]) -> List[Opportunity]:
        gaps = []
        genres = market_data.get("genres", [])
        for genre in genres:
            if genre.get("growth_rate", 0) > 0.15 and genre.get("competition", "medium") in ["low", "medium"]:
                opp = Opportunity(
                    opportunity_id=f"gap_{hash(genre['name']) % 100000:05d}",
                    type=OpportunityType.GROWTH,
                    priority=OpportunityPriority.HIGH,
                    title=f"Growth opportunity in {genre['name']}",
                    description=f"Genre {genre['name']} shows {genre['growth_rate']:.1%} growth with low competition",
                    confidence=0.85,
                    impact_score=0.8,
                    effort_score=0.5,
                    source="market_gap_analysis",
                    metadata=genre,
                )
                gaps.append(opp)
                self._opportunities.append(opp)
        return gaps

    def analyze_performance_gap(self, performance_data: Dict[str, Any]) -> List[Opportunity]:
        gaps = []
        campaigns = performance_data.get("campaigns", [])
        for campaign in campaigns:
            if campaign.get("roas", 1) > 1.5 and campaign.get("budget_utilization", 1) < 0.7:
                opp = Opportunity(
                    opportunity_id=f"perf_{hash(campaign['id']) % 100000:05d}",
                    type=OpportunityType.EFFICIENCY,
                    priority=OpportunityPriority.HIGH,
                    title=f"Scale opportunity: {campaign['id']}",
                    description=f"Campaign has {campaign['roas']:.2f} ROAS but only using {campaign['budget_utilization']:.0%} budget",
                    confidence=0.9,
                    impact_score=0.9,
                    effort_score=0.3,
                    source="performance_gap_analysis",
                    metadata=campaign,
                )
                gaps.append(opp)
                self._opportunities.append(opp)
        return gaps

    def prioritize_opportunities(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        return sorted(opportunities, key=lambda o: (o.priority.value, -o.roi_score))

    def get_top_opportunities(self, n: int = 10) -> List[Opportunity]:
        active = [o for o in self._opportunities if o.status == "new"]
        sorted_opps = self.prioritize_opportunities(active)
        return sorted_opps[:n]

    def get_opportunity(self, opportunity_id: str) -> Optional[Opportunity]:
        for opp in self._opportunities:
            if opp.opportunity_id == opportunity_id:
                return opp
        return None

    def mark_resolved(self, opportunity_id: str) -> bool:
        opp = self.get_opportunity(opportunity_id)
        if opp:
            opp.status = "resolved"
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._opportunities)
        by_type = {}
        by_priority = {}
        for opp in self._opportunities:
            by_type[opp.type.value] = by_type.get(opp.type.value, 0) + 1
            by_priority[opp.priority.name] = by_priority.get(opp.priority.name, 0) + 1

        return {
            "total_opportunities": total,
            "by_type": by_type,
            "by_priority": by_priority,
            "new_count": sum(1 for o in self._opportunities if o.status == "new"),
            "resolved_count": sum(1 for o in self._opportunities if o.status == "resolved"),
        }