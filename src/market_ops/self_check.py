from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from market_ops.card_preview import CardPreviewPaths, render_card_preview_markdown, save_card_previews_from_cards
from market_ops.creative_attribution_audit import CreativeAttributionAuditBuilder
from market_ops.creative_source_readiness import CreativeSourceReadinessBuilder
from market_ops.config import load_settings
from market_ops.final_executive import FinalExecutiveReportBuilder
from market_ops.final_digest import FinalWeeklyDigestBuilder
from market_ops.google_creative_repair_audit import GoogleCreativeRepairAuditBuilder
from market_ops.google_revenue_attribution_audit import GoogleRevenueAttributionAuditBuilder
from market_ops.management_action_list import ManagementActionListBuilder
from market_ops.manual_broadcast import build_artifacts
from market_ops.preview_overview import write_preview_overview
from market_ops.send_payload_consistency import SendPayloadConsistencyBuilder


MIN_ROOT_CAUSE_COUNTRY_COST = 100.0
MIN_ROOT_CAUSE_COUNTRY_SHARE = 0.02


@dataclass(slots=True)
class SelfCheckIssue:
    code: str
    source: str
    message: str
    actual: str
    expected: str


@dataclass(slots=True)
class SelfCheckResult:
    passed: bool
    issues: list[SelfCheckIssue]
    warnings: list[str]
    preview_paths: CardPreviewPaths
    markdown_path: Path
    json_path: Path


def run_self_check(report_date: date, meeting_name: str, output_dir: Path) -> SelfCheckResult:
    settings = load_settings()
    artifacts = build_artifacts(report_date, meeting_name)
    digest_builder = FinalWeeklyDigestBuilder(settings)
    digest_path = digest_builder.save_markdown(artifacts.digest, output_dir)
    executive_builder = FinalExecutiveReportBuilder(settings)
    executive_path = executive_builder.save_markdown(artifacts.executive, output_dir, "weekly")

    preview_paths = save_card_previews_from_cards(
        report_date,
        output_dir,
        summary_card=artifacts.summary_card,
        boss_card=artifacts.boss_card,
        market_card=artifacts.market_simple_card,
        market_detail_card=artifacts.market_detailed_card,
        recovery_card=artifacts.recovery_card,
        action_refinement_notes=artifacts.digest.action_refinement_notes,
    )

    digest_markdown = digest_builder.render_markdown(artifacts.digest)
    executive_markdown = FinalExecutiveReportBuilder(settings).render_markdown(artifacts.executive)
    market_simple_preview = render_card_preview_markdown(artifacts.market_simple_card)
    market_detail_preview = render_card_preview_markdown(artifacts.market_detailed_card)
    recovery_preview = render_card_preview_markdown(artifacts.recovery_card)
    boss_preview = render_card_preview_markdown(artifacts.boss_card)

    issues: list[SelfCheckIssue] = []
    warnings: list[str] = []
    project_names = [item.game for item in artifacts.digest.project_items if item.game]

    _check_company_labels(artifacts.market_simple_card, "market_simple_card", issues)
    _check_company_labels(artifacts.market_detailed_card, "market_detailed_card", issues)
    for source_name, text in (
        ("digest_markdown", digest_markdown),
        ("executive_markdown", executive_markdown),
        ("market_simple_preview", market_simple_preview),
        ("market_detail_preview", market_detail_preview),
        ("recovery_preview", recovery_preview),
        ("boss_preview", boss_preview),
    ):
        _check_text_absence(source_name, text, "公司 ROI", issues, "公司总收入ROI")
        _check_text_absence(source_name, text, "Meta", issues, "Facebook")
        _check_text_encoding(source_name, text, issues)
        _check_stale_action_logic(source_name, text, issues)
    _check_current_weekly_report(output_dir, report_date, issues, artifacts.digest.company_metrics)
    management_action_payload = ManagementActionListBuilder(settings).build_payload(report_date)
    _check_current_action_tracker(settings.action_tracker_csv, report_date, issues, management_action_payload)
    for source_name, text in (
        ("digest_markdown", digest_markdown),
        ("market_detail_preview", market_detail_preview),
        ("recovery_preview", recovery_preview),
    ):
        _check_text_absence(source_name, text, "未知项目 / 未知渠道", issues, "素材或项目上下文必须补齐，不能输出未知项目/未知渠道")
    for source_name, text in (
        ("market_simple_preview", market_simple_preview),
        ("market_detail_preview", market_detail_preview),
        ("boss_preview", boss_preview),
    ):
        _check_text_presence(source_name, text, "素材", issues, "素材可信度状态提示")
    for required in (
        "第一页",
        "数据可信度",
        "第二层",
        "第三层",
        "第四层",
        "问题=",
        "原因=",
        "行动=",
        "负责人=",
        "截止时间=",
        "验证指标=",
    ):
        _check_text_presence("boss_preview", boss_preview, required, issues, f"老板版必要字段 {required}")
    for required in (
        "数据可信度",
        "风险清单",
        "市场负责人摘要",
        "风险判断：",
        "建议动作：",
        "问题=",
        "负责人=",
        "截止时间=",
        "验证指标=",
    ):
        _check_text_presence("market_detail_preview", market_detail_preview, required, issues, f"市场版必要字段 {required}")
    for required in ("第一层：管理层摘要", "第二层：项目分析", "第三层：投放分析", "第四层：素材分析", "回本门槛："):
        _check_text_presence("executive_markdown", executive_markdown, required, issues, f"老板版文稿必要字段 {required}")
    for required in ("回本门槛：", "第三层：投放分析"):
        _check_text_presence("boss_preview", boss_preview, required, issues, f"老板版卡片必要字段 {required}")
    for required in ("回本门槛：", "3. Campaign 投放分析"):
        _check_text_presence("market_detail_preview", market_detail_preview, required, issues, f"市场版必要字段 {required}")
    _check_payback_gate_availability(settings, report_date, digest_markdown, market_simple_preview, market_detail_preview, boss_preview, issues)
    _check_text_presence("digest_markdown", digest_markdown, "市场负责人摘要", issues, "市场版文稿必须包含负责人摘要")
    _check_text_presence("market_simple_preview", market_simple_preview, "市场负责人摘要", issues, "市场简版必须包含负责人摘要")
    _check_text_presence("market_detail_preview", market_detail_preview, "市场负责人摘要", issues, "市场详细版必须包含负责人摘要")
    _check_market_summary_quality("digest_markdown", digest_markdown, issues)
    _check_market_summary_quality("market_simple_preview", market_simple_preview, issues)
    _check_market_summary_quality("market_detail_preview", market_detail_preview, issues)
    _check_summary_campaign_action_alignment("digest_markdown", digest_markdown, issues)
    _check_summary_campaign_action_alignment("market_simple_preview", market_simple_preview, issues)
    _check_summary_campaign_action_alignment("market_detail_preview", market_detail_preview, issues)
    _check_adjust_creative_roi_consistency(output_dir, report_date, digest_markdown, "digest_markdown", issues)
    _check_adjust_creative_roi_consistency(output_dir, report_date, market_detail_preview, "market_detail_preview", issues)
    _check_boss_summary_length("executive_markdown", executive_markdown, issues)
    _check_boss_summary_length("boss_preview", boss_preview, issues)
    _check_management_action_sample_gates(management_action_payload, issues)

    _check_recovery_labels(recovery_preview, issues)

    for project in project_names:
        digest_block = _extract_project_block(digest_markdown, project, project_names)
        simple_block = _extract_project_block(market_simple_preview, project, project_names)
        detail_block = _extract_project_block(market_detail_preview, project, project_names)
        recovery_block = _extract_project_block(recovery_preview, project, project_names)
        for source_name, block in (
            ("digest_markdown", digest_block),
            ("market_simple_preview", simple_block),
            ("market_detail_preview", detail_block),
            ("recovery_preview", recovery_block),
        ):
            if not block:
                issues.append(SelfCheckIssue("missing_project_block", source_name, f"缺少项目块：{project}", "", project))
        if not all((digest_block, simple_block, detail_block, recovery_block)):
            continue

        digest_metrics = _extract_project_metrics(digest_block)
        simple_metrics = _extract_project_metrics(simple_block)
        detail_metrics = _extract_project_metrics(detail_block)
        recovery_metrics = _extract_project_metrics(recovery_block)

        for source_name, metrics in (
            ("digest_markdown", digest_metrics),
            ("market_simple_preview", simple_metrics),
            ("market_detail_preview", detail_metrics),
            ("recovery_preview", recovery_metrics),
        ):
            _check_payback_math(project, source_name, metrics, issues)

        for right_source, right_metrics in (
            ("market_simple_preview", simple_metrics),
            ("market_detail_preview", detail_metrics),
            ("recovery_preview", recovery_metrics),
        ):
            _compare_metric(project, "花费", digest_metrics.get("spend"), right_metrics.get("spend"), "digest_markdown", right_source, issues)
            _compare_metric(project, "预测ROI", digest_metrics.get("forecast"), right_metrics.get("forecast"), "digest_markdown", right_source, issues)
            _compare_metric(project, "回本差额", digest_metrics.get("gap"), right_metrics.get("gap"), "digest_markdown", right_source, issues)
            _compare_metric(project, "利润空间", digest_metrics.get("profit"), right_metrics.get("profit"), "digest_markdown", right_source, issues)

        for right_source, right_metrics in (
            ("market_detail_preview", detail_metrics),
            ("recovery_preview", recovery_metrics),
        ):
            _compare_metric(
                project,
                "回收变化",
                digest_metrics.get("recovery_change"),
                right_metrics.get("recovery_change"),
                "digest_markdown",
                right_source,
                issues,
            )

    digest_project_map = {item.game: item for item in artifacts.digest.project_items if item.game}
    executive_project_map = {item.project: item for item in artifacts.executive.project_items if item.project}
    for project in sorted(set(digest_project_map) & set(executive_project_map)):
        digest_item = digest_project_map[project]
        executive_item = executive_project_map[project]
        _compare_metric(
            project,
            "老板版项目花费",
            f"{executive_item.spend:.0f}",
            f"{digest_item.spend:.0f}",
            "executive_markdown",
            "digest_markdown",
            issues,
        )
        _compare_metric(
            project,
            "老板版项目收入",
            f"{executive_item.revenue:.0f}",
            f"{digest_item.total_revenue:.0f}",
            "executive_markdown",
            "digest_markdown",
            issues,
        )
        _compare_metric(
            project,
            "老板版项目ROI",
            f"{executive_item.roi:.2f}",
            f"{digest_item.project_roi:.2f}",
            "executive_markdown",
            "digest_markdown",
            issues,
        )

    creative_audit_paths, creative_audit_payload = _load_or_build_creative_audit(settings, report_date)
    creative_source_readiness_paths, creative_source_readiness_payload = _load_or_build_creative_source_readiness(settings, report_date)
    google_creative_repair_paths, google_creative_repair_payload = _load_or_build_google_creative_repair(settings, report_date)
    google_revenue_attribution_result, google_revenue_attribution_payload = _load_or_build_google_revenue_attribution(settings, report_date)
    warnings.extend(_build_creative_source_readiness_warnings(creative_source_readiness_payload))
    warnings.extend(_build_creative_audit_warnings(creative_audit_payload))
    warnings.extend(_build_google_creative_repair_warnings(google_creative_repair_payload))
    warnings.extend(_build_google_revenue_attribution_warnings(google_revenue_attribution_payload))
    payload_consistency = SendPayloadConsistencyBuilder().build(
        report_date=report_date,
        meeting_name=meeting_name,
        output_dir=output_dir,
        artifacts=artifacts,
        preview_paths=preview_paths,
    )
    for item in payload_consistency.issues:
        issues.append(
            SelfCheckIssue(
                code="send_payload_mismatch",
                source=item.card_name,
                message=item.message,
                actual=item.actual,
                expected=item.expected,
            )
        )

    stamp = report_date.strftime("%Y%m%d")
    v25_payload = _check_v25_artifacts(output_dir, report_date, issues)
    markdown_path = output_dir / f"self_check_{stamp}.md"
    json_path = output_dir / f"self_check_{stamp}.json"
    report_audit_path = output_dir / f"report_audit_{stamp}.md"
    pre_send_summary_path = output_dir / f"pre_send_summary_{stamp}.md"

    payload = {
        "passed": not issues,
        "report_date": report_date.isoformat(),
        "meeting_name": meeting_name,
        "preview_paths": {
            "weekly_digest_markdown": str(digest_path),
            "executive_markdown": str(executive_path),
            "overview_markdown": str(preview_paths.overview_markdown),
            "summary_markdown": str(preview_paths.summary_markdown),
            "summary_json": str(preview_paths.summary_json),
            "boss_markdown": str(preview_paths.boss_markdown),
            "boss_json": str(preview_paths.boss_json),
            "market_markdown": str(preview_paths.market_markdown),
            "market_json": str(preview_paths.market_json),
            "market_detail_markdown": str(preview_paths.market_detail_markdown),
            "market_detail_json": str(preview_paths.market_detail_json),
            "recovery_markdown": str(preview_paths.recovery_markdown),
            "recovery_json": str(preview_paths.recovery_json),
            "index_markdown": str(preview_paths.index_markdown),
        },
        "action_refinement_notes": list(artifacts.digest.action_refinement_notes),
        "warnings": warnings,
        "creative_attribution_audit": {
            "summary_path": str(creative_audit_paths["summary"]),
            "json_path": str(creative_audit_paths["json"]),
            "coverage_path": str(creative_audit_paths["coverage"]),
            "top_entities_path": str(creative_audit_paths["top_entities"]),
            "readiness": creative_audit_payload.get("readiness", {}),
            "warnings": creative_audit_payload.get("warnings", []),
            "issues": creative_audit_payload.get("issues", []),
        },
        "creative_source_readiness": {
            "summary_path": str(creative_source_readiness_paths["summary"]),
            "json_path": str(creative_source_readiness_paths["json"]),
            "summary": creative_source_readiness_payload.get("summary", {}),
            "blockers": creative_source_readiness_payload.get("blockers", []),
        },
        "google_creative_repair_audit": {
            "summary_path": str(google_creative_repair_paths["summary"]),
            "json_path": str(google_creative_repair_paths["json"]),
            "segments_path": str(google_creative_repair_paths["segments"]),
            "resolver_ready": google_creative_repair_payload.get("resolver_ready"),
            "live_google_source_ready": google_creative_repair_payload.get("live_google_source_ready"),
            "placeholder_cost_share": google_creative_repair_payload.get("placeholder_cost_share"),
            "placeholder_cost": google_creative_repair_payload.get("placeholder_cost"),
            "resolved_cost": google_creative_repair_payload.get("resolved_cost"),
        },
        "google_revenue_attribution_audit": {
            "summary_path": str(google_revenue_attribution_result.markdown_path),
            "json_path": str(google_revenue_attribution_result.json_path),
            "csv_path": str(google_revenue_attribution_result.csv_path),
            "passed": google_revenue_attribution_payload.get("passed"),
            "risk_level": google_revenue_attribution_payload.get("risk_level"),
            "summary": google_revenue_attribution_payload.get("summary", {}),
            "conclusion": google_revenue_attribution_payload.get("conclusion"),
        },
        "management_action_sample_gate": {
            "min_country_cost": MIN_ROOT_CAUSE_COUNTRY_COST,
            "min_country_share": MIN_ROOT_CAUSE_COUNTRY_SHARE,
        },
        "send_payload_consistency": {
            "summary_path": str(payload_consistency.markdown_path),
            "json_path": str(payload_consistency.json_path),
            "passed": payload_consistency.passed,
            "issue_count": len(payload_consistency.issues),
        },
        "v25_decision_loop": v25_payload,
        "issues": [asdict(issue) for issue in issues],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_self_check_markdown(payload), encoding="utf-8")
    write_preview_overview(
        report_date,
        preview_paths.overview_markdown,
        summary_markdown=preview_paths.summary_markdown,
        summary_json=preview_paths.summary_json,
        index_markdown=preview_paths.index_markdown,
        boss_markdown=preview_paths.boss_markdown,
        market_markdown=preview_paths.market_markdown,
        market_detail_markdown=preview_paths.market_detail_markdown,
        recovery_markdown=preview_paths.recovery_markdown,
        self_check_markdown=markdown_path,
        report_audit_markdown=report_audit_path if report_audit_path.exists() else None,
        pre_send_summary_markdown=pre_send_summary_path if pre_send_summary_path.exists() else None,
        health_check_markdown=(output_dir / f"weekly_health_check_{stamp}.md") if (output_dir / f"weekly_health_check_{stamp}.md").exists() else None,
        creative_source_readiness_markdown=creative_source_readiness_paths["summary"],
        data_quality_audit_markdown=(output_dir / f"data_quality_audit_{stamp}.md") if (output_dir / f"data_quality_audit_{stamp}.md").exists() else None,
        creative_attribution_audit_markdown=creative_audit_paths["summary"],
        google_creative_repair_audit_markdown=google_creative_repair_paths["summary"],
        google_revenue_attribution_audit_markdown=google_revenue_attribution_result.markdown_path,
        send_payload_consistency_markdown=payload_consistency.markdown_path,
        tecdo_probe_markdown=(output_dir / f"tecdo_probe_{stamp}.md") if (output_dir / f"tecdo_probe_{stamp}.md").exists() else None,
        tecdo_account_reconciliation_markdown=(output_dir / f"tecdo_account_reconciliation_{stamp}.md") if (output_dir / f"tecdo_account_reconciliation_{stamp}.md").exists() else None,
        tecdo_sync_checklist_markdown=(output_dir / f"tecdo_sync_checklist_{stamp}.md") if (output_dir / f"tecdo_sync_checklist_{stamp}.md").exists() else None,
        management_action_list_markdown=(output_dir / f"management_action_list_{stamp}.md") if (output_dir / f"management_action_list_{stamp}.md").exists() else None,
        action_refinement_notes=list(artifacts.digest.action_refinement_notes),
    )

    return SelfCheckResult(
        passed=not issues,
        issues=issues,
        warnings=warnings,
        preview_paths=preview_paths,
        markdown_path=markdown_path,
        json_path=json_path,
    )


def _load_or_build_creative_audit(settings, report_date: date) -> tuple[dict[str, Path], dict]:
    stamp = report_date.strftime("%Y%m%d")
    paths = {
        "summary": settings.active_output_dir / f"creative_attribution_audit_{stamp}.md",
        "json": settings.active_output_dir / f"creative_attribution_audit_{stamp}.json",
        "coverage": settings.output_dir / f"creative_attribution_coverage_{stamp}.csv",
        "top_entities": settings.output_dir / f"creative_attribution_top_entities_{stamp}.csv",
    }
    payload = _load_existing_json(paths["json"])
    if payload is not None and paths["summary"].exists():
        return paths, payload
    paths = CreativeAttributionAuditBuilder(settings).build(report_date=report_date)
    return paths, json.loads(paths["json"].read_text(encoding="utf-8"))


def _load_or_build_creative_source_readiness(settings, report_date: date) -> tuple[dict[str, Path], dict]:
    stamp = report_date.strftime("%Y%m%d")
    paths = {
        "summary": settings.active_output_dir / f"creative_source_readiness_{stamp}.md",
        "json": settings.active_output_dir / f"creative_source_readiness_{stamp}.json",
    }
    payload = _load_existing_json(paths["json"])
    if payload is not None and paths["summary"].exists():
        return paths, payload
    paths = CreativeSourceReadinessBuilder(settings).build(report_date=report_date)
    return paths, json.loads(paths["json"].read_text(encoding="utf-8"))


def _load_or_build_google_creative_repair(settings, report_date: date) -> tuple[dict[str, Path], dict]:
    stamp = report_date.strftime("%Y%m%d")
    paths = {
        "summary": settings.active_output_dir / f"google_creative_repair_audit_{stamp}.md",
        "json": settings.active_output_dir / f"google_creative_repair_audit_{stamp}.json",
        "segments": settings.output_dir / f"google_creative_repair_segments_{stamp}.csv",
    }
    payload = _load_existing_json(paths["json"])
    if payload is not None and paths["summary"].exists():
        return paths, payload
    paths = GoogleCreativeRepairAuditBuilder(settings).build(report_date=report_date)
    return paths, json.loads(paths["json"].read_text(encoding="utf-8"))


def _load_or_build_google_revenue_attribution(settings, report_date: date):
    stamp = report_date.strftime("%Y%m%d")
    markdown_path = settings.active_output_dir / f"google_revenue_attribution_audit_{stamp}.md"
    json_path = settings.active_output_dir / f"google_revenue_attribution_audit_{stamp}.json"
    csv_path = settings.output_dir / f"google_revenue_zero_segments_{stamp}.csv"
    payload = _load_existing_json(json_path)
    if payload is not None and markdown_path.exists():
        result = SimpleNamespace(
            markdown_path=markdown_path,
            json_path=json_path,
            csv_path=csv_path,
            passed=bool(payload.get("passed")),
        )
        return result, payload
    result = GoogleRevenueAttributionAuditBuilder(settings).build(report_date=report_date)
    return result, json.loads(result.json_path.read_text(encoding="utf-8"))


def _load_existing_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _check_company_labels(card: dict, source: str, issues: list[SelfCheckIssue]) -> None:
    expected = ["本周花费", "整体收入", "公司总收入ROI", "主投渠道"]
    actual: list[str] = []
    for element in card.get("elements", []):
        fields = element.get("fields")
        if not isinstance(fields, list):
            continue
        for field in fields:
            content = str(field.get("text", {}).get("content", ""))
            match = re.search(r"\*\*(.+?)\*\*", content)
            if match:
                actual.append(match.group(1))
        if actual:
            break
    if actual[:4] != expected:
        issues.append(
            SelfCheckIssue(
                "company_metric_labels",
                source,
                "公司层指标标签不一致",
                " | ".join(actual[:4]),
                " | ".join(expected),
            )
        )


def _check_text_absence(source: str, text: str, forbidden: str, issues: list[SelfCheckIssue], expected: str) -> None:
    if forbidden in text:
        issues.append(
            SelfCheckIssue(
                "forbidden_text",
                source,
                f"出现了不允许的文案：{forbidden}",
                forbidden,
                expected,
            )
        )


def _check_text_presence(source: str, text: str, required: str, issues: list[SelfCheckIssue], label: str) -> None:
    if required in text:
        return
    issues.append(
        SelfCheckIssue(
            "missing_required_text",
            source,
            f"缺少{label}",
            text[:200],
            required,
        )
    )


def _check_text_encoding(source: str, text: str, issues: list[SelfCheckIssue]) -> None:
    mojibake_markers = ("锛", "銆", "鏈", "闆", "鍥", "浼", "璇")
    marker_hits = sum(text.count(marker) for marker in mojibake_markers)
    if marker_hits < 3:
        return
    issues.append(
        SelfCheckIssue(
            "encoding_mojibake",
            source,
            "检测到疑似乱码文本，当前内容不可发送",
            text[:200],
            "输出应为可读中文",
        )
    )


def _check_stale_action_logic(source: str, text: str, issues: list[SelfCheckIssue]) -> None:
    forbidden_snippets = (
        "7天总收入ROI先回到 0.60",
        "7天总收入ROI 回到 0.80",
        "先把付费净 ROI 拉回到 0.80",
        "付费净 ROI 拉回到 0.80",
        "3日 ROAS 恢复到 1.00",
        "3日 ROI 回到目标线以上后再决定是否恢复或扩大预算",
        "再决定是否恢复或扩大预算",
        "再决定是否恢复预算",
        "再讨论是否恢复",
        "降权或停测",
        "D7 至少回到",
        "D30 尽快接近",
        "短周期回收已过门槛",
        "先维持预算稳定，只优化已验证的回收组合",
        "当前最需要压缩的低效段",
        "下周重点关注：先压缩",
        "放量期间收入/花费比保持在目标线以上",
        "暂停 P02 Mermaid",
        "暂停：P02 Mermaid",
        "加码：P02 Mermaid",
        "P02 Mermaid 高回收投放",
        "暂停 P04 Witch",
        "Google（ROI 0.00）",
        "当前最弱渠道是 Google（ROI 0.00）",
        "当前最弱渠道是 Google（ROI ",
        "继续复制高回收素材",
        "复制并扩充变体",
    )
    for snippet in forbidden_snippets:
        if snippet in text:
            issues.append(
                SelfCheckIssue(
                    "stale_action_logic",
                    source,
                    "检测到已废弃的强动作或旧回本依据，不能进入发送版本",
                    snippet,
                    "使用当前 Actual/Forecast/可信度口径，不输出旧 0.60/0.80 强阈值或强暂停结论",
                )
            )
    stale_owner_patterns = (
        r"姜会伟：处理\s+P0[247][^（\n；]*[/／][^（\n；]*(Facebook|Google|iOS|Android|Amazon)",
        r"姜会伟：处理\s+P0[247][^（\n；]*(Facebook|Google|iOS|Android|Amazon)[^（\n；]*[/／]",
    )
    for pattern in stale_owner_patterns:
        match = re.search(pattern, text)
        if match:
            issues.append(
                SelfCheckIssue(
                    "paid_scope_wrong_owner",
                    source,
                    "投放组合动作不能分配给项目负责人",
                    match.group(0),
                    "带平台/渠道/预算的动作应由林凯负责；纯项目口径补齐才归姜会伟",
                )
            )
    bare_roi_patterns = (
        r"当前\s*ROI\s*=",
    )
    for pattern in bare_roi_patterns:
        match = re.search(pattern, text)
        if match:
            issues.append(
                SelfCheckIssue(
                    "bare_roi_label",
                    source,
                    "检测到未注明口径的 ROI 文案，容易造成总收入ROI/付费净ROI/Campaign ROI混淆",
                    match.group(0),
                    "使用 公司总收入ROI / 项目总收入ROI / 付费净ROI / Campaign ROI / 素材代理ROI",
                )
            )


def _check_management_action_attribution_gate(payload: dict, issues: list[SelfCheckIssue]) -> None:
    for item in payload.get("items") or []:
        gate = item.get("dimension_gate") or {}
        unreliable_channels = {str(channel) for channel in gate.get("unreliable_revenue_channels") or []}
        if not unreliable_channels:
            continue
        scope = str(item.get("scope") or "")
        action = str(item.get("action") or "")
        for channel in unreliable_channels:
            if channel and (scope.endswith(f"/ {channel}") or f" {channel}" in scope):
                issues.append(
                    SelfCheckIssue(
                        "unreliable_attribution_action_scope",
                        "management_action_list",
                        "归因不可信渠道不能作为预算动作的当前优先处理组合",
                        f"{item.get('project', '')} / {scope}",
                        "先输出归因复核，不直接把该渠道作为预算动作对象",
                    )
                )
            if channel and channel in action and any(keyword in action for keyword in ("控量", "限额", "小额", "新增预算", "提高")):
                issues.append(
                    SelfCheckIssue(
                        "unreliable_attribution_budget_action",
                        "management_action_list",
                        "归因不可信渠道不能直接进入预算动作",
                        action,
                        "先校对归因口径，再决定预算动作",
                    )
                )


def _check_management_action_sample_gates(payload: dict, issues: list[SelfCheckIssue]) -> None:
    for item in payload.get("items", []) or []:
        reason = str(item.get("reason") or "")
        country_match = re.search(r"最弱国家是\s+([^（；。\n]+)", reason)
        if not country_match:
            continue
        country = country_match.group(1).strip()
        countries = item.get("country_breakdown") or []
        total_country_cost = sum(float(row.get("cost") or 0.0) for row in countries if isinstance(row, dict))
        country_row = next(
            (row for row in countries if isinstance(row, dict) and str(row.get("key") or "").strip() == country),
            None,
        )
        if not country_row:
            issues.append(
                SelfCheckIssue(
                    "weak_country_not_in_breakdown",
                    "management_action_list",
                    "动作原因中出现最弱国家，但国家明细里找不到对应项",
                    country,
                    "最弱国家必须来自本周 breakdown 明细",
                )
            )
            continue
        cost = float(country_row.get("cost") or 0.0)
        share = cost / total_country_cost if total_country_cost else 0.0
        min_cost = max(MIN_ROOT_CAUSE_COUNTRY_COST, total_country_cost * MIN_ROOT_CAUSE_COUNTRY_SHARE)
        if cost < min_cost:
            issues.append(
                SelfCheckIssue(
                    "weak_country_sample_too_small",
                    "management_action_list",
                    "低花费国家被写成强根因，容易误导投放判断",
                    f"{item.get('project', '')} / {country} 花费={cost:.2f} 占比={share:.1%}",
                    f"只有国家花费 >= {min_cost:.2f} 才允许写成最弱国家；否则只能作为观察样本",
                )
            )


def _check_current_weekly_report(output_dir: Path, report_date: date, issues: list[SelfCheckIssue], company_metrics=None) -> None:
    stamp = report_date.strftime("%Y%m%d")
    path = output_dir / f"weekly_report_{stamp}.md"
    if not path.exists():
        issues.append(
            SelfCheckIssue(
                "missing_weekly_report",
                "weekly_report",
                "缺少当前周底层 weekly_report，无法确认草拟任务是否干净",
                str(path),
                "生成 weekly_report 后再通过发送门禁",
            )
        )
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    _check_text_encoding(f"weekly_report_{stamp}", text, issues)
    _check_stale_action_logic(f"weekly_report_{stamp}", text, issues)
    _check_weekly_report_company_metrics(f"weekly_report_{stamp}", text, company_metrics or [], issues)
    for stale_phrase in (
        "整体平均 ROAS",
        "窗口总收入：",
        "收入/花费比为",
        "仍是当前主要投放项目",
        "最佳渠道：All",
        "All 是当前回收表现相对更稳的渠道",
    ):
        _check_text_absence(
            f"weekly_report_{stamp}",
            text,
            stale_phrase,
            issues,
            "底层 weekly_report 必须复用当前发送 digest 口径，不得保留旧 AI 摘要",
        )
    if "ROAS 0.00" in text and "复制素材" in text:
        issues.append(
            SelfCheckIssue(
                "stale_creative_action",
                f"weekly_report_{stamp}",
                "底层周报仍用 ROAS=0 素材生成复制任务",
                "ROAS 0.00 + 复制素材",
                "素材低可信或未过回收门槛时不得生成复制素材任务",
            )
        )


def _check_payback_gate_availability(
    settings,
    report_date: date,
    digest_markdown: str,
    market_simple_preview: str,
    market_detail_preview: str,
    boss_preview: str,
    issues: list[SelfCheckIssue],
) -> None:
    stamp = report_date.strftime("%Y%m%d")
    payback_csv = settings.output_dir / f"payback_targets_{stamp}.csv"
    if not payback_csv.exists():
        return
    text = payback_csv.read_text(encoding="utf-8-sig", errors="replace")
    has_all_projects = all(project in text for project in ("P02", "P04", "P07"))
    has_gate_columns = "floor_D7" in text and "floor_D30" in text
    if not (has_all_projects and has_gate_columns):
        return
    for source, content in (
        ("digest_markdown", digest_markdown),
        ("market_simple_preview", market_simple_preview),
        ("market_detail_preview", market_detail_preview),
        ("boss_preview", boss_preview),
    ):
        if "暂无项目回本门槛" in content or "暂无可用门槛" in content:
            issues.append(
                SelfCheckIssue(
                    "payback_gate_missing_despite_targets",
                    source,
                    "已有项目回本门槛文件，但发送内容仍显示暂无门槛",
                    "暂无项目回本门槛",
                    f"读取 {payback_csv} 中的 D7/D30 门槛并展示",
                )
            )


def _check_weekly_report_company_metrics(source: str, text: str, company_metrics, issues: list[SelfCheckIssue]) -> None:
    metric_map = {
        str(getattr(item, "label", "") or "").strip(): str(getattr(item, "value", "") or "").strip()
        for item in company_metrics or []
    }
    for label in ("本周花费", "整体收入", "公司总收入ROI", "主投渠道"):
        expected_value = metric_map.get(label)
        if not expected_value:
            continue
        if label not in text or expected_value not in text:
            issues.append(
                SelfCheckIssue(
                    "weekly_report_company_metric_mismatch",
                    source,
                    f"底层 weekly_report 未复用发送卡片的公司指标：{label}",
                    _first_matching_line(text, label),
                    f"{label} {expected_value}",
                )
            )


def _first_matching_line(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return line.strip()
    return ""


def _check_current_action_tracker(
    path: Path | None,
    report_date: date,
    issues: list[SelfCheckIssue],
    management_action_payload: dict | None = None,
) -> None:
    if path is None:
        return
    if not path.exists():
        issues.append(
            SelfCheckIssue(
                "missing_action_tracker",
                "action_tracker",
                "缺少 Action Tracker CSV，无法确认当前周任务是否干净",
                str(path),
                "生成 action_tracker.csv 后再通过发送门禁",
            )
        )
        return
    prefix = report_date.strftime("%Y%m%d")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    current_lines = [line for line in text.splitlines() if line.startswith(prefix)]
    current_text = "\n".join(current_lines)
    if not current_lines:
        return
    _check_text_encoding(f"action_tracker_{prefix}", current_text, issues)
    _check_stale_action_logic(f"action_tracker_{prefix}", current_text, issues)
    expected_items = (management_action_payload or {}).get("items") or []
    expected_count = min(3, len(expected_items))
    if expected_count and len(current_lines) != expected_count:
        issues.append(
            SelfCheckIssue(
                "action_tracker_current_week_count_mismatch",
                f"action_tracker_{prefix}",
                "Action Tracker 当前周任务数与管理动作台账不一致，可能残留旧任务",
                str(len(current_lines)),
                str(expected_count),
            )
        )
    if "复制素材" in current_text and ("CTR 高于账户中位数" in current_text or "已验证效果" in current_text):
        issues.append(
            SelfCheckIssue(
                "stale_creative_action",
                f"action_tracker_{prefix}",
                "Action Tracker 当前周仍有低可信素材复制任务",
                "复制素材 + CTR/已验证效果",
                "素材未过可信门槛时不得进入任务表",
            )
        )
    for stale_geo in ("Macao", "Luxembourg", "Finland"):
        if f"最弱国家是 {stale_geo}" in current_text:
            issues.append(
                SelfCheckIssue(
                    "action_tracker_low_sample_country",
                    f"action_tracker_{prefix}",
                    "Action Tracker 当前周仍含低样本国家强根因",
                    stale_geo,
                    "低样本国家只能作为观察样本，不得写入执行任务根因",
                )
            )


def _check_recovery_labels(recovery_preview: str, issues: list[SelfCheckIssue]) -> None:
    if "实际回收倍率" not in recovery_preview or "预测回收倍率" not in recovery_preview:
        issues.append(
            SelfCheckIssue(
                "recovery_labels",
                "recovery_preview",
                "回收卡片标签未切到回收倍率口径",
                recovery_preview,
                "包含“实际回收倍率”和“预测回收倍率”",
            )
        )


def _extract_project_block(markdown: str, project: str, project_names: list[str]) -> str:
    lines = markdown.splitlines()
    project_markers = {f"- {name}" for name in project_names} | {f"**{name}**" for name in project_names}
    current_markers = {f"- {project}", f"**{project}**"}
    collecting = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not collecting and stripped in current_markers:
            collecting = True
            collected.append(stripped)
            continue
        if not collecting:
            continue
        if stripped in project_markers and stripped not in current_markers:
            break
        if stripped.startswith("## ") or stripped == "---":
            break
        collected.append(stripped)
    return "\n".join(line for line in collected if line)


def _extract_project_metrics(block: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    spend_match = re.search(r"花费\s*`?(\d+(?:\.\d+)?)", block)
    if spend_match:
        metrics["spend"] = f"{float(spend_match.group(1)):.0f}"

    forecast_candidates = re.findall(r"预测D?(180|90|60)\s*`?([0-9.]+)|预测 D(180|90|60)\s*=?\s*([0-9.]+)", block)
    parsed_candidates: list[tuple[int, float]] = []
    for a, b, c, d in forecast_candidates:
        day = a or c
        value = b or d
        if day and value:
            parsed_candidates.append((int(day), float(value)))
    if parsed_candidates:
        parsed_candidates.sort(reverse=True)
        metrics["forecast"] = f"{parsed_candidates[0][1]:.2f}"

    gap_match = re.search(r"距离回本还差(?:约)?\s*(\d+)", block)
    if gap_match:
        metrics["gap"] = gap_match.group(1)

    profit_match = re.search(r"利润空间约\s*(\d+)", block)
    if profit_match:
        metrics["profit"] = profit_match.group(1)

    recovery_change_match = re.search(r"回收变化：(.+)", block)
    if recovery_change_match:
        metrics["recovery_change"] = recovery_change_match.group(1).strip()
    return metrics


def _check_payback_math(project: str, source: str, metrics: dict[str, str], issues: list[SelfCheckIssue]) -> None:
    spend_text = metrics.get("spend")
    forecast_text = metrics.get("forecast")
    if not spend_text or not forecast_text:
        return
    spend = round(float(spend_text))
    forecast = float(forecast_text)
    if "gap" in metrics:
        expected_gap = f"{round(spend * max(0.0, 1.0 - forecast)):.0f}"
        if metrics["gap"] != expected_gap:
            issues.append(
                SelfCheckIssue(
                    "payback_gap_math",
                    source,
                    f"{project} 回本差额与展示 forecast ROI 不一致",
                    metrics["gap"],
                    expected_gap,
                )
            )
    if "profit" in metrics:
        expected_profit = f"{round(spend * max(0.0, forecast - 1.0)):.0f}"
        if metrics["profit"] != expected_profit:
            issues.append(
                SelfCheckIssue(
                    "payback_profit_math",
                    source,
                    f"{project} 利润空间与展示 forecast ROI 不一致",
                    metrics["profit"],
                    expected_profit,
                )
            )


def _compare_metric(
    project: str,
    metric_name: str,
    left: str | None,
    right: str | None,
    left_source: str,
    right_source: str,
    issues: list[SelfCheckIssue],
) -> None:
    if left == right:
        return
    issues.append(
        SelfCheckIssue(
            "cross_source_mismatch",
            f"{left_source} vs {right_source}",
            f"{project} 的{metric_name}不一致",
            str(left),
            str(right),
        )
    )


def _check_boss_summary_length(source_name: str, text: str, issues: list[SelfCheckIssue]) -> None:
    if "第一页：管理层摘要" in text:
        start_marker = "第一页：管理层摘要"
        end_candidates = ["---", "第二层：项目分析"]
    elif "## 第一层：管理层摘要" in text:
        start_marker = "## 第一层：管理层摘要"
        end_candidates = ["## 第二层：项目分析", "## 数据可信度"]
    else:
        return

    start = text.find(start_marker)
    if start < 0:
        return
    end_positions = [text.find(marker, start + len(start_marker)) for marker in end_candidates if text.find(marker, start + len(start_marker)) >= 0]
    end = min(end_positions) if end_positions else len(text)
    block = text[start:end]
    bullet_count = sum(1 for line in block.splitlines() if line.strip().startswith("- "))
    if bullet_count > 5:
        issues.append(
            SelfCheckIssue(
                "boss_summary_too_long",
                source_name,
                "老板版第一页超过 5 条，不符合管理层摘要限制",
                str(bullet_count),
                "<=5",
            )
        )
    summary_lines = [line.strip() for line in block.splitlines() if line.strip().startswith("- ")]
    if summary_lines:
        has_summary_confidence = any("数据可信度：" in line for line in summary_lines)
        has_separate_confidence_section = ("**数据可信度**" in text) or ("## 数据可信度" in text)
        if not has_summary_confidence and not has_separate_confidence_section:
            issues.append(
                SelfCheckIssue(
                    "boss_summary_missing_confidence",
                    source_name,
                    "老板版第一页缺少数据可信度摘要",
                    block[:200],
                    "需要包含 数据可信度：经营指标=...；素材=...",
                )
            )
        action_lines = [line for line in summary_lines if "下周重点动作：" in line]
        if action_lines and "；验证 " in action_lines[0]:
            issues.append(
                SelfCheckIssue(
                    "boss_summary_action_too_detailed",
                    source_name,
                    "老板版第一页动作仍包含过细验证描述，不够管理层化",
                    action_lines[0],
                    "动作摘要不应包含 ；验证 ...",
                )
            )
        if action_lines:
            action_line = action_lines[0]
            for noisy_field in ("负责人=", "截止时间=", "验证指标=", "KPI", "复制素材"):
                if noisy_field in action_line:
                    issues.append(
                        SelfCheckIssue(
                            "boss_summary_action_not_executive",
                            source_name,
                            "老板版第一页动作不够管理层化，仍包含任务字段或低可信度素材动作",
                            action_line,
                            "应保留短句动作，不包含 负责人=/截止时间=/验证指标=/KPI/复制素材",
                        )
                    )
                    break


def _check_market_summary_quality(source_name: str, text: str, issues: list[SelfCheckIssue]) -> None:
    if "**市场负责人摘要**" in text:
        start_marker = "**市场负责人摘要**"
        end_candidates = ["---", "**1. 公司总体数据情况**", "## 1. 公司总体数据情况"]
    elif "## 市场负责人摘要" in text:
        start_marker = "## 市场负责人摘要"
        end_candidates = ["## 1. 公司总体数据情况", "**1. 公司总体数据情况**"]
    else:
        return

    start = text.find(start_marker)
    if start < 0:
        return
    end_positions = [text.find(marker, start + len(start_marker)) for marker in end_candidates if text.find(marker, start + len(start_marker)) >= 0]
    end = min(end_positions) if end_positions else len(text)
    block = text[start:end]
    summary_lines = [line.strip() for line in block.splitlines() if line.strip().startswith("- ")]
    if len(summary_lines) > 6:
        issues.append(
            SelfCheckIssue(
                "market_summary_too_long",
                source_name,
                "市场负责人摘要超过 6 条，已偏离负责人摘要口径",
                str(len(summary_lines)),
                "<=6",
            )
        )
    action_lines = [line for line in summary_lines if line.startswith("- 本周执行优先级：")]
    if action_lines:
        action_line = action_lines[0]
        for noisy_field in ("截止时间", "KPI", "负责人："):
            if noisy_field in action_line:
                issues.append(
                    SelfCheckIssue(
                        "market_summary_action_too_detailed",
                        source_name,
                        "市场负责人摘要动作过细，仍带任务字段",
                        action_line,
                        "不应包含 负责人：/ 截止时间 / KPI",
                    )
                )
                break
        if "复制素材" in action_line and "Facebook素材=低" in block and "Google素材=低" in block:
            issues.append(
                SelfCheckIssue(
                    "market_summary_low_confidence_creative_action",
                    source_name,
                    "市场负责人摘要在素材低可信度时仍输出复制素材强动作",
                    action_line,
                    "素材低可信度时应优先输出投放动作",
                )
            )
    low_creative_confidence = "Facebook素材=低" in text and "Google素材=低" in text
    if low_creative_confidence:
        for strong_phrase in ("当前最值得看的素材是", "当前表现最好的素材ID是", "当前最弱的素材ID是"):
            if strong_phrase in text:
                issues.append(
                    SelfCheckIssue(
                        "market_creative_strong_claim_under_low_confidence",
                        source_name,
                        "素材低可信度时仍输出了素材强结论",
                        strong_phrase,
                        "素材低可信度时只允许输出观察提示，不允许输出最佳/最弱/最值得看的素材结论",
                    )
                )
                break


def _check_summary_campaign_action_alignment(source_name: str, text: str, issues: list[SelfCheckIssue]) -> None:
    block = _extract_market_summary_block(text)
    if not block:
        return
    action_segments = _extract_summary_action_segments(block)
    campaign_segments = _extract_summary_campaign_segments(block)
    if not action_segments or not campaign_segments:
        return
    if action_segments.isdisjoint(campaign_segments):
        issues.append(
            SelfCheckIssue(
                "summary_campaign_action_mismatch",
                source_name,
                "市场负责人摘要里的重点Campaign没有落在本周执行优先级组合内，容易造成行动对象误读",
                f"campaign={sorted(campaign_segments)}; actions={sorted(action_segments)}",
                "重点Campaign应优先选择本周执行优先级对应的商店/渠道组合",
            )
        )


def _extract_market_summary_block(text: str) -> str:
    if "**市场负责人摘要**" in text:
        start_marker = "**市场负责人摘要**"
        end_candidates = ["---", "**1. 公司总体数据情况**", "## 1. 公司总体数据情况"]
    elif "## 市场负责人摘要" in text:
        start_marker = "## 市场负责人摘要"
        end_candidates = ["## 1. 公司总体数据情况", "**1. 公司总体数据情况**", "---"]
    else:
        return ""
    start = text.find(start_marker)
    if start < 0:
        return ""
    tail = text[start + len(start_marker):]
    end_positions = [tail.find(marker) for marker in end_candidates if tail.find(marker) >= 0]
    end = min(end_positions) if end_positions else len(tail)
    return tail[:end]


def _extract_summary_action_segments(summary: str) -> set[str]:
    result: set[str] = set()
    for line in summary.splitlines():
        if "本周执行优先级：" not in line and "下周重点动作：" not in line:
            continue
        for match in re.finditer(r"[\u4e00-\u9fff]+：[^；。]*?/\s*([^/；。]+?)\s*/\s*([^/；。]+?)(?:（|；|。|$)", line):
            result.add(_normalize_segment_for_check(f"{match.group(1)} / {match.group(2)}"))
    return result


def _extract_summary_campaign_segments(summary: str) -> set[str]:
    result: set[str] = set()
    for line in summary.splitlines():
        if "重点Campaign：" not in line and "重点 Campaign" not in line:
            continue
        channel_match = re.search(r"重点\s*Campaign：?[^/；。]*?/\s*([^/；。]+?)\s*/", line)
        if not channel_match:
            continue
        channel = channel_match.group(1).strip()
        upper_line = line.upper()
        store = "iOS" if "IOS" in upper_line or "-IOS-" in upper_line else ""
        if not store and ("ANDROID" in upper_line or "-AND-" in upper_line):
            store = "Android"
        if store:
            result.add(_normalize_segment_for_check(f"{store} / {channel}"))
    return result


def _normalize_segment_for_check(value: str) -> str:
    cleaned = str(value or "").strip().replace("／", "/")
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = cleaned.replace("Meta", "Facebook").replace("meta", "facebook")
    cleaned = cleaned.replace("Facebook", "facebook")
    return cleaned.lower()


def _check_adjust_creative_roi_consistency(
    output_dir: Path,
    report_date: date,
    text: str,
    source_name: str,
    issues: list[SelfCheckIssue],
) -> None:
    json_path = output_dir / f"adjust_creative_analysis_{report_date.strftime('%Y%m%d')}.json"
    if not json_path.exists():
        return
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        issues.append(
            SelfCheckIssue(
                "adjust_creative_json_invalid",
                source_name,
                "Adjust 素材分析 JSON 不是合法 JSON",
                str(json_path),
                "合法 JSON",
            )
        )
        return
    totals: dict[str, dict[str, float]] = {}
    for item in payload.get("all_items") or []:
        creative_id = str(item.get("creative_id") or "").strip()
        if not creative_id:
            continue
        spend = float(item.get("spend") or 0.0)
        revenue = float(item.get("revenue") or 0.0)
        bucket = totals.setdefault(creative_id, {"spend": 0.0, "revenue": 0.0})
        bucket["spend"] += spend
        bucket["revenue"] += revenue
    expected = {
        creative_id: values["revenue"] / values["spend"]
        for creative_id, values in totals.items()
        if values["spend"] > 0
    }
    for match in re.finditer(r"([0-9]{8,}) 当前素材代理ROI=([0-9]+(?:\.[0-9]+)?)", text):
        creative_id = match.group(1)
        displayed = float(match.group(2))
        if creative_id not in expected:
            continue
        target = round(expected[creative_id], 2)
        if abs(displayed - target) > 0.05:
            issues.append(
                SelfCheckIssue(
                    "adjust_creative_roi_mismatch",
                    source_name,
                    f"{creative_id} 周报素材代理ROI与 Adjust 素材分析不一致",
                    f"{displayed:.2f}",
                    f"{target:.2f}",
                )
            )


def _render_self_check_markdown(payload: dict) -> str:
    lines = [
        f"# 周报自检 | {payload['report_date']}",
        "",
        f"- 会议：{payload['meeting_name']}",
        f"- 状态：{'通过' if payload['passed'] else '失败'}",
        f"- 先看摘要卡：{payload['preview_paths']['summary_markdown']}",
        f"- 本地预览：{payload['preview_paths']['index_markdown']}",
        f"- JSON报告：self_check_{payload['report_date'].replace('-', '')}.json",
    ]
    action_notes = payload.get("action_refinement_notes") or []
    if action_notes:
        lines.extend(["", "## 动作替换说明", ""])
        lines.extend(f"- {note}" for note in action_notes)
    warnings = payload.get("warnings") or []
    creative_audit = payload.get("creative_attribution_audit") or {}
    if warnings or creative_audit:
        lines.extend(["", "## 数据可用性提示", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        readiness = creative_audit.get("readiness") or {}
        if readiness:
            lines.append(
                f"- Campaign级={'可用' if readiness.get('campaign_analysis_ready') else '不可用'} / "
                f"Adgroup级={'可用' if readiness.get('adgroup_analysis_ready') else '不可用'} / "
                f"Creative级={'可用' if readiness.get('creative_analysis_ready') else '部分可用'}"
            )
        summary_path = creative_audit.get("summary_path")
        if summary_path:
            lines.append(f"- 创意归因审计：{summary_path}")
    v25 = payload.get("v25_decision_loop") or {}
    if v25:
        lines.extend(["", "## V2.5 决策闭环", ""])
        lines.append(f"- 状态：{'通过' if v25.get('passed') else '失败'}")
        lines.append(f"- 决策引擎：{v25.get('decision_engine_json', '')}")
        lines.append(f"- 实验计划：{v25.get('experiment_plan_json', '')}")
        lines.append(f"- 动作反馈：{v25.get('action_feedback_json', '')}")
        summary = v25.get("summary") or {}
        if summary:
            lines.append(
                f"- 并行验证：决策 {summary.get('decision_count', 0)} 条；"
                f"扩量决策 {summary.get('scale_decision_count', 0)} 条；"
                f"实验 {summary.get('experiment_count', 0)} 条。"
            )
    issues = payload["issues"]
    if issues:
        lines.extend(["", "## 失败项", ""])
        for issue in issues:
            lines.append(
                f"- [{issue['code']}] {issue['source']} | {issue['message']} | 实际：{issue['actual']} | 预期：{issue['expected']}"
            )
    else:
        lines.extend(["", "## 结果", "", "- 所有关键检查均已通过。"])
    lines.append("")
    return "\n".join(lines)


def _check_v25_artifacts(output_dir: Path, report_date: date, issues: list[SelfCheckIssue]) -> dict:
    stamp = report_date.strftime("%Y%m%d")
    decision_path = output_dir / f"decision_engine_{stamp}.json"
    experiment_path = output_dir / f"experiment_plan_{stamp}.json"
    feedback_path = output_dir / f"action_feedback_{stamp}.json"
    payload = {
        "passed": True,
        "decision_engine_json": str(decision_path),
        "experiment_plan_json": str(experiment_path),
        "action_feedback_json": str(feedback_path),
        "summary": {},
    }

    decision_payload = _load_required_v25_json(decision_path, "decision_engine", issues)
    experiment_payload = _load_required_v25_json(experiment_path, "experiment_plan", issues)
    feedback_payload = _load_required_v25_json(feedback_path, "action_feedback", issues)
    if decision_payload is None or experiment_payload is None or feedback_payload is None:
        payload["passed"] = False
        return payload

    decisions = decision_payload.get("items") or []
    experiments = experiment_payload.get("experiments") or []
    scale_decisions = [item for item in decisions if item.get("decision") == "small_scale_up"]
    growth_experiments = [
        item
        for item in experiments
        if item.get("experiment_type") in {"budget_scale_test", "creative_copy_test"}
    ]
    if len(growth_experiments) < len(scale_decisions):
        issues.append(
            SelfCheckIssue(
                code="v25_scale_experiment_missing",
                source="v25_decision_loop",
                message="V2.5 扩量类决策缺少对应实验计划",
                actual=f"scale_decisions={len(scale_decisions)}, growth_experiments={len(growth_experiments)}",
                expected="每条 small_scale_up 决策至少有一个增长实验计划",
            )
        )
    for experiment in experiments:
        if not experiment.get("rollback_metrics"):
            issues.append(
                SelfCheckIssue(
                    code="v25_experiment_rollback_missing",
                    source=str(experiment.get("experiment_id") or "experiment_plan"),
                    message="V2.5 实验计划缺少回滚指标",
                    actual=json.dumps(experiment, ensure_ascii=False),
                    expected="rollback_metrics 非空",
                )
            )

    payload["summary"] = {
        "decision_count": len(decisions),
        "scale_decision_count": len(scale_decisions),
        "experiment_count": len(experiments),
        "feedback_count": len(feedback_payload.get("items") or []),
    }
    payload["passed"] = not any(issue.code.startswith("v25_") for issue in issues)
    return payload


def _load_required_v25_json(path: Path, source: str, issues: list[SelfCheckIssue]) -> dict | None:
    if not path.exists():
        issues.append(
            SelfCheckIssue(
                code="v25_artifact_missing",
                source=source,
                message="V2.5 必要附件缺失",
                actual=str(path),
                expected="文件存在",
            )
        )
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            SelfCheckIssue(
                code="v25_json_invalid",
                source=source,
                message="V2.5 附件不是合法 JSON",
                actual=f"{path}: {exc}",
                expected="合法 JSON",
            )
        )
        return None


def _build_creative_audit_warnings(payload: dict) -> list[str]:
    warnings: list[str] = []
    readiness = payload.get("readiness") or {}
    if readiness and not readiness.get("creative_analysis_ready"):
        for item in readiness.get("channel_details") or []:
            if item.get("ready"):
                continue
            note = str(item.get("note", "") or "")
            note = note.replace("Google creative field is partially generic; needs asset join", "Google 创意字段仍有部分是通用占位值，需补素材标识映射")
            note = note.replace("creative IDs look usable", "创意 ID 当前可直接使用")
            warnings.append(
                f"创意归因提示：{item.get('project', '')}/{item.get('store', '')}/{item.get('channel', '')} "
                f"创意级归因仍未完全可信，{note}"
            )
    for warning in payload.get("warnings") or []:
        normalized = str(warning or "")
        normalized = normalized.replace(
            "Google creative fields are not fully resolved to asset-level IDs. Current values include generic labels on part of spend.",
            "Google 创意字段还没有完全解析到素材 ID 层，当前仍有一部分花费落在通用占位值上。",
        )
        warnings.append(f"创意归因审计提示：{normalized}")
    return warnings


def _build_creative_source_readiness_warnings(payload: dict) -> list[str]:
    warnings: list[str] = []
    summary = payload.get("summary") or {}
    tecdo_formal = bool(summary.get("tecdo_is_formal_source"))
    if not summary.get("meta_can_run_now") and not tecdo_formal:
        missing = ", ".join(summary.get("meta_missing_env") or [])
        warnings.append(f"素材API提示：Facebook 官方素材接口当前未启用，缺少 {missing}")
    if summary.get("tecdo_can_run_now") and summary.get("tecdo_probe_has_rows") is False:
        warnings.append("素材API提示：TecDo 已授权，且 report/query 接口可调用；当前为空是因为服务商后台数据同步尚未完成，暂时不能作为可用素材数据源。")
    elif not summary.get("tecdo_can_run_now"):
        probe_message = str(summary.get("tecdo_probe_message") or "").strip()
        missing = ", ".join(summary.get("tecdo_missing_env") or [])
        if probe_message:
            warnings.append(f"素材API提示：TecDo 代理素材源当前不可用，原因：{probe_message}")
        elif missing:
            warnings.append(f"素材API提示：TecDo 代理素材源当前未启用，缺少 {missing}")
        else:
            warnings.append("素材API提示：TecDo 代理素材源当前未启用，且未返回可识别的失败原因。")
    if not summary.get("google_can_run_now") and not tecdo_formal:
        missing = ", ".join(summary.get("google_missing_env") or [])
        warnings.append(f"素材API提示：Google 官方素材接口当前未启用，缺少 {missing}")
    return warnings


def _build_google_creative_repair_warnings(payload: dict) -> list[str]:
    warnings: list[str] = []
    placeholder_share = float(payload.get("placeholder_cost_share") or 0.0)
    placeholder_cost = float(payload.get("placeholder_cost") or 0.0)
    if placeholder_share <= 0 or placeholder_cost <= 0:
        return warnings
    warnings.append(
        "Google素材修复提示："
        f"Google付费花费 {placeholder_share:.1%} 仍落在占位素材上，"
        "当前报表已具备 Google 素材修复链路；在 Google 官方素材接口未接通前，仍先按 source_id/adgroup_id/campaign_id 输出修复候选"
    )
    top_segments = payload.get("top_placeholder_segments") or []
    for item in top_segments[:3]:
        warnings.append(
            "Google代理素材候选："
            f"{item.get('project', '')}/{item.get('store', '')} | "
            f"source_id={item.get('source_id', '-') or '-'} | "
            f"source_name={item.get('source_name', '-') or '-'} | "
            f"spend={float(item.get('cost') or 0.0):.0f} | "
            f"gross_roi={float(item.get('gross_roi') or 0.0):.2f}"
        )
    return warnings


def _build_google_revenue_attribution_warnings(payload: dict) -> list[str]:
    warnings: list[str] = []
    if not payload or payload.get("passed"):
        return warnings
    summary = payload.get("summary") or {}
    zero_share = float(summary.get("zero_revenue_cost_share") or 0.0)
    zero_cost = float(summary.get("zero_revenue_cost") or 0.0)
    total_cost = float(summary.get("google_total_cost") or 0.0)
    warnings.append(
        "Google收入归因提示："
        f"Google本周有花费无收入花费 {zero_cost:.0f}/{total_cost:.0f}（{zero_share:.1%}），"
        "Google ROI 先作为归因复核优先级，不作为强停投依据。"
    )
    for item in (payload.get("zero_revenue_segments") or [])[:3]:
        warnings.append(
            "Google零收入复核候选："
            f"{item.get('project', '')}/{item.get('store', '')}/{item.get('country', '')} | "
            f"campaign={item.get('campaign', '-') or '-'} | "
            f"adgroup={item.get('adgroup_id', '-') or '-'} | "
            f"creative={item.get('creative_id', '-') or '-'} | "
            f"spend={float(item.get('cost') or 0.0):.0f}"
        )
    return warnings
