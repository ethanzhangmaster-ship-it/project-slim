from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_engine import DiscoveryEngineBuilder


@dataclass(slots=True)
class DiscoveryPatternPriorResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryPatternPriorBuilder:
    """Builds a signal-only prior layer from active discovery pattern candidates."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryPatternPriorResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_pattern_prior_{suffix}.md"
        json_path = output_dir / f"discovery_pattern_prior_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryPatternPriorResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        discovery_payload = _load_or_build(
            self._settings.active_output_dir / f"discovery_engine_{suffix}.json",
            lambda: DiscoveryEngineBuilder(self._settings).build(report_date),
        )
        project_index = {
            str(item.get("project") or "").strip(): item
            for item in discovery_payload.get("projects") or []
            if str(item.get("project") or "").strip()
        }
        priors = [
            _prior_from_pattern(item, project_index.get(str(item.get("project") or "").strip(), {}), index)
            for index, item in enumerate(discovery_payload.get("discovery_slot_patterns") or [], start=1)
        ]
        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_pattern_prior",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "decision_engine_owns_actions": True,
                "purpose": "Bias discovery planning toward the most active reusable pattern candidates without mutating budgets or ad platforms.",
            },
            "summary": {
                "prior_count": len(priors),
                "project_count": len({str(item.get("project") or "").strip() for item in priors if str(item.get("project") or "").strip()}),
                "approval_pending_prior_count": sum(1 for item in priors if item.get("prior_state") == "approval_pending"),
                "result_capture_pending_prior_count": sum(1 for item in priors if item.get("prior_state") == "result_capture_pending"),
                "pattern_ready_prior_count": sum(1 for item in priors if item.get("prior_state") == "pattern_ready"),
                "total_pending_slots": sum(int(item.get("pending_slot_count") or 0) for item in priors),
            },
            "priors": priors,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Pattern Prior | {payload['report_date']}",
            "",
            "- Mode: discovery_pattern_prior",
            "- Purpose: convert active discovery pattern candidates into reusable planning bias before they become validated playbook rules.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Priors: {summary.get('prior_count', 0)}",
            f"- Projects: {summary.get('project_count', 0)}",
            f"- Approval pending: {summary.get('approval_pending_prior_count', 0)}",
            f"- Result capture pending: {summary.get('result_capture_pending_prior_count', 0)}",
            f"- Pattern ready: {summary.get('pattern_ready_prior_count', 0)}",
            f"- Pending slots: {summary.get('total_pending_slots', 0)}",
            "",
            "## Priors",
            "",
        ]
        if not payload.get("priors"):
            lines.append("- None.")
        for item in payload.get("priors") or []:
            focuses = ",".join(item.get("prioritized_change_focuses") or []) or "none"
            lines.append(
                f"- {item['project']} | {item['channel']}/{item['country']} | {item['test_type']} | "
                f"state={item['prior_state']} | strength={item['prior_strength']:.2f} | focuses={focuses} | "
                f"next={item['next_learning_step']}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_or_build(path: Path, builder: Any) -> dict[str, Any]:
    if not path.exists():
        builder()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _prior_from_pattern(item: dict[str, Any], project_item: dict[str, Any], index: int) -> dict[str, Any]:
    signal_score = float(project_item.get("signal_score") or 0.0)
    pending_slot_count = int(item.get("pending_slot_count") or 0)
    critical_count = int((item.get("priority_breakdown") or {}).get("critical") or 0)
    next_learning_step = str(item.get("next_learning_step") or "")
    if next_learning_step == "resolve_approval_and_capture_slot_results":
        prior_state = "approval_pending"
    elif next_learning_step == "capture_slot_results":
        prior_state = "result_capture_pending"
    else:
        prior_state = "pattern_ready"
    prior_strength = min(0.95, max(0.35, (signal_score * 0.65) + (pending_slot_count * 0.04) + (critical_count * 0.02)))
    learning_speed_bias = min(1.0, 0.40 + (pending_slot_count * 0.05))
    blockers = sorted(
        {
            str(blocker or "").strip()
            for slot in item.get("slots") or []
            for blocker in list(slot.get("missing_evidence") or [])
            if str(blocker or "").strip()
        }
    )
    recommendation = (
        "Resolve approval first, then run the slot validation plan."
        if prior_state == "approval_pending"
        else ("Capture slot win/loss outcomes next." if prior_state == "result_capture_pending" else "Promote the closed pattern into reusable memory.")
    )
    return {
        "prior_id": f"discovery_pattern_prior_{index:03d}",
        "project": item.get("project", ""),
        "channel": item.get("channel", ""),
        "country": item.get("country", ""),
        "test_type": item.get("test_type", ""),
        "prior_state": prior_state,
        "prior_strength": round(prior_strength, 4),
        "learning_speed_bias": round(learning_speed_bias, 4),
        "pending_slot_count": pending_slot_count,
        "critical_slot_count": critical_count,
        "prioritized_change_focuses": list(item.get("change_focuses") or []),
        "prioritized_pattern_keys": list(item.get("reusable_pattern_keys") or []),
        "approval_ids": list(item.get("approval_ids") or []),
        "manual_input_file": str(item.get("manual_input_file") or ""),
        "result_template_file": str(item.get("result_template_file") or ""),
        "next_learning_step": next_learning_step,
        "current_blockers": blockers,
        "recommendation": recommendation,
        "source_project_signal_score": round(signal_score, 4),
        "source_project_scale_potential": round(float(project_item.get("predicted_scale_potential") or 0.0), 4),
    }
