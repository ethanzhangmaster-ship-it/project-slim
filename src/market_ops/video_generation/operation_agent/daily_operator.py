from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class DailyReport:
    report_id: str
    date: datetime
    summary: str
    key_metrics: Dict[str, float] = field(default_factory=dict)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class DailyOperator:
    def __init__(self):
        self.workflow_steps = [
            "collect_data",
            "analyze",
            "generate_plan",
            "execute",
            "report",
        ]

    def run_daily(self, data: Dict[str, Any]) -> DailyReport:
        report_id = f"daily_report_{datetime.now().strftime('%Y%m%d')}"
        
        collected_data = self._collect_data(data)
        analysis = self._analyze(collected_data)
        plan = self._generate_plan(analysis)
        execution = self._execute(plan)
        
        return self._generate_report(report_id, analysis, plan, execution)

    def _collect_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "revenue": data.get("revenue", 0),
            "spend": data.get("spend", 0),
            "roas": data.get("roas", 0),
            "installs": data.get("installs", 0),
            "purchases": data.get("purchases", 0),
            "creatives": data.get("creatives", []),
            "campaigns": data.get("campaigns", []),
        }

    def _analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        roas = data.get("roas", 0)
        spend = data.get("spend", 0)
        revenue = data.get("revenue", 0)
        
        insights = []
        if roas > 2.0:
            insights.append("ROAS is above target")
        elif roas < 1.0:
            insights.append("ROAS is below threshold")
        
        if spend > 10000:
            insights.append("High daily spend")
        
        return {
            "insights": insights,
            "health_score": min(roas / 2.0, 1.0),
            "key_metrics": data,
        }

    def _generate_plan(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        health = analysis.get("health_score", 0.5)
        insights = analysis.get("insights", [])
        
        plan = []
        if "ROAS is above target" in insights:
            plan.append({"action": "scale_winners", "priority": 1})
        if "ROAS is below threshold" in insights:
            plan.append({"action": "optimize_underperforming", "priority": 1})
            plan.append({"action": "creative_testing", "priority": 2})
        if health > 0.7:
            plan.append({"action": "audience_expansion", "priority": 2})
        
        return plan

    def _execute(self, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for action in plan:
            results.append({
                "action": action.get("action"),
                "status": "completed",
                "priority": action.get("priority"),
            })
        return {"results": results, "success_count": len(results)}

    def _generate_report(self, report_id: str, analysis: Dict[str, Any], plan: List[Dict[str, Any]], execution: Dict[str, Any]) -> DailyReport:
        summary = f"Daily operations completed. {execution.get('success_count', 0)} actions executed."
        
        if "ROAS is above target" in analysis.get("insights", []):
            summary += " ROAS is healthy."
        elif "ROAS is below threshold" in analysis.get("insights", []):
            summary += " ROAS needs attention."

        return DailyReport(
            report_id=report_id,
            date=datetime.now(),
            summary=summary,
            key_metrics=analysis.get("key_metrics", {}),
            actions=execution.get("results", []),
            issues=[],
            recommendations=[
                "Continue monitoring performance",
                "Scale high-performing campaigns",
                "Test new creatives",
            ],
        )

    def run_daily_demo(self) -> DailyReport:
        data = {
            "revenue": 12500,
            "spend": 5000,
            "roas": 2.5,
            "installs": 2000,
            "purchases": 80,
        }
        return self.run_daily(data)
