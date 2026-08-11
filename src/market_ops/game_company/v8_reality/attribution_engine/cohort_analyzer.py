from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class Cohort:
    cohort_id: str
    cohort_date: datetime
    user_count: int
    platform: Optional[str] = None
    country: Optional[str] = None
    acquisition_channel: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "cohort_date": self.cohort_date.isoformat(),
            "user_count": self.user_count,
            "platform": self.platform,
            "country": self.country,
            "acquisition_channel": self.acquisition_channel,
        }


@dataclass
class RetentionCurve:
    cohort_id: str
    day_0: float = 1.0
    day_1: float = 0.0
    day_3: float = 0.0
    day_7: float = 0.0
    day_14: float = 0.0
    day_30: float = 0.0
    day_60: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "day_0": self.day_0,
            "day_1": self.day_1,
            "day_3": self.day_3,
            "day_7": self.day_7,
            "day_14": self.day_14,
            "day_30": self.day_30,
            "day_60": self.day_60,
        }

    @property
    def curve_points(self) -> List[float]:
        return [self.day_0, self.day_1, self.day_3, self.day_7, self.day_14, self.day_30, self.day_60]


@dataclass
class CohortAnalysis:
    analysis_id: str
    cohort: Cohort
    retention_curve: RetentionCurve
    metrics: Dict[str, float] = field(default_factory=dict)
    analysis_date: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "cohort": self.cohort.to_dict(),
            "retention_curve": self.retention_curve.to_dict(),
            "metrics": self.metrics,
            "analysis_date": self.analysis_date.isoformat() if self.analysis_date else None,
        }


class CohortAnalyzer:
    def __init__(self):
        self._cohorts: Dict[str, Cohort] = {}
        self._analyses: Dict[str, CohortAnalysis] = {}

    def analyze_cohort(self, cohort_data: Dict[str, Any]) -> CohortAnalysis:
        now = datetime.now()
        cohort_date = cohort_data.get("cohort_date", now)
        if isinstance(cohort_date, str):
            cohort_date = datetime.fromisoformat(cohort_date)

        cohort = Cohort(
            cohort_id=f"cohort_{hash(str(cohort_date)) % 100000:05d}",
            cohort_date=cohort_date,
            user_count=cohort_data.get("user_count", 1000),
            platform=cohort_data.get("platform"),
            country=cohort_data.get("country"),
            acquisition_channel=cohort_data.get("channel"),
        )

        self._cohorts[cohort.cohort_id] = cohort

        retention_curve = RetentionCurve(
            cohort_id=cohort.cohort_id,
            day_0=1.0,
            day_1=0.45 + (cohort_data.get("retention_offset", 0) * 0.05),
            day_3=0.32,
            day_7=0.22,
            day_14=0.15,
            day_30=0.08,
            day_60=0.04,
        )

        metrics = {
            "avg_session_duration": 180.5,
            "avg_revenue_per_user": 2.34,
            "conversion_rate": 3.8,
            "ltv": 15.67,
            "arpu": 4.52,
        }

        analysis = CohortAnalysis(
            analysis_id=f"analysis_{hash(str(now)) % 100000:05d}",
            cohort=cohort,
            retention_curve=retention_curve,
            metrics=metrics,
            analysis_date=now,
        )

        self._analyses[analysis.analysis_id] = analysis
        return analysis

    def calculate_retention(self, cohort_id: str) -> RetentionCurve:
        cohort = self._cohorts.get(cohort_id)
        if not cohort:
            return RetentionCurve(cohort_id=cohort_id)

        base_retention = 0.45
        day_offset = (datetime.now() - cohort.cohort_date).days

        retention_curve = RetentionCurve(
            cohort_id=cohort_id,
            day_0=1.0,
            day_1=base_retention if day_offset >= 1 else 0.0,
            day_3=base_retention * 0.7 if day_offset >= 3 else 0.0,
            day_7=base_retention * 0.5 if day_offset >= 7 else 0.0,
            day_14=base_retention * 0.33 if day_offset >= 14 else 0.0,
            day_30=base_retention * 0.18 if day_offset >= 30 else 0.0,
            day_60=base_retention * 0.09 if day_offset >= 60 else 0.0,
        )

        return retention_curve

    def get_cohort_report(self, cohort_id: str) -> Dict[str, Any]:
        cohort = self._cohorts.get(cohort_id)
        if not cohort:
            return {"error": f"Cohort {cohort_id} not found"}

        retention_curve = self.calculate_retention(cohort_id)

        return {
            "report_id": f"report_{cohort_id}",
            "generated_at": datetime.now().isoformat(),
            "cohort": cohort.to_dict(),
            "retention_curve": retention_curve.to_dict(),
            "summary": {
                "total_users": cohort.user_count,
                "day_1_retention": retention_curve.day_1,
                "day_7_retention": retention_curve.day_7,
                "day_30_retention": retention_curve.day_30,
                "projected_ltv": cohort.user_count * 15.67,
            },
        }

    def compare_cohorts(self) -> Dict[str, Any]:
        if len(self._cohorts) < 2:
            return {"error": "Need at least 2 cohorts to compare"}

        cohorts_list = list(self._cohorts.values())
        comparison_data = []

        for cohort in cohorts_list:
            retention = self.calculate_retention(cohort.cohort_id)
            comparison_data.append({
                "cohort_id": cohort.cohort_id,
                "cohort_date": cohort.cohort_date.isoformat(),
                "user_count": cohort.user_count,
                "day_1_retention": retention.day_1,
                "day_7_retention": retention.day_7,
                "day_30_retention": retention.day_30,
            })

        comparison_data.sort(key=lambda x: x["cohort_date"])

        return {
            "comparison_id": f"comp_{hash(str(datetime.now())) % 100000:05d}",
            "generated_at": datetime.now().isoformat(),
            "cohorts_count": len(cohorts_list),
            "comparison": comparison_data,
            "insights": {
                "best_day_1": max(comparison_data, key=lambda x: x["day_1_retention"])["cohort_id"],
                "worst_day_1": min(comparison_data, key=lambda x: x["day_1_retention"])["cohort_id"],
                "trend": "up" if comparison_data[-1]["day_7_retention"] > comparison_data[0]["day_7_retention"] else "down",
            },
        }

    def get_cohorts(self) -> List[Cohort]:
        return list(self._cohorts.values())