"""Reflection - 反思模块"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class ReflectionResult:
    """反思结果"""
    reflection_id: str = ""
    plan_id: str = ""
    successes: List[str] = None
    failures: List[str] = None
    insights: List[str] = None
    improvements: List[str] = None
    overall_score: float = 0.0
    
    def __post_init__(self):
        if self.successes is None:
            self.successes = []
        if self.failures is None:
            self.failures = []
        if self.insights is None:
            self.insights = []
        if self.improvements is None:
            self.improvements = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "plan_id": self.plan_id,
            "successes": self.successes,
            "failures": self.failures,
            "insights": self.insights,
            "improvements": self.improvements,
            "overall_score": round(self.overall_score, 2),
        }


class ReflectionEngine:
    """反思引擎"""
    
    def reflect(self, execution_results: List[Dict[str, Any]], plan_id: str = "") -> ReflectionResult:
        """反思执行结果"""
        successes = []
        failures = []
        
        for result in execution_results:
            if result.get("success", False):
                successes.append(f"{result['action']} completed successfully")
            else:
                failures.append(f"{result['action']} failed: {result.get('error', 'Unknown')}")
        
        # 生成洞察
        insights = self._generate_insights(successes, failures)
        
        # 生成改进建议
        improvements = self._generate_improvements(failures)
        
        # 计算总体分数
        success_rate = len(successes) / max(len(successes) + len(failures), 1)
        overall_score = min(success_rate * 0.8 + len(insights) * 0.05, 1.0)
        
        return ReflectionResult(
            reflection_id=f"reflection_{plan_id}",
            plan_id=plan_id,
            successes=successes,
            failures=failures,
            insights=insights,
            improvements=improvements,
            overall_score=overall_score,
        )
    
    def _generate_insights(self, successes: List[str], failures: List[str]) -> List[str]:
        """生成洞察"""
        insights = []
        
        if len(successes) >= 5:
            insights.append("Daily workflow completed successfully")
        
        if any("discover_winners" in s for s in successes):
            insights.append("Winning patterns identified")
        
        if any("adjust_budget" in s for s in successes):
            insights.append("Budget optimization applied")
        
        if failures:
            insights.append(f"{len(failures)} step(s) failed - needs attention")
        
        return insights
    
    def _generate_improvements(self, failures: List[str]) -> List[str]:
        """生成改进建议"""
        improvements = []
        
        if any("read_data" in f for f in failures):
            improvements.append("Check data source connections")
        
        if any("attribution" in f for f in failures):
            improvements.append("Review attribution pipeline")
        
        if any("adjust_budget" in f for f in failures):
            improvements.append("Verify budget API credentials")
        
        if not failures:
            improvements.append("Continue current workflow")
        
        return improvements
    
    def reflect_demo(self) -> ReflectionResult:
        """演示反思"""
        execution_results = [
            {"step_id": "step_01", "action": "read_data", "success": True, "result": {"records": 10000}},
            {"step_id": "step_02", "action": "attribution", "success": True, "result": {"attributed": 50}},
            {"step_id": "step_03", "action": "discover_winners", "success": True, "result": {"winners": 5}},
            {"step_id": "step_04", "action": "match_audiences", "success": True, "result": {"matches": 8}},
            {"step_id": "step_05", "action": "generate_strategy", "success": True, "result": {"strategies": 3}},
            {"step_id": "step_06", "action": "adjust_budget", "success": True, "result": {"adjusted": 5}},
            {"step_id": "step_07", "action": "create_experiments", "success": True, "result": {"experiments": 2}},
            {"step_id": "step_08", "action": "generate_report", "success": True, "result": {"report": True}},
        ]
        
        return self.reflect(execution_results, "plan_0001")
