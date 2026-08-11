"""P3.2 — Sections（各 section 数据装配，纯 READ，不重算）。

输入都是「已完成分析」的产物：CompanySnapshot / DailyRunResult /
ExecutionDailyReport / AuditReport / RecoveryResult / patterns。
本模块只做聚合与字段搬运，不调用任何决策/执行/Provider。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.ceo_intelligence.daily_operator.models import STATUS_LABEL

from .models import (
    ExecutionSummary,
    HealthSummary,
    OpportunityItem,
    RiskItem,
)


def build_health_summary(
    company: Optional[Any],
    daily: Any,
    record: Optional[Any] = None,
) -> HealthSummary:
    status = "healthy"
    if daily is not None:
        cs = getattr(daily, "company_status", None)
        status = cs.value if hasattr(cs, "value") else str(cs or "healthy")
    label = STATUS_LABEL.get(status, f"未知({status})")

    game_count = total_revenue = total_dau = total_spend = 0
    avg_conf = 0.0
    at_risk: List[str] = []
    if company is not None:
        game_count = int(getattr(company, "game_count", 0) or 0)
        total_revenue = float(getattr(company, "total_revenue", 0.0) or 0.0)
        total_dau = int(getattr(company, "total_dau", 0) or 0)
        total_spend = float(getattr(company, "total_spend", 0.0) or 0.0)
        avg_conf = float(getattr(company, "avg_confidence", 0.0) or 0.0)
        at_risk = list(getattr(company, "at_risk", []) or [])

    auto = approval = blocked = observed = 0
    if record is not None:
        auto = int(getattr(record, "executed", 0) or 0)
        approval = int(getattr(record, "approved", 0) or 0)
        blocked = int(getattr(record, "blocked", 0) or 0)
        observed = int(getattr(record, "observed", 0) or 0)

    return HealthSummary(
        company_status=status,
        status_label=label,
        game_count=game_count,
        total_revenue=total_revenue,
        total_dau=total_dau,
        total_spend=total_spend,
        avg_confidence=avg_conf,
        at_risk=at_risk,
        auto_count=auto,
        approval_count=approval,
        blocked_count=blocked,
        observed_count=observed,
    )


def build_opportunities(priorities: List[Any]) -> List[OpportunityItem]:
    out: List[OpportunityItem] = []
    for p in priorities or []:
        gate = getattr(p, "gate", "") or ""
        gate = gate.upper() if gate else "—"
        out.append(
            OpportunityItem(
                rank=int(getattr(p, "rank", 0) or 0),
                game_id=str(getattr(p, "game_id", "")),
                action=str(getattr(p, "action", "")),
                opportunity_type=str(getattr(p, "opportunity_type", "")),
                priority_score=float(getattr(p, "priority_score_value", 0.0) or 0.0),
                expected_value=float(getattr(p, "impact", 0.0) or 0.0),
                confidence=float(getattr(p, "confidence", 0.0) or 0.0),
                urgency=float(getattr(p, "urgency", 0.0) or 0.0),
                sim_gate=gate,
            )
        )
    return out


def build_risks(
    company: Optional[Any],
    daily: Optional[Any],
    exec_report: Optional[Any],
    recoveries: Optional[List[Any]] = None,
) -> List[RiskItem]:
    risks: List[RiskItem] = []

    # 1) 执行告警（P2.5）
    if exec_report is not None:
        for w in getattr(exec_report, "warnings", []) or []:
            risks.append(RiskItem(level="warn", title="执行告警", detail=str(w)))
        health = getattr(exec_report, "health_level", "") or ""
        if health and health not in ("green", "GREEN"):
            risks.append(RiskItem(
                level="warn", title="执行健康等级",
                detail=f"执行链路健康等级：{health}",
            ))

    # 2) 风险游戏名单（P1.7 / E17.1）
    if company is not None:
        at_risk = list(getattr(company, "at_risk", []) or [])
        if at_risk:
            names = "、".join(at_risk[:10])
            more = f" 等 {len(at_risk)} 款" if len(at_risk) > 10 else ""
            risks.append(RiskItem(
                level="warn", title="风险游戏名单",
                detail=f"{names}{more}",
            ))

    # 3) 模拟闸门阻断（E17.8 → ActionKind.BLOCK）
    if daily is not None:
        from src.ceo_intelligence.daily_operator.models import ActionKind
        for a in getattr(daily, "actions", []) or []:
            if getattr(a, "kind", None) == ActionKind.BLOCK:
                risks.append(RiskItem(
                    level="warn", title="模拟闸门阻断",
                    detail=f"{a.game_id} — {a.action}：{a.detail or '未通过模拟闸门'}",
                ))

    # 4) 恢复升级事件（P2.6）
    for r in recoveries or []:
        st = str(getattr(r, "status", "") or "").lower()
        if "escalated" in st:
            risks.append(RiskItem(
                level="critical", title="恢复升级事件",
                detail=f"事件 {getattr(r, 'incident_id', '?')}：已升级人工处理",
            ))
        elif "recovered" in st:
            risks.append(RiskItem(
                level="info", title="自动恢复",
                detail=f"事件 {getattr(r, 'incident_id', '?')}：已自动恢复",
            ))

    if not risks:
        risks.append(RiskItem(
            level="info", title="无显著风险", detail="今日未发现需特别关注的风险项。"
        ))
    return risks


def build_learning(
    exec_report: Optional[Any],
    patterns: Optional[List[str]] = None,
) -> List[str]:
    out: List[str] = []
    if exec_report is not None:
        out.extend(list(getattr(exec_report, "learnings", []) or []))
    if patterns:
        out.extend(list(patterns))
    if not out:
        out.append("（今日无新学习点，经验回流待真实执行累积）")
    return out


def build_execution_summary(
    exec_report: Optional[Any],
    recoveries: Optional[List[Any]] = None,
    real_api_called: bool = False,
) -> ExecutionSummary:
    total = success = failed = rollback = blocked = 0
    health = ""
    warnings: List[str] = []
    if exec_report is not None:
        total = int(getattr(exec_report, "total_executions", 0) or 0)
        success = int(getattr(exec_report, "success", 0) or 0)
        failed = int(getattr(exec_report, "failed", 0) or 0)
        rollback = int(getattr(exec_report, "rollback", 0) or 0)
        blocked = int(getattr(exec_report, "blocked", 0) or 0)
        health = str(getattr(exec_report, "health_level", "") or "")
        warnings = list(getattr(exec_report, "warnings", []) or [])

    recovered = escalated = 0
    for r in recoveries or []:
        st = str(getattr(r, "status", "") or "").lower()
        if "recovered" in st:
            recovered += 1
        elif "escalated" in st:
            escalated += 1

    return ExecutionSummary(
        total_executions=total,
        success=success,
        failed=failed,
        rollback=rollback,
        blocked=blocked,
        health_level=health,
        warnings=warnings,
        recovered=recovered,
        escalated=escalated,
        real_api_called=bool(real_api_called),
    )


def build_portfolio_recommendation_section(result: Any) -> Dict[str, Any]:
    """把 P3.4.5 ``PortfolioOptimizationResult`` 收敛成 CEO 报告的

    ``Portfolio Recommendation`` 段（只读、纯搬运，不重算/不决策/不调 Provider）。

    参数
    ----
    result: ``PortfolioOptimizationResult``（来自 ``src.operator.portfolio``）。

    返回
    ----
    纯 dict section：``{title, status, summary, recommendation, guard_verdict,
    confidence, items, real_api_called}``，可直接并入 CEO 报告正文。

    纪律：本函数不触碰执行链、不创建 ``ExecutionContract``、不修改入参。
    """
    # 延迟导入避免 import-time 耦合（report 包下游、portfolio 包上游）。
    from src.operator.portfolio.optimizer import PortfolioOptimizationResult

    if not isinstance(result, PortfolioOptimizationResult):
        raise TypeError(
            "build_portfolio_recommendation_section expects a "
            "PortfolioOptimizationResult, got "
            f"{type(result).__name__}"
        )
    return result.to_report_section()


def build_memory_reasoning_section(bundle: Any) -> Dict[str, Any]:
    """把 P3.6.1 ``KnowledgeBundle``（dict 或对象）收敛成 CEO 报告的

    ``Memory Reasoning`` 段（只读、纯搬运，不重算/不决策）。

    返回
    ----
    纯 dict section：``{title, similar_games, historical_success_rate,
    latest_validation, conflicts, confidence, memories_count, explanation,
    real_api_called}``，可直接并入 CEO 报告正文。

    纪律：本函数不触碰执行链、不创建任何写操作。
    """
    d = bundle.to_dict() if hasattr(bundle, "to_dict") else dict(bundle or {})
    memories = d.get("memories") or []
    sims = [m.get("key", "") for m in memories if m.get("memory_type") == "similar_game"]
    validated = [m for m in memories if (m.get("quality") or 0.0) > 0]
    sr = (
        sum(float(m.get("success_rate", 0.0)) for m in validated) / len(validated)
        if validated else 0.0
    )
    ts = [str(m.get("validated_at", "")) for m in memories if m.get("validated_at")]
    return {
        "title": "Memory Reasoning（知识推理）",
        "similar_games": list(sims),
        "historical_success_rate": round(float(sr), 6),
        "latest_validation": max(ts) if ts else "",
        "conflicts": list(d.get("conflicts") or []),
        "confidence": round(float(d.get("confidence", 0.0)), 6),
        "memories_count": len(memories),
        "explanation": str(d.get("explanation", "")),
        "real_api_called": bool(d.get("real_api_called", False)),
    }


def build_strategic_memory_section(bundle: Any) -> Dict[str, Any]:
    """把 P3.6.2 ``KnowledgeBundle.strategic_insights`` 收敛成 CEO 报告的

    ``Strategic Memory`` 段（只读、纯搬运，不重算/不决策）。

    返回
    ----
    纯 dict section：``{title, insights, real_api_called}``，insights 为
    ``[{category, statement, success_rate, confidence, evidence_count,
    counter_examples, supporting_memories}]``。
    """
    d = bundle.to_dict() if hasattr(bundle, "to_dict") else dict(bundle or {})
    insights = d.get("strategic_insights") or []
    return {
        "title": "Strategic Memory（长期战略规律）",
        "insights": [
            {
                "category": str(i.get("category", "")),
                "statement": str(i.get("statement", "")),
                "success_rate": round(float(i.get("success_rate", 0.0)), 6),
                "confidence": round(float(i.get("confidence", 0.0)), 6),
                "evidence_count": int(i.get("evidence_count", 0)),
                "counter_examples": list(i.get("counter_examples", [])),
                "supporting_memories": list(i.get("supporting_memories", [])),
            }
            for i in insights
        ],
        "real_api_called": bool(d.get("real_api_called", False)),
    }


def build_reflection_section(reflection: Any) -> Dict[str, Any]:
    """把 P3.6.3 ``CEOReflection``（dict 或对象）收敛成 CEO 报告的

    ``Memory Reflection`` 段（只读、纯搬运，不重算/不决策）。

    返回
    ----
    纯 dict section：``{title, period, wins, mistakes, unresolved_count,
    changed_beliefs, new_rules, evidence_count, generated_at,
    real_api_called}``，可直接并入 CEO 报告正文。

    纪律：本函数不触碰执行链、不创建任何写操作。
    """
    d = reflection.to_dict() if hasattr(reflection, "to_dict") else dict(reflection or {})
    return {
        "title": "Memory Reflection（昨日复盘）",
        "period": str(d.get("period", "")),
        "wins": list(d.get("wins") or []),
        "mistakes": list(d.get("mistakes") or []),
        "unresolved_count": int(d.get("unresolved_count", 0)),
        "changed_beliefs": list(d.get("changed_beliefs") or []),
        "new_rules": list(d.get("new_rules") or []),
        "evidence_count": int(d.get("evidence_count", 0)),
        "generated_at": str(d.get("generated_at", "")),
        "real_api_called": bool(d.get("real_api_called", False)),
    }


def build_governance_section(governance: Any) -> Dict[str, Any]:
    """Pure transport from governance records to the CEO report section."""
    data = governance.to_dict() if hasattr(governance, "to_dict") else dict(governance or {})
    records = list(data.get("records") or [])
    actions = [str(item.get("action", "")) for item in records]
    reviews = [item for item in records if item.get("requires_ceo_review")]
    return {
        "title": "Memory Governance（记忆治理）",
        "records": records,
        "duplicate_merges": actions.count("merge_duplicates"),
        "obsolete_marked": actions.count("mark_obsolete"),
        "conflicts_resolved": actions.count("resolve_conflict"),
        "requires_ceo_review": len(reviews),
        "archived": actions.count("mark_archived"),
        "health": dict(data.get("health") or {}),
        "real_api_called": bool(data.get("real_api_called", False)),
    }


__all__ = [
    "build_health_summary",
    "build_opportunities",
    "build_risks",
    "build_learning",
    "build_execution_summary",
    "build_portfolio_recommendation_section",
    "build_memory_reasoning_section",
    "build_strategic_memory_section",
    "build_reflection_section",
    "build_governance_section",
]
