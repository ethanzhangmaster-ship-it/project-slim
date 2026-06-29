from __future__ import annotations

from pathlib import Path

from market_ops.models import AnalysisSection, DailySyncReport, WeeklyReport


def _md_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_section(section: AnalysisSection) -> str:
    lines = [f"## {section.title}", ""]
    lines.append("### 结论")
    lines.extend(f"- {item}" for item in section.conclusions)
    lines.append("")
    lines.append("### 重点")
    lines.extend(f"- {item}" for item in section.highlights)
    lines.append("")
    lines.append("### 建议")
    lines.extend(f"- {item}" for item in section.recommendations)
    lines.append("")
    return "\n".join(lines)


def render_markdown_report(report: WeeklyReport) -> str:
    lines = [
        f"# {report.meeting_name}",
        "",
        f"- 报告日期：{report.report_date.isoformat()}",
        f"- 草拟任务数：{len(report.draft_actions)}",
        "",
        "## 会议规则",
        "",
        "- 会议只做决策，不重复念数据。",
        "- 每条确认通过的决策都必须落到可追踪的任务和指标上。",
        "",
        _render_section(report.growth_analysis),
        _render_section(report.creative_analysis),
        _render_section(report.revenue_analysis),
        "## 结构化决策",
        "",
        "| 类型 | 对象 | 负责人 | KPI | 预计影响 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report.decisions:
        lines.append(
            f"| {_md_cell(item.recommendation_type)} | {_md_cell(item.target)} | {_md_cell(item.owner)} | {_md_cell(item.kpi_target)} | {_md_cell(item.estimated_impact)} |"
        )
    lines.extend(
        [
            "",
            "## 草拟 Action List",
            "",
            "| Task ID | 类型 | 标题 | 负责人 | 状态 | 验收指标 | 截止时间 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in report.draft_actions:
        lines.append(
            f"| {_md_cell(item.task_id)} | {_md_cell(item.action_type)} | {_md_cell(item.title)} | {_md_cell(item.owner)} | "
            f"{_md_cell(item.status)} | {_md_cell(item.acceptance_metric)} | {_md_cell(item.due_date.isoformat())} |"
        )
    lines.extend(["", "## 备注", ""])
    for item in report.draft_actions:
        lines.append(f"- {item.task_id}: {item.description}")
    lines.append("")
    return "\n".join(lines)


def save_markdown_report(report: WeeklyReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"weekly_report_{report.report_date.strftime('%Y%m%d')}.md"
    path.write_text(render_markdown_report(report), encoding="utf-8")
    return path


def render_daily_sync_report(report: DailySyncReport) -> str:
    lines = [
        "# Daily Task Sync",
        "",
        f"- As Of Date: {report.as_of_date.isoformat()}",
        f"- Total Tasks: {report.total_tasks}",
        f"- Updated Tasks: {len(report.updated_tasks)}",
        f"- Overdue Tasks: {len(report.overdue_tasks)}",
        "",
        "## Status Updates",
        "",
    ]
    if report.updated_tasks:
        lines.append("| Task ID | Previous Status | New Status | Latest Note |")
        lines.append("| --- | --- | --- | --- |")
        for item in report.updated_tasks:
            lines.append(
                f"| {_md_cell(item.task_id)} | {_md_cell(item.previous_status)} | {_md_cell(item.new_status)} | {_md_cell(item.latest_note)} |"
            )
    else:
        lines.append("- No task status changes.")

    lines.extend(["", "## Overdue Tasks", ""])
    if report.overdue_tasks:
        lines.append("| Task ID | Title | Owner | Due Date | Current Status |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in report.overdue_tasks:
            lines.append(
                f"| {_md_cell(item.task_id)} | {_md_cell(item.title)} | {_md_cell(item.owner)} | {_md_cell(item.due_date.isoformat())} | {_md_cell(item.status)} |"
            )
    else:
        lines.append("- No overdue tasks.")
    lines.append("")
    return "\n".join(lines)


def save_daily_sync_report(report: DailySyncReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"daily_sync_{report.as_of_date.strftime('%Y%m%d')}.md"
    path.write_text(render_daily_sync_report(report), encoding="utf-8")
    return path
