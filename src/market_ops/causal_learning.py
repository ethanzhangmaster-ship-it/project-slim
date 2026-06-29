from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.decision_engine import DecisionEngineBuilder
from market_ops.experiment_manager import ExperimentPlanBuilder
from market_ops.growth_memory_store import GrowthMemoryStoreBuilder
from market_ops.learning_memory import LearningMemoryBuilder


@dataclass(slots=True)
class CausalLearningResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class CausalLearningBuilder:
    """Builds an auditable hypothesis ledger without claiming unverified causality."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> CausalLearningResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"causal_learning_{suffix}.md"
        json_path = output_dir / f"causal_learning_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return CausalLearningResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        decision_payload = _load_or_build(output_dir / f"decision_engine_{suffix}.json", lambda: DecisionEngineBuilder(self._settings).build(report_date))
        experiment_payload = _load_or_build(output_dir / f"experiment_plan_{suffix}.json", lambda: ExperimentPlanBuilder(self._settings).build(report_date))
        learning_payload = _load_or_build(output_dir / f"learning_memory_{suffix}.json", lambda: LearningMemoryBuilder(self._settings).build(report_date))
        memory_payload = _load_or_build(output_dir / "growth_memory_store_latest.json", lambda: GrowthMemoryStoreBuilder(self._settings).build(report_date))
        result_payload = _load_or_build(output_dir / f"experiment_result_ingestion_{suffix}.json", lambda: _build_result_ingestion(self._settings, report_date))

        decision_index = _index_decisions(decision_payload.get("items") or [])
        learning_index = _index_learning_records(learning_payload.get("records") or [])
        memory_index = _index_learning_records((memory_payload.get("closed_memory") or []) + (memory_payload.get("pending_memory") or []))
        result_index = _index_result_evidence(result_payload.get("learning_evidence") or [])

        hypotheses = [
            _hypothesis_from_experiment(item, index, decision_index, learning_index, memory_index, result_index)
            for index, item in enumerate(experiment_payload.get("experiments") or [], start=1)
        ]
        slot_hypotheses = [
            _hypothesis_from_learning_record(item, index)
            for index, item in enumerate(learning_payload.get("records") or [], start=1)
        ]
        hypotheses = [item for item in hypotheses + slot_hypotheses if item]
        validated = [item for item in hypotheses if item["causal_state"] == "validated"]
        invalidated = [item for item in hypotheses if item["causal_state"] == "invalidated"]
        pending = [item for item in hypotheses if item["causal_state"] == "pending_outcome"]
        needs_execution = [item for item in hypotheses if item["causal_state"] == "needs_execution_confirmation"]

        return {
            "report_date": report_date.isoformat(),
            "mode": "causal_hypothesis_ledger",
            "passed": True,
            "rules": {
                "no_unverified_causal_claims": True,
                "decision_engine_only": "Causal Learning emits learning signals only; it does not emit final actions.",
                "requires_outcome_evidence": "Validated and invalidated states require actual post-action outcome records.",
            },
            "summary": {
                "hypothesis_count": len(hypotheses),
                "validated_count": len(validated),
                "invalidated_count": len(invalidated),
                "pending_outcome_count": len(pending),
                "needs_execution_confirmation_count": len(needs_execution),
            },
            "hypotheses": hypotheses,
            "next_validation_actions": [_next_validation_action(item) for item in needs_execution + pending][:30],
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Causal Learning Layer | {payload['report_date']}",
            "",
            "- Mode: causal_hypothesis_ledger",
            "- Purpose: track which growth hypotheses are proven, disproven, or still missing outcome evidence.",
            "- Boundary: signal layer only; final actions still belong to Decision Engine and Action Layer.",
            "",
            "## Summary",
            "",
            f"- Hypotheses: {summary['hypothesis_count']}",
            f"- Validated: {summary['validated_count']}",
            f"- Invalidated: {summary['invalidated_count']}",
            f"- Pending outcome: {summary['pending_outcome_count']}",
            f"- Needs execution confirmation: {summary['needs_execution_confirmation_count']}",
            "",
            "## Hypotheses",
            "",
        ]
        if not payload["hypotheses"]:
            lines.append("- None.")
        for item in payload["hypotheses"][:40]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(
                f"- {item['hypothesis_id']} | {item['causal_state']} | {item['experiment_type']} | "
                f"{item['target']} | confidence={item['confidence']} | missing={missing}"
            )

        lines.extend(["", "## Next Validation Actions", ""])
        if not payload["next_validation_actions"]:
            lines.append("- None.")
        for item in payload["next_validation_actions"]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(f"- {item['hypothesis_id']} | {item['required_update']} | missing={missing}")
        lines.append("")
        return "\n".join(lines)


def _load_or_build(path: Path, builder: Any) -> dict[str, Any]:
    if not path.exists():
        builder()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _build_result_ingestion(settings: Settings, report_date: date) -> None:
    from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder

    ExperimentResultIngestionBuilder(settings).build(report_date)


def _index_decisions(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        keys = {
            str(item.get("entity_id") or ""),
            _target_key(" / ".join(part for part in (item.get("project"), item.get("scope"), item.get("entity_id")) if part)),
        }
        for key in keys:
            if key:
                index[key] = item
    return index


def _index_learning_records(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        for key in (str(item.get("target") or ""), str(item.get("action_id") or ""), str(item.get("learning_id") or "")):
            key = _target_key(key)
            if key:
                index[key] = item
    return index


def _index_result_evidence(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        for key in (str(item.get("hypothesis_id") or ""), str(item.get("experiment_id") or ""), str(item.get("target") or "")):
            key = _target_key(key)
            if key:
                index[key] = item
    return index


def _hypothesis_from_experiment(
    experiment: dict[str, Any],
    index: int,
    decision_index: dict[str, dict[str, Any]],
    learning_index: dict[str, dict[str, Any]],
    memory_index: dict[str, dict[str, Any]],
    result_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target = str(experiment.get("target") or "")
    decision = decision_index.get(_target_key(target)) or decision_index.get(str(target.split("/")[-1]).strip()) or {}
    result = (
        result_index.get(str(experiment.get("experiment_id") or ""))
        or _best_learning_match(target, result_index)
        or {}
    )
    learning = result or _best_learning_match(target, learning_index) or _best_learning_match(target, memory_index) or {}
    causal_state = _causal_state(learning)
    missing_evidence = _missing_evidence(experiment, decision, learning, causal_state)
    return {
        "hypothesis_id": f"cause_{index:03d}",
        "experiment_id": experiment.get("experiment_id", ""),
        "experiment_type": experiment.get("experiment_type", ""),
        "target": target,
        "linked_decision": experiment.get("linked_decision", ""),
        "source": experiment.get("source", ""),
        "creative_id": experiment.get("creative_id", ""),
        "creative_name": experiment.get("creative_name", ""),
        "decision_confidence": decision.get("confidence", experiment.get("experiment_confidence", 0.0)),
        "causal_state": causal_state,
        "hypothesis": experiment.get("hypothesis", ""),
        "intervention": experiment.get("change", ""),
        "expected_metrics": list(experiment.get("success_metrics") or []),
        "rollback_metrics": list(experiment.get("rollback_metrics") or []),
        "observed_result": learning.get("actual_signal", ""),
        "success": learning.get("success"),
        "post_metrics": learning.get("post_metrics") or {},
        "learning_pattern": _learning_pattern(experiment, learning),
        "structure_context": _structure_context_from_learning(learning),
        "structure_signature": _structure_signature_from_learning(learning),
        "structural_test_rationale": str(learning.get("structural_test_rationale") or ""),
        "discovery_prioritized_change_focuses": list(learning.get("discovery_prioritized_change_focuses") or []),
        "confidence": _confidence(causal_state, decision, learning, experiment),
        "missing_evidence": missing_evidence,
        "source_modules": ["experiment_plan", "decision_engine", "experiment_result_ingestion", "learning_memory", "growth_memory_store"],
    }


def _hypothesis_from_learning_record(
    learning: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    if str(learning.get("source_type") or "") != "discovery_slot_result_ingestion":
        return {}
    causal_state = _causal_state(learning)
    missing_evidence = list(learning.get("missing_fields") or [])
    target = str(learning.get("target") or "")
    post_metrics = dict(learning.get("post_metrics") or {})
    pattern_family = _canonical_pattern_family(str(learning.get("test_type") or ""))
    return {
        "hypothesis_id": f"cause_slot_{index:03d}",
        "experiment_id": learning.get("experiment_id", ""),
        "parent_experiment_id": learning.get("parent_experiment_id", ""),
        "experiment_type": "discovery_slot_test",
        "target": target,
        "linked_decision": learning.get("linked_decision", ""),
        "source": learning.get("source", ""),
        "creative_id": learning.get("creative_id", ""),
        "creative_name": learning.get("creative_name", ""),
        "decision_confidence": 0.0,
        "causal_state": causal_state,
        "hypothesis": learning.get("hypothesis", ""),
        "intervention": str(post_metrics.get("change_focus") or learning.get("change_focus") or ""),
        "expected_metrics": [learning.get("acceptance_metric", "")] if str(learning.get("acceptance_metric") or "").strip() else [],
        "rollback_metrics": [],
        "observed_result": learning.get("actual_signal", ""),
        "success": learning.get("success"),
        "post_metrics": post_metrics,
        "learning_pattern": {
            "pattern_family": pattern_family,
            "variant_type": str(post_metrics.get("change_focus") or ""),
            "baseline_asset": str((learning.get("baseline_asset_preview") or [""])[0] if learning.get("baseline_asset_preview") else ""),
            "learning_note": str(post_metrics.get("slot_result_summary") or ""),
            "post_action_ctr": str(post_metrics.get("post_action_ctr") or ""),
            "post_action_cpi": str(post_metrics.get("post_action_cpi") or ""),
            "created_variant_count": "",
        },
        "structure_context": _structure_context_from_learning(learning),
        "structure_signature": _structure_signature_from_learning(learning),
        "structural_test_rationale": str(
            learning.get("structural_test_rationale") or post_metrics.get("structural_test_rationale") or ""
        ),
        "discovery_prioritized_change_focuses": list(
            learning.get("discovery_prioritized_change_focuses") or post_metrics.get("discovery_prioritized_change_focuses") or []
        ),
        "pattern_memory_state": learning.get("pattern_memory_state", ""),
        "reusable_pattern_key": learning.get("reusable_pattern_key", ""),
        "confidence": "high" if causal_state in {"validated", "invalidated"} else ("medium" if learning.get("actual_signal") else "low"),
        "missing_evidence": missing_evidence,
        "source_modules": ["learning_memory", "experiment_result_ingestion"],
        "slot_id": learning.get("slot_id", ""),
        "variant_name": learning.get("variant_name", ""),
        "change_focus": learning.get("change_focus", ""),
        "primary_test_axis": learning.get("primary_test_axis", ""),
    }


def _best_learning_match(target: str, index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target_key = _target_key(target)
    if target_key in index:
        return index[target_key]
    target_parts = [part.strip().lower() for part in target.split("/") if part.strip()]
    for key, item in index.items():
        key_l = key.lower()
        if key_l and any(part and part in key_l for part in target_parts):
            return item
    return {}


def _causal_state(learning: dict[str, Any]) -> str:
    if learning.get("success") is True:
        return "validated"
    if learning.get("success") is False:
        return "invalidated"
    if learning.get("learning_state") == "needs_execution_confirmation":
        return "needs_execution_confirmation"
    return "pending_outcome"


def _missing_evidence(
    experiment: dict[str, Any],
    decision: dict[str, Any],
    learning: dict[str, Any],
    causal_state: str,
) -> list[str]:
    missing: list[str] = []
    if not decision and str(experiment.get("source") or "") not in {"local_winner_prior", "discovery_backlog"}:
        missing.append("linked_decision_evidence")
    if not experiment.get("success_metrics"):
        missing.append("success_metrics")
    if not experiment.get("rollback_metrics"):
        missing.append("rollback_metrics")
    if causal_state == "needs_execution_confirmation":
        missing.append("execution_confirmation")
    if causal_state in {"needs_execution_confirmation", "pending_outcome"}:
        missing.extend(item for item in (learning.get("missing_fields") or ["actual_result_note"]) if item not in missing)
    return missing


def _confidence(
    causal_state: str,
    decision: dict[str, Any],
    learning: dict[str, Any],
    experiment: dict[str, Any],
) -> str:
    if causal_state in {"validated", "invalidated"} and learning.get("actual_signal"):
        return "high"
    base = float(decision.get("confidence") or experiment.get("experiment_confidence") or 0.0)
    if base >= 0.75 and experiment.get("success_metrics") and experiment.get("rollback_metrics"):
        return "medium"
    return "low"


def _next_validation_action(item: dict[str, Any]) -> dict[str, Any]:
    if item["causal_state"] == "needs_execution_confirmation":
        required = "Confirm whether the planned action or experiment was executed, then attach post-action metrics."
    else:
        required = "Add post-experiment outcome metrics so the hypothesis can be validated or invalidated."
    return {
        "hypothesis_id": item["hypothesis_id"],
        "experiment_id": item["experiment_id"],
        "target": item["target"],
        "required_update": required,
        "missing_evidence": item["missing_evidence"],
    }


def _learning_pattern(experiment: dict[str, Any], learning: dict[str, Any]) -> dict[str, Any]:
    post_metrics = learning.get("post_metrics") or {}
    return {
        "pattern_family": _canonical_pattern_family(
            str(learning.get("test_type") or "") or _pattern_family(experiment)
        ),
        "variant_type": str(post_metrics.get("winner_variant_type") or ""),
        "baseline_asset": str(post_metrics.get("winner_baseline_asset") or experiment.get("creative_name") or ""),
        "learning_note": str(post_metrics.get("learning_note") or ""),
        "post_action_ctr": str(post_metrics.get("post_action_ctr") or ""),
        "post_action_cpi": str(post_metrics.get("post_action_cpi") or ""),
        "created_variant_count": str(post_metrics.get("created_variant_count") or ""),
        "baseline_asset_type": str(learning.get("baseline_asset_type") or post_metrics.get("baseline_asset_type") or ""),
        "structure_signature": _structure_signature_from_learning(learning),
    }


def _pattern_family(experiment: dict[str, Any]) -> str:
    hypothesis = str(experiment.get("hypothesis") or "").lower()
    if "image" in hypothesis or "动效" in str(experiment.get("hypothesis") or ""):
        return "winner_image_to_motion"
    return "winner_hook_clone"


def _canonical_pattern_family(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized == "winner_hook_clone_test":
        return "winner_hook_clone"
    if normalized == "winner_image_to_motion_test":
        return "winner_image_to_motion"
    return normalized


def _target_key(value: str) -> str:
    return " / ".join(part.strip() for part in str(value or "").split("/") if part.strip())


def _structure_context_from_learning(learning: dict[str, Any]) -> dict[str, Any]:
    if isinstance(learning.get("structure_context"), dict):
        return dict(learning.get("structure_context") or {})
    post_metrics = learning.get("post_metrics") or {}
    if isinstance(post_metrics.get("structure_context"), dict):
        return dict(post_metrics.get("structure_context") or {})
    winner_structure_bias = list(learning.get("winner_structure_bias") or post_metrics.get("winner_structure_bias") or [])
    baseline_asset_type = str(learning.get("baseline_asset_type") or post_metrics.get("baseline_asset_type") or "")
    context: dict[str, Any] = {}
    if baseline_asset_type:
        context["asset_type"] = baseline_asset_type
    for item in winner_structure_bias:
        bias_type = str(item.get("bias_type") or "").strip()
        if not bias_type:
            continue
        context[bias_type] = str(item.get("value") or "")
    return context


def _structure_signature_from_learning(learning: dict[str, Any]) -> str:
    signature = str(learning.get("structure_signature") or "").strip()
    if signature:
        return signature
    post_metrics = learning.get("post_metrics") or {}
    signature = str(post_metrics.get("structure_signature") or "").strip()
    if signature:
        return signature
    context = _structure_context_from_learning(learning)
    ordered_keys = ["asset_type", "orientation", "aspect_ratio", "duration_bucket"]
    tokens: list[str] = []
    for key in ordered_keys:
        value = context.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if str(value or "").strip():
            tokens.append(f"{key}={value}")
    for key in sorted(context):
        if key in ordered_keys or key == "recommended_focuses":
            continue
        value = context.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if str(value or "").strip():
            tokens.append(f"{key}={value}")
    return " | ".join(tokens)
