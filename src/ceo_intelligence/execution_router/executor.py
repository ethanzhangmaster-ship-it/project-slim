"""E17.6 — ActionCompiler：把 E17.4 StrategyTask 编译为 ExecutionAction。

确定性三级映射（无 LLM，可审计）：
1. 精确表：模板 action 文本（归一化小写）→ (domain, action_type, risk)
   带参数的文本（"Generate 30 new creatives" / "Increase budget 20%"）用正则抽参。
2. 人类任务：owner ∈ {Product, Engineering, QA} 的步骤机器不可执行，
   编译为 ANALYTICS:track_human_task（SAFE，登记 + 追踪，由人落地）。
3. 关键词兜底：monitor/evaluate/validate/observe/measure/diagnose/analyze 开头
   → ANALYTICS 只读登记；其余 → ANALYTICS:track_task。

风险标定（供 Permission Gate 升级判断）：
  只读 0.05 ｜ 生成类 0.1 ｜ 动钱/改店写操作 0.4–0.5 ｜ halt 止血 0.2
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.ceo_intelligence.strategy_planner.models import GrowthStrategyPlan, StrategyTask

from .models import ExecutionAction, ExecutionDomain

_UA = ExecutionDomain.UA.value
_ASO = ExecutionDomain.ASO.value
_CRE = ExecutionDomain.CREATIVE.value
_ECO = ExecutionDomain.ECONOMY.value
_REL = ExecutionDomain.RELEASE.value
_ANA = ExecutionDomain.ANALYTICS.value

# 归一化 action 文本 -> (domain, action_type, risk_level)
_EXACT: Dict[str, Tuple[str, str, float]] = {
    # creative_refresh
    "analyze winning creative dna": (_CRE, "analyze_dna", 0.05),
    "clip screen top variants": (_CRE, "clip_screen", 0.1),
    "run meta experiment": (_UA, "run_experiment", 0.4),
    "evaluate roas": (_ANA, "evaluate_roas", 0.05),
    # ua_scale
    "check budget headroom": (_UA, "check_budget", 0.05),
    "monitor cpi": (_ANA, "monitor_cpi", 0.05),
    "monitor roas": (_ANA, "monitor_roas", 0.05),
    "scale or stop": (_ANA, "scale_or_stop_review", 0.05),
    # ua_stop_loss
    "pause losing campaigns": (_UA, "pause_campaigns", 0.4),
    "reallocate budget to winners": (_UA, "reallocate_budget", 0.4),
    # aso_optimization
    "keyword analysis": (_ASO, "keyword_analysis", 0.05),
    "build new listing": (_ASO, "update_listing", 0.4),
    "run a/b experiment": (_ASO, "run_ab_experiment", 0.4),
    "validate cvr": (_ANA, "validate_cvr", 0.05),
    # monetization
    "analyze revenue structure": (_ECO, "analyze_revenue", 0.05),
    "design pack/price adjustment": (_ECO, "design_pricing", 0.1),
    "a/b test pricing": (_ECO, "ab_test_pricing", 0.5),
    "observe payer change": (_ANA, "observe_payer_change", 0.05),
    # revenue_recovery / retention（Analytics 步骤）
    "diagnose revenue drop": (_ANA, "diagnose_revenue_drop", 0.05),
    "monitor revenue trend": (_ANA, "monitor_revenue", 0.05),
    "validate recovery": (_ANA, "validate_recovery", 0.05),
    "analyze churn cohorts": (_ANA, "analyze_churn", 0.05),
    "measure retention": (_ANA, "measure_retention", 0.05),
    # release_health
    "triage health issues": (_REL, "triage_health", 0.05),
    "halt release": (_REL, "halt_release", 0.2),
    "halt rollout": (_REL, "halt_release", 0.2),
    "advance rollout": (_REL, "advance_rollout", 0.4),
}

# owner 为纯人类角色的任务：机器只登记追踪
_HUMAN_OWNERS = {"product", "engineering", "qa"}

# 关键词兜底（只读分析域）
_READONLY_PREFIX = re.compile(
    r"^(monitor|evaluate|validate|observe|measure|diagnose|analyze)\b", re.IGNORECASE
)

_GEN_CREATIVES = re.compile(r"^generate\s+(\d+)\s+new\s+creatives$", re.IGNORECASE)
_INC_BUDGET = re.compile(r"^increase\s+budget\s+(\d+)\s*%$", re.IGNORECASE)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48]


class ActionCompiler:
    """StrategyTask → ExecutionAction（确定性编译器）。"""

    def compile_task(
        self, plan: GrowthStrategyPlan, task: StrategyTask
    ) -> ExecutionAction:
        text = " ".join(task.action.split())
        norm = text.lower()
        payload: Dict[str, Any] = {}

        mapped: Optional[Tuple[str, str, float]] = None

        m = _GEN_CREATIVES.match(norm)
        if m:
            mapped = (_CRE, "generate_creatives", 0.1)
            payload["count"] = int(m.group(1))
        if mapped is None:
            m = _INC_BUDGET.match(norm)
            if m:
                mapped = (_UA, "increase_budget", 0.5)
                payload["percent"] = int(m.group(1))
        if mapped is None:
            mapped = _EXACT.get(norm)
        if mapped is None and task.owner.strip().lower() in _HUMAN_OWNERS:
            mapped = (_ANA, "track_human_task", 0.05)
            payload["task"] = text
            payload["owner"] = task.owner
        if mapped is None:
            if _READONLY_PREFIX.match(norm):
                mapped = (_ANA, _slug(text), 0.05)
            else:
                mapped = (_ANA, "track_task", 0.05)
                payload["task"] = text

        domain, action_type, risk = mapped
        # plan 级审批要求只传导给会"动手"的域；只读分析域不受影响
        approval = bool(plan.needs_approval) and domain != _ANA
        return ExecutionAction(
            action_id="",
            game_id=plan.game_id,
            domain=domain,
            action_type=action_type,
            payload=payload,
            risk_level=risk,
            approval_required=approval,
            decision_id=plan.decision_id,
            plan_strategy_type=plan.strategy_type,
            source_task_order=task.order,
            dependency=list(task.dependency),
        )

    def compile_plan(self, plan: GrowthStrategyPlan) -> List[ExecutionAction]:
        return [
            self.compile_task(plan, t)
            for t in sorted(plan.tasks, key=lambda x: x.order)
        ]


__all__ = ["ActionCompiler"]
