from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    REPUTATIONAL = "reputational"
    COMPLIANCE = "compliance"
    TECHNICAL = "technical"


@dataclass
class RiskEvent:
    event_id: str
    category: RiskCategory
    level: RiskLevel
    description: str
    source: str = "system"
    affected_systems: List[str] = field(default_factory=list)
    potential_impact: float = 0.0
    probability: float = 0.5
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    mitigation_action: str = ""


@dataclass
class RiskAssessment:
    assessment_id: str
    overall_risk_level: RiskLevel
    overall_risk_score: float
    risks: List[RiskEvent] = field(default_factory=list)
    financial_risk: float = 0.0
    operational_risk: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)


class RiskController:
    def __init__(self):
        self._risks: Dict[str, RiskEvent] = {}
        self._assessments: List[RiskAssessment] = []
        self._thresholds = {
            "spend_spike_rate": 2.0,
            "revenue_drop_rate": 0.5,
            "install_drop_rate": 0.3,
            "crash_rate": 0.05,
            "fraud_probability": 0.7,
        }

    def detect_spend_spike(self, current_spend: float, baseline_spend: float) -> Optional[RiskEvent]:
        if baseline_spend <= 0:
            return None

        rate = current_spend / baseline_spend

        if rate >= self._thresholds["spend_spike_rate"]:
            level = RiskLevel.CRITICAL if rate >= 3.0 else RiskLevel.HIGH
            event = RiskEvent(
                event_id=f"risk_{hash(str(current_spend) + str(baseline_spend)) % 10000:04d}",
                category=RiskCategory.FINANCIAL,
                level=level,
                description=f"Spend spike detected: {rate:.1f}x baseline (${current_spend:.0f} vs ${baseline_spend:.0f})",
                source="spend_monitor",
                affected_systems=["ua_bidding"],
                potential_impact=current_spend - baseline_spend,
                probability=0.8,
            )
            self._risks[event.event_id] = event
            return event

        return None

    def detect_revenue_drop(self, current_revenue: float, baseline_revenue: float) -> Optional[RiskEvent]:
        if baseline_revenue <= 0:
            return None

        drop_rate = 1.0 - (current_revenue / baseline_revenue)

        if drop_rate >= self._thresholds["revenue_drop_rate"]:
            level = RiskLevel.CRITICAL if drop_rate >= 0.7 else RiskLevel.HIGH
            event = RiskEvent(
                event_id=f"risk_rev_{hash(str(current_revenue)) % 10000:04d}",
                category=RiskCategory.FINANCIAL,
                level=level,
                description=f"Revenue drop detected: {drop_rate*100:.0f}% decrease",
                source="revenue_monitor",
                affected_systems=["monetization", "ua"],
                potential_impact=baseline_revenue - current_revenue,
                probability=0.9,
            )
            self._risks[event.event_id] = event
            return event

        return None

    def detect_fraud(self, installs: int, suspicious_installs: int) -> Optional[RiskEvent]:
        if installs <= 0:
            return None

        fraud_rate = suspicious_installs / installs

        if fraud_rate >= 0.1:
            level = RiskLevel.HIGH if fraud_rate >= 0.2 else RiskLevel.MEDIUM
            event = RiskEvent(
                event_id=f"risk_fraud_{hash(str(installs)) % 10000:04d}",
                category=RiskCategory.FINANCIAL,
                level=level,
                description=f"Fraud detected: {fraud_rate*100:.1f}% suspicious installs",
                source="fraud_detection",
                affected_systems=["attribution", "ua"],
                potential_impact=suspicious_installs * 2.5,
                probability=fraud_rate,
            )
            self._risks[event.event_id] = event
            return event

        return None

    def detect_crash_spike(self, crash_rate: float) -> Optional[RiskEvent]:
        if crash_rate >= self._thresholds["crash_rate"]:
            level = RiskLevel.CRITICAL if crash_rate >= 0.1 else RiskLevel.HIGH
            event = RiskEvent(
                event_id=f"risk_crash_{hash(str(crash_rate)) % 10000:04d}",
                category=RiskCategory.TECHNICAL,
                level=level,
                description=f"Crash rate spike: {crash_rate*100:.1f}%",
                source="crash_monitor",
                affected_systems=["game_client", "backend"],
                potential_impact=0,
                probability=1.0,
            )
            self._risks[event.event_id] = event
            return event

        return None

    def assess_overall_risk(self, data: Dict[str, Any] = None) -> RiskAssessment:
        risks = [r for r in self._risks.values() if not r.resolved]

        if data:
            if "current_spend" in data and "baseline_spend" in data:
                self.detect_spend_spike(data["current_spend"], data["baseline_spend"])
            if "current_revenue" in data and "baseline_revenue" in data:
                self.detect_revenue_drop(data["current_revenue"], data["baseline_revenue"])
            if "crash_rate" in data:
                self.detect_crash_spike(data["crash_rate"])

        risks = [r for r in self._risks.values() if not r.resolved]

        financial_risks = [r for r in risks if r.category == RiskCategory.FINANCIAL]
        operational_risks = [r for r in risks if r.category == RiskCategory.OPERATIONAL]

        financial_score = sum(
            r.potential_impact * r.probability for r in financial_risks
        )
        operational_score = len(operational_risks) * 0.1

        overall_score = min(
            1.0,
            financial_score / 100000 + operational_score
        )

        if overall_score >= 0.7:
            overall_level = RiskLevel.CRITICAL
        elif overall_score >= 0.4:
            overall_level = RiskLevel.HIGH
        elif overall_score >= 0.2:
            overall_level = RiskLevel.MEDIUM
        else:
            overall_level = RiskLevel.LOW

        assessment = RiskAssessment(
            assessment_id=f"assess_{hash(str(datetime.now())) % 10000:04d}",
            overall_risk_level=overall_level,
            overall_risk_score=round(overall_score, 4),
            risks=risks,
            financial_risk=round(financial_score, 2),
            operational_risk=round(operational_score, 4),
        )

        self._assessments.append(assessment)
        return assessment

    def resolve_risk(self, risk_id: str, action: str = "") -> bool:
        risk = self._risks.get(risk_id)
        if risk:
            risk.resolved = True
            risk.resolved_at = datetime.now()
            risk.mitigation_action = action
            return True
        return False

    def get_active_risks(self, min_level: RiskLevel = None) -> List[RiskEvent]:
        active = [r for r in self._risks.values() if not r.resolved]
        if min_level:
            level_order = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4}
            min_order = level_order.get(min_level, 0)
            active = [r for r in active if level_order.get(r.level, 0) >= min_order]
        return sorted(active, key=lambda r: r.detected_at, reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        active = self.get_active_risks()
        critical = len(self.get_active_risks(RiskLevel.CRITICAL))
        return {
            "total_risks": len(self._risks),
            "active_risks": len(active),
            "critical_risks": critical,
            "resolved_risks": len(self._risks) - len(active),
            "total_assessments": len(self._assessments),
        }
