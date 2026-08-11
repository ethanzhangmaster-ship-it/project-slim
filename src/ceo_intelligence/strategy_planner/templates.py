"""E17.4 — 确定性策略模板库（无 LLM，可审计）。

每个策略类型对应一组有序 StrategyTask，含 owner / action / dependency / expected_output / deadline。
依赖用前置 task 的 order（字符串）表达，供 StrategyGraph 拓扑排序。

触发键 = OpportunityType.value（creative_refresh / ua_scale / aso_optimization / monetization ...）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import StrategyTask


@dataclass
class _Step:
    order: int
    owner: str
    action: str
    deps: List[str]
    output: str
    deadline: str


def _s(order: int, owner: str, action: str, deps: List[str], output: str, deadline: str) -> _Step:
    return _Step(order, owner, action, list(deps), output, deadline)


@dataclass
class StrategyTemplate:
    strategy_type: str
    objective: str
    steps: List[_Step]
    success_metrics: Dict[str, str]
    rollback_plan: str
    estimated_duration_days: int
    confidence: float


_TEMPLATES: Dict[str, StrategyTemplate] = {
    "creative_refresh": StrategyTemplate(
        "creative_refresh", "Recover creative fatigue",
        [
            _s(1, "Creative Analyst", "Analyze winning creative DNA", [], "Winner DNA report", "1"),
            _s(2, "Creative Agent", "Generate 30 new creatives", ["1"], "30 candidate creatives", "3"),
            _s(3, "Creative Agent", "CLIP screen top variants", ["2"], "Top 10 shortlist", "5"),
            _s(4, "UA Agent", "Run Meta experiment", ["3"], "Live UA experiment", "7"),
            _s(5, "Analytics", "Evaluate ROAS", ["4"], "ROAS delta report", "14"),
        ],
        {"ctr": "+15%", "roas": "+10%"}, "Stop losing variants", 14, 0.85,
    ),
    "ua_scale": StrategyTemplate(
        "ua_scale", "Scale profitable UA",
        [
            _s(1, "Finance Agent", "Check budget headroom", [], "Budget report", "1"),
            _s(2, "UA Agent", "Increase budget 20%", ["1"], "New daily cap", "2"),
            _s(3, "UA Agent", "Monitor CPI", ["2"], "CPI trend", "5"),
            _s(4, "Analytics", "Monitor ROAS", ["2"], "ROAS trend", "7"),
            _s(5, "UA Agent", "Scale or stop", ["3", "4"], "Scale decision", "10"),
        ],
        {"roas": "+5%", "cpi": "-5%"}, "Revert to previous budget", 10, 0.80,
    ),
    "ua_stop_loss": StrategyTemplate(
        "ua_stop_loss", "Stop UA loss",
        [
            _s(1, "UA Agent", "Pause losing campaigns", [], "Paused campaigns", "1"),
            _s(2, "UA Agent", "Reallocate budget to winners", ["1"], "Reallocated budget", "2"),
            _s(3, "Analytics", "Monitor ROAS", ["2"], "ROAS delta", "5"),
        ],
        {"roas": "+15%", "spend": "-20%"}, "Restore original allocation", 5, 0.85,
    ),
    "aso_optimization": StrategyTemplate(
        "aso_optimization", "Improve store conversion",
        [
            _s(1, "ASO Agent", "Keyword analysis", [], "Target keyword set", "1"),
            _s(2, "Store Ops", "Build new listing", ["1"], "New store listing", "3"),
            _s(3, "Store Ops", "Run A/B experiment", ["2"], "Live A/B test", "5"),
            _s(4, "Analytics", "Validate CVR", ["3"], "CVR delta report", "10"),
        ],
        {"cvr": "+10%", "impressions": "+15%"}, "Revert to previous listing", 10, 0.82,
    ),
    "monetization": StrategyTemplate(
        "monetization", "Increase monetization efficiency",
        [
            _s(1, "Economy Agent", "Analyze revenue structure", [], "Revenue breakdown", "1"),
            _s(2, "Economy Agent", "Design pack/price adjustment", ["1"], "New pricing plan", "3"),
            _s(3, "Product", "A/B test pricing", ["2"], "Live A/B test", "7"),
            _s(4, "Analytics", "Observe payer change", ["3"], "Payer delta report", "14"),
        ],
        {"arpu": "+8%", "payer_rate": "+5%"}, "Revert pricing to baseline", 14, 0.70,
    ),
    "revenue_recovery": StrategyTemplate(
        "revenue_recovery", "Recover declining revenue",
        [
            _s(1, "Analytics", "Diagnose revenue drop", [], "Root cause report", "1"),
            _s(2, "Product", "Fix top revenue leak", ["1"], "Shipped fix", "3"),
            _s(3, "Analytics", "Monitor revenue trend", ["2"], "Revenue trend", "7"),
            _s(4, "Analytics", "Validate recovery", ["3"], "Recovery report", "14"),
        ],
        {"revenue": "+12%", "dau": "+5%"}, "Roll back the fix", 14, 0.75,
    ),
    "retention": StrategyTemplate(
        "retention", "Improve retention",
        [
            _s(1, "Analytics", "Analyze churn cohorts", [], "Cohort report", "1"),
            _s(2, "Product", "Design retention hook", ["1"], "New feature spec", "5"),
            _s(3, "Product", "Roll out feature", ["2"], "Live feature", "8"),
            _s(4, "Analytics", "Measure retention", ["3"], "Retention delta", "14"),
        ],
        {"d1_retention": "+5%", "d7_retention": "+3%"}, "Roll back feature", 14, 0.78,
    ),
    "release_health": StrategyTemplate(
        "release_health", "Restore release health",
        [
            _s(1, "Release Agent", "Triage health issues", [], "Issue list", "1"),
            _s(2, "Engineering", "Fix crashes/ANRs", ["1"], "Hotfix build", "3"),
            _s(3, "QA", "Verify stability", ["2"], "Stability report", "5"),
        ],
        {"crash_rate": "-50%", "rating": "+0.2"}, "Roll back release", 5, 0.85,
    ),
}


def get_template(strategy_type: str):
    """按策略类型取模板；未知类型返回 None（质量门禁会拒绝）。"""
    return _TEMPLATES.get(strategy_type)


def build_tasks(template) -> List[StrategyTask]:
    return [
        StrategyTask(
            order=st.order,
            owner=st.owner,
            action=st.action,
            dependency=list(st.deps),
            expected_output=st.output,
            deadline=st.deadline,
        )
        for st in template.steps
    ]
