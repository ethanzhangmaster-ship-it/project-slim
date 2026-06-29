from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from market_ops.action_feedback import ActionFeedbackBuilder
from market_ops.action_layer import ActionLayerBuilder
from market_ops.ai_media_buyer_plan import AiMediaBuyerPlanBuilder
from market_ops.approval_feedback_gate import ApprovalFeedbackGateBuilder
from market_ops.discovery_action_queue import DiscoveryActionQueueBuilder
from market_ops.discovery_action_state_board import DiscoveryActionStateBoardBuilder
from market_ops.card_preview import CardPreviewPaths, render_card_preview_markdown, save_card_previews
from market_ops.causal_learning import CausalLearningBuilder
from market_ops.config import load_settings
from market_ops.adjust_creative_analysis import AdjustCreativeAnalysisBuilder
from market_ops.creative_clusters import CreativeClustersBuilder
from market_ops.creative_dna import CreativeDnaBuilder
from market_ops.creative_fatigue import CreativeFatigueBuilder
from market_ops.creative_action_thresholds import CreativeActionThresholdsBuilder
from market_ops.creative_attribution_audit import CreativeAttributionAuditBuilder
from market_ops.creative_source_readiness import CreativeSourceReadinessBuilder
from market_ops.data_quality_audit import DataQualityAuditBuilder
from market_ops.decision_engine import DecisionEngineBuilder
from market_ops.dynamic_payback import DynamicPaybackBuilder
from market_ops.discovery_engine import DiscoveryEngineBuilder
from market_ops.discovery_pattern_prior import DiscoveryPatternPriorBuilder
from market_ops.discovery_approval_packet import DiscoveryApprovalPacketBuilder
from market_ops.discovery_learning_state_board import DiscoveryLearningStateBoardBuilder
from market_ops.discovery_result_capture_packets import DiscoveryResultCapturePacketsBuilder
from market_ops.discovery_slot_operator_packet import DiscoverySlotOperatorPacketBuilder
from market_ops.discovery_slot_status_board import DiscoverySlotStatusBoardBuilder
from market_ops.discovery_unlock_operator_handoff import DiscoveryUnlockOperatorHandoffBuilder
from market_ops.discovery_unlock_sequence import DiscoveryUnlockSequenceBuilder
from market_ops.discovery_validator import DiscoveryValidator
from market_ops.closure_status import ClosureStatusBuilder
from market_ops.project_detail_coverage import ProjectDetailCoverageBuilder
from market_ops.p04_source_checklist import P04SourceChecklistBuilder
from market_ops.p04_mapping_verify import P04MappingVerifyBuilder
from market_ops.external_blockers import ExternalBlockersBuilder
from market_ops.detail_reply_checklist import DetailReplyChecklistBuilder
from market_ops.event_server import FeishuEventServer
from market_ops.experiment_execution_queue import ExperimentExecutionQueueBuilder
from market_ops.experiment_manager import ExperimentPlanBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder
from market_ops.google_creative_repair_audit import GoogleCreativeRepairAuditBuilder
from market_ops.google_revenue_attribution_audit import GoogleRevenueAttributionAuditBuilder
from market_ops.creative_loop_orchestrator import CreativeLoopOrchestrator
from market_ops.growth_priorities import GrowthPrioritiesBuilder
from market_ops.growth_playbook import GrowthPlaybookBuilder
from market_ops.group_approved_executor import execute_group_approved_tasks
from market_ops.group_send_log import GroupSendLog
from market_ops.guarded_execution import GuardedExecutionBuilder
from market_ops.growth_memory_store import GrowthMemoryStoreBuilder
from market_ops.health_check_report import HealthCheckReportBuilder
from market_ops.learning_evidence_queue import LearningEvidenceQueueBuilder
from market_ops.learning_memory import LearningMemoryBuilder
from market_ops.lifecycle_prediction import LifecyclePredictionBuilder
from market_ops.local_visual_assets import LocalVisualAssetManifestBuilder
from market_ops.management_action_list import ManagementActionListBuilder
from market_ops.manual_broadcast import send_market_all_cards, send_selected_cards
from market_ops.media_buyer_loop import MediaBuyerLoopBuilder
from market_ops.payback_targets import PaybackTargetsBuilder
from market_ops.pipeline import (
    DailySyncPipeline,
    ExecutiveReportPipeline,
    FeishuSourceSyncPipeline,
    ForecastValidationPipeline,
    MeetingApprovalPipeline,
    MeetingCloseoutPipeline,
    WeeklyBroadcastPipeline,
    WeeklyDigestPipeline,
    WeeklyPipeline,
)
from market_ops.platform_write_readiness import PlatformWriteReadinessBuilder
from market_ops.profitability_audit import ProfitabilityAuditBuilder
from market_ops.metric_reconciliation import WeeklyMetricReconciliationBuilder
from market_ops.pre_send_summary import PreSendSummaryBuilder
from market_ops.report_audit import ReportAuditBuilder
from market_ops.rollback_monitor import RollbackMonitorBuilder
from market_ops.self_check import run_self_check
from market_ops.strategy_context import StrategyContextBuilder
from market_ops.tecdo_account_reconciliation import TecDoAccountReconciliationBuilder
from market_ops.tecdo_probe import TecDoProbeBuilder
from market_ops.tecdo_sync_checklist import TecDoSyncChecklistBuilder
from market_ops.user_quality import UserQualityBuilder
from market_ops.visual_intelligence import VisualIntelligenceBuilder


def _boss_send_enabled(settings) -> bool:
    return bool(settings.allow_boss_send and (settings.feishu_boss_webhook or "").strip())


def _format_gate_blocked(overview_path: str, gate_path: str, audit_path: str) -> str:
    return f"发送已拦截。先看总览页：{overview_path} | 自检：{gate_path} | 审计：{audit_path}"


def _format_send_success(label: str, sent_items: list[str], overview_path: str) -> str:
    sent_text = "、".join(sent_items) if sent_items else "无"
    return f"{label}：{sent_text} | 先看总览页：{overview_path}"


def _format_report_success(label: str, overview_path: str) -> str:
    return f"{label} | 先看总览页：{overview_path}"


def _write_market_ops_status_snapshot(settings) -> Path:
    active_dir = settings.active_output_dir
    callback_json_path = active_dir / "feishu_callback_live.json"
    weekly_gate_path = active_dir / "weekly_release_gate_latest.md"
    observed_path = active_dir / "feishu_detail_chat_observations.json"

    callback_payload: dict = {}
    if callback_json_path.exists():
        try:
            callback_payload = json.loads(callback_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            callback_payload = {}

    gate_text = weekly_gate_path.read_text(encoding="utf-8") if weekly_gate_path.exists() else ""

    observed_payload: dict = {}
    if observed_path.exists():
        try:
            observed_payload = json.loads(observed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            observed_payload = {}
    observed_items = observed_payload.get("items") or []
    allowed_groups: list[str] = []
    configured_allowed_groups = [str(item).strip() for item in (settings.feishu_detail_allowed_chat_ids or []) if str(item).strip()]
    for chat_id in configured_allowed_groups:
        if chat_id not in allowed_groups:
            allowed_groups.append(chat_id)
    for item in observed_items:
        chat_id = str(item.get("chat_id") or "").strip()
        if not chat_id or not item.get("allowlisted") or chat_id in allowed_groups:
            continue
        allowed_groups.append(chat_id)

    payload = {
        "metrics_consistency_path": str(active_dir / "weekly_metrics_consistency_latest.md"),
        "callback_text_path": str(active_dir / "feishu_callback_live.txt"),
        "weekly_release_gate": "PASS" if "Status: PASS" in gate_text else "BLOCKED",
        "allowed_groups": allowed_groups,
        "callback_url": str(callback_payload.get("callback_url") or ""),
        "callback_json_path": str(callback_json_path),
        "startup_shortcut_installed": True,
        "allowed_group_count": len(allowed_groups),
        "weekly_gate_path": str(weekly_gate_path),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "callback_health": "OK" if callback_payload.get("callback_url") else "UNKNOWN",
    }
    status_path = active_dir / "market_ops_status_latest.json"
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = active_dir / "market_ops_status_latest.md"
    markdown_lines = [
        "# Market Ops Status",
        "",
        f"Generated at: {payload['generated_at']}",
        "",
        "Core status:",
        f"- callback health: {payload['callback_health']}",
        f"- callback url: {payload['callback_url']}",
        f"- startup shortcut installed: {payload['startup_shortcut_installed']}",
        f"- allowed group count: {payload['allowed_group_count']}",
        f"- weekly release gate: {payload['weekly_release_gate']}",
        "",
        "Artifacts:",
        f"- callback text: {payload['callback_text_path']}",
        f"- callback json: {payload['callback_json_path']}",
        f"- weekly gate: {payload['weekly_gate_path']}",
        f"- metrics consistency: {payload['metrics_consistency_path']}",
        "",
        "Allowed groups:",
    ]
    markdown_lines.extend(f"- {item}" for item in payload["allowed_groups"])
    markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    return status_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Market Ops workflow runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    weekly = subparsers.add_parser("weekly-run", help="Generate weekly report and draft actions")
    weekly.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    weekly.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")

    approve = subparsers.add_parser("approve-meeting-actions", help="Move pending meeting actions into execution")
    approve.add_argument("--report-date", required=True, help="Meeting date in YYYY-MM-DD format or latest")
    approve.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")

    closeout = subparsers.add_parser("meeting-closeout", help="Approve meeting actions and send the closeout summary")
    closeout.add_argument("--report-date", required=True, help="Meeting date in YYYY-MM-DD format or latest")
    closeout.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    closeout.add_argument("--no-send", action="store_true", help="Do not send the closeout card to Feishu")

    daily = subparsers.add_parser("daily-sync", help="Sync task statuses using the latest KPI signals")
    daily.add_argument("--as-of-date", required=True, help="Sync date in YYYY-MM-DD format")

    sync = subparsers.add_parser("sync-feishu-sources", help="Normalize the current Feishu sheets into internal CSV tables")
    sync.add_argument("--print-summary", action="store_true", help="Print row counts and latest date")

    digest = subparsers.add_parser("weekly-digest", help="Build the final weekly digest for the Feishu group")
    digest.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    digest.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    digest.add_argument("--send", action="store_true", help="Send the digest card to Feishu group webhook")
    digest.add_argument("--detailed", action="store_true", help="Send the detailed market version instead of the simple version")

    weekly_pack = subparsers.add_parser("weekly-pack", help="Build both the team digest and executive report together")
    weekly_pack.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    weekly_pack.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    weekly_pack.add_argument("--send", action="store_true", help="Send both cards to the Feishu group webhook")
    weekly_pack.add_argument("--detailed", action="store_true", help="Send the detailed market digest instead of the simple version")

    executive = subparsers.add_parser("executive-report", help="Build the management-facing executive report")
    executive.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    executive.add_argument("--period", choices=("weekly", "monthly"), default="weekly", help="Report cadence")
    executive.add_argument("--send", action="store_true", help="Send the executive report card to Feishu group webhook")

    validation = subparsers.add_parser("forecast-validation", help="Build the standalone forecast validation backtest report")
    validation.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    validation.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")

    audit = subparsers.add_parser("profitability-audit", help="Build profitability and paid-channel attribution audit tables")
    audit.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    creative_audit = subparsers.add_parser(
        "creative-attribution-audit",
        help="Audit Adjust campaign/adgroup/creative/source coverage and readiness",
    )
    creative_audit.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    adjust_creative = subparsers.add_parser(
        "adjust-creative-analysis",
        help="Build Adjust API creative-level analysis with sample gates and confidence labels",
    )
    adjust_creative.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    creative_source_readiness = subparsers.add_parser(
        "creative-source-readiness",
        help="Audit whether Meta and Google Ads creative API sources are runnable in the current environment",
    )
    creative_source_readiness.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    tecdo_probe = subparsers.add_parser(
        "tecdo-probe",
        help="Probe TecDo account/platform access without running the full weekly report flow",
    )
    tecdo_probe.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    tecdo_account_reconciliation = subparsers.add_parser(
        "tecdo-account-reconciliation",
        help="Build a TecDo account reconciliation report with real account info and recent report-row coverage",
    )
    tecdo_account_reconciliation.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    tecdo_account_reconciliation.add_argument("--lookback-days", type=int, default=180, help="How many recent days to inspect for report-row coverage")

    google_creative_repair = subparsers.add_parser(
        "google-creative-repair-audit",
        help="Audit Google Adjust creative placeholders and produce a repair join checklist",
    )
    google_creative_repair.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    google_revenue_attribution = subparsers.add_parser(
        "google-revenue-attribution-audit",
        help="Audit Google paid segments with zero attributed revenue and produce a reconciliation checklist",
    )
    google_revenue_attribution.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    payback_targets = subparsers.add_parser("payback-targets", help="Build historical payback target thresholds by project")
    payback_targets.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    growth_priorities = subparsers.add_parser(
        "growth-priorities",
        help="Build growth priority ranking with local breakthrough candidates",
    )
    growth_priorities.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    creative_loop = subparsers.add_parser(
        "creative-loop",
        help="Run the end-to-end creative closed loop: discover winners → extract patterns → generate variants → feedback learning",
    )
    creative_loop.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    creative_loop.add_argument("--max-winners", type=int, default=5, help="Maximum winner creatives to analyze (default: 5)")
    creative_loop.add_argument("--max-variants", type=int, default=10, help="Maximum variant suggestions to generate (default: 10)")

    creative_dna = subparsers.add_parser(
        "creative-dna",
        help="Build creative DNA labels from existing creative names, campaign names, and optional manual labels",
    )
    creative_dna.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    creative_clusters = subparsers.add_parser(
        "creative-clusters",
        help="Build creative pattern clusters from creative DNA and performance",
    )
    creative_clusters.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    visual_intelligence = subparsers.add_parser(
        "visual-intelligence",
        help="Audit whether creative intelligence has true visual assets or only proxy labels",
    )
    visual_intelligence.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    local_visual_assets = subparsers.add_parser(
        "local-visual-assets",
        help="Scan configured local material folders and build a real visual-asset manifest",
    )
    local_visual_assets.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    creative_fatigue = subparsers.add_parser(
        "creative-fatigue",
        help="Detect creative fatigue using available 14-day CTR/CPI/ROI/spend trends",
    )
    creative_fatigue.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    dynamic_payback = subparsers.add_parser(
        "dynamic-payback",
        help="Build dynamic D7/D30 payback references with current user quality signals",
    )
    dynamic_payback.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    user_quality = subparsers.add_parser(
        "user-quality",
        help="Build standalone user quality signals from CPI, retention, ARPU/ARPPU, and payback",
    )
    user_quality.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    lifecycle_prediction = subparsers.add_parser(
        "lifecycle-prediction",
        help="Build lifecycle stage and growth-potential prediction signals from payback, quality, creative, and fatigue layers",
    )
    lifecycle_prediction.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    strategy_context = subparsers.add_parser(
        "strategy-context",
        help="Build the human-owned strategy context signal for AI Media Buyer prioritization",
    )
    strategy_context.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    ai_media_buyer_plan = subparsers.add_parser(
        "ai-media-buyer-plan",
        help="Build advisory AI Media Buyer actions from growth, creative, fatigue, and dynamic payback outputs",
    )
    ai_media_buyer_plan.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    action_layer = subparsers.add_parser(
        "action-layer",
        help="Build dry-run execution intents with approval gates and blocked reasons",
    )
    action_layer.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    platform_write_readiness = subparsers.add_parser(
        "platform-write-readiness",
        help="Build platform write readiness and safety-gate status for future execution connectors",
    )
    platform_write_readiness.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    guarded_execution = subparsers.add_parser(
        "guarded-execution",
        help="Build guarded dry-run execution attempts from Action Layer intents",
    )
    guarded_execution.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    rollback_monitor = subparsers.add_parser(
        "rollback-monitor",
        help="Build rollback monitoring signals for executed media-buyer actions",
    )
    rollback_monitor.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_engine = subparsers.add_parser(
        "discovery-engine",
        help="Build Discovery Engine MVP outputs for new-product exploration",
    )
    discovery_engine.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery = subparsers.add_parser(
        "discovery",
        help="Alias for discovery-engine: Build Discovery Engine MVP outputs",
    )
    discovery.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_validate = subparsers.add_parser(
        "discovery-validate",
        help="Run closed-loop validation: experiment results → hypothesis verdicts → feedback",
    )
    discovery_validate.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    discovery_validate.add_argument(
        "--min-sample-size",
        type=int,
        default=100,
        help="Minimum sample (impressions) required for a conclusive verdict (default 100)",
    )
    discovery_validate.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.95,
        help="Normalized confidence threshold for confirmed/rejected verdict (default 0.95)",
    )

    creative_publish = subparsers.add_parser(
        "creative-publish",
        help="Publish generated images to Facebook Ads: upload → create creatives → create ads",
    )
    creative_publish.add_argument("--image-dir", required=True, help="Directory containing generated PNG images")
    creative_publish.add_argument("--access-token", required=True, help="Facebook access token")
    creative_publish.add_argument("--ad-account-id", required=True, help="Facebook ad account ID (e.g. act_123456)")
    creative_publish.add_argument("--adset-id", required=True, help="Facebook adset ID to create ads under")
    creative_publish.add_argument("--page-id", default="", help="Facebook page ID")
    creative_publish.add_argument("--api-version", default="v22.0", help="Facebook API version")
    creative_publish.add_argument("--headline", default="Play Now!", help="Ad headline")
    creative_publish.add_argument("--primary-text", default="", help="Ad primary text")
    creative_publish.add_argument("--auto-activate", action="store_true", help="Set ads to ACTIVE instead of PAUSED")

    creative_daily = subparsers.add_parser(
        "creative-daily",
        help="Run full creative daily loop: collect → generate → publish (requires config JSON)",
    )
    creative_daily.add_argument("--config", required=True, help="Path to JSON config file with campaign and auto_publish settings")
    creative_daily.add_argument("--output-dir", default="output/creative_growth_loop", help="Output directory")
    creative_daily.add_argument("--generations", type=int, default=3, help="Number of generations")

    decision_engine = subparsers.add_parser(
        "decision-engine",
        help="Build V2.5 parallel-validation unified decision engine output",
    )
    decision_engine.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    experiment_plan = subparsers.add_parser(
        "experiment-plan",
        help="Build V2.5 experiment and rollback plans from decision-engine output",
    )
    experiment_plan.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    action_feedback = subparsers.add_parser(
        "action-feedback",
        help="Build V2.5 action feedback records from the current action tracker",
    )
    action_feedback.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    learning_memory = subparsers.add_parser(
        "learning-memory",
        help="Build non-mutating growth learning memory from action outcomes and missing outcome fields",
    )
    learning_memory.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    growth_memory_store = subparsers.add_parser(
        "growth-memory-store",
        help="Build the long-term growth memory ledger from all available learning-memory artifacts",
    )
    growth_memory_store.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    growth_playbook = subparsers.add_parser(
        "growth-playbook",
        help="Build reusable decision rules from validated or invalidated causal learning",
    )
    growth_playbook.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    learning_evidence_queue = subparsers.add_parser(
        "learning-evidence-queue",
        help="Build prioritized missing-evidence queue for playbook candidate rules",
    )
    learning_evidence_queue.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_result_capture_packets = subparsers.add_parser(
        "discovery-result-capture-packets",
        help="Build slot-level result capture packets for discovery experiments",
    )
    discovery_result_capture_packets.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_experiment_cards = subparsers.add_parser(
        "discovery-experiment-cards",
        help="Build operator-facing discovery experiment cards",
    )
    discovery_experiment_cards.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_test_plans = subparsers.add_parser(
        "discovery-test-plans",
        help="Build structured discovery variant-slot plans",
    )
    discovery_test_plans.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_execution_packets = subparsers.add_parser(
        "discovery-execution-packets",
        help="Build slot-level discovery execution packets",
    )
    discovery_execution_packets.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_learning_packets = subparsers.add_parser(
        "discovery-learning-packets",
        help="Build discovery learning packets that bind slots to learning questions",
    )
    discovery_learning_packets.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_pattern_prior = subparsers.add_parser(
        "discovery-pattern-prior",
        help="Build signal-only discovery pattern priors from active slot-pattern candidates",
    )
    discovery_pattern_prior.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_learning_state_board = subparsers.add_parser(
        "discovery-learning-state-board",
        help="Build a discovery learning state board from approval, execution, and result evidence",
    )
    discovery_learning_state_board.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_slot_status_board = subparsers.add_parser(
        "discovery-slot-status-board",
        help="Build an operator-facing status board for discovery slot execution and learning",
    )
    discovery_slot_status_board.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_slot_operator_packet = subparsers.add_parser(
        "discovery-slot-operator-packet",
        help="Build a guided operator packet for discovery slot execution and result capture",
    )
    discovery_slot_operator_packet.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_unlock_sequence = subparsers.add_parser(
        "discovery-unlock-sequence",
        help="Build a ranked discovery unlock sequence from approval and slot evidence",
    )
    discovery_unlock_sequence.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_unlock_operator_handoff = subparsers.add_parser(
        "discovery-unlock-operator-handoff",
        help="Build an operator-facing handoff from discovery unlock ranking to exact manual work order",
    )
    discovery_unlock_operator_handoff.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_action_queue = subparsers.add_parser(
        "discovery-action-queue",
        help="Build a standardized manual action queue for discovery approval, variant creation, and result capture",
    )
    discovery_action_queue.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_action_state_board = subparsers.add_parser(
        "discovery-action-state-board",
        help="Build a state board that tracks each discovery action from approval to learning closure",
    )
    discovery_action_state_board.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    discovery_approval_packet = subparsers.add_parser(
        "discovery-approval-packet",
        help="Build a discovery-specific approval packet for manual setup and slot execution",
    )
    discovery_approval_packet.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    causal_learning = subparsers.add_parser(
        "causal-learning",
        help="Build the Causal Learning Layer hypothesis ledger from experiments, decisions, and learning outcomes",
    )
    causal_learning.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    experiment_execution_queue = subparsers.add_parser(
        "experiment-execution-queue",
        help="Build a dry-run experiment execution and result-capture queue",
    )
    experiment_execution_queue.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    approval_feedback_gate = subparsers.add_parser(
        "approval-feedback-gate",
        help="Build approval and result-capture requirements for media-buyer experiments",
    )
    approval_feedback_gate.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    experiment_result_ingestion = subparsers.add_parser(
        "experiment-result-ingestion",
        help="Build experiment result templates and ingest manual result evidence when present",
    )
    experiment_result_ingestion.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    v25_decision_loop = subparsers.add_parser(
        "v25-decision-loop",
        help="Build V2.5 decision engine, experiment plan, and action feedback together",
    )
    v25_decision_loop.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    media_buyer_loop = subparsers.add_parser(
        "media-buyer-loop",
        help="Build the top-level AI Media Buyer loop ledger from signals, decisions, experiments, and feedback",
    )
    media_buyer_loop.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    media_buyer_loop.add_argument("--force", action="store_true", help="Rebuild all child AI Media Buyer artifacts before composing the loop")

    reconciliation = subparsers.add_parser("metric-reconciliation", help="Build a weekly metric reconciliation report for published digest numbers")
    reconciliation.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    pre_send = subparsers.add_parser("pre-send-summary", help="Build a one-page send recommendation summary from self-check, audit, and reconciliation outputs")
    pre_send.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    creative_thresholds = subparsers.add_parser("creative-action-thresholds", help="Build creative action threshold recommendation report")
    creative_thresholds.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    data_quality = subparsers.add_parser("data-quality-audit", help="Build data quality audit for decision confidence")
    data_quality.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    report_audit = subparsers.add_parser("report-audit", help="Audit local and Feishu report/tracker records plus self-check gate")
    report_audit.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    report_audit.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")

    preview = subparsers.add_parser("card-preview", help="Build local Feishu card previews without sending")
    preview.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    preview.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    preview.add_argument("--refresh", action="store_true", help="Force rebuild local previews instead of reusing cached files")

    approved_execute = subparsers.add_parser(
        "group-approved-execute",
        help="Execute approved group requirements by regenerating the relevant local previews and closing the queue items",
    )
    approved_execute.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    approved_execute.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    approved_execute.add_argument("--chat-id", default="", help="Only execute approved tasks from this chat_id")
    approved_execute.add_argument(
        "--request-id",
        action="append",
        default=[],
        help="Only execute the specified approved request id. Can be repeated.",
    )

    card_send = subparsers.add_parser("card-send", help="Send selected Feishu cards only after explicit confirmation")
    card_send.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    card_send.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    card_send.add_argument("--boss", action="store_true", help="Send boss version")
    card_send.add_argument("--market", action="store_true", help="Send market version")
    card_send.add_argument("--market-detailed", action="store_true", help="Send detailed market version instead of simple version")
    card_send.add_argument("--no-recovery", action="store_true", help="Do not send the recovery card")
    card_send.add_argument("--boss-webhook", default=None, help="Override boss webhook for this send")
    card_send.add_argument("--market-webhook", default=None, help="Override market webhook for this send")

    market_send = subparsers.add_parser("market-send", help="Send market version to the test group only")
    market_send.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    market_send.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    market_send.add_argument("--detailed", action="store_true", help="Send the detailed market version instead of the simple version")
    market_send.add_argument("--all", action="store_true", help="Send simple market, detailed market, and recovery cards")
    market_send.add_argument("--no-recovery", action="store_true", help="Do not send the recovery card")

    event_server = subparsers.add_parser(
        "feishu-event-server",
        help="Run a Feishu callback server that replies with the detailed market version when the bot is mentioned.",
    )
    event_server.add_argument("--host", default="0.0.0.0", help="Host to bind")
    event_server.add_argument("--port", type=int, default=8080, help="Port to bind")
    event_server.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    event_server.add_argument(
        "--report-date",
        default="latest",
        help="Use a fixed report date in YYYY-MM-DD format, or latest to follow the most recent synced week",
    )

    simulate = subparsers.add_parser(
        "feishu-event-simulate",
        help="Simulate a Feishu @bot message locally and show whether the detailed reply would send.",
    )
    simulate.add_argument("--report-date", default="latest", help="Report date in YYYY-MM-DD format or latest")
    simulate.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    simulate.add_argument("--chat-id", default="chat-test", help="Chat ID to simulate")
    simulate.add_argument("--message-id", default="msg-local-test", help="Message ID to simulate")
    simulate.add_argument("--text", default="@机器人 详细版", help="Message text to simulate")
    simulate.add_argument("--force-allow", action="store_true", help="Bypass allowlist safe mode for local simulation only")

    event_check = subparsers.add_parser(
        "feishu-event-check",
        help="Check whether Feishu event callback settings are ready for go-live.",
    )
    event_check.add_argument(
        "--public-base-url",
        default="",
        help="Optional public base URL, for example https://your-domain.com",
    )

    event_allowlist = subparsers.add_parser(
        "feishu-event-allowlist-suggest",
        help="Suggest FEISHU_DETAIL_ALLOWED_CHAT_IDS from observed detailed-reply chats.",
    )
    event_allowlist.add_argument(
        "--top",
        type=int,
        default=3,
        help="How many most recent observed chat_ids to include in the suggestion",
    )

    event_allowlist_apply = subparsers.add_parser(
        "feishu-event-allowlist-apply",
        help="Write real observed oc_ chat_ids back into .env as FEISHU_DETAIL_ALLOWED_CHAT_IDS.",
    )
    event_allowlist_apply.add_argument(
        "--top",
        type=int,
        default=1,
        help="How many real observed chat_ids to write into .env",
    )
    event_allowlist_apply.add_argument(
        "--chat-id",
        action="append",
        default=[],
        help="Explicit real Feishu group chat_id to write, for example oc_xxx. Can be repeated.",
    )

    health_check = subparsers.add_parser(
        "health-check",
        help="Run a one-shot weekly health check for preview, audit, summary, and event reply readiness.",
    )
    health_check.add_argument("--report-date", default="latest", help="Report date in YYYY-MM-DD format or latest")
    health_check.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    health_check.add_argument("--chat-id", default="chat-test", help="Chat ID to simulate for event reply")
    health_check.add_argument("--message-id", default="msg-health-check", help="Message ID to simulate for event reply")
    health_check.add_argument("--text", default="@机器人 详细版", help="Message text to simulate")
    health_check.add_argument(
        "--public-base-url",
        default="",
        help="Optional public base URL, for example https://your-domain.com",
    )

    status_refresh = subparsers.add_parser(
        "status-refresh",
        help="Force rebuild market_ops_status_latest json and markdown from current active artifacts.",
    )

    send_log_cleanup = subparsers.add_parser(
        "group-send-log-cleanup",
        help="Remove local test send-log entries and keep only real group send history.",
    )

    closure_status = subparsers.add_parser(
        "closure-status",
        help="Build a single closure ledger that shows what is ready, pending, or blocked in the weekly delivery chain.",
    )
    closure_status.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    management_action_list = subparsers.add_parser(
        "management-action-list",
        help="Build a management-ready action ledger from the weekly profitability breakdown.",
    )
    management_action_list.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    project_detail_coverage = subparsers.add_parser(
        "project-detail-coverage",
        help="Audit which projects really have trusted project-level detail coverage in the current weekly window.",
    )
    project_detail_coverage.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    p04_source_checklist = subparsers.add_parser(
        "p04-source-checklist",
        help="Build a concrete checklist for fixing the missing P04 project-level Feishu source mapping.",
    )
    p04_source_checklist.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    detail_reply_checklist = subparsers.add_parser(
        "detail-reply-checklist",
        help="Build a concrete checklist for locking the detailed reply to real Feishu group chat_ids.",
    )
    detail_reply_checklist.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    tecdo_sync_checklist = subparsers.add_parser(
        "tecdo-sync-checklist",
        help="Build a concrete checklist for the current TecDo sync-pending state and retest steps.",
    )
    tecdo_sync_checklist.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    external_blockers = subparsers.add_parser(
        "external-blockers",
        help="Build one consolidated checklist for all remaining external blockers.",
    )
    external_blockers.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    p04_verify_after_mapping = subparsers.add_parser(
        "p04-verify-after-mapping",
        help="After filling P04 mapping, rerun Feishu sync and verify whether P04 becomes trusted.",
    )
    p04_verify_after_mapping.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")

    bitable_sync = subparsers.add_parser(
        "bitable-sync",
        help="Sync weekly report data to Feishu Bitable tables and generate HTML chart report.",
    )
    bitable_sync.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format or latest")
    bitable_sync.add_argument("--meeting-name", default="Weekly Market Ops Review", help="Meeting title")
    bitable_sync.add_argument("--html-only", action="store_true", help="Only generate HTML chart report, skip Bitable write")
    bitable_sync.add_argument("--bitable-only", action="store_true", help="Only write to Bitable, skip HTML report")

    return parser


def _resolve_report_date(settings, raw_value: str) -> datetime.date:
    if raw_value != "latest":
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    pipeline = WeeklyPipeline(settings)
    ads_rows = pipeline._repository.load_ads_performance()
    return max(row.date for row in ads_rows)


def _align_weekly_report_date(report_date: datetime.date) -> datetime.date:
    wednesday = 2
    days_since_wednesday = (report_date.weekday() - wednesday) % 7
    return report_date - timedelta(days=days_since_wednesday)


def _run_send_gate(settings, report_date: datetime.date, meeting_name: str):
    cached = _load_cached_send_gate(settings, report_date)
    if cached is not None:
        print(f"自检门禁已复用：{cached.markdown_path}")
        return cached
    return run_self_check(
        report_date=report_date,
        meeting_name=meeting_name,
        output_dir=settings.active_output_dir,
    )


def _load_cached_send_gate(settings, report_date: datetime.date):
    suffix = report_date.strftime("%Y%m%d")
    active = settings.active_output_dir
    json_path = active / f"self_check_{suffix}.json"
    markdown_path = active / f"self_check_{suffix}.md"
    payload = _load_json_if_readable(json_path)
    if not payload or not payload.get("passed") or not markdown_path.exists():
        return None
    if str(payload.get("report_date") or "") != report_date.isoformat():
        return None
    v25 = payload.get("v25_decision_loop") or {}
    if not v25.get("passed"):
        return None
    if not _cached_v25_paths_ready(settings, report_date):
        return None

    preview_paths_payload = payload.get("preview_paths") or {}
    try:
        preview_paths = CardPreviewPaths(
            overview_markdown=Path(preview_paths_payload["overview_markdown"]),
            summary_markdown=Path(preview_paths_payload["summary_markdown"]),
            summary_json=Path(preview_paths_payload["summary_json"]),
            boss_markdown=Path(preview_paths_payload["boss_markdown"]),
            boss_json=Path(preview_paths_payload["boss_json"]),
            market_markdown=Path(preview_paths_payload["market_markdown"]),
            market_json=Path(preview_paths_payload["market_json"]),
            market_detail_markdown=Path(preview_paths_payload["market_detail_markdown"]),
            market_detail_json=Path(preview_paths_payload["market_detail_json"]),
            recovery_markdown=Path(preview_paths_payload["recovery_markdown"]),
            recovery_json=Path(preview_paths_payload["recovery_json"]),
            index_markdown=Path(preview_paths_payload["index_markdown"]),
        )
    except KeyError:
        return None
    preview_files = [
        preview_paths.overview_markdown,
        preview_paths.summary_markdown,
        preview_paths.summary_json,
        preview_paths.boss_markdown,
        preview_paths.boss_json,
        preview_paths.market_markdown,
        preview_paths.market_json,
        preview_paths.market_detail_markdown,
        preview_paths.market_detail_json,
        preview_paths.recovery_markdown,
        preview_paths.recovery_json,
        preview_paths.index_markdown,
    ]
    if not all(path.exists() for path in preview_files):
        return None

    issues = [
        SimpleNamespace(
            code=str(item.get("code", "")),
            source=str(item.get("source", "")),
            message=str(item.get("message", "")),
            actual=str(item.get("actual", "")),
            expected=str(item.get("expected", "")),
        )
        for item in (payload.get("issues") or [])
        if isinstance(item, dict)
    ]
    warnings = [str(item) for item in (payload.get("warnings") or [])]
    return SimpleNamespace(
        passed=True,
        issues=issues,
        warnings=warnings,
        preview_paths=preview_paths,
        markdown_path=markdown_path,
        json_path=json_path,
    )


def _refresh_bottom_layer(settings, report_date: datetime.date, meeting_name: str) -> None:
    if _reuse_bottom_layer_cache(settings, report_date):
        return
    WeeklyPipeline(settings).run(report_date=report_date, meeting_name=meeting_name, writeback=True)
    AdjustCreativeAnalysisBuilder(settings).build(report_date=report_date)
    DiscoveryEngineBuilder(settings).build(report_date=report_date)
    GrowthPrioritiesBuilder(settings).build(report_date=report_date)
    _refresh_v2_growth_layers(settings, report_date)
    _run_v25_decision_loop(settings, report_date)


def _refresh_v2_growth_layers(settings, report_date: datetime.date) -> None:
    CreativeDnaBuilder(settings).build(report_date=report_date)
    CreativeClustersBuilder(settings).build(report_date=report_date)
    CreativeFatigueBuilder(settings).build(report_date=report_date)
    DynamicPaybackBuilder(settings).build(report_date=report_date)
    AiMediaBuyerPlanBuilder(settings).build(report_date=report_date)


def _run_v25_decision_loop(settings, report_date: datetime.date):
    decision_result = DecisionEngineBuilder(settings).build(report_date=report_date)
    experiment_result = ExperimentPlanBuilder(settings).build(report_date=report_date)
    feedback_result = ActionFeedbackBuilder(settings).build(report_date=report_date)
    return decision_result, experiment_result, feedback_result


def _reuse_bottom_layer_cache(settings, report_date: datetime.date) -> bool:
    paths = _cached_bottom_layer_paths(settings, report_date)
    missing = [path for path in paths if not path.exists()]
    if missing:
        return False
    unreadable = [path for path in paths if path.suffix == ".json" and not _json_file_readable(path)]
    if unreadable:
        return False
    print(f"底层分析已复用：{report_date.isoformat()} | V2.5 决策闭环并行验证已生成")
    return True


def _cached_bottom_layer_paths(settings, report_date: datetime.date) -> list[Path]:
    suffix = report_date.strftime("%Y%m%d")
    active = settings.active_output_dir
    names = [
        f"weekly_report_{suffix}.md",
        f"adjust_creative_analysis_{suffix}.md",
        f"adjust_creative_analysis_{suffix}.json",
        f"adjust_creative_analysis_{suffix}.csv",
        f"discovery_engine_{suffix}.md",
        f"discovery_engine_{suffix}.json",
        f"growth_priorities_{suffix}.md",
        f"growth_priorities_{suffix}.json",
        f"growth_priorities_{suffix}.csv",
        f"creative_dna_{suffix}.md",
        f"creative_dna_{suffix}.json",
        f"creative_dna_{suffix}.csv",
        f"creative_clusters_{suffix}.md",
        f"creative_clusters_{suffix}.json",
        f"creative_clusters_{suffix}.csv",
        f"creative_fatigue_{suffix}.md",
        f"creative_fatigue_{suffix}.json",
        f"creative_fatigue_{suffix}.csv",
        f"dynamic_payback_{suffix}.md",
        f"dynamic_payback_{suffix}.json",
        f"dynamic_payback_{suffix}.csv",
        f"ai_media_buyer_plan_{suffix}.md",
        f"ai_media_buyer_plan_{suffix}.json",
        f"ai_media_buyer_plan_{suffix}.csv",
        f"decision_engine_{suffix}.md",
        f"decision_engine_{suffix}.json",
        f"decision_engine_{suffix}.csv",
        f"experiment_plan_{suffix}.md",
        f"experiment_plan_{suffix}.json",
        f"action_feedback_{suffix}.md",
        f"action_feedback_{suffix}.json",
    ]
    return [active / name for name in names]


def _json_file_readable(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def _load_json_if_readable(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _cached_v25_paths_ready(settings, report_date: datetime.date) -> bool:
    suffix = report_date.strftime("%Y%m%d")
    active = settings.active_output_dir
    paths = [
        active / f"decision_engine_{suffix}.json",
        active / f"decision_engine_{suffix}.md",
        active / f"decision_engine_{suffix}.csv",
        active / f"experiment_plan_{suffix}.json",
        active / f"experiment_plan_{suffix}.md",
        active / f"action_feedback_{suffix}.json",
        active / f"action_feedback_{suffix}.md",
    ]
    if not all(path.exists() for path in paths):
        return False
    return all(_json_file_readable(path) for path in paths if path.suffix == ".json")


def _weekly_pack_outputs_ready(settings, report_date: datetime.date) -> bool:
    suffix = report_date.strftime("%Y%m%d")
    active = settings.active_output_dir
    paths = [
        active / f"weekly_digest_{suffix}.md",
        active / f"executive_report_weekly_{suffix}.md",
        active / f"weekly_preview_overview_{suffix}.md",
        active / f"card_preview_summary_{suffix}.json",
        active / f"card_preview_summary_{suffix}.md",
        active / f"card_preview_boss_{suffix}.json",
        active / f"card_preview_boss_{suffix}.md",
        active / f"card_preview_market_{suffix}.json",
        active / f"card_preview_market_{suffix}.md",
        active / f"card_preview_market_detail_{suffix}.json",
        active / f"card_preview_market_detail_{suffix}.md",
        active / f"card_preview_recovery_{suffix}.json",
        active / f"card_preview_recovery_{suffix}.md",
        active / f"card_preview_index_{suffix}.md",
        active / f"self_check_{suffix}.json",
        active / f"self_check_{suffix}.md",
    ]
    if not all(path.exists() for path in paths):
        return False
    if not all(_json_file_readable(path) for path in paths if path.suffix == ".json"):
        return False
    return _cached_v25_paths_ready(settings, report_date)


def _run_report_audit(settings, report_date: datetime.date, meeting_name: str, *, self_check_result=None):
    builder = ReportAuditBuilder(settings)
    paths = builder.build(
        report_date=report_date,
        meeting_name=meeting_name,
        self_check_result=self_check_result,
    )
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    return payload, paths


def _run_pre_send_summary(settings, report_date: datetime.date):
    DataQualityAuditBuilder(settings).build(report_date=report_date)
    return PreSendSummaryBuilder(settings).build(report_date=report_date)


def _cached_card_preview_paths(settings, report_date: datetime.date) -> list[Path]:
    suffix = report_date.strftime("%Y%m%d")
    active = settings.active_output_dir
    names = [
        f"weekly_preview_overview_{suffix}.md",
        f"card_preview_summary_{suffix}.md",
        f"card_preview_summary_{suffix}.json",
        f"card_preview_boss_{suffix}.md",
        f"card_preview_boss_{suffix}.json",
        f"card_preview_market_{suffix}.md",
        f"card_preview_market_{suffix}.json",
        f"card_preview_market_detail_{suffix}.md",
        f"card_preview_market_detail_{suffix}.json",
        f"card_preview_recovery_{suffix}.md",
        f"card_preview_recovery_{suffix}.json",
        f"card_preview_index_{suffix}.md",
        f"self_check_{suffix}.json",
        f"self_check_{suffix}.md",
        f"report_audit_{suffix}.json",
        f"report_audit_{suffix}.md",
        f"pre_send_summary_{suffix}.json",
        f"pre_send_summary_{suffix}.md",
        f"weekly_health_check_{suffix}.json",
        f"weekly_health_check_{suffix}.md",
        f"growth_priorities_{suffix}.json",
        f"growth_priorities_{suffix}.md",
    ]
    return [active / name for name in names]


def _reuse_card_preview_cache(settings, report_date: datetime.date) -> bool:
    if not all(path.exists() for path in _cached_card_preview_paths(settings, report_date)):
        return False
    suffix = report_date.strftime("%Y%m%d")
    overview = settings.active_output_dir / f"weekly_preview_overview_{suffix}.md"
    health = settings.active_output_dir / f"weekly_health_check_{suffix}.md"
    print(f"预览复用已有结果：{overview}")
    print(f"- 健康检查：{health}")
    print("- 如需强制重新生成，请加 --refresh。")
    return True


def _cached_preview_support_paths(settings, report_date: datetime.date) -> dict[str, Path]:
    suffix = report_date.strftime("%Y%m%d")
    active = settings.active_output_dir
    return {
        "audit_json": active / f"report_audit_{suffix}.json",
        "audit_markdown": active / f"report_audit_{suffix}.md",
        "pre_send_json": active / f"pre_send_summary_{suffix}.json",
        "pre_send_markdown": active / f"pre_send_summary_{suffix}.md",
        "health_json": active / f"weekly_health_check_{suffix}.json",
        "health_markdown": active / f"weekly_health_check_{suffix}.md",
    }


def _reuse_preview_support_after_refresh(settings, report_date: datetime.date, overview_path: Path) -> bool:
    paths = _cached_preview_support_paths(settings, report_date)
    if not all(path.exists() for path in paths.values()):
        return False
    print(f"预览已刷新：{overview_path}")
    print(f"- 审计复用：{paths['audit_markdown']}")
    print(f"- 发前结论复用：{paths['pre_send_markdown']}")
    print(f"- 健康检查复用：{paths['health_markdown']}")
    print("- 本命令未发送飞书，也未执行预算或广告平台写操作。")
    return True


def _run_p04_verify_after_mapping(settings, report_date: datetime.date) -> None:
    report_date = _align_weekly_report_date(report_date)
    sync_summary = FeishuSourceSyncPipeline(settings).run()
    coverage_result = ProjectDetailCoverageBuilder(settings).build(report_date=report_date)
    checklist_result = P04SourceChecklistBuilder(settings).build(report_date=report_date)

    coverage_payload = {}
    try:
        coverage_payload = json.loads(coverage_result.json_path.read_text(encoding="utf-8"))
    except Exception:
        coverage_payload = {}
    p04_row = next(
        (row for row in (coverage_payload.get("rows") or []) if str(row.get("project_key") or "") == "P04"),
        {},
    )
    verify_result = P04MappingVerifyBuilder(settings).build(report_date, sync_summary, coverage_payload)
    print("P04 mapping verify completed:")
    print(f"- sync summary: {sync_summary}")
    print(f"- coverage markdown: {coverage_result.markdown_path}")
    print(f"- checklist markdown: {checklist_result.markdown_path}")
    print(f"- verify markdown: {verify_result.markdown_path}")
    print(f"- verify json: {verify_result.json_path}")
    print(f"- P04 status: {p04_row.get('status', 'unknown')}")
    print(f"- P04 trusted: {p04_row.get('trusted', False)}")
    print(f"- P04 detail rows: {p04_row.get('detail_row_count', 0)}")
    print(f"- P04 next action: {p04_row.get('next_action', '')}")


def _sync_summary_preview_from_pre_send(gate_result, pre_send_result) -> None:
    if gate_result is None or pre_send_result is None:
        return
    try:
        summary_payload = json.loads(pre_send_result.json_path.read_text(encoding="utf-8"))
        summary_card = PreSendSummaryBuilder.build_card(summary_payload)
        gate_result.preview_paths.summary_json.write_text(
            json.dumps(summary_card, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        gate_result.preview_paths.summary_markdown.write_text(
            render_card_preview_markdown(summary_card),
            encoding="utf-8",
        )
    except Exception:
        return


def _send_gate_passed(gate_result, audit_payload, pre_send_result) -> bool:
    return (
        bool(gate_result and gate_result.passed)
        and bool(audit_payload and audit_payload.get("passed"))
        and bool(pre_send_result and pre_send_result.passed)
    )


def _simulate_feishu_event(settings, report_date, meeting_name: str, chat_id: str, message_id: str, text: str, force_allow: bool = False) -> None:
    server = FeishuEventServer(
        settings,
        meeting_name=meeting_name,
        report_date=report_date,
    )
    if force_allow:
        server._allowed_chat_ids = {chat_id}

    class FakeIMClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str]] = []

        def reply_card(self, reply_message_id: str, card: dict) -> dict:
            title = card.get("header", {}).get("title", {}).get("content", "")
            self.calls.append((reply_message_id, "card", title))
            return {"code": 0}

        def reply_text(self, reply_message_id: str, text: str) -> dict:
            self.calls.append((reply_message_id, "text", text))
            return {"code": 0}

    fake_im = FakeIMClient()
    server._im_client = fake_im
    payload = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "token": settings.feishu_event_verification_token or "",
        },
        "event": {
            "message": {
                "message_id": message_id,
                "message_type": "text",
                "chat_type": "group",
                "chat_id": chat_id,
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            "mentions": [{"name": "bot"}],
        },
    }
    status, result = server.handle_request(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    print(f"Simulated callback status: {status}")
    print(f"Simulated callback result: {result}")
    if fake_im.calls:
        print("Replies:")
        for _, kind, content in fake_im.calls:
            if kind == "card":
                print(f"- [card] {content}")
            else:
                print(f"- [text] {content}")
    else:
        print("No reply would be sent.")


def _check_feishu_event_settings(settings, public_base_url: str) -> None:
    missing: list[str] = []
    warnings: list[str] = []

    if not settings.feishu_app_id:
        missing.append("FEISHU_APP_ID")
    if not settings.feishu_app_secret:
        missing.append("FEISHU_APP_SECRET")
    if not settings.feishu_event_verification_token:
        missing.append("FEISHU_EVENT_VERIFICATION_TOKEN")

    if settings.feishu_event_encrypt_key:
        warnings.append("已配置 FEISHU_EVENT_ENCRYPT_KEY；请确认飞书后台的 Encrypt Key 与本地一致。")
    if not settings.feishu_detail_allowed_chat_ids:
        warnings.append("还没有锁定 FEISHU_DETAIL_ALLOWED_CHAT_IDS；当前系统处于安全模式，命中触发词时只观测、不自动回复详细版。")
    if not settings.feishu_detail_trigger_keywords:
        warnings.append("没有配置 FEISHU_DETAIL_TRIGGER_KEYWORDS；将回退到默认关键词。")

    print("Feishu 事件回调配置检查")
    print(f"- 回调路径: {settings.feishu_event_path}")
    print(f"- 详细版关键词: {', '.join(settings.feishu_detail_trigger_keywords) if settings.feishu_detail_trigger_keywords else '(default)'}")
    print(
        "- 群白名单: "
        + (", ".join(settings.feishu_detail_allowed_chat_ids) if settings.feishu_detail_allowed_chat_ids else "(未配置)")
    )
    observed_path = settings.active_output_dir / "feishu_detail_chat_observations.json"
    if observed_path.exists():
        try:
            observed_payload = json.loads(observed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            observed_payload = {}
        items = observed_payload.get("items") if isinstance(observed_payload, dict) else []
        if isinstance(items, list) and items:
            latest = items[0]
            print(f"- 最近触发群: {latest.get('chat_id', '')} ({latest.get('last_seen_at', '')})")
            print(f"- 观测记录: {observed_path}")
    if public_base_url.strip():
        callback_url = public_base_url.rstrip("/") + settings.feishu_event_path
        print(f"- 建议回调地址: {callback_url}")

    if missing:
        print("- 状态: 未就绪")
        print("- 缺少配置:")
        for item in missing:
            print(f"  - {item}")
    else:
        print("- 状态: 基本就绪")

    if warnings:
        print("- 注意事项:")
        for item in warnings:
            print(f"  - {item}")
    else:
        print("- 注意事项: 无")


def _build_feishu_event_allowlist_suggestion(settings, top: int) -> tuple[str, list[dict], str]:
    observed_path = settings.active_output_dir / "feishu_detail_chat_observations.json"
    if not observed_path.exists():
        raise FileNotFoundError("还没有观测记录。先在群里触发一次 @机器人 详细版，再来生成建议值。")
    try:
        payload = json.loads(observed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError(f"观测记录损坏：{observed_path}")
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list) or not items:
        raise ValueError("观测记录里还没有可用的 chat_id。")
    real_items = [item for item in items if str(item.get("chat_id") or "").startswith("oc_")]
    candidate_items = real_items or items
    selected: list[str] = []
    for item in candidate_items:
        chat_id = str(item.get("chat_id") or "").strip()
        if not chat_id or chat_id in selected:
            continue
        selected.append(chat_id)
        if len(selected) >= max(1, top):
            break
    if not selected:
        raise ValueError("观测记录里没有可用的 chat_id。")
    suggestion = ",".join(selected)
    return suggestion, items, str(observed_path)


def _update_env_key(env_path: str, key: str, value: str) -> bool:
    from pathlib import Path

    path = Path(env_path)
    if not path.exists():
        raise FileNotFoundError(f".env 不存在：{path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    updated_lines: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            updated_lines.append(f"{key}={value}")
            replaced = True
        else:
            updated_lines.append(line)
    if not replaced:
        updated_lines.append(f"{key}={value}")
    path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return replaced


def _backup_env_file(env_path: str, backup_dir: str) -> str:
    from datetime import datetime
    from pathlib import Path

    source = Path(env_path)
    if not source.exists():
        raise FileNotFoundError(f".env 不存在：{source}")
    backup_root = Path(backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / f".env.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return str(backup_path)


def _suggest_feishu_event_allowlist(settings, top: int) -> None:
    try:
        suggestion, items, observed_path = _build_feishu_event_allowlist_suggestion(settings, top)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return
    print("建议写入 .env：")
    print(f"FEISHU_DETAIL_ALLOWED_CHAT_IDS={suggestion}")
    print(f"来源记录：{observed_path}")
    print("最近命中的群：")
    for item in items[: max(1, top)]:
        print(
            "- "
            f"{item.get('chat_id', '')} | "
            f"last_seen={item.get('last_seen_at', '')} | "
            f"real_chat_id_style={'yes' if str(item.get('chat_id') or '').startswith('oc_') else 'no'} | "
            f"allowlist_configured={'yes' if item.get('allowlist_configured') else 'no'} | "
            f"reply_sent={'yes' if item.get('reply_sent') else 'no'}"
        )
    real_items = [item for item in items if str(item.get("chat_id") or "").startswith("oc_")]
    suggestion_path = settings.active_output_dir / "feishu_detail_allowlist_suggestion.env"
    if real_items:
        suggestion_path.write_text(f"FEISHU_DETAIL_ALLOWED_CHAT_IDS={suggestion}\n", encoding="utf-8")
        print(f"建议文件：{suggestion_path}")
    else:
        if suggestion_path.exists():
            suggestion_path.unlink()
        print("注意：当前还没有真实飞书群 chat_id 观测记录；建议值仍来自本地模拟。真实飞书群通常以 `oc_` 开头。")
        print("注意：本次不会生成建议文件，避免误把模拟值写入正式配置。")


def _apply_feishu_event_allowlist(settings, top: int, manual_chat_ids: list[str]) -> None:
    selected_ids: list[str] = []
    normalized_manual_ids = [chat_id.strip() for chat_id in manual_chat_ids if chat_id and chat_id.strip()]
    if normalized_manual_ids:
        invalid = [chat_id for chat_id in normalized_manual_ids if not chat_id.startswith("oc_")]
        if invalid:
            print("拒绝写回 .env：手动传入的 chat_id 必须是以 `oc_` 开头的真实飞书群 ID。")
            for item in invalid:
                print(f"- 无效值：{item}")
            return
        for chat_id in normalized_manual_ids:
            if chat_id not in selected_ids:
                selected_ids.append(chat_id)
    else:
        try:
            suggestion, items, observed_path = _build_feishu_event_allowlist_suggestion(settings, top)
        except (FileNotFoundError, ValueError) as exc:
            print(str(exc))
            return
        selected = [item for item in items if str(item.get("chat_id") or "").startswith("oc_")]
        if not selected:
            print("拒绝写回 .env：当前观测记录里还没有真实飞书群 chat_id。请先在真实群里触发一次详细版，或使用 --chat-id 手动传入。")
            return
        for item in selected:
            chat_id = str(item.get("chat_id") or "").strip()
            if not chat_id or chat_id in selected_ids:
                continue
            selected_ids.append(chat_id)
            if len(selected_ids) >= max(1, top):
                break
    if not selected_ids:
        print("拒绝写回 .env：没有可用的真实飞书群 chat_id。")
        return
    applied_value = ",".join(selected_ids)
    backup_path = _backup_env_file(".env", str(settings.active_output_dir))
    replaced = _update_env_key(".env", "FEISHU_DETAIL_ALLOWED_CHAT_IDS", applied_value)
    settings.active_output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = settings.active_output_dir / "feishu_detail_allowlist_applied.env"
    receipt_path.write_text(f"FEISHU_DETAIL_ALLOWED_CHAT_IDS={applied_value}\n", encoding="utf-8")
    print("已写回 .env：")
    print(f"FEISHU_DETAIL_ALLOWED_CHAT_IDS={applied_value}")
    if normalized_manual_ids:
        print("来源：手动传入 --chat-id")
    else:
        print(f"来源记录：{observed_path}")
    print(f".env 备份：{backup_path}")
    print(f"回写凭据：{receipt_path}")
    print(f"更新方式：{'替换现有配置' if replaced else '新增配置项'}")


def _run_health_check(settings, report_date: datetime.date, meeting_name: str, chat_id: str, message_id: str, text: str, public_base_url: str) -> None:
    report_date = _align_weekly_report_date(report_date)
    print(f"健康检查周窗口：{report_date.isoformat()}")

    gate_result = _run_send_gate(settings, report_date, meeting_name)
    print(f"- 自检：{'通过' if gate_result.passed else '失败'}")
    print(f"- 自检报告：{gate_result.markdown_path}")
    print(f"- 总览页：{gate_result.preview_paths.overview_markdown}")

    audit_payload, audit_paths = _run_report_audit(settings, report_date, meeting_name, self_check_result=gate_result)
    print(f"- 审计：{'通过' if audit_payload.get('passed') else '失败'}")
    print(f"- 审计报告：{audit_paths['summary']}")

    pre_send_result = _run_pre_send_summary(settings, report_date)
    print(f"- 发前结论页：{pre_send_result.markdown_path}")
    print(f"- 发前结论状态：{'可发送' if pre_send_result.passed else '不可发送'}")

    _write_market_ops_status_snapshot(settings)
    print("")
    _check_feishu_event_settings(settings, public_base_url)
    print("")
    _simulate_feishu_event(settings, report_date, meeting_name, chat_id, message_id, text)
    report_result = HealthCheckReportBuilder(settings).build(
        report_date=report_date,
        meeting_name=meeting_name,
        self_check_result=gate_result,
        audit_payload=audit_payload,
        pre_send_result=pre_send_result,
    )
    print("")
    print(f"健康检查文件：{report_result.markdown_path}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    settings = load_settings()

    if args.command == "weekly-run":
        pipeline = WeeklyPipeline(settings)
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        _, report_path = pipeline.run(report_date=report_date, meeting_name=args.meeting_name)
        print(f"Report generated: {report_path}")
    elif args.command == "approve-meeting-actions":
        pipeline = MeetingApprovalPipeline(settings)
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        updated_count = pipeline.run(report_date=report_date, meeting_name=args.meeting_name)
        print(f"Meeting actions approved: {updated_count}")
    elif args.command == "meeting-closeout":
        pipeline = MeetingCloseoutPipeline(settings)
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        allow_send = False
        gate_result = None
        audit_payload = None
        audit_paths = None
        pre_send_result = None
        if not args.no_send:
            gate_result = _run_send_gate(settings, report_date, args.meeting_name)
            audit_payload, audit_paths = _run_report_audit(
                settings,
                report_date,
                args.meeting_name,
                self_check_result=gate_result,
            )
            pre_send_result = _run_pre_send_summary(settings, report_date)
            _sync_summary_preview_from_pre_send(gate_result, pre_send_result)
            allow_send = _send_gate_passed(gate_result, audit_payload, pre_send_result)
        approved_count, summary_path, send_result = pipeline.run(
            report_date=report_date,
            meeting_name=args.meeting_name,
            send=allow_send,
        )
        if not args.no_send and not allow_send and gate_result is not None and audit_paths is not None:
            print(_format_gate_blocked(str(gate_result.preview_paths.overview_markdown), str(gate_result.markdown_path), str(audit_paths["summary"])))
        elif send_result is not None:
            print(f"Meeting closeout completed and sent: {summary_path} ({approved_count} actions)")
        else:
            print(f"Meeting closeout completed: {summary_path} ({approved_count} actions)")
    elif args.command == "daily-sync":
        as_of_date = datetime.strptime(args.as_of_date, "%Y-%m-%d").date()
        pipeline = DailySyncPipeline(settings)
        sync_path = pipeline.run(as_of_date=as_of_date)
        print(f"Daily sync generated: {sync_path}")
    elif args.command == "sync-feishu-sources":
        pipeline = FeishuSourceSyncPipeline(settings)
        summary = pipeline.run()
        if args.print_summary:
            print(summary)
        else:
            print("Feishu source sync completed.")
    elif args.command == "weekly-digest":
        pipeline = WeeklyDigestPipeline(settings)
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        _refresh_bottom_layer(settings, report_date, args.meeting_name)
        gate_result = _run_send_gate(settings, report_date, args.meeting_name)
        audit_payload = None
        audit_paths = None
        pre_send_result = None
        if args.send:
            audit_payload, audit_paths = _run_report_audit(
                settings,
                report_date,
                args.meeting_name,
                self_check_result=gate_result,
            )
            pre_send_result = _run_pre_send_summary(settings, report_date)
            _sync_summary_preview_from_pre_send(gate_result, pre_send_result)
        allow_send = args.send and _send_gate_passed(gate_result, audit_payload, pre_send_result)
        digest_path, send_result = pipeline.run(
            report_date=report_date,
            meeting_name=args.meeting_name,
            send=allow_send,
            market_detailed=args.detailed,
        )
        if args.send and not allow_send:
            print(_format_gate_blocked(str(gate_result.preview_paths.overview_markdown), str(gate_result.markdown_path), str(audit_paths["summary"])))
        elif send_result is not None:
            print(_format_report_success("周报已发送", str(gate_result.preview_paths.overview_markdown)))
        else:
            print(_format_report_success("周报已生成", str(gate_result.preview_paths.overview_markdown)))
    elif args.command == "weekly-pack":
        pipeline = WeeklyBroadcastPipeline(settings)
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        if args.send and not _boss_send_enabled(settings):
            print("老板发送仍处于锁定状态。本次 weekly-pack 仅生成预览，不执行发送。")
            args.send = False
        _refresh_bottom_layer(settings, report_date, args.meeting_name)
        gate_result = _run_send_gate(settings, report_date, args.meeting_name)
        audit_payload = None
        audit_paths = None
        pre_send_result = None
        if args.send:
            audit_payload, audit_paths = _run_report_audit(
                settings,
                report_date,
                args.meeting_name,
                self_check_result=gate_result,
            )
            pre_send_result = _run_pre_send_summary(settings, report_date)
            _sync_summary_preview_from_pre_send(gate_result, pre_send_result)
        allow_send = args.send and _send_gate_passed(gate_result, audit_payload, pre_send_result)
        if not args.send and _weekly_pack_outputs_ready(settings, report_date):
            suffix = report_date.strftime("%Y%m%d")
            print(_format_report_success("市场版和老板版已生成", str(gate_result.preview_paths.overview_markdown)))
            print(f"- 市场版周报：{settings.active_output_dir / f'weekly_digest_{suffix}.md'}")
            print(f"- 老板版周报：{settings.active_output_dir / f'executive_report_weekly_{suffix}.md'}")
            print("- V2.5 决策闭环并行验证已生成")
            return
        report_paths, send_result = pipeline.run(
            report_date=report_date,
            meeting_name=args.meeting_name,
            send=allow_send,
            digest_market_detailed=args.detailed,
        )
        if args.send and not allow_send:
            print(_format_gate_blocked(str(gate_result.preview_paths.overview_markdown), str(gate_result.markdown_path), str(audit_paths["summary"])))
        elif send_result is not None:
            print(_format_report_success("市场版和老板版已发送", str(gate_result.preview_paths.overview_markdown)))
        else:
            print(_format_report_success("市场版和老板版已生成", str(gate_result.preview_paths.overview_markdown)))
    elif args.command == "executive-report":
        pipeline = ExecutiveReportPipeline(settings)
        report_date = _resolve_report_date(settings, args.report_date)
        if args.send and not _boss_send_enabled(settings):
            print("老板发送仍处于锁定状态。本次 executive-report 仅生成，不执行发送。")
            args.send = False
        gate_result = None
        audit_payload = None
        audit_paths = None
        pre_send_result = None
        if args.period == "weekly":
            report_date = _align_weekly_report_date(report_date)
            _refresh_bottom_layer(settings, report_date, "Weekly Market Ops Review")
            gate_result = _run_send_gate(settings, report_date, "Weekly Market Ops Review")
            if args.send:
                audit_payload, audit_paths = _run_report_audit(
                    settings,
                    report_date,
                    "Weekly Market Ops Review",
                    self_check_result=gate_result,
                )
                pre_send_result = _run_pre_send_summary(settings, report_date)
                _sync_summary_preview_from_pre_send(gate_result, pre_send_result)
        allow_send = args.send and (
            _send_gate_passed(gate_result, audit_payload, pre_send_result) if gate_result is not None else True
        )
        report_path, send_result = pipeline.run(
            report_date=report_date,
            period=args.period,
            send=allow_send,
        )
        if args.send and gate_result is not None and not allow_send:
            print(_format_gate_blocked(str(gate_result.preview_paths.overview_markdown), str(gate_result.markdown_path), str(audit_paths["summary"])))
        elif send_result is not None:
            print(_format_report_success("老板版已发送", str(gate_result.preview_paths.overview_markdown)))
        else:
            if gate_result is not None:
                print(_format_report_success("老板版已生成", str(gate_result.preview_paths.overview_markdown)))
            else:
                print(f"老板版已生成：{report_path}")
    elif args.command == "forecast-validation":
        pipeline = ForecastValidationPipeline(settings)
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        report_path = pipeline.run(
            report_date=report_date,
            meeting_name=args.meeting_name,
        )
        print(f"Forecast validation report generated: {report_path}")
    elif args.command == "profitability-audit":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = ProfitabilityAuditBuilder(settings).build(report_date=report_date)
        print("Profitability audit generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "creative-attribution-audit":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = CreativeAttributionAuditBuilder(settings).build(report_date=report_date)
        print("Creative attribution audit generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "adjust-creative-analysis":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = AdjustCreativeAnalysisBuilder(settings).build(report_date=report_date)
        print("Adjust creative analysis generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "creative-source-readiness":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = CreativeSourceReadinessBuilder(settings).build(report_date=report_date)
        print("Creative source readiness generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "tecdo-probe":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = TecDoProbeBuilder(settings).build(report_date=report_date)
        print("TecDo probe generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "tecdo-account-reconciliation":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = TecDoAccountReconciliationBuilder(settings).build(
            report_date=report_date,
            lookback_days=max(1, int(args.lookback_days)),
        )
        print("TecDo account reconciliation generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "google-creative-repair-audit":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = GoogleCreativeRepairAuditBuilder(settings).build(report_date=report_date)
        print("Google creative repair audit generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "google-revenue-attribution-audit":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = GoogleRevenueAttributionAuditBuilder(settings).build(report_date=report_date)
        print("Google revenue attribution audit generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "payback-targets":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = PaybackTargetsBuilder(settings).build(report_date=report_date)
        print("Payback targets generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "growth-priorities":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = GrowthPrioritiesBuilder(settings).build(report_date=report_date)
        print("Growth priorities generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
    elif args.command == "creative-loop":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        orchestrator = CreativeLoopOrchestrator(settings)
        result = orchestrator.run(
            report_date=report_date,
            max_winners=getattr(args, "max_winners", 5),
            max_variants=getattr(args, "max_variants", 10),
        )
        print("Creative Loop Orchestrator complete:")
        print(f"- run_id: {result.run_id}")
        print(f"- winners: {len(result.winners)}")
        print(f"- patterns: {len(result.patterns)}")
        print(f"- variants: {len(result.variants)}")
        print(f"- visual mode: {result.visual_mode}")
        print(f"- winners_json: {Path(result.winners_json).name}")
        print(f"- patterns_json: {Path(result.patterns_json).name}")
        print(f"- variants_md: {Path(result.variants_md).name}")
        print(f"- feedback_json: {Path(result.feedback_json).name}")
        if result.errors:
            print(f"- errors: {result.errors}")
        if result.warnings:
            print(f"- warnings: {result.warnings}")
    elif args.command == "creative-dna":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = CreativeDnaBuilder(settings).build(report_date=report_date)
        print("Creative DNA generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
    elif args.command == "creative-clusters":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = CreativeClustersBuilder(settings).build(report_date=report_date)
        print("Creative clusters generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
    elif args.command == "visual-intelligence":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = VisualIntelligenceBuilder(settings).build(report_date=report_date)
        print("Visual Intelligence Readiness generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "local-visual-assets":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = LocalVisualAssetManifestBuilder(settings).build(report_date=report_date)
        print("Local visual asset manifest generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "creative-fatigue":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = CreativeFatigueBuilder(settings).build(report_date=report_date)
        print("Creative fatigue generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
    elif args.command == "dynamic-payback":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DynamicPaybackBuilder(settings).build(report_date=report_date)
        print("Dynamic payback generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
    elif args.command == "user-quality":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = UserQualityBuilder(settings).build(report_date=report_date)
        print("User Quality Layer generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "lifecycle-prediction":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = LifecyclePredictionBuilder(settings).build(report_date=report_date)
        print("Lifecycle Prediction Layer generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "strategy-context":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = StrategyContextBuilder(settings).build(report_date=report_date)
        print("Strategy Context generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "ai-media-buyer-plan":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = AiMediaBuyerPlanBuilder(settings).build(report_date=report_date)
        print("AI Media Buyer plan generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
    elif args.command == "action-layer":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ActionLayerBuilder(settings).build(report_date=report_date)
        print("Action Layer generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "platform-write-readiness":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = PlatformWriteReadinessBuilder(settings).build(report_date=report_date)
        print("Platform Write Readiness generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "guarded-execution":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = GuardedExecutionBuilder(settings).build(report_date=report_date)
        print("Guarded Execution generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "rollback-monitor":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = RollbackMonitorBuilder(settings).build(report_date=report_date)
        print("Rollback Monitor generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command in ("discovery-engine", "discovery"):
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryEngineBuilder(settings).build(report_date=report_date)
        print("Discovery Engine generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        for name, path in result.child_paths.items():
            print(f"- {name}: {path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-validate":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        min_sample = getattr(args, "min_sample_size", 100)
        conf_threshold = getattr(args, "confidence_threshold", 0.95)
        validator = DiscoveryValidator(
            settings=settings,
            min_sample_size=min_sample,
            confidence_threshold=conf_threshold,
        )
        discovery_result, validation_report = DiscoveryEngineBuilder(settings).run_closed_loop(
            report_date=report_date,
        )
        print("Discovery Engine (base):")
        print(f"- markdown: {discovery_result.markdown_path}")
        print(f"- json: {discovery_result.json_path}")
        print(f"- passed: {discovery_result.passed}")
        print()
        print("Discovery Validation (closed-loop):")
        print(f"- markdown: {validation_report.markdown_path}")
        print(f"- json: {validation_report.json_path}")
        print(f"- results: {len(validation_report.results)}")
        print(f"- passed: {validation_report.passed}")
        fb = validation_report.feedback
        print(f"- feedback: cycle={fb.get('cycle')}, win_rate={fb.get('win_rate', 0):.2f}, "
              f"suggested={fb.get('suggested_next_batch')}")
    elif args.command == "creative-publish":
        _m = __import__("market_ops.creative_growth_loop.14_publish.facebook_publisher", fromlist=["FacebookPublisher", "PublishResult"])
        FacebookPublisher = _m.FacebookPublisher
        PublishResult = _m.PublishResult
        
        image_dir = args.image_dir
        publisher = FacebookPublisher(
            access_token=args.access_token,
            ad_account_id=args.ad_account_id,
            api_version=args.api_version,
            page_id=args.page_id,
        )
        campaign_config = {
            "adset_id": args.adset_id,
            "headlines": [args.headline],
            "primary_texts": [args.primary_text],
            "auto_activate": args.auto_activate,
            "page_id": args.page_id,
        }
        result = publisher.publish_and_monitor(
            image_dir=image_dir,
            campaign_config=campaign_config,
        )
        print("Creative Publish Result:")
        print(f"- run_id: {result.run_id}")
        print(f"- images uploaded: {result.uploaded_count}")
        print(f"- creatives created: {result.creative_count}")
        print(f"- ads created: {result.ad_count}")
        print(f"- success: {result.success}")
        if result.image_hashes:
            print(f"- image_hashes: {result.image_hashes[:5]}{'...' if len(result.image_hashes) > 5 else ''}")
        if result.creative_ids:
            print(f"- creative_ids: {result.creative_ids[:5]}{'...' if len(result.creative_ids) > 5 else ''}")
        if result.ad_ids:
            print(f"- ad_ids: {result.ad_ids[:5]}{'...' if len(result.ad_ids) > 5 else ''}")
        if result.errors:
            print(f"- errors: {result.errors}")
    elif args.command == "creative-daily":
        import json as _json
        _m2 = __import__("market_ops.creative_growth_loop.13_scheduler.daily_runner", fromlist=["DailyRunner"])
        DailyRunner = _m2.DailyRunner
        
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: config file not found: {args.config}")
            return
        
        config = _json.loads(config_path.read_text(encoding="utf-8"))
        runner = DailyRunner(
            output_dir=args.output_dir,
            config=config,
        )
        result = runner.run(generations=args.generations)
        print("Creative Daily Loop Complete:")
        print(f"- run_date: {result.run_date}")
        print(f"- winners: {result.total_winners}")
        print(f"- mutations: {result.total_mutations}")
        print(f"- images: {result.total_images}")
        print(f"- valid: {result.valid_images}")
        print(f"- top_score: {result.top_score:.2f}")
        print(f"- families: {result.families_created}")
        if result.errors:
            print(f"- errors: {result.errors}")
    elif args.command == "decision-engine":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DecisionEngineBuilder(settings).build(report_date=report_date)
        print("V2.5 decision engine generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "experiment-plan":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ExperimentPlanBuilder(settings).build(report_date=report_date)
        print("V2.5 experiment plan generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "action-feedback":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ActionFeedbackBuilder(settings).build(report_date=report_date)
        print("V2.5 action feedback generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "learning-memory":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = LearningMemoryBuilder(settings).build(report_date=report_date)
        print("Learning memory generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "growth-memory-store":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = GrowthMemoryStoreBuilder(settings).build(report_date=report_date)
        print("Growth memory store generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "growth-playbook":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = GrowthPlaybookBuilder(settings).build(report_date=report_date)
        print("Growth Playbook generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "learning-evidence-queue":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = LearningEvidenceQueueBuilder(settings).build(report_date=report_date)
        print("Learning Evidence Queue generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-result-capture-packets":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryResultCapturePacketsBuilder(settings).build(report_date=report_date)
        print("Discovery Result Capture Packets generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- slot input csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-experiment-cards":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        from market_ops.discovery_experiment_cards import DiscoveryExperimentCardsBuilder

        result = DiscoveryExperimentCardsBuilder(settings).build(report_date=report_date)
        print("Discovery Experiment Cards generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-test-plans":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        from market_ops.discovery_test_plans import DiscoveryTestPlansBuilder

        result = DiscoveryTestPlansBuilder(settings).build(report_date=report_date)
        print("Discovery Test Plans generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-execution-packets":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        from market_ops.discovery_execution_packets import DiscoveryExecutionPacketsBuilder

        result = DiscoveryExecutionPacketsBuilder(settings).build(report_date=report_date)
        print("Discovery Execution Packets generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-learning-packets":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        from market_ops.discovery_learning_packets import DiscoveryLearningPacketsBuilder

        result = DiscoveryLearningPacketsBuilder(settings).build(report_date=report_date)
        print("Discovery Learning Packets generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-pattern-prior":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryPatternPriorBuilder(settings).build(report_date=report_date)
        print("Discovery Pattern Prior generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-learning-state-board":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryLearningStateBoardBuilder(settings).build(report_date=report_date)
        print("Discovery Learning State Board generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-slot-status-board":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoverySlotStatusBoardBuilder(settings).build(report_date=report_date)
        print("Discovery Slot Status Board generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-slot-operator-packet":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoverySlotOperatorPacketBuilder(settings).build(report_date=report_date)
        print("Discovery Slot Operator Packet generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-unlock-sequence":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryUnlockSequenceBuilder(settings).build(report_date=report_date)
        print("Discovery Unlock Sequence generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-unlock-operator-handoff":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryUnlockOperatorHandoffBuilder(settings).build(report_date=report_date)
        print("Discovery Unlock Operator Handoff generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-action-queue":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryActionQueueBuilder(settings).build(report_date=report_date)
        print("Discovery Action Queue generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-action-state-board":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryActionStateBoardBuilder(settings).build(report_date=report_date)
        print("Discovery Action State Board generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "discovery-approval-packet":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DiscoveryApprovalPacketBuilder(settings).build(report_date=report_date)
        print("Discovery Approval Packet generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- packet csv: {result.csv_path}")
        print(f"- input csv: {result.input_csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "causal-learning":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = CausalLearningBuilder(settings).build(report_date=report_date)
        print("Causal Learning Layer generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "experiment-execution-queue":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ExperimentExecutionQueueBuilder(settings).build(report_date=report_date)
        print("Experiment Execution Queue generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "approval-feedback-gate":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ApprovalFeedbackGateBuilder(settings).build(report_date=report_date)
        print("Approval Feedback Gate generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- csv: {result.csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "experiment-result-ingestion":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ExperimentResultIngestionBuilder(settings).build(report_date=report_date)
        print("Experiment Result Ingestion generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- input csv: {result.input_csv_path}")
        print(f"- template csv: {result.template_csv_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "v25-decision-loop":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        decision_result, experiment_result, feedback_result = _run_v25_decision_loop(settings, report_date)
        print("V2.5 decision loop generated:")
        print(f"- decision markdown: {decision_result.markdown_path}")
        print(f"- decision json: {decision_result.json_path}")
        print(f"- decision csv: {decision_result.csv_path}")
        print(f"- experiment markdown: {experiment_result.markdown_path}")
        print(f"- experiment json: {experiment_result.json_path}")
        print(f"- feedback markdown: {feedback_result.markdown_path}")
        print(f"- feedback json: {feedback_result.json_path}")
        print(f"- passed: {decision_result.passed and experiment_result.passed and feedback_result.passed}")
    elif args.command == "media-buyer-loop":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = MediaBuyerLoopBuilder(settings).build(report_date=report_date, force=args.force)
        print("AI Media Buyer loop generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        for name, path in result.child_paths.items():
            print(f"- {name}: {path}")
        print(f"- passed: {result.passed}")
    elif args.command == "metric-reconciliation":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = WeeklyMetricReconciliationBuilder(settings).build(report_date=report_date)
        print("Metric reconciliation generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "pre-send-summary":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = PreSendSummaryBuilder(settings).build(report_date=report_date)
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        print("Pre-send summary generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
        print(f"- summary: {PreSendSummaryBuilder.build_console_summary(payload)}")
    elif args.command == "creative-action-thresholds":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        paths = CreativeActionThresholdsBuilder(settings).build(report_date=report_date)
        print("Creative action thresholds generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
    elif args.command == "data-quality-audit":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DataQualityAuditBuilder(settings).build(report_date=report_date)
        print("Data quality audit generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "report-audit":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        payload, paths = _run_report_audit(settings, report_date, args.meeting_name)
        print("Report audit generated:")
        for name, path in paths.items():
            print(f"- {name}: {path}")
        print(f"- passed: {payload.get('passed')}")
        if not payload.get("passed"):
            raise SystemExit(2)
    elif args.command == "card-preview":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        if not args.refresh and _reuse_card_preview_cache(settings, report_date):
            return
        if args.refresh:
            AdjustCreativeAnalysisBuilder(settings).build(report_date=report_date)
            GrowthPrioritiesBuilder(settings).build(report_date=report_date)
            _refresh_v2_growth_layers(settings, report_date)
            preview_paths = save_card_previews(report_date, args.meeting_name, settings.active_output_dir)
            overview_path = preview_paths.overview_markdown
            if _reuse_preview_support_after_refresh(settings, report_date, overview_path):
                return
        _refresh_bottom_layer(settings, report_date, args.meeting_name)
        gate_result = _run_send_gate(settings, report_date, args.meeting_name)
        if args.refresh and _reuse_preview_support_after_refresh(settings, report_date, gate_result.preview_paths.overview_markdown):
            return
        DataQualityAuditBuilder(settings).build(report_date=report_date)
        GoogleRevenueAttributionAuditBuilder(settings).build(report_date=report_date)
        payload, paths = _run_report_audit(settings, report_date, args.meeting_name, self_check_result=gate_result)
        pre_send_result = _run_pre_send_summary(settings, report_date)
        ManagementActionListBuilder(settings).build(report_date=report_date)
        ClosureStatusBuilder(settings).build(report_date=report_date)
        ProjectDetailCoverageBuilder(settings).build(report_date=report_date)
        P04SourceChecklistBuilder(settings).build(report_date=report_date)
        DetailReplyChecklistBuilder(settings).build(report_date=report_date)
        TecDoSyncChecklistBuilder(settings).build(report_date=report_date)
        _sync_summary_preview_from_pre_send(gate_result, pre_send_result)
        health_result = HealthCheckReportBuilder(settings).build(
            report_date=report_date,
            meeting_name=args.meeting_name,
            self_check_result=gate_result,
            audit_payload=payload,
            pre_send_result=pre_send_result,
        )
        status_text = "通过" if health_result.passed else "失败"
        print(
            f"预览已生成。状态：{status_text} | 先看总览页：{gate_result.preview_paths.overview_markdown} | 健康检查：{health_result.markdown_path}"
        )
    elif args.command == "group-approved-execute":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result_payload, output_paths = execute_group_approved_tasks(
            settings,
            report_date=report_date,
            meeting_name=args.meeting_name,
            chat_id=args.chat_id,
            request_ids=args.request_id,
        )
        print("已批准待办执行完成：")
        print(f"- 已执行：{result_payload['executed_count']}")
        print(f"- 已跳过：{result_payload['skipped_count']}")
        print(f"- markdown: {output_paths['markdown']}")
        print(f"- json: {output_paths['json']}")
    elif args.command == "card-send":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        if not args.boss and not args.market:
            parser.error("card-send requires at least one target: --boss or --market")
        _refresh_bottom_layer(settings, report_date, args.meeting_name)
        gate_result = _run_send_gate(settings, report_date, args.meeting_name)
        payload, paths = _run_report_audit(settings, report_date, args.meeting_name, self_check_result=gate_result)
        pre_send_result = _run_pre_send_summary(settings, report_date)
        _sync_summary_preview_from_pre_send(gate_result, pre_send_result)
        if not _send_gate_passed(gate_result, payload, pre_send_result):
            print(_format_gate_blocked(str(gate_result.preview_paths.overview_markdown), str(gate_result.markdown_path), str(paths["summary"])))
            return
        send_result = send_selected_cards(
            report_date=report_date,
            meeting_name=args.meeting_name,
            send_boss=args.boss,
            send_market=args.market,
            include_recovery=not args.no_recovery,
            market_detailed=args.market_detailed,
            boss_webhook=args.boss_webhook,
            market_webhook=args.market_webhook,
        )
        print(_format_send_success("已发送卡片", sorted(send_result.keys()), str(gate_result.preview_paths.overview_markdown)))
    elif args.command == "market-send":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        _refresh_bottom_layer(settings, report_date, args.meeting_name)
        gate_result = _run_send_gate(settings, report_date, args.meeting_name)
        payload, paths = _run_report_audit(settings, report_date, args.meeting_name, self_check_result=gate_result)
        pre_send_result = _run_pre_send_summary(settings, report_date)
        _sync_summary_preview_from_pre_send(gate_result, pre_send_result)
        if not _send_gate_passed(gate_result, payload, pre_send_result):
            print(_format_gate_blocked(str(gate_result.preview_paths.overview_markdown), str(gate_result.markdown_path), str(paths["summary"])))
            return
        if args.all:
            send_result = send_market_all_cards(
                report_date=report_date,
                meeting_name=args.meeting_name,
                include_recovery=not args.no_recovery,
            )
        else:
            send_result = send_selected_cards(
                report_date=report_date,
                meeting_name=args.meeting_name,
                send_boss=False,
                send_market=True,
                include_recovery=not args.no_recovery,
                market_detailed=args.detailed,
            )
        print(_format_send_success("已发送卡片", sorted(send_result.keys()), str(gate_result.preview_paths.overview_markdown)))
    elif args.command == "feishu-event-server":
        report_date = None if args.report_date == "latest" else datetime.strptime(args.report_date, "%Y-%m-%d").date()
        server = FeishuEventServer(
            settings,
            meeting_name=args.meeting_name,
            report_date=report_date,
        )
        server.serve(host=args.host, port=args.port)
    elif args.command == "feishu-event-simulate":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        _simulate_feishu_event(
            settings,
            report_date=report_date,
            meeting_name=args.meeting_name,
            chat_id=args.chat_id,
            message_id=args.message_id,
            text=args.text,
            force_allow=args.force_allow,
        )
    elif args.command == "feishu-event-check":
        _check_feishu_event_settings(settings, args.public_base_url)
    elif args.command == "feishu-event-allowlist-suggest":
        _suggest_feishu_event_allowlist(settings, args.top)
    elif args.command == "feishu-event-allowlist-apply":
        _apply_feishu_event_allowlist(settings, args.top, args.chat_id)
    elif args.command == "health-check":
        report_date = _resolve_report_date(settings, args.report_date)
        suffix = _align_weekly_report_date(report_date).strftime("%Y%m%d")
        cached_self_check = settings.active_output_dir / f"self_check_{suffix}.json"
        cached_audit = settings.active_output_dir / f"report_audit_{suffix}.json"
        cached_pre_send = settings.active_output_dir / f"pre_send_summary_{suffix}.json"
        cached_health = settings.active_output_dir / f"weekly_health_check_{suffix}.json"
        if cached_self_check.exists() and cached_audit.exists() and cached_pre_send.exists() and cached_health.exists():
            print(f"健康检查周窗口：{_align_weekly_report_date(report_date).isoformat()}")
            print(f"- 复用已有结果：{cached_health}")
            _write_market_ops_status_snapshot(settings)
            _check_feishu_event_settings(settings, args.public_base_url)
            print("")
            _simulate_feishu_event(
                settings,
                _align_weekly_report_date(report_date),
                args.meeting_name,
                args.chat_id,
                args.message_id,
                args.text,
            )
            print("")
            print(f"健康检查文件：output\\active\\weekly_health_check_{suffix}.md")
        else:
            _run_health_check(
                settings,
                report_date=report_date,
                meeting_name=args.meeting_name,
                chat_id=args.chat_id,
                message_id=args.message_id,
                text=args.text,
                public_base_url=args.public_base_url,
            )
    elif args.command == "group-send-log-cleanup":
        result = GroupSendLog(settings.active_output_dir).cleanup_test_entries()
        print("发送记录清理完成：")
        print(f"- 清理前：{result['before']}")
        print(f"- 清理后：{result['after']}")
        print(f"- 已移除测试记录：{result['removed']}")
    elif args.command == "status-refresh":
        path = _write_market_ops_status_snapshot(settings)
        print("Market Ops status refreshed:")
        print(f"- json: {path}")
        print(f"- markdown: {settings.active_output_dir / 'market_ops_status_latest.md'}")
    elif args.command == "closure-status":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ClosureStatusBuilder(settings).build(report_date=report_date)
        print("Closure status generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "management-action-list":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ManagementActionListBuilder(settings).build(report_date=report_date)
        print("Management action list generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "project-detail-coverage":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ProjectDetailCoverageBuilder(settings).build(report_date=report_date)
        print("Project detail coverage generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "p04-source-checklist":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = P04SourceChecklistBuilder(settings).build(report_date=report_date)
        print("P04 source checklist generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "detail-reply-checklist":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = DetailReplyChecklistBuilder(settings).build(report_date=report_date)
        print("Detail reply checklist generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "tecdo-sync-checklist":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = TecDoSyncChecklistBuilder(settings).build(report_date=report_date)
        print("TecDo sync checklist generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "external-blockers":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        result = ExternalBlockersBuilder(settings).build(report_date=report_date)
        print("External blockers generated:")
        print(f"- markdown: {result.markdown_path}")
        print(f"- json: {result.json_path}")
        print(f"- passed: {result.passed}")
    elif args.command == "p04-verify-after-mapping":
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        _run_p04_verify_after_mapping(settings, report_date)
    elif args.command == "bitable-sync":
        from market_ops.pipeline import BitableSyncPipeline
        report_date = _align_weekly_report_date(_resolve_report_date(settings, args.report_date))
        pipeline = BitableSyncPipeline(settings)
        result = pipeline.run(
            report_date=report_date,
            meeting_name=args.meeting_name,
            html_only=args.html_only,
            bitable_only=args.bitable_only,
        )
        print(f"Bitable sync completed: {report_date.isoformat()}")
        if result.tables_synced:
            print(f"- Tables synced: {', '.join(result.tables_synced)}")
            for table_name, count in result.records_written.items():
                print(f"  - {table_name}: {count} records")
        else:
            print("- Bitable write: skipped (html-only or no credentials)")
        if result.html_path:
            print(f"- HTML report: {result.html_path}")
        else:
            print("- HTML report: skipped (bitable-only)")


if __name__ == "__main__":
    main()
