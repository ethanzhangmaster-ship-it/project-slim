from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class ProjectHealth:
    project_id: str
    financial_health: float
    schedule_health: float
    team_health: float
    quality_health: float
    overall_health_score: float = 0.0
    health_status: str = "unknown"
    assessed_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.overall_health_score == 0.0:
            self.overall_health_score = round(
                (self.financial_health * 0.30
                 + self.schedule_health * 0.25
                 + self.team_health * 0.25
                 + self.quality_health * 0.20), 2
            )
        if self.health_status == "unknown":
            if self.overall_health_score >= 0.7:
                self.health_status = "healthy"
            elif self.overall_health_score >= 0.4:
                self.health_status = "at_risk"
            else:
                self.health_status = "critical"


@dataclass
class KillRecommendation:
    recommendation_id: str
    project_id: str
    should_kill: bool
    confidence: float
    primary_reasons: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    recommended_at: datetime = field(default_factory=datetime.utcnow)


class KillDecision:
    def __init__(self, kill_threshold: float = 0.3):
        self._kill_threshold = kill_threshold
        self._health_records: Dict[str, ProjectHealth] = {}
        self._recommendations: List[KillRecommendation] = []

    def analyze_project_health(self, project: dict) -> ProjectHealth:
        project_id = project.get("project_id", "unknown")

        health = ProjectHealth(
            project_id=project_id,
            financial_health=project.get("financial_health", 0.5),
            schedule_health=project.get("schedule_health", 0.5),
            team_health=project.get("team_health", 0.5),
            quality_health=project.get("quality_health", 0.5),
        )
        self._health_records[project_id] = health
        return health

    def should_kill(self, project: dict) -> KillRecommendation:
        project_id = project.get("project_id", "unknown")
        health = self.analyze_project_health(project)

        reasons = []
        alternatives = ["reduce_scope", "extend_timeline", "inject_resources"]

        if health.financial_health < self._kill_threshold:
            reasons.append("financial_health_critical")
        if health.schedule_health < self._kill_threshold:
            reasons.append("schedule_irrecoverable")
        if health.team_health < self._kill_threshold:
            reasons.append("team_instability")
        if health.quality_health < self._kill_threshold:
            reasons.append("quality_unacceptable")

        should_kill = health.overall_health_score < self._kill_threshold or len(reasons) >= 3
        confidence = min(0.99, max(0.5, 1.0 - health.overall_health_score))

        if not should_kill:
            alternatives = ["continue_monitoring"]

        rec = KillRecommendation(
            recommendation_id=f"kr-{project_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            project_id=project_id,
            should_kill=should_kill,
            confidence=round(confidence, 2),
            primary_reasons=reasons,
            alternatives=alternatives,
        )
        self._recommendations.append(rec)
        return rec

    def get_kill_candidates(self) -> List[KillRecommendation]:
        return [rec for rec in self._recommendations if rec.should_kill]
