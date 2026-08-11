from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.manual_broadcast import build_artifacts
from market_ops.preview_overview import write_preview_overview


@dataclass(slots=True)
class CardPreviewPaths:
    overview_markdown: Path
    summary_markdown: Path
    summary_json: Path
    boss_markdown: Path
    boss_json: Path
    market_markdown: Path
    market_json: Path
    market_detail_markdown: Path
    market_detail_json: Path
    recovery_markdown: Path
    recovery_json: Path
    index_markdown: Path


def save_card_previews_from_cards(
    report_date: date,
    output_dir: Path,
    *,
    summary_card: dict[str, Any],
    boss_card: dict[str, Any],
    market_card: dict[str, Any],
    market_detail_card: dict[str, Any],
    recovery_card: dict[str, Any],
    action_refinement_notes: list[str] | None = None,
) -> CardPreviewPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = report_date.strftime("%Y%m%d")

    overview_markdown = output_dir / f"weekly_preview_overview_{stamp}.md"
    summary_markdown = output_dir / f"card_preview_summary_{stamp}.md"
    summary_json = output_dir / f"card_preview_summary_{stamp}.json"
    boss_markdown = output_dir / f"card_preview_boss_{stamp}.md"
    boss_json = output_dir / f"card_preview_boss_{stamp}.json"
    market_markdown = output_dir / f"card_preview_market_{stamp}.md"
    market_json = output_dir / f"card_preview_market_{stamp}.json"
    market_detail_markdown = output_dir / f"card_preview_market_detail_{stamp}.md"
    market_detail_json = output_dir / f"card_preview_market_detail_{stamp}.json"
    recovery_markdown = output_dir / f"card_preview_recovery_{stamp}.md"
    recovery_json = output_dir / f"card_preview_recovery_{stamp}.json"
    index_markdown = output_dir / f"card_preview_index_{stamp}.md"

    summary_markdown.write_text(render_card_preview_markdown(summary_card), encoding="utf-8")
    summary_json.write_text(json.dumps(summary_card, ensure_ascii=False, indent=2), encoding="utf-8")
    boss_markdown.write_text(render_card_preview_markdown(boss_card), encoding="utf-8")
    boss_json.write_text(json.dumps(boss_card, ensure_ascii=False, indent=2), encoding="utf-8")
    market_markdown.write_text(render_card_preview_markdown(market_card), encoding="utf-8")
    market_json.write_text(json.dumps(market_card, ensure_ascii=False, indent=2), encoding="utf-8")
    market_detail_markdown.write_text(render_card_preview_markdown(market_detail_card), encoding="utf-8")
    market_detail_json.write_text(json.dumps(market_detail_card, ensure_ascii=False, indent=2), encoding="utf-8")
    recovery_markdown.write_text(render_card_preview_markdown(recovery_card), encoding="utf-8")
    recovery_json.write_text(json.dumps(recovery_card, ensure_ascii=False, indent=2), encoding="utf-8")

    index_lines = [
        f"# 飞书卡片本地预览 | {report_date.isoformat()}",
        "",
        f"- 预发送摘要预览 Markdown：{summary_markdown}",
        f"- 预发送摘要卡片 JSON：{summary_json}",
        f"- 老板版预览 Markdown：{boss_markdown}",
        f"- 老板版卡片 JSON：{boss_json}",
        f"- 市场简版预览 Markdown：{market_markdown}",
        f"- 市场简版卡片 JSON：{market_json}",
        f"- 市场详细版预览 Markdown：{market_detail_markdown}",
        f"- 市场详细版卡片 JSON：{market_detail_json}",
        f"- 回收版预览 Markdown：{recovery_markdown}",
        f"- 回收版卡片 JSON：{recovery_json}",
        "",
        "说明：以上文件仅用于本地预览，不会触发飞书发送。",
    ]
    if action_refinement_notes:
        index_lines.extend(["", "## 动作替换说明", ""])
        index_lines.extend(f"- {note}" for note in action_refinement_notes)
    index_markdown.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    write_preview_overview(
        report_date,
        overview_markdown,
        summary_markdown=summary_markdown,
        summary_json=summary_json,
        index_markdown=index_markdown,
        boss_markdown=boss_markdown,
        market_markdown=market_markdown,
        market_detail_markdown=market_detail_markdown,
        recovery_markdown=recovery_markdown,
        self_check_markdown=(output_dir / f"self_check_{stamp}.md"),
        report_audit_markdown=(output_dir / f"report_audit_{stamp}.md"),
        pre_send_summary_markdown=(output_dir / f"pre_send_summary_{stamp}.md"),
        health_check_markdown=(output_dir / f"weekly_health_check_{stamp}.md"),
        creative_source_readiness_markdown=(output_dir / f"creative_source_readiness_{stamp}.md"),
        data_quality_audit_markdown=(output_dir / f"data_quality_audit_{stamp}.md"),
        creative_attribution_audit_markdown=(output_dir / f"creative_attribution_audit_{stamp}.md"),
        google_creative_repair_audit_markdown=(output_dir / f"google_creative_repair_audit_{stamp}.md"),
        google_revenue_attribution_audit_markdown=(output_dir / f"google_revenue_attribution_audit_{stamp}.md"),
        closure_status_markdown=(output_dir / f"closure_status_{stamp}.md"),
        project_detail_coverage_markdown=(output_dir / f"project_detail_coverage_{stamp}.md"),
        p04_source_checklist_markdown=(output_dir / f"p04_source_checklist_{stamp}.md"),
        detail_reply_checklist_markdown=(output_dir / f"detail_reply_checklist_{stamp}.md"),
        management_action_list_markdown=(output_dir / f"management_action_list_{stamp}.md"),
        growth_priorities_markdown=(output_dir / f"growth_priorities_{stamp}.md"),
        creative_dna_markdown=(output_dir / f"creative_dna_{stamp}.md"),
        creative_clusters_markdown=(output_dir / f"creative_clusters_{stamp}.md"),
        creative_fatigue_markdown=(output_dir / f"creative_fatigue_{stamp}.md"),
        dynamic_payback_markdown=(output_dir / f"dynamic_payback_{stamp}.md"),
        ai_media_buyer_plan_markdown=(output_dir / f"ai_media_buyer_plan_{stamp}.md"),
        action_refinement_notes=action_refinement_notes,
    )

    return CardPreviewPaths(
        overview_markdown=overview_markdown,
        summary_markdown=summary_markdown,
        summary_json=summary_json,
        boss_markdown=boss_markdown,
        boss_json=boss_json,
        market_markdown=market_markdown,
        market_json=market_json,
        market_detail_markdown=market_detail_markdown,
        market_detail_json=market_detail_json,
        recovery_markdown=recovery_markdown,
        recovery_json=recovery_json,
        index_markdown=index_markdown,
    )


def save_card_previews(report_date: date, meeting_name: str, output_dir: Path) -> CardPreviewPaths:
    artifacts = build_artifacts(report_date, meeting_name)
    return save_card_previews_from_cards(
        report_date,
        output_dir,
        summary_card=artifacts.summary_card,
        boss_card=artifacts.boss_card,
        market_card=artifacts.market_simple_card,
        market_detail_card=artifacts.market_detailed_card,
        recovery_card=artifacts.recovery_card,
        action_refinement_notes=artifacts.digest.action_refinement_notes,
    )


def render_card_preview_markdown(card: dict[str, Any]) -> str:
    title = card.get("header", {}).get("title", {}).get("content", "飞书卡片预览")
    lines = [f"# {title}", ""]

    for element in card.get("elements", []):
        tag = element.get("tag")
        if tag == "hr":
            lines.extend(["---", ""])
            continue
        if tag != "div":
            continue

        text = element.get("text")
        if isinstance(text, dict):
            content = str(text.get("content", "")).strip()
            if content:
                lines.extend([content, ""])

        fields = element.get("fields")
        if isinstance(fields, list):
            for field in fields:
                field_text = field.get("text", {})
                content = str(field_text.get("content", "")).strip()
                if content:
                    lines.extend([content, ""])

    return "\n".join(lines).rstrip() + "\n"
