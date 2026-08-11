"""P3.2 — CEO Report Builder（聚合编排，唯一新增 Stage 的入口）。

把既有链路的「最终产物」聚合成一张 CEODailyReport，并负责落盘三文件。
不做任何重算 / 决策 / 执行。

落盘：
  <out_dir>/<date>/daily_report.md    运营决策单
  <out_dir>/<date>/daily_report.json  CEODailyReport.to_dict()
  <out_dir>/<date>/actions.json       [CEOAction.to_dict()]
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .action_formatter import ActionFormatter
from .models import CEODailyReport
from .sections import (
    build_execution_summary,
    build_governance_section,
    build_health_summary,
    build_learning,
    build_memory_reasoning_section,
    build_opportunities,
    build_portfolio_recommendation_section,
    build_reflection_section,
    build_risks,
    build_strategic_memory_section,
)


def _index_decisions(daily: Any) -> Dict[str, Any]:
    dec_report = getattr(daily, "dec_report", None)
    if dec_report is None:
        return {}
    return {d.audit_id: d for d in getattr(dec_report, "decisions", [])}


def _index_sims(daily: Any) -> Dict[str, Any]:
    sim_report = getattr(daily, "sim_report", None)
    if sim_report is None:
        return {}
    return {
        s.decision_audit_id: s
        for s in getattr(sim_report, "simulations", [])
        if getattr(s, "decision_audit_id", "")
    }


def _index_priorities(daily: Any) -> Dict[str, Any]:
    return {p.game_id: p for p in getattr(daily, "priorities", [])}


class CEOReportBuilder:
    """聚合既有产物 -> CEODailyReport。"""

    def build(
        self,
        daily: Any,
        company: Optional[Any] = None,
        exec_report: Optional[Any] = None,
        audit_report: Optional[Any] = None,
        recoveries: Optional[List[Any]] = None,
        patterns: Optional[List[str]] = None,
        portfolio_recommendation: Optional[Any] = None,
        memory_reasoning: Optional[Any] = None,
        strategic_memory: Optional[Any] = None,
        reflection: Optional[Any] = None,
        governance: Optional[Any] = None,
    ) -> CEODailyReport:
        date = getattr(daily, "date", "")
        record = getattr(daily, "record", None)
        real_api = bool(
            (getattr(daily, "summary", {}) or {}).get("real_api_called", False)
        )

        health = build_health_summary(company, daily, record=record)
        opportunities = build_opportunities(getattr(daily, "priorities", []) or [])
        actions = ActionFormatter(
            decisions_by_id=_index_decisions(daily),
            sims_by_id=_index_sims(daily),
            priorities_by_game=_index_priorities(daily),
        ).format(getattr(daily, "actions", []) or [])
        risks = build_risks(company, daily, exec_report, recoveries=recoveries)
        learning = build_learning(exec_report, patterns=patterns)
        exec_summary = build_execution_summary(
            exec_report, recoveries=recoveries, real_api_called=real_api
        )
        # P3.1 — 跨游戏资源建议（来自 P3.4.5 PortfolioOptimizationResult，只读搬运）
        portfolio_section = (
            build_portfolio_recommendation_section(portfolio_recommendation)
            if portfolio_recommendation is not None else None
        )
        # P3.6.1 — 知识推理段（来自 MemoryController KnowledgeBundle，只读搬运）
        memory_section = (
            build_memory_reasoning_section(memory_reasoning)
            if memory_reasoning is not None else None
        )
        # P3.6.2 — 战略规律段（来自 Strategic Memory 检索，只读搬运）
        strategic_section = (
            build_strategic_memory_section(strategic_memory)
            if strategic_memory is not None else None
        )
        # P3.6.3 — 认知复盘段（来自 CEOReflection，只读搬运）
        reflection_section = (
            build_reflection_section(reflection)
            if reflection is not None else None
        )
        governance_section = (
            build_governance_section(governance)
            if governance is not None else None
        )

        return CEODailyReport(
            report_id=f"ceo-{date}",
            date=date,
            health_summary=health,
            opportunities=opportunities,
            actions=actions,
            risks=risks,
            learning_summary=learning,
            execution_summary=exec_summary,
            portfolio_recommendation=portfolio_section,
            memory_reasoning=memory_section,
            strategic_memory=strategic_section,
            reflection=reflection_section,
            governance=governance_section,
            real_api_called=real_api,
        )


def build_ceo_report(
    daily: Any,
    company: Optional[Any] = None,
    exec_report: Optional[Any] = None,
    audit_report: Optional[Any] = None,
    recoveries: Optional[List[Any]] = None,
    patterns: Optional[List[str]] = None,
    portfolio_recommendation: Optional[Any] = None,
    memory_reasoning: Optional[Any] = None,
    strategic_memory: Optional[Any] = None,
    reflection: Optional[Any] = None,
    governance: Optional[Any] = None,
) -> CEODailyReport:
    """模块级便捷入口。"""
    return CEOReportBuilder().build(
        daily,
        company=company,
        exec_report=exec_report,
        audit_report=audit_report,
        recoveries=recoveries,
        patterns=patterns,
        portfolio_recommendation=portfolio_recommendation,
        memory_reasoning=memory_reasoning,
        strategic_memory=strategic_memory,
        reflection=reflection,
        governance=governance,
    )


def write_outputs(
    date: str, out_dir: str, report: CEODailyReport
) -> Dict[str, str]:
    """落盘三文件，返回路径 dict。"""
    d = Path(out_dir) / date
    d.mkdir(parents=True, exist_ok=True)

    md_path = d / "daily_report.md"
    json_path = d / "daily_report.json"
    actions_path = d / "actions.json"

    from .renderer import render_markdown

    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(_dump_json(report.to_dict()), encoding="utf-8")
    actions_path.write_text(
        _dump_json([a.to_dict() for a in report.actions]), encoding="utf-8"
    )
    return {
        "report_path": str(md_path),
        "ceo_report_json": str(json_path),
        "actions_path": str(actions_path),
    }


def _dump_json(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)


__all__ = ["CEOReportBuilder", "build_ceo_report", "write_outputs"]
