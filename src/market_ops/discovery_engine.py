from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.early_prediction import EarlyPredictionBuilder
from market_ops.exploration_budget import ExplorationBudgetBuilder
from market_ops.hypothesis_generator import HypothesisGeneratorBuilder
from market_ops.new_product_stage import NewProductStageBuilder
from market_ops.signal_score import SignalScoreBuilder
from market_ops.transfer_learning import TransferLearningBuilder


@dataclass(slots=True)
class DiscoveryEngineResult:
    markdown_path: Path
    json_path: Path
    passed: bool
    child_paths: dict[str, Path]


class DiscoveryEngineBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryEngineResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")

        stage_result = NewProductStageBuilder(self._settings).build(report_date)
        signal_result = SignalScoreBuilder(self._settings).build(report_date)
        budget_result = ExplorationBudgetBuilder(self._settings).build(report_date)
        prediction_result = EarlyPredictionBuilder(self._settings).build(report_date)
        transfer_result = TransferLearningBuilder(self._settings).build(report_date)
        hypothesis_result = HypothesisGeneratorBuilder(self._settings).build(report_date)

        payload = self.build_payload(report_date)
        child_paths = {
            "new_product_stage": stage_result.markdown_path,
            "discovery_signal": signal_result.markdown_path,
            "exploration_budget": budget_result.markdown_path,
            "early_prediction": prediction_result.markdown_path,
            "transfer_learning": transfer_result.markdown_path,
            "hypothesis_plan": hypothesis_result.markdown_path,
        }
        payload["child_paths"] = {key: str(path) for key, path in child_paths.items()}
        payload["passed"] = all(
            result.passed
            for result in (stage_result, signal_result, budget_result, prediction_result, transfer_result, hypothesis_result)
        )

        markdown_path = output_dir / f"discovery_engine_{suffix}.md"
        json_path = output_dir / f"discovery_engine_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryEngineResult(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=bool(payload["passed"]),
            child_paths=child_paths,
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        from market_ops.growth_playbook import GrowthPlaybookBuilder
        from market_ops.learning_evidence_queue import LearningEvidenceQueueBuilder

        stage_payload = NewProductStageBuilder(self._settings).build_payload(report_date)
        signal_payload = SignalScoreBuilder(self._settings).build_payload(report_date)
        budget_payload = ExplorationBudgetBuilder(self._settings).build_payload(report_date)
        prediction_payload = EarlyPredictionBuilder(self._settings).build_payload(report_date)
        hypothesis_payload = HypothesisGeneratorBuilder(self._settings).build_payload(report_date)
        playbook_payload = _load_or_build(
            self._settings.active_output_dir / f"growth_playbook_{suffix}.json",
            lambda: GrowthPlaybookBuilder(self._settings).build(report_date),
        )
        evidence_payload = _load_or_build(
            self._settings.active_output_dir / f"learning_evidence_queue_{suffix}.json",
            lambda: LearningEvidenceQueueBuilder(self._settings).build(report_date),
        )

        signal_index = {item["project"]: item for item in signal_payload.get("items") or []}
        budget_index = {item["project"]: item for item in budget_payload.get("items") or []}
        prediction_index = {item["project"]: item for item in prediction_payload.get("items") or []}
        grouped_hypotheses = _group_hypotheses_by_project(hypothesis_payload.get("hypotheses") or [])
        slot_patterns = _summarize_slot_patterns(
            playbook_payload.get("candidate_rules") or [],
            evidence_payload.get("queue_items") or [],
            hypothesis_payload.get("hypotheses") or [],
        )
        slot_patterns_by_project = _group_slot_patterns_by_project(slot_patterns)

        projects: list[dict[str, Any]] = []
        for stage in stage_payload.get("items") or []:
            project = str(stage.get("project") or "")
            signal = signal_index.get(project, {})
            budget = budget_index.get(project, {})
            prediction = prediction_index.get(project, {})
            project_hypotheses = grouped_hypotheses.get(project, [])
            hypothesis = project_hypotheses[0] if project_hypotheses else {}
            if stage.get("stage") not in {"Discovery", "Validation"}:
                continue
            project_item = {
                "project": project,
                "stage": stage.get("stage"),
                "engine": "Discovery Engine",
                "signal_score": signal.get("signal_score", 0.0),
                "signal_level": signal.get("signal_level", "low"),
                "suggested_daily_budget": budget.get("suggested_daily_budget", 0.0),
                "predicted_scale_potential": prediction.get("predicted_scale_potential", 0.0),
                "next_hypothesis": hypothesis.get("hypothesis", ""),
                "recommended_action": signal.get("recommended_action", "collect_more_signals"),
                "discovery_source": "new_product_stage",
                "winner_material_asset_count": sum(
                    1 for item in project_hypotheses if item.get("source") == "local_winner_prior"
                ),
                "pattern_families": sorted(
                    {
                        str(item.get("test_type") or "")
                        for item in project_hypotheses
                        if str(item.get("test_type") or "").strip()
                    }
                ),
            }
            project_item.update(_slot_pattern_project_fields(slot_patterns_by_project.get(project, [])))
            projects.append(project_item)

        existing_projects = {str(item.get("project") or "") for item in projects}
        for item in _winner_material_projects(grouped_hypotheses, budget_index, prediction_index):
            if item["project"] in existing_projects:
                continue
            item.update(_slot_pattern_project_fields(slot_patterns_by_project.get(item["project"], [])))
            projects.append(item)

        projects.sort(key=lambda item: (item["signal_score"], item["predicted_scale_potential"]), reverse=True)
        winner_material_hypotheses = [
            item for item in (hypothesis_payload.get("hypotheses") or []) if item.get("source") == "local_winner_prior"
        ]

        return {
            "report_date": report_date.isoformat(),
            "window_start": signal_payload.get("window_start"),
            "window_end": signal_payload.get("window_end"),
            "mode": "discovery_mvp",
            "passed": True,
            "principle": "新品阶段优先级: 学习速度 > 方向发现 > 用户质量 > 增长势能 > ROI。",
            "summary": {
                "discovery_project_count": len(projects),
                "high_signal_count": sum(1 for item in projects if item["signal_level"] == "high"),
                "planned_hypotheses": len(hypothesis_payload.get("hypotheses") or []),
                "winner_material_hypotheses": int(
                    (hypothesis_payload.get("summary") or {}).get("winner_material_hypothesis_count") or 0
                ),
                "winner_material_project_count": sum(
                    1 for item in projects if item.get("discovery_source") == "winner_material_backlog"
                ),
                "winner_material_asset_count": len(winner_material_hypotheses),
                "discovery_slot_pattern_count": len(slot_patterns),
                "discovery_slot_candidate_count": sum(
                    int(item.get("pending_slot_count") or 0) for item in slot_patterns
                ),
                "discovery_slot_critical_count": sum(
                    int(item.get("priority_breakdown", {}).get("critical") or 0) for item in slot_patterns
                ),
            },
            "projects": projects,
            "discovery_slot_patterns": slot_patterns[:20],
            "winner_material_hypotheses": [
                {
                    "hypothesis_id": item.get("hypothesis_id"),
                    "project": item.get("project"),
                    "creative_id": item.get("creative_id", ""),
                    "creative_name": item.get("creative_name", ""),
                    "test_type": item.get("test_type"),
                    "hypothesis": item.get("hypothesis"),
                }
                for item in winner_material_hypotheses
            ][:20],
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Discovery Engine MVP | {payload['report_date']}",
            "",
            f"- Window: {payload.get('window_start')} to {payload.get('window_end')}",
            (
                f"- Discovery/validation projects: {summary['discovery_project_count']}; "
                f"high-signal: {summary['high_signal_count']}; hypotheses: {summary['planned_hypotheses']}"
            ),
            (
                f"- Local winner-material backlog projects: {summary['winner_material_project_count']}; "
                f"assets: {summary['winner_material_asset_count']}"
            ),
            (
                f"- Active discovery slot patterns: {summary['discovery_slot_pattern_count']}; "
                f"pending slots: {summary['discovery_slot_candidate_count']}; critical blockers: {summary['discovery_slot_critical_count']}"
            ),
            f"- Principle: {payload['principle']}",
            "- Mode: signal-only exploration backlog. No budget writes, no Feishu send, no ad-platform writes.",
            "",
            "## Exploration View",
            "",
            "| Project | Stage | Signal | Level | Suggested Budget | Scale Potential | Source | Next Hypothesis |",
            "|---|---|---:|---|---:|---:|---|---|",
        ]
        for item in payload["projects"]:
            lines.append(
                f"| {item['project']} | {item['stage']} | {float(item['signal_score']):.2f} | "
                f"{item['signal_level']} | {float(item['suggested_daily_budget']):.0f} | "
                f"{float(item['predicted_scale_potential']):.2f} | {item.get('discovery_source', '')} | "
                f"{item['next_hypothesis'] or 'collect more signals'} |"
            )
        if not payload["projects"]:
            lines.append("| None | - | 0 | low | 0 | 0 | - | no discovery or validation project yet |")

        lines.extend(["", "## Active Discovery Patterns", ""])
        if not payload.get("discovery_slot_patterns"):
            lines.append("- None.")
        for item in payload.get("discovery_slot_patterns") or []:
            focuses = ",".join(item.get("change_focuses") or []) or "none"
            approvals = ",".join(item.get("approval_ids") or []) or "none"
            lines.append(
                f"- {item['project']} | {item['channel']}/{item['country']} | {item['test_type']} | "
                f"slots={item['pending_slot_count']} | focuses={focuses} | approvals={approvals} | "
                f"next={item['next_learning_step']}"
            )

        lines.extend(["", "## Child Artifacts", ""])
        for name, path in (payload.get("child_paths") or {}).items():
            lines.append(f"- {name}: {path}")
        lines.append("")
        return "\n".join(lines)


def _load_or_build(path: Path, builder: Any) -> dict[str, Any]:
    if not path.exists():
        builder()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _group_hypotheses_by_project(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        project = str(item.get("project") or "").strip()
        if not project:
            continue
        grouped.setdefault(project, []).append(item)
    return grouped


def _winner_material_projects(
    grouped_hypotheses: dict[str, list[dict[str, Any]]],
    budget_index: dict[str, dict[str, Any]],
    prediction_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for project, hypotheses in grouped_hypotheses.items():
        winner_items = [item for item in hypotheses if item.get("source") == "local_winner_prior"]
        if not winner_items:
            continue

        budget = budget_index.get(project, {})
        prediction = prediction_index.get(project, {})
        avg_signal = sum(
            float((item.get("source_signals") or {}).get("label_confidence") or 0.0) for item in winner_items
        ) / max(len(winner_items), 1)
        avg_scale = sum(
            float((item.get("source_signals") or {}).get("predicted_scalability") or 0.0) for item in winner_items
        ) / max(len(winner_items), 1)
        signal_score = round(max(avg_signal, avg_scale), 4)
        signal_level = "high" if signal_score >= 0.75 else ("medium" if signal_score >= 0.60 else "low")
        pattern_families = sorted(
            {
                str(item.get("test_type") or "")
                for item in winner_items
                if str(item.get("test_type") or "").strip()
            }
        )
        recommended_action = "manual_winner_material_validation"
        if "winner_hook_clone_test" in pattern_families and "winner_image_to_motion_test" in pattern_families:
            recommended_action = "parallel_winner_pattern_validation"

        projects.append(
            {
                "project": project,
                "stage": "Validation",
                "engine": "Discovery Engine",
                "signal_score": signal_score,
                "signal_level": signal_level,
                "suggested_daily_budget": budget.get("suggested_daily_budget", 0.0),
                "predicted_scale_potential": round(
                    max(float(prediction.get("predicted_scale_potential") or 0.0), avg_scale),
                    4,
                ),
                "next_hypothesis": str(winner_items[0].get("hypothesis") or ""),
                "recommended_action": recommended_action,
                "discovery_source": "winner_material_backlog",
                "winner_material_asset_count": len(winner_items),
                "pattern_families": pattern_families,
            }
        )
    return projects


def _summarize_slot_patterns(
    candidate_rules: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_index = {
        str(item.get("source_hypothesis_id") or ""): item
        for item in evidence_items
        if str(item.get("source_hypothesis_id") or "").strip()
    }
    winner_hypothesis_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in hypotheses:
        if str(item.get("source") or "") != "local_winner_prior":
            continue
        test_plan = item.get("test_plan") or {}
        key = (
            str(item.get("project") or "").strip(),
            str(test_plan.get("channel") or "").strip(),
            str(test_plan.get("country") or "").strip(),
            str(item.get("test_type") or "").strip(),
        )
        if all(key):
            winner_hypothesis_groups.setdefault(key, []).append(item)
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for candidate in candidate_rules:
        if str(candidate.get("experiment_type") or "") != "discovery_slot_test":
            continue
        context = candidate.get("target_context") or {}
        project_label = str(context.get("project_label") or candidate.get("target_project") or "").strip()
        channel = str(context.get("channel") or "").strip()
        country = str(context.get("country") or "").strip()
        test_type = str(candidate.get("discovery_test_slot") or context.get("test_type") or "").strip()
        if not project_label or not test_type:
            continue
        item = dict(candidate)
        item["evidence"] = evidence_index.get(str(candidate.get("source_hypothesis_id") or ""), {})
        item["winner_hypotheses"] = winner_hypothesis_groups.get((project_label, channel, country, test_type), [])
        grouped.setdefault((project_label, channel, country, test_type), []).append(item)

    summaries: list[dict[str, Any]] = []
    for (project, channel, country, test_type), items in grouped.items():
        structure_bias = _structure_bias_from_slot_items(items)
        ordered_change_focuses = _order_change_focuses(
            [
                str(item.get("change_focus") or "").strip()
                for item in items
                if str(item.get("change_focus") or "").strip()
            ],
            structure_bias,
            test_type,
        )
        priority_breakdown = {
            level: sum(1 for item in items if str((item.get("evidence") or {}).get("priority") or "") == level)
            for level in ("critical", "high", "medium", "low")
        }
        approval_ids = sorted(
            {
                str((item.get("evidence") or {}).get("approval_id") or "").strip()
                for item in items
                if str((item.get("evidence") or {}).get("approval_id") or "").strip()
            }
        )
        required_fields = sorted(
            {
                str(field or "").strip()
                for item in items
                for field in list((item.get("evidence") or {}).get("required_template_fields") or [])
                if str(field or "").strip()
            }
        )
        manual_input_file = next(
            (
                str((item.get("evidence") or {}).get("manual_input_file") or "")
                for item in items
                if str((item.get("evidence") or {}).get("manual_input_file") or "").strip()
            ),
            "",
        )
        result_template_file = next(
            (
                str((item.get("evidence") or {}).get("result_template_file") or "")
                for item in items
                if str((item.get("evidence") or {}).get("result_template_file") or "").strip()
            ),
            "",
        )
        next_learning_step = "capture_slot_results"
        if any("approval_unblocked" in list((item.get("evidence") or {}).get("missing_evidence") or []) for item in items):
            next_learning_step = "resolve_approval_and_capture_slot_results"
        summaries.append(
            {
                "project": project,
                "channel": channel,
                "country": country,
                "test_type": test_type,
                "pending_slot_count": len(items),
                "change_focuses": ordered_change_focuses,
                "reusable_pattern_keys": sorted(
                    {
                        str(item.get("reusable_pattern_key") or "").strip()
                        for item in items
                        if str(item.get("reusable_pattern_key") or "").strip()
                    }
                ),
                "contextual_pattern_keys": sorted(
                    {
                        str(item.get("contextual_pattern_key") or "").strip()
                        for item in items
                        if str(item.get("contextual_pattern_key") or "").strip()
                    }
                ),
                "approval_ids": approval_ids,
                "priority_breakdown": priority_breakdown,
                "required_template_fields": required_fields,
                "manual_input_file": manual_input_file,
                "result_template_file": result_template_file,
                "next_learning_step": next_learning_step,
                "winner_structure_bias": structure_bias,
                "structure_signatures": sorted(
                    {
                        str(item.get("structure_signature") or "").strip()
                        for item in items
                        if str(item.get("structure_signature") or "").strip()
                    }
                ),
                "slots": [
                    {
                        "candidate_id": item.get("candidate_id", ""),
                        "source_hypothesis_id": item.get("source_hypothesis_id", ""),
                        "slot_id": item.get("slot_id", ""),
                        "variant_name": item.get("variant_name", ""),
                        "change_focus": item.get("change_focus", ""),
                        "primary_test_axis": item.get("primary_test_axis", ""),
                        "target_signature": item.get("target_signature", ""),
                        "reusable_pattern_key": item.get("reusable_pattern_key", ""),
                        "contextual_pattern_key": item.get("contextual_pattern_key", ""),
                        "structure_signature": item.get("structure_signature", ""),
                        "missing_evidence": list((item.get("evidence") or {}).get("missing_evidence") or item.get("missing_evidence") or []),
                    }
                    for item in items
                ][:12],
            }
        )
    summaries.sort(
        key=lambda item: (
            -int(item.get("priority_breakdown", {}).get("critical") or 0),
            -int(item.get("pending_slot_count") or 0),
            str(item.get("project") or ""),
            str(item.get("test_type") or ""),
        )
    )
    return summaries


def _group_slot_patterns_by_project(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        project = str(item.get("project") or "").strip()
        if not project:
            continue
        grouped.setdefault(project, []).append(item)
    return grouped


def _slot_pattern_project_fields(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "active_discovery_slot_pattern_count": 0,
            "active_discovery_slot_count": 0,
            "active_discovery_change_focuses": [],
            "active_discovery_approval_ids": [],
            "active_discovery_pattern_keys": [],
            "active_discovery_contextual_pattern_keys": [],
            "winner_structure_bias": [],
            "structure_signatures": [],
            "next_learning_step": "",
            "manual_input_file": "",
            "result_template_file": "",
        }
    first = items[0]
    next_learning_step = "capture_slot_results"
    if any(item.get("next_learning_step") == "resolve_approval_and_capture_slot_results" for item in items):
        next_learning_step = "resolve_approval_and_capture_slot_results"
    return {
        "active_discovery_slot_pattern_count": len(items),
        "active_discovery_slot_count": sum(int(item.get("pending_slot_count") or 0) for item in items),
        "active_discovery_change_focuses": sorted(
            {
                focus
                for item in items
                for focus in list(item.get("change_focuses") or [])
                if str(focus or "").strip()
            }
        ),
        "active_discovery_approval_ids": sorted(
            {
                approval_id
                for item in items
                for approval_id in list(item.get("approval_ids") or [])
                if str(approval_id or "").strip()
            }
        ),
        "active_discovery_pattern_keys": sorted(
            {
                pattern_key
                for item in items
                for pattern_key in list(item.get("reusable_pattern_keys") or [])
                if str(pattern_key or "").strip()
            }
        ),
        "active_discovery_contextual_pattern_keys": sorted(
            {
                pattern_key
                for item in items
                for pattern_key in list(item.get("contextual_pattern_keys") or [])
                if str(pattern_key or "").strip()
            }
        ),
        "winner_structure_bias": [
            bias
            for item in items
            for bias in list(item.get("winner_structure_bias") or [])
            if str(bias or "").strip()
        ][:20],
        "structure_signatures": sorted(
            {
                signature
                for item in items
                for signature in list(item.get("structure_signatures") or [])
                if str(signature or "").strip()
            }
        ),
        "next_learning_step": next_learning_step,
        "manual_input_file": str(first.get("manual_input_file") or ""),
        "result_template_file": str(first.get("result_template_file") or ""),
    }


def _structure_bias_from_slot_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    winner_hypotheses: list[dict[str, Any]] = []
    seen_hypothesis_ids: set[str] = set()
    for item in items:
        for hypothesis in list(item.get("winner_hypotheses") or []):
            if str((hypothesis or {}).get("source") or "") != "local_winner_prior":
                continue
            hypothesis_id = str((hypothesis or {}).get("hypothesis_id") or "").strip()
            if hypothesis_id and hypothesis_id in seen_hypothesis_ids:
                continue
            if hypothesis_id:
                seen_hypothesis_ids.add(hypothesis_id)
            winner_hypotheses.append(hypothesis)
    if not winner_hypotheses:
        return []

    orientation_counts: dict[str, int] = {}
    ratio_counts: dict[str, int] = {}
    duration_counts: dict[str, int] = {}
    test_type = str(items[0].get("discovery_test_slot") or items[0].get("test_type") or "")

    for hypothesis in winner_hypotheses:
        signals = hypothesis.get("source_signals") or {}
        orientation = str(signals.get("asset_orientation") or "").strip()
        ratio = str(signals.get("asset_aspect_ratio") or "").strip()
        duration_bucket = str(signals.get("asset_duration_bucket") or "").strip()
        if orientation and orientation != "unknown":
            orientation_counts[orientation] = orientation_counts.get(orientation, 0) + 1
        if ratio and ratio != "unknown":
            ratio_counts[ratio] = ratio_counts.get(ratio, 0) + 1
        if duration_bucket and duration_bucket != "unknown":
            duration_counts[duration_bucket] = duration_counts.get(duration_bucket, 0) + 1

    biases: list[dict[str, Any]] = []
    top_orientation = _top_count_key(orientation_counts)
    top_ratio = _top_count_key(ratio_counts)
    top_duration = _top_count_key(duration_counts)

    if top_orientation:
        biases.append(
            {
                "bias_type": "orientation",
                "value": top_orientation,
                "count": orientation_counts[top_orientation],
                "recommended_focus": "preserve_vertical_composition" if top_orientation == "portrait" else "preserve_square_crop",
            }
        )
    if top_ratio:
        biases.append(
            {
                "bias_type": "aspect_ratio",
                "value": top_ratio,
                "count": ratio_counts[top_ratio],
                "recommended_focus": "keep_9_16_framing" if top_ratio == "9:16_like" else "keep_1_1_framing" if top_ratio == "1:1_like" else "preserve_current_ratio",
            }
        )
    if top_duration and "winner_hook_clone_test" in test_type:
        biases.append(
            {
                "bias_type": "duration_bucket",
                "value": top_duration,
                "count": duration_counts[top_duration],
                "recommended_focus": "compress_opening_without_extending_total_length" if top_duration in {"mid", "long"} else "preserve_short_hook_density",
            }
        )
    return biases


def _top_count_key(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _order_change_focuses(change_focuses: list[str], structure_bias: list[dict[str, Any]], test_type: str) -> list[str]:
    unique_focuses = sorted({focus for focus in change_focuses if str(focus or "").strip()})
    if not unique_focuses:
        return []

    recommended_focuses = {
        str(item.get("recommended_focus") or "").strip()
        for item in structure_bias
        if str(item.get("recommended_focus") or "").strip()
    }

    priority_map: dict[str, int] = {}
    if "winner_hook_clone_test" in test_type:
        if "preserve_vertical_composition" in recommended_focuses or "keep_9_16_framing" in recommended_focuses:
            priority_map.update(
                {
                    "hook_rewrite": 0,
                    "hook_reorder": 1,
                    "subtitle_density": 2,
                    "cta_swap": 3,
                    "urgency_angle": 4,
                    "benefit_angle": 5,
                }
            )
        if "compress_opening_without_extending_total_length" in recommended_focuses:
            priority_map["hook_rewrite"] = min(priority_map.get("hook_rewrite", 99), 0)
            priority_map["hook_reorder"] = min(priority_map.get("hook_reorder", 99), 1)
            priority_map["subtitle_density"] = min(priority_map.get("subtitle_density", 99), 2)
    elif "winner_image_to_motion_test" in test_type:
        if "preserve_square_crop" in recommended_focuses or "keep_1_1_framing" in recommended_focuses:
            priority_map.update(
                {
                    "camera_push": 0,
                    "light_motion": 1,
                    "text_motion": 2,
                    "cta_motion": 3,
                }
            )
        elif "preserve_vertical_composition" in recommended_focuses or "keep_9_16_framing" in recommended_focuses:
            priority_map.update(
                {
                    "light_motion": 0,
                    "camera_push": 1,
                    "text_motion": 2,
                    "cta_motion": 3,
                }
            )

    return sorted(unique_focuses, key=lambda focus: (priority_map.get(focus, 99), focus))

    # ------------------------------------------------------------------
    # 闭环验证入口
    # ------------------------------------------------------------------

    def run_closed_loop(self, report_date: date, experiment_results: list[dict[str, Any]] | None = None):
        """运行完整的 Discovery 闭环：假设 → 验证 → 反馈。

        调用链：
        hypothesis_generator.build() → DiscoveryValidator.validate_batch()
        → generate_feedback() → 产出 validation report

        Args:
            report_date: 报告日期
            experiment_results: 可选，外部传入的实验结果。为 None 时从文件加载。
        """
        from market_ops.discovery_validator import DiscoveryValidator

        # 1) 确保 Discovery Engine 基础报告已生成
        discovery_result = self.build(report_date)

        # 2) 初始化验证器
        validator = DiscoveryValidator(
            settings=self._settings,
            min_sample_size=100,
            confidence_threshold=0.95,
        )

        # 3) 加载或使用传入的实验数据
        if experiment_results is None:
            experiment_results = validator.load_experiment_results(report_date)

        # 4) 执行验证
        if experiment_results:
            validator.validate_batch(experiment_results)
        else:
            # 无实验数据时，仍生成 feedback（基于已有假设）
            validator.load_hypotheses(report_date)  # 触发空验证路径

        # 5) 生成反馈 + 写入报告
        validation_report = validator.build(report_date)

        return discovery_result, validation_report
