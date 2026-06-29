from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.action_feedback import ActionFeedbackBuilder
from market_ops.action_layer import ActionLayerBuilder
from market_ops.ai_media_buyer_plan import AiMediaBuyerPlanBuilder
from market_ops.approval_feedback_gate import ApprovalFeedbackGateBuilder
from market_ops.causal_learning import CausalLearningBuilder
from market_ops.config import Settings
from market_ops.discovery_action_queue import DiscoveryActionQueueBuilder
from market_ops.discovery_action_state_board import DiscoveryActionStateBoardBuilder
from market_ops.discovery_approval_packet import DiscoveryApprovalPacketBuilder
from market_ops.creative_clusters import CreativeClustersBuilder
from market_ops.creative_dna import CreativeDnaBuilder
from market_ops.creative_fatigue import CreativeFatigueBuilder
from market_ops.decision_engine import DecisionEngineBuilder
from market_ops.discovery_experiment_cards import DiscoveryExperimentCardsBuilder
from market_ops.discovery_execution_packets import DiscoveryExecutionPacketsBuilder
from market_ops.discovery_learning_packets import DiscoveryLearningPacketsBuilder
from market_ops.discovery_pattern_prior import DiscoveryPatternPriorBuilder
from market_ops.discovery_learning_state_board import DiscoveryLearningStateBoardBuilder
from market_ops.discovery_result_capture_packets import DiscoveryResultCapturePacketsBuilder
from market_ops.discovery_slot_operator_packet import DiscoverySlotOperatorPacketBuilder
from market_ops.discovery_slot_status_board import DiscoverySlotStatusBoardBuilder
from market_ops.discovery_unlock_operator_handoff import DiscoveryUnlockOperatorHandoffBuilder
from market_ops.discovery_unlock_sequence import DiscoveryUnlockSequenceBuilder
from market_ops.discovery_test_plans import DiscoveryTestPlansBuilder
from market_ops.discovery_engine import DiscoveryEngineBuilder
from market_ops.dynamic_payback import DynamicPaybackBuilder
from market_ops.experiment_execution_queue import ExperimentExecutionQueueBuilder
from market_ops.experiment_manager import ExperimentPlanBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder
from market_ops.growth_memory_store import GrowthMemoryStoreBuilder
from market_ops.growth_playbook import GrowthPlaybookBuilder
from market_ops.growth_priorities import GrowthPrioritiesBuilder
from market_ops.guarded_execution import GuardedExecutionBuilder
from market_ops.learning_evidence_queue import LearningEvidenceQueueBuilder
from market_ops.learning_memory import LearningMemoryBuilder
from market_ops.lifecycle_prediction import LifecyclePredictionBuilder
from market_ops.platform_write_readiness import PlatformWriteReadinessBuilder
from market_ops.rollback_monitor import RollbackMonitorBuilder
from market_ops.strategy_context import StrategyContextBuilder
from market_ops.user_quality import UserQualityBuilder
from market_ops.visual_intelligence import VisualIntelligenceBuilder


@dataclass(slots=True)
class MediaBuyerLoopResult:
    markdown_path: Path
    json_path: Path
    passed: bool
    child_paths: dict[str, Path]


class MediaBuyerLoopBuilder:
    """Builds the auditable top-level AI Media Buyer loop ledger."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date, force: bool = False) -> MediaBuyerLoopResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")

        child_paths = {
            "strategy_context": output_dir / f"strategy_context_{suffix}.json",
            "discovery_engine": output_dir / f"discovery_engine_{suffix}.json",
            "growth_priorities": output_dir / f"growth_priorities_{suffix}.json",
            "creative_dna": output_dir / f"creative_dna_{suffix}.json",
            "visual_intelligence": output_dir / f"visual_intelligence_{suffix}.json",
            "creative_clusters": output_dir / f"creative_clusters_{suffix}.json",
            "creative_fatigue": output_dir / f"creative_fatigue_{suffix}.json",
            "dynamic_payback": output_dir / f"dynamic_payback_{suffix}.json",
            "user_quality": output_dir / f"user_quality_{suffix}.json",
            "lifecycle_prediction": output_dir / f"lifecycle_prediction_{suffix}.json",
            "decision_engine": output_dir / f"decision_engine_{suffix}.json",
            "experiment_plan": output_dir / f"experiment_plan_{suffix}.json",
            "action_feedback": output_dir / f"action_feedback_{suffix}.json",
            "learning_memory": output_dir / f"learning_memory_{suffix}.json",
            "growth_memory_store": output_dir / "growth_memory_store_latest.json",
            "causal_learning": output_dir / f"causal_learning_{suffix}.json",
            "growth_playbook": output_dir / f"growth_playbook_{suffix}.json",
            "learning_evidence_queue": output_dir / f"learning_evidence_queue_{suffix}.json",
            "experiment_execution_queue": output_dir / f"experiment_execution_queue_{suffix}.json",
            "approval_feedback_gate": output_dir / f"approval_feedback_gate_{suffix}.json",
            "experiment_result_ingestion": output_dir / f"experiment_result_ingestion_{suffix}.json",
            "discovery_experiment_cards": output_dir / f"discovery_experiment_cards_{suffix}.json",
            "discovery_test_plans": output_dir / f"discovery_test_plans_{suffix}.json",
            "discovery_execution_packets": output_dir / f"discovery_execution_packets_{suffix}.json",
            "discovery_learning_packets": output_dir / f"discovery_learning_packets_{suffix}.json",
            "discovery_pattern_prior": output_dir / f"discovery_pattern_prior_{suffix}.json",
            "discovery_learning_state_board": output_dir / f"discovery_learning_state_board_{suffix}.json",
            "discovery_result_capture_packets": output_dir / f"discovery_result_capture_packets_{suffix}.json",
            "discovery_approval_packet": output_dir / f"discovery_approval_packet_{suffix}.json",
            "discovery_slot_status_board": output_dir / f"discovery_slot_status_board_{suffix}.json",
            "discovery_slot_operator_packet": output_dir / f"discovery_slot_operator_packet_{suffix}.json",
            "discovery_unlock_sequence": output_dir / f"discovery_unlock_sequence_{suffix}.json",
            "discovery_unlock_operator_handoff": output_dir / f"discovery_unlock_operator_handoff_{suffix}.json",
            "discovery_action_queue": output_dir / f"discovery_action_queue_{suffix}.json",
            "discovery_action_state_board": output_dir / f"discovery_action_state_board_{suffix}.json",
            "ai_media_buyer_plan": output_dir / f"ai_media_buyer_plan_{suffix}.json",
            "platform_write_readiness": output_dir / f"platform_write_readiness_{suffix}.json",
            "action_layer": output_dir / f"action_layer_{suffix}.json",
            "guarded_execution": output_dir / f"guarded_execution_{suffix}.json",
            "rollback_monitor": output_dir / f"rollback_monitor_{suffix}.json",
        }
        child_passed = self._ensure_child_artifacts(report_date=report_date, child_paths=child_paths, force=force)
        payload = self.build_payload(report_date=report_date, child_paths=child_paths)
        payload["passed"] = child_passed and bool(payload["loop_readiness"]["decision_engine_ready"])
        payload["autonomy_ready"] = (
            bool(payload["loop_readiness"]["learning_has_closed_outcomes"])
            and bool(payload["loop_readiness"]["platform_write_ready"])
            and payload["summary"]["blocked_intent_count"] == 0
        )

        markdown_path = output_dir / f"media_buyer_loop_{suffix}.md"
        json_path = output_dir / f"media_buyer_loop_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return MediaBuyerLoopResult(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=bool(payload["passed"]),
            child_paths=child_paths,
        )

    def _fresh_payload(self, key: str, path: Path, builder: Any, *, force: bool = False) -> dict[str, Any]:
        # The loop is an aggregation layer. Rebuild child artifacts only when they are missing
        # or when the caller explicitly asks for a forced refresh.
        discovery_dynamic_keys = {
            "approval_feedback_gate",
            "learning_evidence_queue",
            "experiment_execution_queue",
            "experiment_result_ingestion",
            "discovery_learning_packets",
            "discovery_pattern_prior",
            "discovery_learning_state_board",
            "discovery_result_capture_packets",
            "discovery_approval_packet",
            "discovery_slot_status_board",
            "discovery_slot_operator_packet",
            "discovery_unlock_sequence",
            "discovery_unlock_operator_handoff",
            "discovery_action_queue",
            "discovery_action_state_board",
        }
        if force or key in discovery_dynamic_keys or not path.exists():
            builder.build(report_date=self._current_report_date)
        return _load_json(path)

    def _ensure_child_artifacts(self, *, report_date: date, child_paths: dict[str, Path], force: bool = False) -> bool:
        passed = True
        if force or not child_paths["strategy_context"].exists():
            passed = StrategyContextBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_engine"].exists():
            passed = DiscoveryEngineBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["growth_priorities"].exists():
            passed = GrowthPrioritiesBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["creative_dna"].exists():
            passed = CreativeDnaBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["visual_intelligence"].exists():
            passed = VisualIntelligenceBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["creative_clusters"].exists():
            passed = CreativeClustersBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["creative_fatigue"].exists():
            passed = CreativeFatigueBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["dynamic_payback"].exists():
            passed = DynamicPaybackBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["user_quality"].exists():
            passed = UserQualityBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["lifecycle_prediction"].exists():
            passed = LifecyclePredictionBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["decision_engine"].exists():
            passed = DecisionEngineBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["experiment_plan"].exists():
            passed = ExperimentPlanBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["action_feedback"].exists():
            passed = ActionFeedbackBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["learning_memory"].exists():
            passed = LearningMemoryBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["growth_memory_store"].exists():
            passed = GrowthMemoryStoreBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["causal_learning"].exists():
            passed = CausalLearningBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["growth_playbook"].exists():
            passed = GrowthPlaybookBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["learning_evidence_queue"].exists():
            passed = LearningEvidenceQueueBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["experiment_execution_queue"].exists():
            passed = ExperimentExecutionQueueBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["approval_feedback_gate"].exists():
            passed = ApprovalFeedbackGateBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["experiment_result_ingestion"].exists():
            passed = ExperimentResultIngestionBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_experiment_cards"].exists():
            passed = DiscoveryExperimentCardsBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_test_plans"].exists():
            passed = DiscoveryTestPlansBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_execution_packets"].exists():
            passed = DiscoveryExecutionPacketsBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_learning_packets"].exists():
            passed = DiscoveryLearningPacketsBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_pattern_prior"].exists():
            passed = DiscoveryPatternPriorBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_learning_state_board"].exists():
            passed = DiscoveryLearningStateBoardBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_result_capture_packets"].exists():
            passed = DiscoveryResultCapturePacketsBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_approval_packet"].exists():
            passed = DiscoveryApprovalPacketBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_slot_status_board"].exists():
            passed = DiscoverySlotStatusBoardBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_slot_operator_packet"].exists():
            passed = DiscoverySlotOperatorPacketBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_unlock_sequence"].exists():
            passed = DiscoveryUnlockSequenceBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_unlock_operator_handoff"].exists():
            passed = DiscoveryUnlockOperatorHandoffBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_action_queue"].exists():
            passed = DiscoveryActionQueueBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["discovery_action_state_board"].exists():
            passed = DiscoveryActionStateBoardBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["ai_media_buyer_plan"].exists():
            passed = AiMediaBuyerPlanBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["platform_write_readiness"].exists():
            passed = PlatformWriteReadinessBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["action_layer"].exists():
            passed = ActionLayerBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["guarded_execution"].exists():
            passed = GuardedExecutionBuilder(self._settings).build(report_date=report_date).passed and passed
        if force or not child_paths["rollback_monitor"].exists():
            passed = RollbackMonitorBuilder(self._settings).build(report_date=report_date).passed and passed
        return passed

    def build_payload(self, report_date: date, child_paths: dict[str, Path] | None = None) -> dict[str, Any]:
        self._current_report_date = report_date
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        paths = child_paths or {
            "strategy_context": output_dir / f"strategy_context_{suffix}.json",
            "discovery_engine": output_dir / f"discovery_engine_{suffix}.json",
            "growth_priorities": output_dir / f"growth_priorities_{suffix}.json",
            "creative_dna": output_dir / f"creative_dna_{suffix}.json",
            "visual_intelligence": output_dir / f"visual_intelligence_{suffix}.json",
            "creative_clusters": output_dir / f"creative_clusters_{suffix}.json",
            "creative_fatigue": output_dir / f"creative_fatigue_{suffix}.json",
            "dynamic_payback": output_dir / f"dynamic_payback_{suffix}.json",
            "user_quality": output_dir / f"user_quality_{suffix}.json",
            "lifecycle_prediction": output_dir / f"lifecycle_prediction_{suffix}.json",
            "decision_engine": output_dir / f"decision_engine_{suffix}.json",
            "experiment_plan": output_dir / f"experiment_plan_{suffix}.json",
            "action_feedback": output_dir / f"action_feedback_{suffix}.json",
            "learning_memory": output_dir / f"learning_memory_{suffix}.json",
            "growth_memory_store": output_dir / "growth_memory_store_latest.json",
            "causal_learning": output_dir / f"causal_learning_{suffix}.json",
            "growth_playbook": output_dir / f"growth_playbook_{suffix}.json",
            "learning_evidence_queue": output_dir / f"learning_evidence_queue_{suffix}.json",
            "experiment_execution_queue": output_dir / f"experiment_execution_queue_{suffix}.json",
            "approval_feedback_gate": output_dir / f"approval_feedback_gate_{suffix}.json",
            "experiment_result_ingestion": output_dir / f"experiment_result_ingestion_{suffix}.json",
            "discovery_experiment_cards": output_dir / f"discovery_experiment_cards_{suffix}.json",
            "discovery_test_plans": output_dir / f"discovery_test_plans_{suffix}.json",
            "discovery_execution_packets": output_dir / f"discovery_execution_packets_{suffix}.json",
            "discovery_learning_packets": output_dir / f"discovery_learning_packets_{suffix}.json",
            "discovery_pattern_prior": output_dir / f"discovery_pattern_prior_{suffix}.json",
            "discovery_learning_state_board": output_dir / f"discovery_learning_state_board_{suffix}.json",
            "discovery_result_capture_packets": output_dir / f"discovery_result_capture_packets_{suffix}.json",
            "discovery_approval_packet": output_dir / f"discovery_approval_packet_{suffix}.json",
            "discovery_slot_status_board": output_dir / f"discovery_slot_status_board_{suffix}.json",
            "discovery_slot_operator_packet": output_dir / f"discovery_slot_operator_packet_{suffix}.json",
            "discovery_unlock_sequence": output_dir / f"discovery_unlock_sequence_{suffix}.json",
            "discovery_unlock_operator_handoff": output_dir / f"discovery_unlock_operator_handoff_{suffix}.json",
            "discovery_action_queue": output_dir / f"discovery_action_queue_{suffix}.json",
            "discovery_action_state_board": output_dir / f"discovery_action_state_board_{suffix}.json",
            "ai_media_buyer_plan": output_dir / f"ai_media_buyer_plan_{suffix}.json",
            "platform_write_readiness": output_dir / f"platform_write_readiness_{suffix}.json",
            "action_layer": output_dir / f"action_layer_{suffix}.json",
            "guarded_execution": output_dir / f"guarded_execution_{suffix}.json",
            "rollback_monitor": output_dir / f"rollback_monitor_{suffix}.json",
        }

        strategy_context_payload = self._fresh_payload("strategy_context", paths["strategy_context"], StrategyContextBuilder(self._settings))
        discovery_payload = self._fresh_payload("discovery_engine", paths["discovery_engine"], DiscoveryEngineBuilder(self._settings))
        growth_payload = self._fresh_payload("growth_priorities", paths["growth_priorities"], GrowthPrioritiesBuilder(self._settings))
        creative_dna_payload = self._fresh_payload("creative_dna", paths["creative_dna"], CreativeDnaBuilder(self._settings))
        visual_payload = self._fresh_payload("visual_intelligence", paths["visual_intelligence"], VisualIntelligenceBuilder(self._settings))
        creative_clusters_payload = self._fresh_payload("creative_clusters", paths["creative_clusters"], CreativeClustersBuilder(self._settings))
        creative_fatigue_payload = self._fresh_payload("creative_fatigue", paths["creative_fatigue"], CreativeFatigueBuilder(self._settings))
        dynamic_payback_payload = self._fresh_payload("dynamic_payback", paths["dynamic_payback"], DynamicPaybackBuilder(self._settings))
        user_quality_payload = self._fresh_payload("user_quality", paths["user_quality"], UserQualityBuilder(self._settings))
        lifecycle_prediction_payload = self._fresh_payload("lifecycle_prediction", paths["lifecycle_prediction"], LifecyclePredictionBuilder(self._settings))
        decision_payload = self._fresh_payload("decision_engine", paths["decision_engine"], DecisionEngineBuilder(self._settings))
        experiment_payload = self._fresh_payload("experiment_plan", paths["experiment_plan"], ExperimentPlanBuilder(self._settings))
        feedback_payload = self._fresh_payload("action_feedback", paths["action_feedback"], ActionFeedbackBuilder(self._settings))
        learning_payload = self._fresh_payload("learning_memory", paths["learning_memory"], LearningMemoryBuilder(self._settings))
        growth_memory_payload = self._fresh_payload("growth_memory_store", paths["growth_memory_store"], GrowthMemoryStoreBuilder(self._settings))
        causal_learning_payload = self._fresh_payload("causal_learning", paths["causal_learning"], CausalLearningBuilder(self._settings))
        growth_playbook_payload = self._fresh_payload("growth_playbook", paths["growth_playbook"], GrowthPlaybookBuilder(self._settings))
        learning_evidence_payload = self._fresh_payload("learning_evidence_queue", paths["learning_evidence_queue"], LearningEvidenceQueueBuilder(self._settings))
        execution_queue_payload = self._fresh_payload("experiment_execution_queue", paths["experiment_execution_queue"], ExperimentExecutionQueueBuilder(self._settings))
        approval_gate_payload = self._fresh_payload("approval_feedback_gate", paths["approval_feedback_gate"], ApprovalFeedbackGateBuilder(self._settings))
        result_ingestion_payload = self._fresh_payload("experiment_result_ingestion", paths["experiment_result_ingestion"], ExperimentResultIngestionBuilder(self._settings))
        discovery_cards_payload = self._fresh_payload("discovery_experiment_cards", paths["discovery_experiment_cards"], DiscoveryExperimentCardsBuilder(self._settings))
        discovery_test_plans_payload = self._fresh_payload("discovery_test_plans", paths["discovery_test_plans"], DiscoveryTestPlansBuilder(self._settings))
        discovery_execution_packets_payload = self._fresh_payload("discovery_execution_packets", paths["discovery_execution_packets"], DiscoveryExecutionPacketsBuilder(self._settings))
        discovery_learning_packets_payload = self._fresh_payload("discovery_learning_packets", paths["discovery_learning_packets"], DiscoveryLearningPacketsBuilder(self._settings))
        discovery_pattern_prior_payload = self._fresh_payload("discovery_pattern_prior", paths["discovery_pattern_prior"], DiscoveryPatternPriorBuilder(self._settings))
        discovery_learning_state_board_payload = self._fresh_payload("discovery_learning_state_board", paths["discovery_learning_state_board"], DiscoveryLearningStateBoardBuilder(self._settings))
        discovery_result_capture_packets_payload = self._fresh_payload("discovery_result_capture_packets", paths["discovery_result_capture_packets"], DiscoveryResultCapturePacketsBuilder(self._settings))
        discovery_approval_packet_payload = self._fresh_payload("discovery_approval_packet", paths["discovery_approval_packet"], DiscoveryApprovalPacketBuilder(self._settings))
        discovery_slot_status_board_payload = self._fresh_payload("discovery_slot_status_board", paths["discovery_slot_status_board"], DiscoverySlotStatusBoardBuilder(self._settings))
        discovery_slot_operator_packet_payload = self._fresh_payload("discovery_slot_operator_packet", paths["discovery_slot_operator_packet"], DiscoverySlotOperatorPacketBuilder(self._settings))
        discovery_unlock_sequence_payload = self._fresh_payload("discovery_unlock_sequence", paths["discovery_unlock_sequence"], DiscoveryUnlockSequenceBuilder(self._settings))
        discovery_unlock_operator_handoff_payload = self._fresh_payload("discovery_unlock_operator_handoff", paths["discovery_unlock_operator_handoff"], DiscoveryUnlockOperatorHandoffBuilder(self._settings))
        discovery_action_queue_payload = self._fresh_payload("discovery_action_queue", paths["discovery_action_queue"], DiscoveryActionQueueBuilder(self._settings))
        discovery_action_state_board_payload = self._fresh_payload("discovery_action_state_board", paths["discovery_action_state_board"], DiscoveryActionStateBoardBuilder(self._settings))
        action_plan_payload = self._fresh_payload("ai_media_buyer_plan", paths["ai_media_buyer_plan"], AiMediaBuyerPlanBuilder(self._settings))
        platform_write_payload = self._fresh_payload("platform_write_readiness", paths["platform_write_readiness"], PlatformWriteReadinessBuilder(self._settings))
        action_layer_payload = self._fresh_payload("action_layer", paths["action_layer"], ActionLayerBuilder(self._settings))
        guarded_execution_payload = self._fresh_payload("guarded_execution", paths["guarded_execution"], GuardedExecutionBuilder(self._settings))
        rollback_monitor_payload = self._fresh_payload("rollback_monitor", paths["rollback_monitor"], RollbackMonitorBuilder(self._settings))

        decision_items = list(decision_payload.get("items") or [])
        experiments = list(experiment_payload.get("experiments") or [])
        feedback_items = list(feedback_payload.get("items") or [])
        growth_items = list(growth_payload.get("items") or [])
        discovery_projects = list(discovery_payload.get("projects") or [])
        creative_dna_summary = creative_dna_payload.get("summary") or {}
        creative_dna_items = list(creative_dna_payload.get("items") or [])
        creative_dna_count = int(creative_dna_summary.get("creative_count") or len(creative_dna_items))
        visual_summary = visual_payload.get("summary") or {}
        visual_blocking_gaps = list(visual_payload.get("blocking_gaps") or [])
        creative_clusters = list(creative_clusters_payload.get("clusters") or [])
        fatigue_items = list(creative_fatigue_payload.get("items") or [])
        dynamic_payback_items = list(dynamic_payback_payload.get("items") or [])
        user_quality_summary = user_quality_payload.get("summary") or {}
        user_quality_items = list(user_quality_payload.get("items") or [])
        lifecycle_summary = lifecycle_prediction_payload.get("summary") or {}
        lifecycle_items = list(lifecycle_prediction_payload.get("items") or [])
        action_plan_items = list(action_plan_payload.get("actions") or [])
        learning_records = list(learning_payload.get("records") or [])
        closed_learnings = list(learning_payload.get("closed_learnings") or [])
        learning_gaps = list(learning_payload.get("learning_gaps") or [])
        long_term_memory = growth_memory_payload.get("summary") or {}
        causal_summary = causal_learning_payload.get("summary") or {}
        causal_hypotheses = list(causal_learning_payload.get("hypotheses") or [])
        next_validation_actions = list(causal_learning_payload.get("next_validation_actions") or [])
        playbook_summary = growth_playbook_payload.get("summary") or {}
        playbook_rules = list(growth_playbook_payload.get("decision_rules") or [])
        playbook_candidates = list(growth_playbook_payload.get("candidate_rules") or [])
        evidence_queue_summary = learning_evidence_payload.get("summary") or {}
        evidence_queue_items = list(learning_evidence_payload.get("queue_items") or [])
        execution_queue_summary = execution_queue_payload.get("summary") or {}
        execution_queue_items = list(execution_queue_payload.get("queue_items") or [])
        approval_gate_summary = approval_gate_payload.get("summary") or {}
        approval_items = list(approval_gate_payload.get("approval_items") or [])
        result_ingestion_summary = result_ingestion_payload.get("summary") or {}
        result_rows = list(result_ingestion_payload.get("result_rows") or [])
        discovery_cards_summary = discovery_cards_payload.get("summary") or {}
        discovery_cards = list(discovery_cards_payload.get("cards") or [])
        discovery_test_plans_summary = discovery_test_plans_payload.get("summary") or {}
        discovery_test_plans = list(discovery_test_plans_payload.get("plans") or [])
        discovery_execution_packets_summary = discovery_execution_packets_payload.get("summary") or {}
        discovery_execution_packets = list(discovery_execution_packets_payload.get("packets") or [])
        discovery_learning_packets_summary = discovery_learning_packets_payload.get("summary") or {}
        discovery_learning_packets = list(discovery_learning_packets_payload.get("packets") or [])
        discovery_pattern_prior_summary = discovery_pattern_prior_payload.get("summary") or {}
        discovery_pattern_priors = list(discovery_pattern_prior_payload.get("priors") or [])
        discovery_learning_state_board_summary = discovery_learning_state_board_payload.get("summary") or {}
        discovery_learning_state_packets = list(discovery_learning_state_board_payload.get("packets") or [])
        discovery_result_capture_packets_summary = discovery_result_capture_packets_payload.get("summary") or {}
        discovery_result_capture_packets = list(discovery_result_capture_packets_payload.get("packets") or [])
        discovery_approval_packet_summary = discovery_approval_packet_payload.get("summary") or {}
        discovery_approval_packets = list(discovery_approval_packet_payload.get("packets") or [])
        discovery_slot_status_board_summary = discovery_slot_status_board_payload.get("summary") or {}
        discovery_slot_status_rows = list(discovery_slot_status_board_payload.get("rows") or [])
        discovery_slot_operator_packet_summary = discovery_slot_operator_packet_payload.get("summary") or {}
        discovery_slot_operator_packets = list(discovery_slot_operator_packet_payload.get("packets") or [])
        discovery_unlock_sequence_summary = discovery_unlock_sequence_payload.get("summary") or {}
        discovery_unlock_sequences = list(discovery_unlock_sequence_payload.get("sequences") or [])
        discovery_unlock_operator_handoff_summary = discovery_unlock_operator_handoff_payload.get("summary") or {}
        discovery_unlock_operator_handoffs = list(discovery_unlock_operator_handoff_payload.get("handoffs") or [])
        discovery_action_queue_summary = discovery_action_queue_payload.get("summary") or {}
        discovery_action_queue_items = list(discovery_action_queue_payload.get("actions") or [])
        discovery_action_state_board_summary = discovery_action_state_board_payload.get("summary") or {}
        discovery_action_state_items = list(discovery_action_state_board_payload.get("items") or [])
        platform_write_summary = platform_write_payload.get("summary") or {}
        platform_gates = platform_write_payload.get("platforms") or {}
        execution_intents = list(action_layer_payload.get("execution_intents") or [])
        guarded_summary = guarded_execution_payload.get("summary") or {}
        execution_attempts = list(guarded_execution_payload.get("attempts") or [])
        rollback_summary = rollback_monitor_payload.get("summary") or {}
        rollback_monitors = list(rollback_monitor_payload.get("monitors") or [])
        strategy_context_summary = strategy_context_payload.get("summary") or {}
        strategy_priorities = list(strategy_context_payload.get("priorities") or [])
        strategy_guardrails = list(strategy_context_payload.get("guardrails") or [])
        strategy_missing_fields = list(strategy_context_payload.get("missing_fields") or [])
        ready_intents = [item for item in execution_intents if item.get("execution_status") == "ready_for_approval"]
        blocked_intents = [item for item in execution_intents if item.get("execution_status") == "blocked"]

        small_scale_items = [item for item in decision_items if item.get("decision") == "small_scale_up"]
        blocked_items = [item for item in decision_items if item.get("decision") == "data_blocked"]
        fatigue_risk_items = [item for item in fatigue_items if item.get("status") == "fatigue"]
        loop_readiness = {
            "observation_ready": bool(growth_items),
            "strategy_context_ready": bool(strategy_context_payload.get("strategy_input_ready")),
            "discovery_ready": bool(discovery_payload.get("passed")),
            "creative_intelligence_ready": creative_dna_count > 0,
            "visual_intelligence_ready": bool(visual_summary.get("visual_intelligence_ready")),
            "fatigue_ready": bool(fatigue_items),
            "user_quality_ready": bool(user_quality_payload.get("passed")) and bool(user_quality_items),
            "lifecycle_prediction_ready": bool(lifecycle_prediction_payload.get("passed")) and bool(lifecycle_items),
            "prediction_ready": bool(dynamic_payback_items) and bool(user_quality_payload.get("passed")) and bool(lifecycle_prediction_payload.get("passed")),
            "decision_engine_ready": bool(decision_payload.get("passed")) and not blocked_items,
            "experiment_ready": bool(experiment_payload.get("passed")),
            "feedback_ready": bool(feedback_payload.get("passed")),
            "learning_memory_ready": bool(learning_payload.get("passed")),
            "growth_memory_store_ready": bool(growth_memory_payload.get("passed")),
            "causal_learning_ready": bool(causal_learning_payload.get("passed")),
            "growth_playbook_ready": bool(growth_playbook_payload.get("passed")),
            "learning_evidence_queue_ready": bool(learning_evidence_payload.get("passed")),
            "experiment_execution_queue_ready": bool(execution_queue_payload.get("passed")),
            "approval_feedback_gate_ready": bool(approval_gate_payload.get("passed")),
            "experiment_result_ingestion_ready": bool(result_ingestion_payload.get("passed")),
            "discovery_experiment_cards_ready": bool(discovery_cards_payload.get("passed")),
            "discovery_test_plans_ready": bool(discovery_test_plans_payload.get("passed")),
            "discovery_execution_packets_ready": bool(discovery_execution_packets_payload.get("passed")),
            "discovery_learning_packets_ready": bool(discovery_learning_packets_payload.get("passed")),
            "discovery_pattern_prior_ready": bool(discovery_pattern_prior_payload.get("passed")),
            "discovery_learning_state_board_ready": bool(discovery_learning_state_board_payload.get("passed")),
            "discovery_result_capture_packets_ready": bool(discovery_result_capture_packets_payload.get("passed")),
            "discovery_approval_packet_ready": bool(discovery_approval_packet_payload.get("passed")),
            "discovery_slot_status_board_ready": bool(discovery_slot_status_board_payload.get("passed")),
            "discovery_slot_operator_packet_ready": bool(discovery_slot_operator_packet_payload.get("passed")),
            "discovery_unlock_sequence_ready": bool(discovery_unlock_sequence_payload.get("passed")),
            "discovery_unlock_operator_handoff_ready": bool(discovery_unlock_operator_handoff_payload.get("passed")),
            "discovery_action_queue_ready": bool(discovery_action_queue_payload.get("passed")),
            "discovery_action_state_board_ready": bool(discovery_action_state_board_payload.get("passed")),
            "platform_write_readiness_ready": bool(platform_write_payload.get("passed")),
            "action_layer_ready": bool(action_layer_payload.get("passed")),
            "guarded_execution_ready": bool(guarded_execution_payload.get("passed")),
            "rollback_monitor_ready": bool(rollback_monitor_payload.get("passed")),
            "learning_has_closed_outcomes": bool(closed_learnings),
            "platform_write_ready": False,
            "action_mode": "dry_run_approval_gated" if action_layer_payload.get("passed") else "human_review_only",
        }

        payload = {
            "report_date": report_date.isoformat(),
            "window_start": decision_payload.get("window_start") or growth_payload.get("window_start") or discovery_payload.get("window_start"),
            "window_end": decision_payload.get("window_end") or growth_payload.get("window_end") or discovery_payload.get("window_end"),
            "system_positioning": "AI Autonomous Media Buyer",
            "mode": "audited_growth_loop",
            "passed": False,
            "autonomy_ready": False,
            "loop_readiness": loop_readiness,
            "summary": {
                "growth_signal_count": len(growth_items),
                "strategy_priority_count": int(strategy_context_summary.get("priority_count") or len(strategy_priorities)),
                "strategy_active_priority_count": int(strategy_context_summary.get("active_priority_count") or 0),
                "strategy_guardrail_count": int(strategy_context_summary.get("guardrail_count") or len(strategy_guardrails)),
                "strategy_missing_field_count": int(strategy_context_summary.get("missing_field_count") or len(strategy_missing_fields)),
                "decision_count": len(decision_items),
                "small_scale_up_count": len(small_scale_items),
                "data_blocked_count": len(blocked_items),
                "experiment_count": len(experiments),
                "feedback_count": len(feedback_items),
                "learning_record_count": len(learning_records),
                "closed_learning_count": len(closed_learnings),
                "learning_gap_count": len(learning_gaps),
                "long_term_memory_records": int(long_term_memory.get("total_records") or 0),
                "long_term_pending_records": int(long_term_memory.get("pending_records") or 0),
                "long_term_closed_records": int(long_term_memory.get("closed_records") or 0),
                "long_term_closed_discovery_pattern_count": int(long_term_memory.get("closed_discovery_pattern_count") or 0),
                "long_term_pending_discovery_pattern_count": int(long_term_memory.get("pending_discovery_pattern_count") or 0),
                "causal_hypothesis_count": int(causal_summary.get("hypothesis_count") or len(causal_hypotheses)),
                "causal_validated_count": int(causal_summary.get("validated_count") or 0),
                "causal_invalidated_count": int(causal_summary.get("invalidated_count") or 0),
                "causal_pending_outcome_count": int(causal_summary.get("pending_outcome_count") or 0),
                "causal_needs_execution_confirmation_count": int(causal_summary.get("needs_execution_confirmation_count") or 0),
                "playbook_decision_rule_count": int(playbook_summary.get("decision_rule_count") or len(playbook_rules)),
                "playbook_validated_rule_count": int(playbook_summary.get("validated_rule_count") or 0),
                "playbook_invalidated_rule_count": int(playbook_summary.get("invalidated_rule_count") or 0),
                "playbook_candidate_rule_count": int(playbook_summary.get("candidate_rule_count") or len(playbook_candidates)),
                "playbook_missing_evidence_count": int(playbook_summary.get("missing_evidence_count") or 0),
                "playbook_discovery_pattern_candidate_count": sum(
                    1 for item in playbook_candidates if str(item.get("memory_scope") or "") == "discovery_pattern"
                ),
                "playbook_discovery_pattern_rule_count": sum(
                    1 for item in playbook_rules if str(item.get("memory_scope") or "") == "discovery_pattern"
                ),
                "learning_evidence_queue_count": int(evidence_queue_summary.get("queue_item_count") or len(evidence_queue_items)),
                "learning_evidence_critical_count": int(evidence_queue_summary.get("critical_count") or 0),
                "learning_evidence_high_count": int(evidence_queue_summary.get("high_count") or 0),
                "learning_evidence_post_metric_needed_count": int(evidence_queue_summary.get("post_metric_needed_count") or 0),
                "learning_evidence_capture_needed_count": int(evidence_queue_summary.get("evidence_capture_needed_count") or 0),
                "execution_queue_item_count": int(execution_queue_summary.get("queue_item_count") or len(execution_queue_items)),
                "execution_queue_platform_blocked_count": int(execution_queue_summary.get("platform_write_blocked_count") or 0),
                "execution_queue_manual_approval_required_count": int(execution_queue_summary.get("manual_approval_required_count") or 0),
                "execution_queue_manual_required_count": int(execution_queue_summary.get("manual_execution_required_count") or 0),
                "execution_queue_manual_execution_approved_count": int(execution_queue_summary.get("manual_execution_approved_count") or 0),
                "execution_queue_waiting_result_count": int(execution_queue_summary.get("waiting_result_capture_count") or 0),
                "execution_queue_completed_count": int(execution_queue_summary.get("completed_count") or 0),
                "approval_item_count": int(approval_gate_summary.get("approval_item_count") or len(approval_items)),
                "approval_blocked_count": int(approval_gate_summary.get("approval_blocked_count") or 0),
                "ready_for_manual_approval_count": int(approval_gate_summary.get("ready_for_manual_approval_count") or 0),
                "ready_for_manual_execution_count": int(approval_gate_summary.get("ready_for_manual_execution_count") or 0),
                "awaiting_result_capture_count": int(approval_gate_summary.get("awaiting_result_capture_count") or 0),
                "approval_closed_count": int(approval_gate_summary.get("closed_count") or 0),
                "result_row_count": int(result_ingestion_summary.get("result_row_count") or len(result_rows)),
                "closed_result_count": int(result_ingestion_summary.get("closed_result_count") or 0),
                "needs_manual_result_input_count": int(result_ingestion_summary.get("needs_manual_input_count") or 0),
                "result_approval_blocked_count": int(result_ingestion_summary.get("approval_blocked_count") or 0),
                "discovery_experiment_card_count": int(discovery_cards_summary.get("card_count") or len(discovery_cards)),
                "discovery_test_plan_count": int(discovery_test_plans_summary.get("plan_count") or len(discovery_test_plans)),
                "discovery_test_plan_slot_count": int(discovery_test_plans_summary.get("slot_count") or sum(len(item.get("variant_slots") or []) for item in discovery_test_plans)),
                "discovery_execution_packet_count": int(discovery_execution_packets_summary.get("packet_count") or len(discovery_execution_packets)),
                "discovery_execution_packet_slot_count": int(discovery_execution_packets_summary.get("slot_count") or sum(len(item.get("slot_packets") or []) for item in discovery_execution_packets)),
                "discovery_learning_packet_count": int(discovery_learning_packets_summary.get("packet_count") or len(discovery_learning_packets)),
                "discovery_learning_slot_count": int(discovery_learning_packets_summary.get("slot_question_count") or sum(len(item.get("slot_learning_packets") or []) for item in discovery_learning_packets)),
                "discovery_pattern_prior_count": int(discovery_pattern_prior_summary.get("prior_count") or len(discovery_pattern_priors)),
                "discovery_pattern_prior_project_count": int(discovery_pattern_prior_summary.get("project_count") or 0),
                "discovery_pattern_prior_approval_pending_count": int(discovery_pattern_prior_summary.get("approval_pending_prior_count") or 0),
                "discovery_pattern_prior_result_capture_pending_count": int(discovery_pattern_prior_summary.get("result_capture_pending_prior_count") or 0),
                "discovery_learning_awaiting_approval_count": int(discovery_learning_state_board_summary.get("awaiting_approval_count") or 0),
                "discovery_learning_awaiting_execution_count": int(discovery_learning_state_board_summary.get("awaiting_execution_count") or 0),
                "discovery_learning_awaiting_result_count": int(discovery_learning_state_board_summary.get("awaiting_result_count") or 0),
                "discovery_learning_ready_for_pattern_memory_count": int(discovery_learning_state_board_summary.get("ready_for_pattern_memory_count") or 0),
                "discovery_learning_pattern_memory_closed_count": int(discovery_learning_state_board_summary.get("pattern_memory_closed_count") or 0),
                "discovery_result_capture_packet_count": int(discovery_result_capture_packets_summary.get("packet_count") or len(discovery_result_capture_packets)),
                "discovery_result_capture_slot_count": int(discovery_result_capture_packets_summary.get("slot_capture_count") or sum(len(item.get("slot_capture_packets") or []) for item in discovery_result_capture_packets)),
                "discovery_approval_packet_count": int(discovery_approval_packet_summary.get("packet_count") or len(discovery_approval_packets)),
                "discovery_approval_manual_ready_count": int(discovery_approval_packet_summary.get("manual_approval_ready_count") or 0),
                "discovery_approval_unexpected_blocker_count": int(discovery_approval_packet_summary.get("unexpected_blocker_count") or 0),
                "discovery_approval_approved_count": int(discovery_approval_packet_summary.get("approved_for_manual_execution_count") or 0),
                "discovery_approval_pending_input_count": int(discovery_approval_packet_summary.get("pending_input_count") or 0),
                "discovery_slot_status_count": int(discovery_slot_status_board_summary.get("slot_count") or len(discovery_slot_status_rows)),
                "discovery_slot_approval_blocked_count": int(discovery_slot_status_board_summary.get("approval_blocked_count") or 0),
                "discovery_slot_ready_to_execute_count": int(discovery_slot_status_board_summary.get("ready_to_execute_count") or 0),
                "discovery_slot_awaiting_result_count": int(discovery_slot_status_board_summary.get("awaiting_result_count") or 0),
                "discovery_slot_learned_count": int(discovery_slot_status_board_summary.get("learned_count") or 0),
                "discovery_slot_operator_packet_count": int(discovery_slot_operator_packet_summary.get("packet_count") or len(discovery_slot_operator_packets)),
                "discovery_unlock_sequence_count": int(discovery_unlock_sequence_summary.get("sequence_count") or len(discovery_unlock_sequences)),
                "discovery_unlock_operator_handoff_count": int(discovery_unlock_operator_handoff_summary.get("handoff_count") or len(discovery_unlock_operator_handoffs)),
                "discovery_action_queue_count": int(discovery_action_queue_summary.get("action_count") or len(discovery_action_queue_items)),
                "discovery_action_state_item_count": int(discovery_action_state_board_summary.get("item_count") or len(discovery_action_state_items)),
                "platform_write_global_enabled": bool(platform_write_payload.get("global_write_enabled")),
                "platform_write_ready_platform_count": int(platform_write_summary.get("ready_platform_count") or 0),
                "platform_write_blocked_platform_count": int(platform_write_summary.get("blocked_platform_count") or 0),
                "discovery_project_count": len(discovery_projects),
                "creative_dna_count": creative_dna_count,
                "visual_asset_ready_count": int(visual_summary.get("visual_asset_ready_count") or 0),
                "visual_proxy_only_count": int(visual_summary.get("proxy_only_count") or 0),
                "visual_low_confidence_count": int(visual_summary.get("low_confidence_count") or 0),
                "visual_blocking_gap_count": len(visual_blocking_gaps),
                "creative_cluster_count": len(creative_clusters),
                "fatigue_signal_count": len(fatigue_risk_items),
                "dynamic_payback_project_count": len(dynamic_payback_items),
                "user_quality_project_count": int(user_quality_summary.get("project_count") or len(user_quality_items)),
                "user_quality_high_count": int(user_quality_summary.get("high_quality_count") or 0),
                "user_quality_mixed_count": int(user_quality_summary.get("mixed_quality_count") or 0),
                "user_quality_gap_count": int(user_quality_summary.get("quality_data_gap_count") or 0),
                "user_quality_missing_field_count": int(user_quality_summary.get("missing_quality_field_count") or 0),
                "lifecycle_project_count": int(lifecycle_summary.get("project_count") or len(lifecycle_items)),
                "lifecycle_scale_candidate_count": int(lifecycle_summary.get("scale_candidate_count") or 0),
                "lifecycle_validation_count": int(lifecycle_summary.get("validation_count") or 0),
                "lifecycle_fatigue_risk_count": int(lifecycle_summary.get("fatigue_risk_count") or 0),
                "lifecycle_data_gap_count": int(lifecycle_summary.get("data_gap_count") or 0),
                "lifecycle_learning_required_count": int(lifecycle_summary.get("learning_required_count") or 0),
                "action_plan_count": len(action_plan_items),
                "discovery_action_plan_count": sum(
                    1 for item in action_plan_items if str(item.get("source") or "") == "discovery_engine"
                ),
                "execution_intent_count": len(execution_intents),
                "discovery_execution_intent_count": sum(
                    1
                    for item in execution_intents
                    if str(((item.get("source_action") or {}).get("source") or "")) == "discovery_engine"
                ),
                "ready_for_approval_count": len(ready_intents),
                "blocked_intent_count": len(blocked_intents),
                "execution_attempt_count": int(guarded_summary.get("attempt_count") or len(execution_attempts)),
                "execution_attempt_blocked_count": int(guarded_summary.get("blocked_count") or 0),
                "execution_attempt_dry_run_ready_count": int(guarded_summary.get("dry_run_ready_count") or 0),
                "execution_attempt_executed_count": int(guarded_summary.get("executed_count") or 0),
                "rollback_monitor_count": int(rollback_summary.get("monitor_count") or len(rollback_monitors)),
                "rollback_required_count": int(rollback_summary.get("rollback_required_count") or 0),
                "rollback_monitoring_count": int(rollback_summary.get("monitoring_count") or 0),
                "rollback_passed_count": int(rollback_summary.get("passed_count") or 0),
                "rollback_not_started_count": int(rollback_summary.get("not_started_count") or 0),
            },
            "north_star_mapping": self._north_star_mapping(
                strategy_context_payload=strategy_context_payload,
                growth_payload=growth_payload,
                discovery_payload=discovery_payload,
                creative_dna_payload=creative_dna_payload,
                visual_payload=visual_payload,
                creative_clusters_payload=creative_clusters_payload,
                creative_fatigue_payload=creative_fatigue_payload,
                dynamic_payback_payload=dynamic_payback_payload,
                user_quality_payload=user_quality_payload,
                lifecycle_prediction_payload=lifecycle_prediction_payload,
                decision_payload=decision_payload,
                experiment_payload=experiment_payload,
                feedback_payload=feedback_payload,
                learning_payload=learning_payload,
                growth_memory_payload=growth_memory_payload,
                causal_learning_payload=causal_learning_payload,
                growth_playbook_payload=growth_playbook_payload,
                action_plan_payload=action_plan_payload,
                action_layer_payload=action_layer_payload,
                loop_readiness=loop_readiness,
            ),
            "strategy_context": {
                "summary": strategy_context_summary,
                "strategy_input_ready": bool(strategy_context_payload.get("strategy_input_ready")),
                "source_file": strategy_context_payload.get("source_file", ""),
                "priorities": [_strategy_priority_digest(item) for item in strategy_priorities[:12]],
                "guardrails": strategy_guardrails[:12],
                "missing_fields": strategy_missing_fields,
                "suggested_template_file": strategy_context_payload.get("suggested_template_file", ""),
            },
            "top_decisions": [_decision_digest(item) for item in decision_items[:12]],
            "top_creative_patterns": [_cluster_digest(item) for item in creative_clusters[:12]],
            "visual_intelligence": {
                "summary": visual_summary,
                "blocking_gaps": visual_blocking_gaps[:12],
            },
            "fatigue_watchlist": [_fatigue_digest(item) for item in fatigue_items[:12]],
            "user_quality": [_user_quality_digest(item) for item in user_quality_items[:12]],
            "lifecycle_prediction": [_lifecycle_digest(item) for item in lifecycle_items[:12]],
            "next_experiments": [_experiment_digest(item) for item in experiments[:12]],
            "learning_queue": [_feedback_digest(item) for item in feedback_items[:12]],
            "learning_gaps": [_learning_gap_digest(item) for item in learning_gaps[:12]],
            "causal_hypotheses": [_causal_hypothesis_digest(item) for item in causal_hypotheses[:12]],
            "next_validation_actions": [_validation_action_digest(item) for item in next_validation_actions[:12]],
            "growth_playbook": {
                "summary": playbook_summary,
                "decision_rules": [_playbook_rule_digest(item) for item in playbook_rules[:12]],
                "candidate_rules": [_playbook_candidate_digest(item) for item in playbook_candidates[:12]],
            },
            "discovery_pattern_memory": {
                "closed_patterns": [
                    _discovery_pattern_memory_digest(item)
                    for item in (growth_memory_payload.get("closed_discovery_patterns") or [])[:20]
                ],
                "pending_patterns": [
                    _discovery_pattern_memory_digest(item)
                    for item in (growth_memory_payload.get("pending_discovery_patterns") or [])[:20]
                ],
            },
            "learning_evidence_queue": [_learning_evidence_digest(item) for item in evidence_queue_items[:12]],
            "experiment_execution_queue": [_execution_queue_digest(item) for item in execution_queue_items[:12]],
            "approval_feedback_gate": [_approval_gate_digest(item) for item in approval_items[:12]],
            "experiment_result_rows": [_result_row_digest(item) for item in result_rows[:12]],
            "discovery_experiment_briefs": [
                _discovery_experiment_digest(item)
                for item in experiments
                if str(item.get("experiment_type") or "") == "discovery_creative_test_plan"
            ][:12],
            "discovery_experiment_cards": [_discovery_card_digest(item) for item in discovery_cards[:12]],
            "discovery_test_plans": [_discovery_test_plan_digest(item) for item in discovery_test_plans[:12]],
            "discovery_execution_packets": [_discovery_execution_packet_digest(item) for item in discovery_execution_packets[:12]],
            "discovery_learning_packets": [_discovery_learning_packet_digest(item) for item in discovery_learning_packets[:12]],
            "discovery_pattern_prior": [_discovery_pattern_prior_digest(item) for item in discovery_pattern_priors[:20]],
            "discovery_learning_state_board": [_discovery_learning_state_digest(item) for item in discovery_learning_state_packets[:12]],
            "discovery_result_capture_packets": [_discovery_result_capture_packet_digest(item) for item in discovery_result_capture_packets[:12]],
            "discovery_approval_packets": [_discovery_approval_packet_digest(item) for item in discovery_approval_packets[:12]],
            "discovery_slot_status_board": [_discovery_slot_status_digest(item) for item in discovery_slot_status_rows[:20]],
            "discovery_slot_operator_packets": [_discovery_slot_operator_packet_digest(item) for item in discovery_slot_operator_packets[:12]],
            "discovery_unlock_sequence": [_discovery_unlock_sequence_digest(item) for item in discovery_unlock_sequences[:12]],
            "discovery_unlock_operator_handoff": [_discovery_unlock_operator_handoff_digest(item) for item in discovery_unlock_operator_handoffs[:12]],
            "discovery_action_queue": [_discovery_action_queue_digest(item) for item in discovery_action_queue_items[:20]],
            "discovery_action_state_board": [_discovery_action_state_digest(item) for item in discovery_action_state_items[:20]],
            "experiment_result_files": {
                "manual_input_file": (result_ingestion_payload.get("rules") or {}).get("manual_input_file", ""),
                "template_file": (result_ingestion_payload.get("rules") or {}).get("template_file", ""),
                "slot_manual_input_file": (result_ingestion_payload.get("rules") or {}).get("slot_manual_input_file", ""),
                "manual_approval_input_file": (result_ingestion_payload.get("rules") or {}).get("manual_approval_input_file", ""),
            },
            "platform_write_readiness": [_platform_gate_digest(name, item) for name, item in platform_gates.items()],
            "action_plan": [_action_plan_digest(item) for item in action_plan_items[:12]],
            "execution_intents": [_execution_intent_digest(item) for item in execution_intents[:12]],
            "execution_attempts": [_execution_attempt_digest(item) for item in execution_attempts[:12]],
            "rollback_monitors": [_rollback_monitor_digest(item) for item in rollback_monitors[:12]],
            "guardrails": [
                "Only Decision Engine may emit final action decisions.",
                "Strategy Context is human-owned input; it can bias prioritization only through Decision Engine, not emit actions.",
                "All write actions remain human-review-only until platform execution connectors and rollback gates are verified.",
                "Discovery-stage projects prioritize learning speed and signal quality before ROI maximization.",
                "Every experiment must define success metrics and rollback metrics before execution.",
                "Learning Memory and Growth Memory Store are the source for future learning; unknown outcomes keep learning incomplete.",
                "Causal Learning records hypotheses and evidence gaps; it must not claim causality without post-action outcomes.",
                "Growth Playbook can only promote validated or invalidated causal outcomes into reusable decision rules.",
                "Learning Evidence Queue prioritizes missing outcome evidence only; it does not mutate trackers or execute experiments.",
                "Visual Intelligence must use real visual assets before the system treats hook/emotion labels as visual understanding.",
                "Experiment Execution Queue is dry-run; it separates platform-write blockers, manual execution, and result-capture blockers.",
                "Approval Feedback Gate defines approval and result-capture requirements but does not mutate the action tracker.",
                "Experiment Result Ingestion reads manual result CSVs and turns closed rows into learning evidence without tracker mutation.",
                "Platform Write Readiness must pass before Action Layer can mark platform write intents ready.",
                "Guarded Execution creates dry-run execution attempts only; connector calls remain disabled.",
                "Rollback Monitor emits rollback signals only; rollback execution must pass Decision Engine and Action Layer gates.",
                "Creative DNA and cluster outputs are signal layers; they cannot override Decision Engine decisions.",
                "Fatigue and dynamic payback outputs are risk and prediction layers; they must flow into decisions before action.",
                "Lifecycle Prediction is a signal layer; it predicts stage and potential but does not authorize scaling by itself.",
                "Action Layer is dry-run and approval-gated; platform write is disabled until connectors and rollback gates are verified.",
            ],
            "child_paths": {name: str(path) for name, path in paths.items()},
        }
        payload["next_bottleneck"] = self._next_bottleneck(payload)
        return payload

    @staticmethod
    def _north_star_mapping(
        *,
        strategy_context_payload: dict[str, Any],
        growth_payload: dict[str, Any],
        discovery_payload: dict[str, Any],
        creative_dna_payload: dict[str, Any],
        visual_payload: dict[str, Any],
        creative_clusters_payload: dict[str, Any],
        creative_fatigue_payload: dict[str, Any],
        dynamic_payback_payload: dict[str, Any],
        user_quality_payload: dict[str, Any],
        lifecycle_prediction_payload: dict[str, Any],
        decision_payload: dict[str, Any],
        experiment_payload: dict[str, Any],
        feedback_payload: dict[str, Any],
        learning_payload: dict[str, Any],
        growth_memory_payload: dict[str, Any],
        causal_learning_payload: dict[str, Any],
        growth_playbook_payload: dict[str, Any],
        action_plan_payload: dict[str, Any],
        action_layer_payload: dict[str, Any],
        loop_readiness: dict[str, Any],
    ) -> list[dict[str, Any]]:
        strategy_summary = strategy_context_payload.get("summary") or {}
        strategy_priorities = strategy_context_payload.get("priorities") or []
        strategy_missing_fields = strategy_context_payload.get("missing_fields") or []
        growth_items = growth_payload.get("items") or []
        discovery_projects = discovery_payload.get("projects") or []
        creative_dna_summary = creative_dna_payload.get("summary") or {}
        creative_dna_items = creative_dna_payload.get("items") or []
        creative_dna_count = int(creative_dna_summary.get("creative_count") or len(creative_dna_items))
        visual_summary = visual_payload.get("summary") or {}
        creative_clusters = creative_clusters_payload.get("clusters") or []
        fatigue_items = creative_fatigue_payload.get("items") or []
        fatigue_risk_items = [item for item in fatigue_items if item.get("status") == "fatigue"]
        dynamic_payback_items = dynamic_payback_payload.get("items") or []
        user_quality_items = user_quality_payload.get("items") or []
        user_quality_summary = user_quality_payload.get("summary") or {}
        lifecycle_items = lifecycle_prediction_payload.get("items") or []
        lifecycle_summary = lifecycle_prediction_payload.get("summary") or {}
        decision_items = decision_payload.get("items") or []
        experiments = experiment_payload.get("experiments") or []
        feedback_items = feedback_payload.get("items") or []
        learning_records = learning_payload.get("records") or []
        closed_learnings = learning_payload.get("closed_learnings") or []
        growth_memory_summary = growth_memory_payload.get("summary") or {}
        causal_summary = causal_learning_payload.get("summary") or {}
        playbook_summary = growth_playbook_payload.get("summary") or {}
        action_plan_items = action_plan_payload.get("actions") or []
        execution_intents = action_layer_payload.get("execution_intents") or []
        source_modules = decision_payload.get("source_modules") or {}

        return [
            {
                "capability": "Strategy",
                "status": "active" if strategy_context_payload.get("strategy_input_ready") else ("partial" if strategy_priorities else "missing"),
                "signal_count": int(strategy_summary.get("active_priority_count") or 0),
                "evidence": ["strategy_context"],
                "current_output": (
                    "human-owned strategic priorities and guardrails; "
                    f"ready={strategy_context_payload.get('strategy_input_ready', False)}, "
                    f"missing_fields={len(strategy_missing_fields)}"
                ),
            },
            {
                "capability": "Observation",
                "status": "active" if growth_items else "missing",
                "signal_count": len(growth_items),
                "evidence": ["growth_priorities", "data_quality_audit", "creative_attribution_audit"],
                "current_output": "growth signals, risk signals, quality confidence, attribution confidence",
            },
            {
                "capability": "Reasoning",
                "status": "partial" if decision_items else "missing",
                "signal_count": len(decision_items) + creative_dna_count,
                "evidence": ["decision_engine.top_positive_signals", "decision_engine.top_negative_signals", "creative_dna"],
                "current_output": "explainable entity signals plus creative DNA labels",
            },
            {
                "capability": "Prediction",
                "status": "partial" if source_modules or dynamic_payback_items or lifecycle_items else "missing",
                "signal_count": len(source_modules) + len(dynamic_payback_items) + len(user_quality_items) + len(lifecycle_items),
                "evidence": ["dynamic_payback", "user_quality", "lifecycle_prediction", "payback_targets", "early_prediction", "decision_engine.weights"],
                "current_output": "dynamic payback references, user-quality signals, lifecycle stage, ROI confidence, and scale-potential proxies",
            },
            {
                "capability": "User Quality",
                "status": "active" if user_quality_items else ("partial" if user_quality_payload.get("passed") else "missing"),
                "signal_count": len(user_quality_items),
                "evidence": ["user_quality", "dynamic_payback", "payback_targets"],
                "current_output": (
                    f"CPI, retention, ARPU/ARPPU, and payback quality layer; "
                    f"high={user_quality_summary.get('high_quality_count', 0)}, "
                    f"mixed={user_quality_summary.get('mixed_quality_count', 0)}, "
                    f"gaps={user_quality_summary.get('quality_data_gap_count', 0)}"
                ),
            },
            {
                "capability": "Discovery",
                "status": "active" if discovery_projects else ("partial" if discovery_payload.get("passed") else "missing"),
                "signal_count": len(discovery_projects),
                "evidence": ["discovery_engine", "signal_score", "hypothesis_generator"],
                "current_output": "new-product exploration projects and next hypotheses",
            },
            {
                "capability": "Lifecycle",
                "status": "active" if lifecycle_items else ("partial" if lifecycle_prediction_payload.get("passed") else "missing"),
                "signal_count": len(lifecycle_items),
                "evidence": ["lifecycle_prediction", "creative_fatigue", "creative_clusters", "dynamic_payback", "user_quality"],
                "current_output": (
                    f"project lifecycle stage and growth-potential signals; "
                    f"scale={lifecycle_summary.get('scale_candidate_count', 0)}, "
                    f"validation={lifecycle_summary.get('validation_count', 0)}, "
                    f"fatigue={lifecycle_summary.get('fatigue_risk_count', 0)}, "
                    f"gaps={lifecycle_summary.get('data_gap_count', 0)}"
                ),
            },
            {
                "capability": "Creative DNA",
                "status": "active" if creative_dna_count else "missing",
                "signal_count": creative_dna_count,
                "evidence": ["creative_dna"],
                "current_output": "hook, emotion, pace, UI, structure, confidence, and scalability labels",
            },
            {
                "capability": "Visual Intelligence",
                "status": "active" if visual_summary.get("visual_intelligence_ready") else ("partial" if visual_summary else "missing"),
                "signal_count": int(visual_summary.get("visual_asset_ready_count") or 0),
                "evidence": ["visual_intelligence", "creative_source_readiness", "creative_dna"],
                "current_output": (
                    f"visual asset readiness audit; proxy-only rows={visual_summary.get('proxy_only_count', 0)}, "
                    f"low-confidence labels={visual_summary.get('low_confidence_count', 0)}"
                ),
            },
            {
                "capability": "Cluster",
                "status": "active" if creative_clusters else "missing",
                "signal_count": len(creative_clusters),
                "evidence": ["creative_clusters"],
                "current_output": "creative pattern clusters and variant directions",
            },
            {
                "capability": "Fatigue",
                "status": "active" if fatigue_items else "missing",
                "signal_count": len(fatigue_risk_items),
                "evidence": ["creative_fatigue"],
                "current_output": "CTR, CPI, ROI trend-based fatigue watchlist",
            },
            {
                "capability": "Experiment",
                "status": "active" if experiments else "missing",
                "signal_count": len(experiments),
                "evidence": ["experiment_plan"],
                "current_output": "test plan with success and rollback metrics",
            },
            {
                "capability": "Learning",
                "status": "active" if closed_learnings else ("partial" if learning_records or feedback_items else "missing"),
                "signal_count": int(causal_summary.get("hypothesis_count") or 0) + int(playbook_summary.get("decision_rule_count") or 0),
                "evidence": ["causal_learning", "growth_playbook", "growth_memory_store", "learning_memory", "action_feedback"],
                "current_output": (
                    f"causal hypothesis ledger plus long-term memory store "
                    f"({growth_memory_summary.get('total_records', 0)} memory records, "
                    f"{causal_summary.get('validated_count', 0)} validated hypotheses, "
                    f"{playbook_summary.get('decision_rule_count', 0)} reusable rules)"
                ),
            },
            {
                "capability": "Decision",
                "status": "active" if loop_readiness["decision_engine_ready"] else "blocked",
                "signal_count": len(decision_items),
                "evidence": ["decision_engine"],
                "current_output": "single audited decision enum for each growth object",
            },
            {
                "capability": "Action",
                "status": "dry_run" if execution_intents else "review_only",
                "signal_count": len(execution_intents) or len(action_plan_items),
                "evidence": ["action_layer", "ai_media_buyer_plan", "experiment_plan", "guardrails"],
                "current_output": (
                    "dry-run execution intents with approval gates; "
                    f"discovery-linked intents={sum(1 for item in execution_intents if str(((item.get('source_action') or {}).get('source') or '')) == 'discovery_engine')}; "
                    "no automatic ad-platform write operation"
                ),
            },
        ]

    @staticmethod
    def _next_bottleneck(payload: dict[str, Any]) -> str:
        readiness = payload["loop_readiness"]
        summary = payload["summary"]
        if not readiness["observation_ready"]:
            return "Build reliable observation signals before decision generation."
        if summary["data_blocked_count"]:
            return "Resolve data-blocked decisions before scaling."
        if not readiness["creative_intelligence_ready"]:
            return "Build creative DNA signals before explaining why creatives win."
        if not readiness["prediction_ready"]:
            return "Build dynamic payback and user-quality signals before autonomous budget decisions."
        if not readiness["learning_has_closed_outcomes"]:
            return "Close action outcomes in the feedback tracker so the system can learn from its own decisions."
        if readiness["action_mode"] == "human_review_only":
            return "Add audited platform write connectors before autonomous execution."
        return "Continue the next growth loop iteration."

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# AI Media Buyer Loop | {payload['report_date']}",
            "",
            f"- Window: {payload.get('window_start')} to {payload.get('window_end')}",
            f"- Positioning: {payload['system_positioning']}",
            f"- Mode: {payload['mode']}",
            f"- Passed: {payload['passed']}",
            f"- Autonomy ready: {payload['autonomy_ready']}",
            f"- Action mode: {payload['loop_readiness']['action_mode']}",
            f"- Next bottleneck: {payload['next_bottleneck']}",
            "",
            "## Loop Summary",
            "",
            f"- Strategy context: ready={payload['strategy_context']['strategy_input_ready']} | active priorities={summary['strategy_active_priority_count']} | guardrails={summary['strategy_guardrail_count']} | missing fields={summary['strategy_missing_field_count']}",
            f"- Growth signals: {summary['growth_signal_count']}",
            f"- Creative DNA rows: {summary['creative_dna_count']} | clusters: {summary['creative_cluster_count']} | fatigue risks: {summary['fatigue_signal_count']}",
            f"- Visual intelligence: assets ready={summary['visual_asset_ready_count']} | proxy only={summary['visual_proxy_only_count']} | low confidence={summary['visual_low_confidence_count']} | blocking gaps={summary['visual_blocking_gap_count']}",
            f"- Dynamic payback projects: {summary['dynamic_payback_project_count']} | user quality projects: {summary['user_quality_project_count']} | high: {summary['user_quality_high_count']} | mixed: {summary['user_quality_mixed_count']} | gaps: {summary['user_quality_gap_count']} | missing fields: {summary['user_quality_missing_field_count']}",
            f"- Lifecycle prediction: projects={summary['lifecycle_project_count']} | scale candidates={summary['lifecycle_scale_candidate_count']} | validation={summary['lifecycle_validation_count']} | fatigue risk={summary['lifecycle_fatigue_risk_count']} | data gaps={summary['lifecycle_data_gap_count']} | learning required={summary['lifecycle_learning_required_count']}",
            f"- Review-only action plans: {summary['action_plan_count']}",
            f"- Decisions: {summary['decision_count']} | small scale-up: {summary['small_scale_up_count']} | data blocked: {summary['data_blocked_count']}",
            f"- Experiments: {summary['experiment_count']} | feedback records: {summary['feedback_count']} | closed learning records: {summary['closed_learning_count']}",
            f"- Learning memory records: {summary['learning_record_count']} | learning gaps: {summary['learning_gap_count']}",
            f"- Long-term growth memory: {summary['long_term_memory_records']} records | closed: {summary['long_term_closed_records']} | pending: {summary['long_term_pending_records']} | discovery patterns closed: {summary['long_term_closed_discovery_pattern_count']} | discovery patterns pending: {summary['long_term_pending_discovery_pattern_count']}",
            f"- Causal hypotheses: {summary['causal_hypothesis_count']} | validated: {summary['causal_validated_count']} | invalidated: {summary['causal_invalidated_count']} | pending: {summary['causal_pending_outcome_count']} | needs execution confirmation: {summary['causal_needs_execution_confirmation_count']}",
            f"- Growth playbook: decision rules={summary['playbook_decision_rule_count']} | validated={summary['playbook_validated_rule_count']} | invalidated={summary['playbook_invalidated_rule_count']} | candidates={summary['playbook_candidate_rule_count']} | discovery pattern rules={summary['playbook_discovery_pattern_rule_count']} | discovery pattern candidates={summary['playbook_discovery_pattern_candidate_count']} | missing evidence={summary['playbook_missing_evidence_count']}",
            f"- Discovery pattern prior: priors={summary['discovery_pattern_prior_count']} | projects={summary['discovery_pattern_prior_project_count']} | approval pending={summary['discovery_pattern_prior_approval_pending_count']} | result capture pending={summary['discovery_pattern_prior_result_capture_pending_count']}",
            f"- Learning evidence queue: items={summary['learning_evidence_queue_count']} | critical={summary['learning_evidence_critical_count']} | high={summary['learning_evidence_high_count']} | post metrics needed={summary['learning_evidence_post_metric_needed_count']} | evidence capture needed={summary['learning_evidence_capture_needed_count']}",
            f"- Experiment execution queue: {summary['execution_queue_item_count']} | platform blocked: {summary['execution_queue_platform_blocked_count']} | manual approval required: {summary['execution_queue_manual_approval_required_count']} | manual required: {summary['execution_queue_manual_required_count']} | manual approved: {summary['execution_queue_manual_execution_approved_count']} | waiting result: {summary['execution_queue_waiting_result_count']} | completed: {summary['execution_queue_completed_count']}",
            f"- Approval gate: {summary['approval_item_count']} | blocked: {summary['approval_blocked_count']} | ready manual approval: {summary['ready_for_manual_approval_count']} | ready manual execution: {summary['ready_for_manual_execution_count']} | awaiting result: {summary['awaiting_result_capture_count']} | closed: {summary['approval_closed_count']}",
            f"- Result ingestion: {summary['result_row_count']} | closed: {summary['closed_result_count']} | needs manual input: {summary['needs_manual_result_input_count']} | approval blocked: {summary['result_approval_blocked_count']}",
            f"- Discovery learning state: awaiting approval={summary['discovery_learning_awaiting_approval_count']} | awaiting execution={summary['discovery_learning_awaiting_execution_count']} | awaiting result={summary['discovery_learning_awaiting_result_count']} | ready for pattern memory={summary['discovery_learning_ready_for_pattern_memory_count']} | pattern memory closed={summary['discovery_learning_pattern_memory_closed_count']}",
            f"- Discovery result capture packets: {summary['discovery_result_capture_packet_count']} | slot capture tasks: {summary['discovery_result_capture_slot_count']}",
            f"- Discovery approval packets: {summary['discovery_approval_packet_count']} | manual ready: {summary['discovery_approval_manual_ready_count']} | approved: {summary['discovery_approval_approved_count']} | pending input: {summary['discovery_approval_pending_input_count']} | unexpected blockers: {summary['discovery_approval_unexpected_blocker_count']}",
            f"- Discovery slot status board: slots={summary['discovery_slot_status_count']} | approval blocked={summary['discovery_slot_approval_blocked_count']} | ready to execute={summary['discovery_slot_ready_to_execute_count']} | awaiting result={summary['discovery_slot_awaiting_result_count']} | learned={summary['discovery_slot_learned_count']}",
            f"- Discovery slot operator packets: {summary['discovery_slot_operator_packet_count']}",
            f"- Discovery unlock sequence: {summary['discovery_unlock_sequence_count']}",
            f"- Discovery unlock operator handoff: {summary['discovery_unlock_operator_handoff_count']}",
            f"- Discovery action queue: {summary['discovery_action_queue_count']}",
            f"- Discovery action state board: {summary['discovery_action_state_item_count']}",
            f"- Platform write readiness: global enabled={summary['platform_write_global_enabled']} | ready platforms: {summary['platform_write_ready_platform_count']} | blocked platforms: {summary['platform_write_blocked_platform_count']}",
            f"- Action Layer intents: {summary['execution_intent_count']} | ready for approval: {summary['ready_for_approval_count']} | blocked: {summary['blocked_intent_count']}",
            f"- Guarded execution attempts: {summary['execution_attempt_count']} | dry-run ready: {summary['execution_attempt_dry_run_ready_count']} | blocked: {summary['execution_attempt_blocked_count']} | executed: {summary['execution_attempt_executed_count']}",
            f"- Rollback monitors: {summary['rollback_monitor_count']} | required: {summary['rollback_required_count']} | monitoring: {summary['rollback_monitoring_count']} | passed: {summary['rollback_passed_count']} | not started: {summary['rollback_not_started_count']}",
            f"- Discovery projects: {summary['discovery_project_count']}",
            "",
            "## North Star Mapping",
            "",
            "| Capability | Status | Signals | Evidence | Current output |",
            "|---|---|---:|---|---|",
        ]
        for item in payload["north_star_mapping"]:
            lines.append(
                f"| {item['capability']} | {item['status']} | {item['signal_count']} | "
                f"{', '.join(item['evidence'])} | {item['current_output']} |"
            )

        lines.extend(["", "## Strategy Context", ""])
        strategy = payload["strategy_context"]
        lines.append(f"- Strategy input ready: {strategy['strategy_input_ready']}")
        lines.append(f"- Source file: {strategy['source_file'] or 'not configured'}")
        if strategy["missing_fields"]:
            lines.append(f"- Missing fields: {', '.join(strategy['missing_fields'])}")
            lines.append(f"- Template: {strategy['suggested_template_file']}")
        if not strategy["priorities"]:
            lines.append("- No active strategy priorities loaded.")
        for item in strategy["priorities"]:
            lines.append(
                f"- {item['name']} | {item['status']} | project={item['project']} | "
                f"country={item['country']} | platform={item['platform']} | objective={item['objective']}"
            )
        if strategy["guardrails"]:
            for guardrail in strategy["guardrails"]:
                lines.append(f"- Guardrail: {guardrail}")

        lines.extend(["", "## Top Decisions", ""])
        if not payload["top_decisions"]:
            lines.append("- No decisions generated.")
        for item in payload["top_decisions"]:
            lines.append(
                f"- {item['decision']} | {item['project']} | {item['scope']} | "
                f"score={item['final_growth_score']} | risk={item['final_risk_score']} | confidence={item['confidence']}"
            )

        lines.extend(["", "## Creative Patterns", ""])
        if not payload["top_creative_patterns"]:
            lines.append("- No creative clusters generated.")
        for item in payload["top_creative_patterns"]:
            lines.append(
                f"- {item['cluster_name']} | creatives={item['creative_count']} | ROI={item['avg_roi']} | "
                f"scalability={item['predicted_scalability']} | confidence={item['confidence']}"
            )

        lines.extend(["", "## Visual Intelligence", ""])
        visual_summary = payload["visual_intelligence"]["summary"]
        if not visual_summary:
            lines.append("- No visual intelligence readiness generated.")
        else:
            lines.append(
                f"- Ready: {visual_summary.get('visual_intelligence_ready')} | "
                f"assets ready={visual_summary.get('visual_asset_ready_count')} | "
                f"proxy only={visual_summary.get('proxy_only_count')} | "
                f"low confidence={visual_summary.get('low_confidence_count')}"
            )
        for gap in payload["visual_intelligence"]["blocking_gaps"]:
            lines.append(f"- Gap: {gap}")

        lines.extend(["", "## User Quality", ""])
        if not payload["user_quality"]:
            lines.append("- No user quality rows generated.")
        for item in payload["user_quality"]:
            missing = ", ".join(item["missing_quality_fields"]) if item["missing_quality_fields"] else "none"
            lines.append(
                f"- {item['project']} | {item['quality_status']} | score={item['quality_score']} | "
                f"D7={item['current_d7']} / target={item['dynamic_break_even_d7']} | "
                f"CPI={item['current_cpi']} | D1={item['current_retention_d1']} | missing={missing}"
            )

        lines.extend(["", "## Lifecycle Prediction", ""])
        if not payload["lifecycle_prediction"]:
            lines.append("- No lifecycle prediction rows generated.")
        for item in payload["lifecycle_prediction"]:
            needs = ", ".join(item["next_learning_need"]) if item["next_learning_need"] else "none"
            lines.append(
                f"- {item['project']} | {item['lifecycle_stage']} | potential={item['predicted_growth_potential']} | "
                f"risk={item['lifecycle_risk_score']} | curve={item['predicted_ltv_curve']} | "
                f"decision_input={item['recommended_decision_input']} | need={needs}"
            )

        lines.extend(["", "## Fatigue Watchlist", ""])
        if not payload["fatigue_watchlist"]:
            lines.append("- No fatigue rows generated.")
        for item in payload["fatigue_watchlist"]:
            lines.append(
                f"- {item['status']} | {item['project']} | {item['channel']} | {item['country']} | "
                f"{item['creative_id']} | ROI={item['roi']} | spend={item['spend']}"
            )

        lines.extend(["", "## Next Experiments", ""])
        if not payload["next_experiments"]:
            lines.append("- No experiments generated.")
        for item in payload["next_experiments"]:
            lines.append(f"- {item['experiment_id']} | {item['experiment_type']} | {item['target']} | {item['linked_decision']}")

        lines.extend(["", "## Learning Queue", ""])
        if not payload["learning_queue"]:
            lines.append("- No feedback records loaded.")
        for item in payload["learning_queue"]:
            lines.append(f"- {item['action_id']} | success={item['success']} | {item['target']}")

        lines.extend(["", "## Learning Gaps", ""])
        if not payload["learning_gaps"]:
            lines.append("- No learning gaps loaded.")
        for item in payload["learning_gaps"]:
            missing = ", ".join(item["missing_fields"]) if item["missing_fields"] else "none"
            lines.append(f"- {item['learning_id']} | {item['learning_state']} | missing={missing} | {item['next_update_required']}")

        lines.extend(["", "## Causal Hypotheses", ""])
        if not payload["causal_hypotheses"]:
            lines.append("- No causal hypotheses loaded.")
        for item in payload["causal_hypotheses"]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(
                f"- {item['hypothesis_id']} | {item['causal_state']} | {item['experiment_type']} | "
                f"{item['target']} | confidence={item['confidence']} | missing={missing}"
            )

        lines.extend(["", "## Next Validation Actions", ""])
        if not payload["next_validation_actions"]:
            lines.append("- No validation actions loaded.")
        for item in payload["next_validation_actions"]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(f"- {item['hypothesis_id']} | {item['required_update']} | missing={missing}")

        lines.extend(["", "## Growth Playbook", ""])
        playbook = payload["growth_playbook"]
        playbook_summary = playbook["summary"]
        lines.append(
            f"- Decision rules: {playbook_summary.get('decision_rule_count', 0)} | "
            f"candidates: {playbook_summary.get('candidate_rule_count', 0)} | "
            f"missing evidence: {playbook_summary.get('missing_evidence_count', 0)}"
        )
        if not playbook["decision_rules"]:
            lines.append("- No reusable decision rules yet; causal outcomes are not validated or invalidated.")
        for item in playbook["decision_rules"]:
            lines.append(
                f"- {item['rule_id']} | {item['rule_state']} | {item['decision_signal']} | "
                f"{item['target_signature']} | confidence={item['confidence']}"
            )
        if playbook["candidate_rules"]:
            lines.append("- Candidate rules waiting for evidence:")
        for item in playbook["candidate_rules"]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(f"- {item['candidate_id']} | {item['causal_state']} | {item['target_signature']} | missing={missing}")

        lines.extend(["", "## Learning Evidence Queue", ""])
        if not payload["learning_evidence_queue"]:
            lines.append("- No missing learning evidence queued.")
        for item in payload["learning_evidence_queue"]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            fields = ", ".join(item["required_template_fields"]) if item["required_template_fields"] else "none"
            recommended = ", ".join(item.get("recommended_template_fields") or []) or "none"
            input_file = item.get("manual_input_file") or "none"
            lines.append(
                f"- {item['evidence_id']} | {item['priority']} | {item['target']} | "
                f"approval={item['approval_id'] or 'none'} | missing={missing} | fields={fields} | recommended={recommended} | input={input_file}"
            )

        lines.extend(["", "## Experiment Execution Queue", ""])
        if not payload["experiment_execution_queue"]:
            lines.append("- No experiment execution queue loaded.")
        for item in payload["experiment_execution_queue"]:
            reasons = ", ".join(item["blocked_reasons"]) if item["blocked_reasons"] else "none"
            lines.append(
                f"- {item['queue_id']} | {item['queue_status']} | {item['experiment_type']} | "
                f"{item['target']} | intent={item['matched_intent_id'] or 'none'} | blocked={reasons}"
            )

        lines.extend(["", "## Approval Feedback Gate", ""])
        if not payload["approval_feedback_gate"]:
            lines.append("- No approval feedback gate loaded.")
        for item in payload["approval_feedback_gate"]:
            blockers = ", ".join(item["approval_blockers"]) if item["approval_blockers"] else "none"
            fields = ", ".join(item["required_result_fields"]) if item["required_result_fields"] else "none"
            recommended = ", ".join(item.get("recommended_result_fields") or []) or "none"
            lines.append(
                f"- {item['approval_id']} | {item['approval_status']} | {item['target']} | "
                f"blockers={blockers} | result_fields={fields} | recommended={recommended}"
            )

        lines.extend(["", "## Experiment Result Ingestion", ""])
        result_files = payload["experiment_result_files"]
        lines.append(f"- Parent manual input file: {result_files.get('manual_input_file') or 'not configured'}")
        lines.append(f"- Slot manual input file: {result_files.get('slot_manual_input_file') or 'not configured'}")
        lines.append(f"- Manual approval input file: {result_files.get('manual_approval_input_file') or 'not configured'}")
        lines.append(f"- Template file: {result_files.get('template_file') or 'not generated'}")
        if not payload["experiment_result_rows"]:
            lines.append("- No experiment result rows loaded.")
        for item in payload["experiment_result_rows"]:
            missing = ", ".join(item["missing_result_fields"]) if item["missing_result_fields"] else "none"
            required = ", ".join(item.get("required_result_fields") or []) or "none"
            recommended = ", ".join(item.get("recommended_result_fields") or []) or "none"
            lines.append(
                f"- {item['approval_id']} | {item['result_state']} | {item['target']} | "
                f"success={item['success']} | missing={missing} | required={required} | recommended={recommended}"
            )

        lines.extend(["", "## Discovery Result Capture Packets", ""])
        if not payload["discovery_result_capture_packets"]:
            lines.append("- No discovery result capture packets loaded.")
        for item in payload["discovery_result_capture_packets"]:
            required = ", ".join(item["required_parent_fields"]) if item["required_parent_fields"] else "none"
            recommended = ", ".join(item.get("recommended_parent_fields") or []) or "none"
            slot_input = item.get("slot_manual_input_file") or "none"
            lines.append(
                f"- {item['capture_packet_id']} | {item['target']} | "
                f"approval={item['approval_id'] or 'none'} | required={required} | recommended={recommended} | slot_input={slot_input}"
            )

        lines.extend(["", "## Discovery Learning State Board", ""])
        if not payload["discovery_learning_state_board"]:
            lines.append("- No discovery learning state packets loaded.")
        for item in payload["discovery_learning_state_board"]:
            lines.append(
                f"- {item['learning_state_packet_id']} | {item['target']} | state={item['learning_state']} | "
                f"parent={item['parent_result_state'] or 'missing'} | next={item['next_update_required']}"
            )

        lines.extend(["", "## Discovery Approval Packets", ""])
        if not payload["discovery_approval_packets"]:
            lines.append("- No discovery approval packets loaded.")
        for item in payload["discovery_approval_packets"]:
            blockers = ", ".join(item.get("approval_blockers") or []) or "none"
            breakdown = item.get("status_breakdown") or {}
            lines.append(
                f"- {item['approval_packet_id']} | {item['target']} | approval={item['approval_status']} | "
                f"manual_state={item['approval_resolution_state']} | blockers={blockers} | "
                f"blocked={breakdown.get('approval_blocked', 0)} | ready={breakdown.get('ready_to_execute', 0)} | "
                f"awaiting_result={breakdown.get('awaiting_result', 0)} | learned={breakdown.get('learned', 0)}"
            )

        lines.extend(["", "## Discovery Slot Status Board", ""])
        if not payload["discovery_slot_status_board"]:
            lines.append("- No discovery slot status rows loaded.")
        for item in payload["discovery_slot_status_board"]:
            required = ", ".join(item.get("required_fields") or []) or "none"
            missing = ", ".join(item.get("missing_evidence") or []) or "none"
            lines.append(
                f"- {item['approval_id']} / {item['slot_id']} | {item['slot_status']} | {item['target']} | "
                f"focus={item['change_focus']} | required={required} | missing={missing} | input={item['manual_input_file'] or 'none'}"
            )

        lines.extend(["", "## Discovery Slot Operator Packets", ""])
        if not payload["discovery_slot_operator_packets"]:
            lines.append("- No discovery slot operator packets loaded.")
        for item in payload["discovery_slot_operator_packets"]:
            breakdown = item.get("status_breakdown") or {}
            lines.append(
                f"- {item['operator_packet_id']} | {item['target']} | approval={item['approval_status']} | "
                f"blocked={breakdown.get('approval_blocked', 0)} | ready={breakdown.get('ready_to_execute', 0)} | "
                f"awaiting_result={breakdown.get('awaiting_result', 0)} | learned={breakdown.get('learned', 0)} | "
                f"input={item['slot_manual_input_file'] or 'none'}"
            )

        lines.extend(["", "## Platform Write Readiness", ""])
        if not payload["platform_write_readiness"]:
            lines.append("- No platform readiness rows loaded.")
        for item in payload["platform_write_readiness"]:
            blockers = ", ".join(item["blockers"]) if item["blockers"] else "none"
            missing = ", ".join(item["missing_credentials"]) if item["missing_credentials"] else "none"
            operations = ", ".join(item["supported_operations"]) if item["supported_operations"] else "none"
            lines.append(
                f"- {item['platform']} | write_ready={item['write_ready']} | operations={operations} | "
                f"missing={missing} | blockers={blockers}"
            )

        lines.extend(["", "## Review-Only Action Plan", ""])
        if not payload["action_plan"]:
            lines.append("- No media buyer actions generated.")
        for item in payload["action_plan"]:
            lines.append(
                f"- {item['action_type']} | {item['target']} | priority={item['priority']} | "
                f"approval_required={item['approval_required']} | confidence={item['confidence']}"
            )

        lines.extend(["", "## Execution Intents", ""])
        if not payload["execution_intents"]:
            lines.append("- No execution intents generated.")
        for item in payload["execution_intents"]:
            reasons = ", ".join(item["blocked_reasons"]) if item["blocked_reasons"] else "none"
            lines.append(
                f"- {item['intent_id']} | {item['execution_status']} | {item['platform']} | "
                f"{item['operation']} | {item['target']} | blocked={reasons}"
            )

        lines.extend(["", "## Guarded Execution", ""])
        if not payload["execution_attempts"]:
            lines.append("- No guarded execution attempts generated.")
        for item in payload["execution_attempts"]:
            blockers = ", ".join(item["blockers"]) if item["blockers"] else "none"
            lines.append(
                f"- {item['attempt_id']} | {item['attempt_status']} | {item['platform']} | "
                f"{item['operation']} | {item['target']} | connector={item['connector_method'] or 'none'} | blockers={blockers}"
            )

        lines.extend(["", "## Rollback Monitor", ""])
        if not payload["rollback_monitors"]:
            lines.append("- No rollback monitors generated.")
        for item in payload["rollback_monitors"]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(
                f"- {item['monitor_id']} | {item['monitor_status']} | {item['target']} | "
                f"signal={item['rollback_signal']} | missing={missing}"
            )

        lines.extend(["", "## Guardrails", ""])
        lines.extend(f"- {item}" for item in payload["guardrails"])
        lines.extend(["", "## Child Artifacts", ""])
        lines.extend(f"- {name}: {path}" for name, path in payload["child_paths"].items())
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _decision_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": item.get("entity_type", ""),
        "entity_id": item.get("entity_id", ""),
        "project": item.get("project", ""),
        "scope": item.get("scope", ""),
        "decision": item.get("decision", ""),
        "final_growth_score": item.get("final_growth_score", 0.0),
        "final_risk_score": item.get("final_risk_score", 0.0),
        "confidence": item.get("confidence", 0.0),
    }


def _strategy_priority_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "priority_id": item.get("priority_id", ""),
        "name": item.get("name", ""),
        "status": item.get("status", ""),
        "project": item.get("project", ""),
        "audience": item.get("audience", ""),
        "genre": item.get("genre", ""),
        "country": item.get("country", ""),
        "platform": item.get("platform", ""),
        "monetization": item.get("monetization", ""),
        "objective": item.get("objective", ""),
        "priority_weight": item.get("priority_weight", 1.0),
        "notes": item.get("notes", ""),
    }


def _experiment_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": item.get("experiment_id", ""),
        "experiment_type": item.get("experiment_type", ""),
        "target": item.get("target", ""),
        "linked_decision": item.get("linked_decision", ""),
        "duration": item.get("duration", ""),
        "experiment_confidence": item.get("experiment_confidence", 0.0),
    }


def _cluster_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_name": item.get("cluster_name", ""),
        "cluster_key": item.get("cluster_key", ""),
        "creative_count": item.get("creative_count", 0),
        "avg_roi": item.get("avg_roi", 0.0),
        "predicted_scalability": item.get("predicted_scalability", 0.0),
        "confidence": item.get("confidence", ""),
        "variant_direction": item.get("variant_direction", ""),
    }


def _fatigue_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": item.get("project", ""),
        "channel": item.get("channel", ""),
        "country": item.get("country", ""),
        "creative_id": item.get("creative_id", ""),
        "status": item.get("status", ""),
        "spend": item.get("spend", 0.0),
        "roi": item.get("roi", 0.0),
        "ctr_drop_pct": item.get("ctr_drop_pct", 0.0),
        "cpi_rise_pct": item.get("cpi_rise_pct", 0.0),
    }


def _user_quality_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": item.get("project", ""),
        "quality_status": item.get("quality_status", ""),
        "quality_score": item.get("quality_score", 0.0),
        "current_d7": item.get("current_d7", 0.0),
        "dynamic_break_even_d7": item.get("dynamic_break_even_d7", 0.0),
        "current_cpi": item.get("current_cpi", 0.0),
        "current_retention_d1": item.get("current_retention_d1", 0.0),
        "current_arpu": item.get("current_arpu", 0.0),
        "current_arppu": item.get("current_arppu", 0.0),
        "confidence": item.get("confidence", 0.0),
        "missing_quality_fields": list(item.get("missing_quality_fields") or []),
    }


def _lifecycle_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": item.get("project", ""),
        "lifecycle_stage": item.get("lifecycle_stage", ""),
        "predicted_growth_potential": item.get("predicted_growth_potential", 0.0),
        "lifecycle_risk_score": item.get("lifecycle_risk_score", 0.0),
        "predicted_ltv_curve": item.get("predicted_ltv_curve", ""),
        "payback_ratio": item.get("payback_ratio", 0.0),
        "quality_status": item.get("quality_status", ""),
        "creative_cluster_count": item.get("creative_cluster_count", 0),
        "fatigue_signal_count": item.get("fatigue_signal_count", 0),
        "recommended_decision_input": item.get("recommended_decision_input", ""),
        "next_learning_need": list(item.get("next_learning_need") or []),
    }


def _feedback_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": item.get("action_id", ""),
        "action": item.get("action", ""),
        "target": item.get("target", ""),
        "owner": item.get("owner", ""),
        "success": item.get("success"),
    }


def _learning_gap_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "learning_id": item.get("learning_id", ""),
        "action_id": item.get("action_id", ""),
        "learning_state": item.get("learning_state", ""),
        "target": item.get("target", ""),
        "missing_fields": list(item.get("missing_fields") or []),
        "next_update_required": item.get("next_update_required", ""),
    }


def _causal_hypothesis_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "hypothesis_id": item.get("hypothesis_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "experiment_type": item.get("experiment_type", ""),
        "target": item.get("target", ""),
        "linked_decision": item.get("linked_decision", ""),
        "causal_state": item.get("causal_state", ""),
        "confidence": item.get("confidence", ""),
        "missing_evidence": list(item.get("missing_evidence") or []),
    }


def _validation_action_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "hypothesis_id": item.get("hypothesis_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "required_update": item.get("required_update", ""),
        "missing_evidence": list(item.get("missing_evidence") or []),
    }


def _playbook_rule_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": item.get("rule_id", ""),
        "rule_state": item.get("rule_state", ""),
        "source_hypothesis_id": item.get("source_hypothesis_id", ""),
        "experiment_type": item.get("experiment_type", ""),
        "target_signature": item.get("target_signature", ""),
        "target_project": item.get("target_project", ""),
        "decision_signal": item.get("decision_signal", ""),
        "growth_bias": item.get("growth_bias", 0.0),
        "risk_bias": item.get("risk_bias", 0.0),
        "confidence": item.get("confidence", ""),
    }


def _playbook_candidate_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item.get("candidate_id", ""),
        "source_hypothesis_id": item.get("source_hypothesis_id", ""),
        "causal_state": item.get("causal_state", ""),
        "experiment_type": item.get("experiment_type", ""),
        "target_signature": item.get("target_signature", ""),
        "target_project": item.get("target_project", ""),
        "missing_evidence": list(item.get("missing_evidence") or []),
        "confidence": item.get("confidence", ""),
    }


def _learning_evidence_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id", ""),
        "priority": item.get("priority", ""),
        "queue_status": item.get("queue_status", ""),
        "candidate_id": item.get("candidate_id", ""),
        "source_hypothesis_id": item.get("source_hypothesis_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "target_project": item.get("target_project", ""),
        "experiment_type": item.get("experiment_type", ""),
        "result_state": item.get("result_state", ""),
        "approval_status": item.get("approval_status", ""),
        "missing_evidence": list(item.get("missing_evidence") or []),
        "required_template_fields": list(item.get("required_template_fields") or []),
        "recommended_template_fields": list(item.get("recommended_template_fields") or []),
        "manual_input_file": item.get("manual_input_file", ""),
    }


def _execution_queue_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "queue_id": item.get("queue_id", ""),
        "queue_status": item.get("queue_status", ""),
        "experiment_id": item.get("experiment_id", ""),
        "experiment_type": item.get("experiment_type", ""),
        "target": item.get("target", ""),
        "matched_intent_id": item.get("matched_intent_id", ""),
        "platform": item.get("platform", ""),
        "operation": item.get("operation", ""),
        "blocked_reasons": list(item.get("blocked_reasons") or []),
        "result_capture_required": item.get("result_capture_required", True),
    }


def _approval_gate_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "approval_id": item.get("approval_id", ""),
        "approval_status": item.get("approval_status", ""),
        "queue_id": item.get("queue_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "requested_execution": item.get("requested_execution", ""),
        "approval_blockers": list(item.get("approval_blockers") or []),
        "required_result_fields": list(item.get("required_result_fields") or []),
        "recommended_result_fields": list(item.get("recommended_result_fields") or []),
        "learning_close_condition": item.get("learning_close_condition", ""),
    }


def _result_row_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "result_id": item.get("result_id", ""),
        "approval_id": item.get("approval_id", ""),
        "result_state": item.get("result_state", ""),
        "experiment_id": item.get("experiment_id", ""),
        "hypothesis_id": item.get("hypothesis_id", ""),
        "target": item.get("target", ""),
        "success": item.get("success"),
        "missing_result_fields": list(item.get("missing_result_fields") or []),
        "required_result_fields": list(item.get("required_result_fields") or []),
        "recommended_result_fields": list(item.get("recommended_result_fields") or []),
    }


def _discovery_experiment_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "test_type": item.get("test_type", ""),
        "learning_goal": item.get("learning_goal", ""),
        "winner_material_asset_count": int(item.get("winner_material_asset_count") or 0),
        "variant_count_target": int(item.get("variant_count_target") or 0),
        "primary_test_axis": item.get("primary_test_axis", ""),
        "control_dimensions": list(item.get("control_dimensions") or []),
        "baseline_asset_preview": list(item.get("baseline_asset_preview") or []),
        "variant_plan_summary": item.get("variant_plan_summary", ""),
    }


def _discovery_card_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_id": item.get("card_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "approval_status": item.get("approval_status", ""),
        "result_state": item.get("result_state", ""),
        "learning_goal": item.get("learning_goal", ""),
        "variant_count_target": int(item.get("variant_count_target") or 0),
        "primary_test_axis": item.get("primary_test_axis", ""),
        "control_dimensions": list(item.get("control_dimensions") or []),
        "baseline_asset_preview": list(item.get("baseline_asset_preview") or []),
        "variant_plan_summary": item.get("variant_plan_summary", ""),
    }


def _discovery_test_plan_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_id": item.get("plan_id", ""),
        "card_id": item.get("card_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "approval_status": item.get("approval_status", ""),
        "intent_id": item.get("intent_id", ""),
        "intent_status": item.get("intent_status", ""),
        "variant_count_target": int(item.get("variant_count_target") or 0),
        "primary_test_axis": item.get("primary_test_axis", ""),
        "control_dimensions": list(item.get("control_dimensions") or []),
        "naming_rule": item.get("naming_rule", ""),
        "variant_slots": list(item.get("variant_slots") or []),
    }


def _discovery_execution_packet_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "packet_id": item.get("packet_id", ""),
        "plan_id": item.get("plan_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "approval_status": item.get("approval_status", ""),
        "intent_id": item.get("intent_id", ""),
        "intent_status": item.get("intent_status", ""),
        "naming_rule": item.get("naming_rule", ""),
        "allowed_change_summary": item.get("allowed_change_summary", ""),
        "slot_packets": list(item.get("slot_packets") or []),
    }


def _discovery_learning_packet_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "learning_packet_id": item.get("learning_packet_id", ""),
        "packet_id": item.get("packet_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "learning_goal": item.get("learning_goal", ""),
        "approval_status": item.get("approval_status", ""),
        "slot_learning_packets": list(item.get("slot_learning_packets") or []),
        "result_defaults": dict(item.get("result_defaults") or {}),
        "required_result_fields": list(item.get("required_result_fields") or []),
    }


def _discovery_pattern_prior_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "prior_id": item.get("prior_id", ""),
        "project": item.get("project", ""),
        "channel": item.get("channel", ""),
        "country": item.get("country", ""),
        "test_type": item.get("test_type", ""),
        "prior_state": item.get("prior_state", ""),
        "prior_strength": item.get("prior_strength", 0.0),
        "prioritized_change_focuses": list(item.get("prioritized_change_focuses") or []),
        "prioritized_pattern_keys": list(item.get("prioritized_pattern_keys") or []),
        "next_learning_step": item.get("next_learning_step", ""),
    }


def _discovery_learning_state_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "learning_state_packet_id": item.get("learning_state_packet_id", ""),
        "learning_packet_id": item.get("learning_packet_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "learning_state": item.get("learning_state", ""),
        "parent_result_state": item.get("parent_result_state", ""),
        "learning_close_signal": item.get("learning_close_signal", ""),
        "next_update_required": item.get("next_update_required", ""),
        "slot_states": list(item.get("slot_states") or []),
    }


def _discovery_pattern_memory_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "learning_id": item.get("learning_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "slot_id": item.get("slot_id", ""),
        "variant_name": item.get("variant_name", ""),
        "change_focus": item.get("change_focus", ""),
        "pattern_memory_state": item.get("pattern_memory_state", ""),
        "reusable_pattern_key": item.get("reusable_pattern_key", ""),
        "success": item.get("success"),
        "next_update_required": item.get("next_update_required", ""),
    }


def _discovery_result_capture_packet_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "capture_packet_id": item.get("capture_packet_id", ""),
        "learning_packet_id": item.get("learning_packet_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "approval_id": item.get("approval_id", ""),
        "target": item.get("target", ""),
        "capture_priority": item.get("capture_priority", ""),
        "parent_result_state": item.get("parent_result_state", ""),
        "required_parent_fields": list(item.get("required_parent_fields") or []),
        "slot_rollup_parent_fields": list(item.get("slot_rollup_parent_fields") or []),
        "manual_parent_fields": list(item.get("manual_parent_fields") or []),
        "parent_manual_input_file": item.get("parent_manual_input_file", ""),
        "recommended_parent_fields": list(item.get("recommended_parent_fields") or []),
        "slot_manual_input_file": item.get("slot_manual_input_file", ""),
        "parent_next_step": item.get("parent_next_step", ""),
        "slot_capture_packets": list(item.get("slot_capture_packets") or []),
    }


def _discovery_approval_packet_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "approval_packet_id": item.get("approval_packet_id", ""),
        "approval_id": item.get("approval_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "approval_status": item.get("approval_status", ""),
        "approval_resolution_state": item.get("approval_resolution_state", ""),
        "manual_approval_state": item.get("manual_approval_state", ""),
        "approval_blockers": list(item.get("approval_blockers") or []),
        "status_breakdown": dict(item.get("status_breakdown") or {}),
        "slot_manual_input_file": item.get("slot_manual_input_file", ""),
    }


def _discovery_slot_status_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "approval_id": item.get("approval_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "slot_id": item.get("slot_id", ""),
        "slot_status": item.get("slot_status", ""),
        "approval_status": item.get("approval_status", ""),
        "result_state": item.get("result_state", ""),
        "change_focus": item.get("change_focus", ""),
        "variant_name": item.get("variant_name", ""),
        "required_fields": list(item.get("required_fields") or []),
        "missing_evidence": list(item.get("missing_evidence") or []),
        "manual_input_file": item.get("manual_input_file", ""),
    }


def _discovery_slot_operator_packet_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "operator_packet_id": item.get("operator_packet_id", ""),
        "approval_id": item.get("approval_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "approval_status": item.get("approval_status", ""),
        "slot_manual_input_file": item.get("slot_manual_input_file", ""),
        "status_breakdown": dict(item.get("status_breakdown") or {}),
    }


def _discovery_unlock_sequence_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence_id": item.get("sequence_id", ""),
        "approval_id": item.get("approval_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "manual_approval_state": item.get("manual_approval_state", ""),
        "decision_wait_match_count": item.get("decision_wait_match_count", 0),
        "unlock_order": list(item.get("unlock_order") or []),
        "reopened_decision_targets": list(item.get("reopened_decision_targets") or [])[:10],
    }


def _discovery_unlock_operator_handoff_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "handoff_id": item.get("handoff_id", ""),
        "approval_id": item.get("approval_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "manual_approval_state": item.get("manual_approval_state", ""),
        "approval_step_required": item.get("approval_step_required", False),
        "next_human_surface": item.get("next_human_surface", ""),
        "decision_wait_match_count": item.get("decision_wait_match_count", 0),
        "unlock_order": list(item.get("unlock_order") or []),
        "reopened_decision_targets": list(item.get("reopened_decision_targets") or [])[:10],
    }


def _discovery_action_queue_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": item.get("action_id", ""),
        "queue_rank": item.get("queue_rank", 0),
        "action_type": item.get("action_type", ""),
        "priority_label": item.get("priority_label", ""),
        "approval_id": item.get("approval_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "slot_id": item.get("slot_id", ""),
        "human_surface": item.get("human_surface", ""),
        "human_work_item": item.get("human_work_item", ""),
        "decision_wait_match_count": item.get("decision_wait_match_count", 0),
        "parent_result_required_fields": list(item.get("parent_result_required_fields") or []),
    }


def _discovery_action_state_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": item.get("action_id", ""),
        "queue_rank": item.get("queue_rank", 0),
        "action_type": item.get("action_type", ""),
        "action_state": item.get("action_state", ""),
        "approval_id": item.get("approval_id", ""),
        "slot_id": item.get("slot_id", ""),
        "next_transition": item.get("next_transition", ""),
        "blocking_reason": item.get("blocking_reason", ""),
        "decision_wait_match_count": item.get("decision_wait_match_count", 0),
    }


def _platform_gate_digest(name: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": item.get("platform", name),
        "write_ready": item.get("write_ready", False),
        "supported_operations": list(item.get("supported_operations") or []),
        "missing_credentials": list(item.get("missing_credentials") or []),
        "blockers": list(item.get("blockers") or []),
    }


def _action_plan_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_type": item.get("action_type", ""),
        "target": item.get("target", ""),
        "project": item.get("project", ""),
        "priority": item.get("priority", 0.0),
        "approval_required": item.get("approval_required", True),
        "confidence": item.get("confidence", ""),
        "max_change_pct": item.get("max_change_pct", 0.0),
    }


def _execution_intent_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent_id": item.get("intent_id", ""),
        "execution_status": item.get("execution_status", ""),
        "platform": item.get("platform", ""),
        "operation": item.get("operation", ""),
        "target": item.get("target", ""),
        "project": item.get("project", ""),
        "approval_required": item.get("approval_required", True),
        "blocked_reasons": list(item.get("blocked_reasons") or []),
        "confidence": item.get("confidence", ""),
    }


def _execution_attempt_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt_id": item.get("attempt_id", ""),
        "attempt_status": item.get("attempt_status", ""),
        "intent_id": item.get("intent_id", ""),
        "platform": item.get("platform", ""),
        "operation": item.get("operation", ""),
        "target": item.get("target", ""),
        "connector_method": item.get("connector_method", ""),
        "blockers": list(item.get("blockers") or []),
    }


def _rollback_monitor_digest(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "monitor_id": item.get("monitor_id", ""),
        "monitor_status": item.get("monitor_status", ""),
        "attempt_id": item.get("attempt_id", ""),
        "intent_id": item.get("intent_id", ""),
        "target": item.get("target", ""),
        "operation": item.get("operation", ""),
        "rollback_signal": item.get("rollback_signal", ""),
        "missing_evidence": list(item.get("missing_evidence") or []),
    }
