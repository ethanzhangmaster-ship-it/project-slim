from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class AnalysisResult:
    analysis_id: str
    project_id: str
    failure_type: str = ""
    root_cause: str = ""
    contributing_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0


class FailureAnalysis:
    def __init__(self):
        self.analyses: Dict[str, AnalysisResult] = {}

    def analyze(self, project_data: Dict[str, Any], performance_data: Dict[str, Any]) -> AnalysisResult:
        failure_type = self._identify_failure_type(performance_data)
        root_cause = self._find_root_cause(project_data, performance_data)
        factors = self._find_contributing_factors(performance_data)
        recommendations = self._generate_recommendations(failure_type, factors)

        analysis = AnalysisResult(
            analysis_id=f"analysis_{hash(str(project_data)) % 10000:04d}",
            project_id=project_data.get("project_id", "unknown"),
            failure_type=failure_type,
            root_cause=root_cause,
            contributing_factors=factors,
            recommendations=recommendations,
            confidence=self._calculate_confidence(len(factors)),
        )

        self.analyses[analysis.analysis_id] = analysis
        return analysis

    def _identify_failure_type(self, data: Dict[str, Any]) -> str:
        d1 = data.get("d1", 0.5)
        d30 = data.get("d30", 0.1)
        arpdau = data.get("arpdau", 0.15)
        cpi = data.get("cpi", 2.5)

        if d1 < 0.25:
            return "retention"
        if cpi > 5.0:
            return "user_acquisition"
        if arpdau < 0.05:
            return "monetization"
        if d30 < 0.03:
            return "long_term_retention"
        return "mixed"

    def _find_root_cause(self, project_data: Dict[str, Any], data: Dict[str, Any]) -> str:
        failure_type = self._identify_failure_type(data)
        
        root_causes = {
            "retention": "Poor onboarding or unclear core loop",
            "user_acquisition": "Ineffective creative or targeting",
            "monetization": "Weak economy design or lack of value props",
            "long_term_retention": "Missing progression or content drought",
            "mixed": "Multiple factors contributing to underperformance",
        }
        
        return root_causes.get(failure_type, "Unknown")

    def _find_contributing_factors(self, data: Dict[str, Any]) -> List[str]:
        factors = []
        
        if data.get("ctr", 0.02) < 0.015:
            factors.append("Low CTR")
        if data.get("cvr", 0.03) < 0.015:
            factors.append("Low CVR")
        if data.get("d7", 0.2) < 0.1:
            factors.append("Weak D7 retention")
        if data.get("session_length", 5) < 3:
            factors.append("Short session length")
        
        return factors

    def _generate_recommendations(self, failure_type: str, factors: List[str]) -> List[str]:
        recommendations = []
        
        if failure_type == "retention":
            recommendations.append("Improve onboarding tutorial")
            recommendations.append("Add more frequent rewards")
        if failure_type == "user_acquisition":
            recommendations.append("Refresh creative assets")
            recommendations.append("Test new audience segments")
        if failure_type == "monetization":
            recommendations.append("Redesign economy system")
            recommendations.append("Add more IAP options")
        
        if "Low CTR" in factors:
            recommendations.append("Optimize ad creatives")
        if "Weak D7 retention" in factors:
            recommendations.append("Add social features")
        
        return recommendations[:5]

    def _calculate_confidence(self, factor_count: int) -> float:
        base = 0.6
        if factor_count >= 3:
            base += 0.25
        elif factor_count >= 2:
            base += 0.15
        return min(base, 0.95)

    def analyze_demo(self) -> AnalysisResult:
        project_data = {"project_id": "proj_001", "name": "Failed Game"}
        performance_data = {"d1": 0.2, "d7": 0.08, "d30": 0.02, "arpdau": 0.03, "cpi": 3.5}
        return self.analyze(project_data, performance_data)
