from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


@dataclass
class WeeklyReviewResult:
    week_start: str
    week_end: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    insights: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    completed_at: Optional[datetime] = None


class WeeklyReview:
    def __init__(self):
        self._reviews: Dict[str, WeeklyReviewResult] = {}
        self._metrics_reviewers: Dict[str, Any] = {}

    def get_week_dates(self, date: datetime = None) -> tuple:
        if date is None:
            date = datetime.now()
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=6)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def run_review(
        self,
        metrics_data: Dict[str, Any] = None,
        week_start: str = None,
        week_end: str = None,
    ) -> WeeklyReviewResult:
        if week_start is None or week_end is None:
            week_start, week_end = self.get_week_dates()

        review = WeeklyReviewResult(
            week_start=week_start,
            week_end=week_end,
        )

        if metrics_data:
            review.metrics = metrics_data
        else:
            review.metrics = self._generate_sample_metrics()

        review.insights = self._generate_insights(review.metrics)
        review.decisions = self._generate_decisions(review.insights)
        review.action_items = self._generate_action_items(review.decisions)
        review.completed_at = datetime.now()

        self._reviews[week_start] = review
        return review

    def _generate_sample_metrics(self) -> Dict[str, Any]:
        return {
            "revenue": {
                "this_week": 85420.50,
                "last_week": 78250.30,
                "change_percent": 9.2,
            },
            "spend": {
                "this_week": 42500.00,
                "last_week": 38000.00,
                "change_percent": 11.8,
            },
            "roi": {
                "this_week": 2.01,
                "last_week": 2.06,
                "change_percent": -2.4,
            },
            "installs": {
                "this_week": 45000,
                "last_week": 41200,
                "change_percent": 9.2,
            },
            "d7_retention": {
                "this_week": 0.185,
                "last_week": 0.178,
                "change_percent": 3.9,
            },
            "arpdau": {
                "this_week": 0.152,
                "last_week": 0.148,
                "change_percent": 2.7,
            },
        }

    def _generate_insights(self, metrics: Dict[str, Any]) -> List[str]:
        insights = []

        revenue = metrics.get("revenue", {}).get("change_percent", 0)
        if revenue > 5:
            insights.append(f"Revenue grew {revenue:.1f}% WoW, outperforming target")
        elif revenue < -5:
            insights.append(f"Revenue declined {abs(revenue):.1f}% WoW, needs investigation")

        spend = metrics.get("spend", {}).get("change_percent", 0)
        if spend > 10:
            insights.append(f"Spend increased {spend:.1f}% WoW, monitoring ROI impact")

        roi = metrics.get("roi", {}).get("this_week", 0)
        if roi >= 2.0:
            insights.append(f"ROI strong at {roi}x, room for scaling")
        elif roi < 1.5:
            insights.append(f"ROI at {roi}x, below target, optimization needed")

        retention = metrics.get("d7_retention", {}).get("change_percent", 0)
        if retention > 3:
            insights.append(f"D7 retention improved {retention:.1f}%, product changes working")

        return insights

    def _generate_decisions(self, insights: List[str]) -> List[str]:
        decisions = []

        for insight in insights:
            if "scaling" in insight.lower():
                decisions.append("Increase UA budget by 15% for top-performing channels")
            elif "optimization needed" in insight.lower():
                decisions.append("Reduce spend on underperforming campaigns by 20%")
            elif "retention" in insight.lower() and "improved" in insight.lower():
                decisions.append("Scale up creative testing with retention-focused hooks")

        if not decisions:
            decisions.append("Maintain current strategy, continue monitoring")

        return decisions

    def _generate_action_items(self, decisions: List[str]) -> List[Dict[str, Any]]:
        items = []
        for i, decision in enumerate(decisions):
            items.append({
                "id": f"action_{i:02d}",
                "decision": decision,
                "owner": "AI CEO",
                "priority": "high" if i == 0 else "medium",
                "status": "pending",
                "due_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            })
        return items

    def get_review(self, week_start: str) -> Optional[WeeklyReviewResult]:
        return self._reviews.get(week_start)

    def get_recent_reviews(self, count: int = 4) -> List[WeeklyReviewResult]:
        reviews = sorted(self._reviews.values(), key=lambda r: r.week_start, reverse=True)
        return reviews[:count]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_reviews": len(self._reviews),
            "latest_week": max(self._reviews.keys()) if self._reviews else None,
            "total_insights": sum(len(r.insights) for r in self._reviews.values()),
            "total_action_items": sum(len(r.action_items) for r in self._reviews.values()),
        }
