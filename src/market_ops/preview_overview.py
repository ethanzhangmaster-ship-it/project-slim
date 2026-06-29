from __future__ import annotations

from datetime import date
from pathlib import Path


def _existing(path: Path | None) -> Path | None:
    return path if path is not None and path.exists() else None


def _extract_market_summary_lines(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    markers = [
        ("**市场负责人摘要**", ["---", "**1. 公司总体数据情况**", "## 1. 公司总体数据情况"]),
        ("## 市场负责人摘要", ["## 1. 公司总体数据情况", "**1. 公司总体数据情况**"]),
    ]
    for start_marker, end_candidates in markers:
        start = text.find(start_marker)
        if start < 0:
            continue
        end_positions = [
            text.find(marker, start + len(start_marker))
            for marker in end_candidates
            if text.find(marker, start + len(start_marker)) >= 0
        ]
        end = min(end_positions) if end_positions else len(text)
        block = text[start:end]
        return [line.strip() for line in block.splitlines() if line.strip().startswith("- ")]
    return []


def write_preview_overview(
    report_date: date,
    output_path: Path,
    *,
    summary_markdown: Path,
    summary_json: Path,
    index_markdown: Path,
    boss_markdown: Path,
    market_markdown: Path,
    market_detail_markdown: Path,
    recovery_markdown: Path,
    self_check_markdown: Path | None = None,
    report_audit_markdown: Path | None = None,
    pre_send_summary_markdown: Path | None = None,
    health_check_markdown: Path | None = None,
    creative_source_readiness_markdown: Path | None = None,
    data_quality_audit_markdown: Path | None = None,
    creative_attribution_audit_markdown: Path | None = None,
    google_creative_repair_audit_markdown: Path | None = None,
    google_revenue_attribution_audit_markdown: Path | None = None,
    send_payload_consistency_markdown: Path | None = None,
    tecdo_probe_markdown: Path | None = None,
    tecdo_account_reconciliation_markdown: Path | None = None,
    tecdo_sync_checklist_markdown: Path | None = None,
    closure_status_markdown: Path | None = None,
    project_detail_coverage_markdown: Path | None = None,
    p04_source_checklist_markdown: Path | None = None,
    detail_reply_checklist_markdown: Path | None = None,
    management_action_list_markdown: Path | None = None,
    growth_priorities_markdown: Path | None = None,
    creative_dna_markdown: Path | None = None,
    creative_clusters_markdown: Path | None = None,
    creative_fatigue_markdown: Path | None = None,
    dynamic_payback_markdown: Path | None = None,
    ai_media_buyer_plan_markdown: Path | None = None,
    action_refinement_notes: list[str] | None = None,
) -> None:
    self_check_markdown = _existing(self_check_markdown)
    report_audit_markdown = _existing(report_audit_markdown)
    pre_send_summary_markdown = _existing(pre_send_summary_markdown)
    health_check_markdown = _existing(health_check_markdown)
    creative_source_readiness_markdown = _existing(creative_source_readiness_markdown)
    data_quality_audit_markdown = _existing(data_quality_audit_markdown)
    creative_attribution_audit_markdown = _existing(creative_attribution_audit_markdown)
    google_creative_repair_audit_markdown = _existing(google_creative_repair_audit_markdown)
    google_revenue_attribution_audit_markdown = _existing(google_revenue_attribution_audit_markdown)
    send_payload_consistency_markdown = _existing(send_payload_consistency_markdown)
    tecdo_probe_markdown = _existing(tecdo_probe_markdown)
    tecdo_account_reconciliation_markdown = _existing(tecdo_account_reconciliation_markdown)
    tecdo_sync_checklist_markdown = _existing(tecdo_sync_checklist_markdown)
    closure_status_markdown = _existing(closure_status_markdown)
    project_detail_coverage_markdown = _existing(project_detail_coverage_markdown)
    p04_source_checklist_markdown = _existing(p04_source_checklist_markdown)
    detail_reply_checklist_markdown = _existing(detail_reply_checklist_markdown)
    management_action_list_markdown = _existing(management_action_list_markdown)
    growth_priorities_markdown = _existing(growth_priorities_markdown)
    creative_dna_markdown = _existing(creative_dna_markdown)
    creative_clusters_markdown = _existing(creative_clusters_markdown)
    creative_fatigue_markdown = _existing(creative_fatigue_markdown)
    dynamic_payback_markdown = _existing(dynamic_payback_markdown)
    ai_media_buyer_plan_markdown = _existing(ai_media_buyer_plan_markdown)
    market_summary_lines = _extract_market_summary_lines(market_markdown)

    def line_or_placeholder(index: int, label: str, path: Path | None) -> str:
        return f"{index}. {label}：{path}" if path is not None else f"{index}. {label}：生成后会补到这里"

    lines = [
        f"# 周报本地总览 | {report_date.isoformat()}",
        "",
        "## 建议阅读顺序",
        "",
        f"1. 先看预发送摘要：{summary_markdown}",
        line_or_placeholder(2, "再看发送前结论页", pre_send_summary_markdown),
        line_or_placeholder(3, "再看自检报告", self_check_markdown),
        line_or_placeholder(4, "再看审计报告", report_audit_markdown),
        line_or_placeholder(5, "再看周报健康检查", health_check_markdown),
    ]

    optional_sequence: list[tuple[str, Path | None]] = [
        ("如需确认素材 API 就绪度", creative_source_readiness_markdown),
        ("如需先确认数据质量和可决策性", data_quality_audit_markdown),
        ("如需确认 TecDo 账户权限", tecdo_probe_markdown),
        ("如需确认 TecDo 账户核对表", tecdo_account_reconciliation_markdown),
        ("如需确认 TecDo 同步清单", tecdo_sync_checklist_markdown),
        ("如需确认创意归因覆盖", creative_attribution_audit_markdown),
        ("如需确认 Google 素材修复清单", google_creative_repair_audit_markdown),
        ("如需确认 Google 收入归因异常", google_revenue_attribution_audit_markdown),
        ("如需确认预览卡片与发送载荷是否完全一致", send_payload_consistency_markdown),
        ("如需看当前还有哪些缺口待收口", closure_status_markdown),
        ("如需直接看管理动作台账", management_action_list_markdown),
        ("如需看项目级可信明细覆盖情况", project_detail_coverage_markdown),
        ("如需处理 P04 来源缺口", p04_source_checklist_markdown),
        ("如需处理详细版未锁群", detail_reply_checklist_markdown),
    ]
    optional_sequence.extend(
        [
            ("查看增长优先级与局部突破", growth_priorities_markdown),
            ("查看素材 DNA 识别", creative_dna_markdown),
            ("查看素材模式聚类", creative_clusters_markdown),
            ("查看素材疲劳检测", creative_fatigue_markdown),
            ("查看动态回本线", dynamic_payback_markdown),
            ("查看 AI Media Buyer 动作计划", ai_media_buyer_plan_markdown),
        ]
    )
    next_index = 6
    for label, path in optional_sequence:
        if path is not None:
            lines.append(f"{next_index}. {label}：{path}")
            next_index += 1

    lines.extend(
        [
            f"{next_index}. 最后看完整卡片索引：{index_markdown}",
            "",
            "## 预览文件",
            "",
            f"- 摘要卡 Markdown：{summary_markdown}",
            f"- 摘要卡 JSON：{summary_json}",
            f"- 老板版预览：{boss_markdown}",
            f"- 市场简版预览：{market_markdown}",
            f"- 市场详细版预览：{market_detail_markdown}",
            f"- 回收版预览：{recovery_markdown}",
            f"- 完整卡片索引：{index_markdown}",
            f"- 周报健康检查：{health_check_markdown}" if health_check_markdown is not None else "- 周报健康检查：未生成",
            f"- 素材 API 就绪度：{creative_source_readiness_markdown}" if creative_source_readiness_markdown is not None else "- 素材 API 就绪度：未生成",
            f"- 数据质量审计：{data_quality_audit_markdown}" if data_quality_audit_markdown is not None else "- 数据质量审计：未生成",
            f"- TecDo 账户探针：{tecdo_probe_markdown}" if tecdo_probe_markdown is not None else "- TecDo 账户探针：未生成",
            f"- TecDo 账户核对表：{tecdo_account_reconciliation_markdown}" if tecdo_account_reconciliation_markdown is not None else "- TecDo 账户核对表：未生成",
            f"- TecDo 同步清单：{tecdo_sync_checklist_markdown}" if tecdo_sync_checklist_markdown is not None else "- TecDo 同步清单：未生成",
            f"- 创意归因审计：{creative_attribution_audit_markdown}" if creative_attribution_audit_markdown is not None else "- 创意归因审计：未生成",
            f"- Google 素材修复清单：{google_creative_repair_audit_markdown}" if google_creative_repair_audit_markdown is not None else "- Google 素材修复清单：未生成",
            f"- Google 收入归因异常审计：{google_revenue_attribution_audit_markdown}" if google_revenue_attribution_audit_markdown is not None else "- Google 收入归因异常审计：未生成",
            f"- 发送载荷一致性审计：{send_payload_consistency_markdown}" if send_payload_consistency_markdown is not None else "- 发送载荷一致性审计：未生成",
            f"- 闭环状态台账：{closure_status_markdown}" if closure_status_markdown is not None else "- 闭环状态台账：未生成",
            f"- 管理动作台账：{management_action_list_markdown}" if management_action_list_markdown is not None else "- 管理动作台账：未生成",
            f"- 项目明细覆盖审计：{project_detail_coverage_markdown}" if project_detail_coverage_markdown is not None else "- 项目明细覆盖审计：未生成",
            f"- P04 来源核对清单：{p04_source_checklist_markdown}" if p04_source_checklist_markdown is not None else "- P04 来源核对清单：未生成",
            f"- 详细版回复核对清单：{detail_reply_checklist_markdown}" if detail_reply_checklist_markdown is not None else "- 详细版回复核对清单：未生成",
            "- 当前状态：TecDo 已作为当前代理素材主来源，Meta/Google 官方素材接口凭证属于增强项，不是当前周报主链路阻塞项。",
            "",
            "说明：这些文件只用于本地核对，不会直接触发飞书发送。",
        ]
    )
    lines.append(
        f"- 增长优先级与局部突破：{growth_priorities_markdown}"
        if growth_priorities_markdown is not None
        else "- 增长优先级与局部突破：未生成"
    )

    lines.extend(
        [
            f"- 素材 DNA 识别：{creative_dna_markdown}" if creative_dna_markdown is not None else "- 素材 DNA 识别：未生成",
            f"- 素材模式聚类：{creative_clusters_markdown}" if creative_clusters_markdown is not None else "- 素材模式聚类：未生成",
            f"- 素材疲劳检测：{creative_fatigue_markdown}" if creative_fatigue_markdown is not None else "- 素材疲劳检测：未生成",
            f"- 动态回本线：{dynamic_payback_markdown}" if dynamic_payback_markdown is not None else "- 动态回本线：未生成",
            f"- AI Media Buyer 动作计划：{ai_media_buyer_plan_markdown}" if ai_media_buyer_plan_markdown is not None else "- AI Media Buyer 动作计划：未生成",
        ]
    )

    if market_summary_lines:
        lines.extend(["", "## 市场负责人摘要摘录", ""])
        lines.extend(market_summary_lines[:6])
    if action_refinement_notes:
        lines.extend(["", "## 动作替换说明", ""])
        lines.extend(f"- {note}" for note in action_refinement_notes)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
