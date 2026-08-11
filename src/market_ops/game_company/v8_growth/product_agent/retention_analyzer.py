from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class RetentionMetricType(Enum):
    D1 = "d1"
    D3 = "d3"
    D7 = "d7"
    D14 = "d14"
    D30 = "d30"
    D90 = "d90"


class CohortType(Enum):
    ALL_USERS = "all_users"
    NEW_USERS = "new_users"
    PAID_USERS = "paid_users"
    ENGAGED_USERS = "engaged_users"
    SEGMENT_A = "segment_a"
    SEGMENT_B = "segment_b"


@dataclass
class RetentionData:
    cohort_date: str
    cohort_type: CohortType
    user_count: int = 0
    retention_rates: Dict[RetentionMetricType, float] = field(default_factory=dict)
    churn_rates: Dict[RetentionMetricType, float] = field(default_factory=dict)
    arpu: float = 0.0
    avg_session_duration: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_date": self.cohort_date,
            "cohort_type": self.cohort_type.value,
            "user_count": self.user_count,
            "retention_rates": {k.value: v for k, v in self.retention_rates.items()},
            "churn_rates": {k.value: v for k, v in self.churn_rates.items()},
            "arpu": self.arpu,
            "avg_session_duration": self.avg_session_duration,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RetentionAnalysis:
    analysis_id: str
    cohort_type: CohortType
    average_d1: float = 0.0
    average_d7: float = 0.0
    average_d30: float = 0.0
    trend: str = "stable"
    churn_risk_segments: List[str] = field(default_factory=list)
    high_value_segments: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "cohort_type": self.cohort_type.value,
            "average_d1": self.average_d1,
            "average_d7": self.average_d7,
            "average_d30": self.average_d30,
            "trend": self.trend,
            "churn_risk_segments": self.churn_risk_segments,
            "high_value_segments": self.high_value_segments,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RetentionRecommendation:
    recommendation_id: str
    segment: str
    action: str
    expected_improvement: float = 0.0
    priority: int = 5
    confidence: float = 0.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "segment": self.segment,
            "action": self.action,
            "expected_improvement": self.expected_improvement,
            "priority": self.priority,
            "confidence": self.confidence,
            "description": self.description,
        }


class RetentionAnalyzer:
    def __init__(self):
        self._retention_data: Dict[str, RetentionData] = {}
        self._analyses: Dict[str, RetentionAnalysis] = {}
        self._recommendations: List[RetentionRecommendation] = []
        self._targets: Dict[RetentionMetricType, float] = {
            RetentionMetricType.D1: 0.40,
            RetentionMetricType.D7: 0.20,
            RetentionMetricType.D30: 0.10,
        }

    def record_retention(
        self,
        cohort_date: str,
        cohort_type: CohortType,
        user_count: int,
        retention_rates: Dict[str, float] = None
    ) -> RetentionData:
        data_id = f"ret_{cohort_date}_{cohort_type.value}"
        rates = {}
        churn = {}

        for metric in RetentionMetricType:
            rate = retention_rates.get(metric.value, random.uniform(0.05, 0.6)) if retention_rates else random.uniform(0.05, 0.6)
            rates[metric] = rate
            churn[metric] = 1 - rate

        data = RetentionData(
            cohort_date=cohort_date,
            cohort_type=cohort_type,
            user_count=user_count,
            retention_rates=rates,
            churn_rates=churn,
            arpu=random.uniform(1.0, 15.0),
            avg_session_duration=random.uniform(5.0, 45.0),
        )
        self._retention_data[data_id] = data
        return data

    def analyze_retention(self, cohort_type: CohortType = None) -> RetentionAnalysis:
        analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cohort_type = cohort_type or CohortType.ALL_USERS

        relevant_data = [d for d in self._retention_data.values() if d.cohort_type == cohort_type]
        if not relevant_data:
            return RetentionAnalysis(analysis_id=analysis_id, cohort_type=cohort_type)

        d1_values = [d.retention_rates.get(RetentionMetricType.D1, 0) for d in relevant_data]
        d7_values = [d.retention_rates.get(RetentionMetricType.D7, 0) for d in relevant_data]
        d30_values = [d.retention_rates.get(RetentionMetricType.D30, 0) for d in relevant_data]

        avg_d1 = sum(d1_values) / len(d1_values)
        avg_d7 = sum(d7_values) / len(d7_values)
        avg_d30 = sum(d30_values) / len(d30_values)

        trend = self._calculate_trend(relevant_data)
        churn_risk = self._identify_churn_risks(relevant_data)
        high_value = self._identify_high_value(relevant_data)
        recs = self._generate_recommendations(avg_d1, avg_d7, avg_d30, trend)

        analysis = RetentionAnalysis(
            analysis_id=analysis_id,
            cohort_type=cohort_type,
            average_d1=avg_d1,
            average_d7=avg_d7,
            average_d30=avg_d30,
            trend=trend,
            churn_risk_segments=churn_risk,
            high_value_segments=high_value,
            recommendations=recs,
        )
        self._analyses[analysis_id] = analysis
        return analysis

    def _calculate_trend(self, data: List[RetentionData]) -> str:
        if len(data) < 5:
            return "insufficient_data"

        recent_d7 = [d.retention_rates.get(RetentionMetricType.D7, 0) for d in data[-5:]]
        older_d7 = [d.retention_rates.get(RetentionMetricType.D7, 0) for d in data[:-5]] if len(data) > 5 else recent_d7

        recent_avg = sum(recent_d7) / len(recent_d7)
        older_avg = sum(older_d7) / len(older_d7)

        if recent_avg > older_avg * 1.1:
            return "improving"
        elif recent_avg < older_avg * 0.9:
            return "declining"
        return "stable"

    def _identify_churn_risks(self, data: List[RetentionData]) -> List[str]:
        risks = []
        for d in data:
            d1 = d.retention_rates.get(RetentionMetricType.D1, 0)
            if d1 < self._targets[RetentionMetricType.D1] * 0.7:
                risks.append(f"{d.cohort_date}_{d.cohort_type.value}")
        return risks[:10]

    def _identify_high_value(self, data: List[RetentionData]) -> List[str]:
        high = []
        for d in data:
            d7 = d.retention_rates.get(RetentionMetricType.D7, 0)
            if d7 > self._targets[RetentionMetricType.D7] * 1.2:
                high.append(f"{d.cohort_date}_{d.cohort_type.value}")
        return high[:10]

    def _generate_recommendations(self, d1: float, d7: float, d30: float, trend: str) -> List[str]:
        recs = []
        if d1 < self._targets[RetentionMetricType.D1]:
            recs.append("Improve first day experience - tutorial and onboarding optimization")
        if d7 < self._targets[RetentionMetricType.D7]:
            recs.append("Engage users in week 1 - push notifications and daily rewards")
        if d30 < self._targets[RetentionMetricType.D30]:
            recs.append("Increase long-term engagement - events and social features")
        if trend == "declining":
            recs.append("Retention trend declining - investigate recent changes")
        if not recs:
            recs.append("Retention metrics healthy - continue current strategy")
        return recs

    def get_retention_data(self, cohort_type: CohortType = None) -> List[RetentionData]:
        data = list(self._retention_data.values())
        if cohort_type:
            data = [d for d in data if d.cohort_type == cohort_type]
        return data

    def get_analysis(self, analysis_id: str) -> Optional[RetentionAnalysis]:
        return self._analyses.get(analysis_id)

    def get_all_analyses(self) -> List[RetentionAnalysis]:
        return list(self._analyses.values())

    def set_target(self, metric: RetentionMetricType, target: float):
        self._targets[metric] = target

    def get_targets(self) -> Dict[str, float]:
        return {k.value: v for k, v in self._targets.items()}

    def get_stats(self) -> Dict[str, Any]:
        data = list(self._retention_data.values())
        return {
            "total_retention_records": len(data),
            "records_by_cohort_type": {
                ct.value: sum(1 for d in data if d.cohort_type == ct)
                for ct in CohortType
            },
            "total_analyses": len(self._analyses),
            "current_targets": self.get_targets(),
        }