"""Test Planner — 自动实验计划生成"""
from typing import List, Dict
from pathlib import Path
import json

from ..models import CreativePrediction


class TestPlanner:
    """为 TOP Creatives 生成买量测试计划"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code

    def plan(self, predictions: List[CreativePrediction],
             budget_per_day: float = 100.0,
             test_duration_days: int = 3) -> Dict:
        """生成测试计划"""

        # 只取推荐 TEST 的
        test_ready = [p for p in predictions if p.recommendation in ["TEST", "TEST_LOW_BUDGET"]]
        top10 = test_ready[:10]

        # 分组策略：高分组 vs 低分组（基于实际分数分布）
        high_budget = [p for p in top10 if p.overall_score >= 40][:5]
        low_budget = [p for p in top10 if 30 <= p.overall_score < 40][:5]

        plan = {
            "game": self.game_code,
            "total_creatives": len(top10),
            "test_duration_days": test_duration_days,
            "total_budget": budget_per_day * test_duration_days,
            "campaigns": [],
        }

        if high_budget:
            plan["campaigns"].append({
                "name": "Campaign_A_High_Potential",
                "budget_per_day": budget_per_day * 0.6,
                "creatives": [p.creative_id for p in high_budget],
                "expected_roas_range": f"{min(p.expected_roas for p in high_budget):.2f} - {max(p.expected_roas for p in high_budget):.2f}",
                "strategy": "优先放量",
            })

        if low_budget:
            plan["campaigns"].append({
                "name": "Campaign_B_Explore",
                "budget_per_day": budget_per_day * 0.4,
                "creatives": [p.creative_id for p in low_budget],
                "expected_roas_range": f"{min(p.expected_roas for p in low_budget):.2f} - {max(p.expected_roas for p in low_budget):.2f}",
                "strategy": "小预算探索",
            })

        # 每日监控指标
        plan["daily_metrics"] = [
            "spend", "impressions", "clicks", "ctr",
            "installs", "cvr", "purchase", "revenue", "roas"
        ]

        plan["stop_rules"] = {
            "roas_below_0.5_for_2_days": "暂停",
            "ctr_below_0.01_for_1_day": "暂停",
            "roas_above_2.0": "立即加预算 50%",
        }

        return plan
