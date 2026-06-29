from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.causal_learning import CausalLearningBuilder
from market_ops.config import Settings


@dataclass(slots=True)
class GrowthPlaybookResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class GrowthPlaybookBuilder:
    """Converts proven causal learning into reusable decision signals."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> GrowthPlaybookResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"growth_playbook_{suffix}.md"
        json_path = output_dir / f"growth_playbook_{suffix}.json"
        latest_json_path = output_dir / "growth_playbook_latest.json"
        latest_markdown_path = output_dir / "growth_playbook_latest.md"
        markdown = self._render_markdown(payload)
        markdown_path.write_text(markdown, encoding="utf-8")
        json_payload = json.dumps(payload, ensure_ascii=False, indent=2)
        json_path.write_text(json_payload, encoding="utf-8")
        latest_json_path.write_text(json_payload, encoding="utf-8")
        latest_markdown_path.write_text(markdown, encoding="utf-8")
        return GrowthPlaybookResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        causal_payload = _load_or_build(
            self._settings.active_output_dir / f"causal_learning_{report_date.strftime('%Y%m%d')}.json",
            lambda: CausalLearningBuilder(self._settings).build(report_date),
        )
        hypotheses = [item for item in causal_payload.get("hypotheses") or [] if isinstance(item, dict)]
        validated = [item for item in hypotheses if item.get("causal_state") == "validated"]
        invalidated = [item for item in hypotheses if item.get("causal_state") == "invalidated"]
        candidates = [item for item in hypotheses if item.get("causal_state") not in {"validated", "invalidated"}]
        rules = [_rule_from_hypothesis(item, index) for index, item in enumerate(validated + invalidated, start=1)]
        candidate_rules = [_candidate_from_hypothesis(item, index) for index, item in enumerate(candidates, start=1)]
        return {
            "report_date": report_date.isoformat(),
            "mode": "validated_growth_playbook",
            "passed": True,
            "rules": {
                "signal_only": True,
                "requires_validated_or_invalidated_causality": True,
                "pending_hypotheses_are_not_decision_rules": True,
                "decision_engine_owns_actions": True,
            },
            "summary": {
                "hypothesis_count": len(hypotheses),
                "validated_rule_count": sum(1 for item in rules if item["rule_state"] == "validated"),
                "invalidated_rule_count": sum(1 for item in rules if item["rule_state"] == "invalidated"),
                "decision_rule_count": len(rules),
                "candidate_rule_count": len(candidate_rules),
                "missing_evidence_count": sum(len(item.get("missing_evidence") or []) for item in candidate_rules),
            },
            "decision_rules": rules,
            "candidate_rules": candidate_rules[:100],
            "next_evidence_actions": [_next_evidence_action(item) for item in candidate_rules[:30]],
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Growth Playbook | {payload['report_date']}",
            "",
            "- Mode: validated_growth_playbook",
            "- Boundary: signal layer only; rules can bias Decision Engine but cannot emit actions.",
            "",
            "## Summary",
            "",
            f"- Hypotheses: {summary['hypothesis_count']}",
            f"- Decision rules: {summary['decision_rule_count']}",
            f"- Validated rules: {summary['validated_rule_count']}",
            f"- Invalidated rules: {summary['invalidated_rule_count']}",
            f"- Candidate rules waiting for evidence: {summary['candidate_rule_count']}",
            f"- Missing evidence fields: {summary['missing_evidence_count']}",
            "",
            "## Decision Rules",
            "",
        ]
        if not payload["decision_rules"]:
            lines.append("- None yet. No causal hypotheses have validated or invalidated outcome evidence.")
        for item in payload["decision_rules"][:40]:
            lines.append(
                f"- {item['rule_id']} | {item['rule_state']} | {item['decision_signal']} | "
                f"{item['target_signature']} | confidence={item['confidence']}"
            )

        lines.extend(["", "## Candidate Rules", ""])
        if not payload["candidate_rules"]:
            lines.append("- None.")
        for item in payload["candidate_rules"][:40]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(
                f"- {item['candidate_id']} | {item['causal_state']} | {item['target_signature']} | missing={missing}"
            )

        lines.extend(["", "## Next Evidence Actions", ""])
        if not payload["next_evidence_actions"]:
            lines.append("- None.")
        for item in payload["next_evidence_actions"]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(f"- {item['candidate_id']} | {item['required_update']} | missing={missing}")
        lines.append("")
        return "\n".join(lines)


def _load_or_build(path: Path, builder: Any) -> dict[str, Any]:
    if not path.exists():
        builder()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _rule_from_hypothesis(item: dict[str, Any], index: int) -> dict[str, Any]:
    causal_state = str(item.get("causal_state") or "")
    decision_signal = "prefer_similar" if causal_state == "validated" else "avoid_similar"
    learning_pattern = item.get("learning_pattern") or {}
    rule = {
        "rule_id": f"playbook_{index:03d}",
        "rule_state": causal_state,
        "source_hypothesis_id": item.get("hypothesis_id", ""),
        "source_experiment_id": item.get("experiment_id", ""),
        "parent_experiment_id": item.get("parent_experiment_id", ""),
        "experiment_type": item.get("experiment_type", ""),
        "source": item.get("source", ""),
        "target_signature": _target_signature(item.get("target")),
        "target_project": _project_from_target(item.get("target")),
        "target_context": _target_context(item.get("target")),
        "decision_signal": decision_signal,
        "growth_bias": 0.18 if decision_signal == "prefer_similar" else -0.18,
        "risk_bias": 0.0 if decision_signal == "prefer_similar" else 0.18,
        "hypothesis": item.get("hypothesis", ""),
        "intervention": item.get("intervention", ""),
        "expected_metrics": list(item.get("expected_metrics") or []),
        "observed_result": item.get("observed_result", ""),
        "success": item.get("success"),
        "confidence": item.get("confidence", "low"),
        "learning_pattern": learning_pattern,
        "structure_context": dict(item.get("structure_context") or {}),
        "structure_signature": str(item.get("structure_signature") or ""),
        "structural_test_rationale": str(item.get("structural_test_rationale") or ""),
        "discovery_prioritized_change_focuses": list(item.get("discovery_prioritized_change_focuses") or []),
        "reusable_pattern_key": _reusable_pattern_key(item, learning_pattern),
        "contextual_pattern_key": _contextual_pattern_key(item, learning_pattern),
        "contextual_pattern_scope": _contextual_pattern_scope(item),
        "memory_scope": "discovery_pattern" if str(item.get("experiment_type") or "") == "discovery_slot_test" else "general_learning",
        "pattern_memory_state": item.get("pattern_memory_state", ""),
        "evidence_refs": [item.get("hypothesis_id", ""), item.get("experiment_id", "")],
        "source_modules": ["causal_learning", "experiment_result_ingestion", "learning_memory"],
    }
    rule.update(_slot_rule_context(item, learning_pattern))
    return rule


def _candidate_from_hypothesis(item: dict[str, Any], index: int) -> dict[str, Any]:
    learning_pattern = item.get("learning_pattern") or {}
    candidate = {
        "candidate_id": f"candidate_{index:03d}",
        "source_hypothesis_id": item.get("hypothesis_id", ""),
        "source_experiment_id": item.get("experiment_id", ""),
        "parent_experiment_id": item.get("parent_experiment_id", ""),
        "causal_state": item.get("causal_state", ""),
        "experiment_type": item.get("experiment_type", ""),
        "source": item.get("source", ""),
        "target_signature": _target_signature(item.get("target")),
        "target_project": _project_from_target(item.get("target")),
        "target_context": _target_context(item.get("target")),
        "hypothesis": item.get("hypothesis", ""),
        "intervention": item.get("intervention", ""),
        "missing_evidence": list(item.get("missing_evidence") or []),
        "confidence": item.get("confidence", "low"),
        "learning_pattern": learning_pattern,
        "structure_context": dict(item.get("structure_context") or {}),
        "structure_signature": str(item.get("structure_signature") or ""),
        "structural_test_rationale": str(item.get("structural_test_rationale") or ""),
        "discovery_prioritized_change_focuses": list(item.get("discovery_prioritized_change_focuses") or []),
        "reusable_pattern_key": _reusable_pattern_key(item, learning_pattern),
        "contextual_pattern_key": _contextual_pattern_key(item, learning_pattern),
        "contextual_pattern_scope": _contextual_pattern_scope(item),
        "memory_scope": "discovery_pattern" if str(item.get("experiment_type") or "") == "discovery_slot_test" else "general_learning",
        "pattern_memory_state": item.get("pattern_memory_state", ""),
        "decision_usable": False,
    }
    candidate.update(_slot_rule_context(item, learning_pattern))
    return candidate


def _next_evidence_action(item: dict[str, Any]) -> dict[str, Any]:
    missing = list(item.get("missing_evidence") or [])
    if "execution_confirmation" in missing:
        required = "Confirm whether the experiment or action was executed."
    elif any("result" in field or "roi" in field.lower() or "ctr" in field.lower() for field in missing):
        required = "Attach post-action result metrics."
    else:
        required = "Fill missing evidence before promoting this candidate into a decision rule."
    return {
        "candidate_id": item.get("candidate_id", ""),
        "source_hypothesis_id": item.get("source_hypothesis_id", ""),
        "target_signature": item.get("target_signature", ""),
        "required_update": required,
        "missing_evidence": missing,
    }


def _target_signature(value: Any) -> str:
    return " / ".join(part.strip() for part in str(value or "").split("/") if part.strip())


def _project_from_target(value: Any) -> str:
    match = re.search(r"\bP0*([0-9]+)\b", str(value or "").upper())
    if match:
        return f"P{int(match.group(1)):02d}"
    return ""


def _target_context(value: Any) -> dict[str, str]:
    parts = [part.strip() for part in str(value or "").split("/") if part.strip()]
    return {
        "project_label": parts[0] if len(parts) > 0 else "",
        "project_code": _project_from_target(value),
        "channel": parts[1] if len(parts) > 1 else "",
        "country": parts[2] if len(parts) > 2 else "",
        "test_type": parts[3] if len(parts) > 3 else "",
        "variant_name": parts[4] if len(parts) > 4 else "",
    }


def _slot_rule_context(item: dict[str, Any], learning_pattern: dict[str, Any]) -> dict[str, Any]:
    if str(item.get("experiment_type") or "") != "discovery_slot_test":
        return {}
    post_metrics = item.get("post_metrics") or {}
    return {
        "slot_id": item.get("slot_id", ""),
        "variant_name": item.get("variant_name", "") or post_metrics.get("variant_name", ""),
        "change_focus": item.get("change_focus", "") or post_metrics.get("change_focus", ""),
        "primary_test_axis": item.get("primary_test_axis", ""),
        "baseline_asset": learning_pattern.get("baseline_asset", ""),
        "baseline_asset_type": learning_pattern.get("baseline_asset_type", ""),
        "baseline_asset_group": post_metrics.get("baseline_asset_group", ""),
        "discovery_test_slot": post_metrics.get("discovery_test_slot", ""),
        "variant_plan_summary": post_metrics.get("variant_plan_summary", ""),
    }


def _reusable_pattern_key(item: dict[str, Any], learning_pattern: dict[str, Any]) -> str:
    if str(item.get("experiment_type") or "") == "discovery_slot_test":
        context = _target_context(item.get("target"))
        post_metrics = item.get("post_metrics") or {}
        change_focus = (
            item.get("change_focus")
            or post_metrics.get("change_focus")
            or learning_pattern.get("variant_type")
            or item.get("intervention")
            or "unspecified_change"
        )
        project = context.get("project_code") or _project_from_target(item.get("target")) or "unknown_project"
        channel = context.get("channel") or "unknown_channel"
        country = context.get("country") or "unknown_country"
        test_type = (
            post_metrics.get("discovery_test_slot")
            or context.get("test_type")
            or learning_pattern.get("pattern_family")
            or "unknown_test"
        )
        return ":".join(
            _key_token(part)
            for part in (project, channel, country, test_type, change_focus)
            if str(part or "").strip()
        )
    source = str(item.get("source") or "")
    if source == "local_winner_prior":
        project = _project_from_target(item.get("target"))
        family = str(learning_pattern.get("pattern_family") or "winner_pattern")
        variant = str(learning_pattern.get("variant_type") or "unspecified_variant")
        return f"{project}:{family}:{variant}"
    return _target_signature(item.get("target"))


def _contextual_pattern_key(item: dict[str, Any], learning_pattern: dict[str, Any]) -> str:
    base_key = _reusable_pattern_key(item, learning_pattern)
    structure_signature = str(item.get("structure_signature") or learning_pattern.get("structure_signature") or "").strip()
    if not base_key or not structure_signature:
        return base_key
    return ":".join(
        part
        for part in (
            base_key,
            _structure_token(structure_signature),
        )
        if str(part or "").strip()
    )


def _contextual_pattern_scope(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": _project_from_target(item.get("target")),
        "channel": str((item.get("target_context") or {}).get("channel") or ""),
        "country": str((item.get("target_context") or {}).get("country") or ""),
        "test_type": str((item.get("target_context") or {}).get("test_type") or item.get("discovery_test_slot") or ""),
        "structure_signature": str(item.get("structure_signature") or ""),
        "structure_context": dict(item.get("structure_context") or {}),
    }


def _key_token(value: Any) -> str:
    token = re.sub(r"[^0-9A-Za-z]+", "_", str(value or "").strip())
    return token.strip("_")


def _structure_token(value: str) -> str:
    return _key_token(value).lower()
