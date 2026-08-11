from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.decision_engine import DecisionEngineBuilder
from market_ops.discovery_engine import DiscoveryEngineBuilder
from market_ops.hypothesis_generator import HypothesisGeneratorBuilder


@dataclass(slots=True)
class ExperimentPlanResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class ExperimentPlanBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ExperimentPlanResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"experiment_plan_{suffix}.md"
        json_path = output_dir / f"experiment_plan_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return ExperimentPlanResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        decision_payload = self._load_or_build_decisions(report_date)
        decision_experiments = [self._plan_for_decision(item, index) for index, item in enumerate(decision_payload.get("items") or [], start=1)]
        decision_experiments = [item for item in decision_experiments if item]
        proactive_experiments = self._load_winner_material_experiments(report_date)
        discovery_pattern_prior_payload = self._load_or_build_discovery_pattern_prior(report_date)
        discovery_experiments = self._load_discovery_backlog_experiments(report_date, discovery_pattern_prior_payload)
        experiments = proactive_experiments + discovery_experiments + decision_experiments
        return {
            "report_date": report_date.isoformat(),
            "mode": "parallel_validation",
            "passed": all(bool(item.get("rollback_metrics")) for item in experiments),
            "decision_engine_json": str(self._settings.active_output_dir / f"decision_engine_{report_date.strftime('%Y%m%d')}.json"),
            "discovery_pattern_prior_json": str(
                self._settings.active_output_dir / f"discovery_pattern_prior_{report_date.strftime('%Y%m%d')}.json"
            ),
            "summary": {
                "experiment_count": len(experiments),
                "growth_experiments": sum(
                    1
                    for item in experiments
                    if item.get("experiment_type") in {"budget_scale_test", "creative_copy_test", "discovery_creative_test_plan"}
                ),
                "protective_monitors": sum(1 for item in experiments if item.get("experiment_type") == "protective_monitor"),
                "evidence_capture": sum(1 for item in experiments if item.get("experiment_type") == "evidence_capture"),
                "proactive_winner_material_experiments": len(proactive_experiments),
                "discovery_backlog_experiments": len(discovery_experiments),
                "discovery_prior_attached_experiments": sum(
                    1 for item in discovery_experiments if float(item.get("discovery_pattern_prior_strength") or 0.0) > 0.0
                ),
            },
            "experiments": experiments,
        }

    def _load_or_build_decisions(self, report_date: date) -> dict[str, Any]:
        path = self._settings.active_output_dir / f"decision_engine_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            DecisionEngineBuilder(self._settings).build(report_date)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": []}

    def _load_or_build_discovery_pattern_prior(self, report_date: date) -> dict[str, Any]:
        path = self._settings.active_output_dir / f"discovery_pattern_prior_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            from market_ops.discovery_pattern_prior import DiscoveryPatternPriorBuilder

            DiscoveryPatternPriorBuilder(self._settings).build(report_date)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"priors": []}

    def _load_winner_material_experiments(self, report_date: date) -> list[dict[str, Any]]:
        hypothesis_payload = self._load_existing_hypotheses(report_date)
        experiments: list[dict[str, Any]] = []
        index = 1
        for item in hypothesis_payload.get("hypotheses") or []:
            if item.get("source") != "local_winner_prior":
                continue
            test_plan = item.get("test_plan") or {}
            source_signals = item.get("source_signals") or {}
            experiments.append(
                {
                    "experiment_id": f"exp_local_winner_{index:03d}",
                    "experiment_type": "creative_copy_test",
                    "target": " / ".join(
                        part
                        for part in (
                            item.get("project"),
                            test_plan.get("channel"),
                            test_plan.get("country"),
                            item.get("creative_id"),
                        )
                        if part
                    ),
                    "linked_decision": "proactive_local_winner_test",
                    "hypothesis": item.get("hypothesis"),
                    "change": f"{test_plan.get('variant_a', '')} -> {test_plan.get('variant_b', '')}",
                    "duration": str(test_plan.get("duration") or "3d"),
                    "success_metrics": list(item.get("success_metrics") or []),
                    "rollback_metrics": list(item.get("rollback_metrics") or []),
                    "experiment_confidence": source_signals.get("label_confidence", 0.0),
                    "owner": "素材负责人",
                    "mode": "proactive_winner_material_validation",
                    "source": "local_winner_prior",
                    "creative_id": item.get("creative_id", ""),
                    "creative_name": item.get("creative_name", ""),
                }
            )
            index += 1
        return experiments

    def _load_discovery_backlog_experiments(
        self,
        report_date: date,
        discovery_pattern_prior_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        suffix = report_date.strftime("%Y%m%d")
        discovery_payload = _load_json(self._settings.active_output_dir / f"discovery_engine_{suffix}.json")
        hypothesis_payload = self._load_existing_hypotheses(report_date)
        winner_hypotheses = [item for item in (hypothesis_payload.get("hypotheses") or []) if item.get("source") == "local_winner_prior"]
        grouped_hypotheses = _group_winner_hypotheses(winner_hypotheses)
        slot_pattern_index = {
            (
                str(item.get("project") or "").strip(),
                str(item.get("test_type") or "").strip(),
                str(item.get("channel") or "").strip(),
                str(item.get("country") or "").strip(),
            ): item
            for item in discovery_payload.get("discovery_slot_patterns") or []
            if str(item.get("project") or "").strip() and str(item.get("test_type") or "").strip()
        }
        prior_index = {
            (
                str(item.get("project") or "").strip(),
                str(item.get("test_type") or "").strip(),
                str(item.get("channel") or "").strip(),
                str(item.get("country") or "").strip(),
            ): item
            for item in discovery_pattern_prior_payload.get("priors") or []
            if str(item.get("project") or "").strip() and str(item.get("test_type") or "").strip()
        }
        experiments: list[dict[str, Any]] = []
        for item in discovery_payload.get("projects") or []:
            if str(item.get("discovery_source") or "") != "winner_material_backlog":
                continue
            if float(item.get("signal_score") or 0.0) < 0.60:
                continue
            project = str(item.get("project") or "").strip()
            if not project:
                continue
            for key, hypotheses in grouped_hypotheses.items():
                if key[0] != project:
                    continue
                experiments.append(
                    _build_discovery_backlog_experiment(
                        project_payload=item,
                        hypotheses=hypotheses,
                        test_type=key[1],
                        channel=key[2],
                        country=key[3],
                        slot_pattern=slot_pattern_index.get((key[0], key[1], key[2], key[3]), {}),
                        pattern_prior=prior_index.get((key[0], key[1], key[2], key[3]), {}),
                    )
                )
        experiments.sort(
            key=lambda item: (
                -float(item.get("planning_priority_score") or 0.0),
                -float(item.get("discovery_pattern_prior_strength") or 0.0),
                -float(item.get("experiment_confidence") or 0.0),
                str(item.get("target") or ""),
            )
        )
        return experiments

    def _load_existing_hypotheses(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        return _load_json(self._settings.active_output_dir / f"hypothesis_plan_{suffix}.json")

    @staticmethod
    def _plan_for_decision(item: dict[str, Any], index: int) -> dict[str, Any] | None:
        decision = str(item.get("decision") or "")
        if decision == "hold":
            return None
        target = " / ".join(part for part in (item.get("project"), item.get("scope"), item.get("entity_id")) if part)
        owner = _owner_for_item(item)
        action_text = str(item.get("recommended_action_signal") or "")
        if decision == "data_blocked":
            experiment_type = "evidence_capture"
            change = "capture missing quality, payback, fatigue, and attribution evidence; no budget change"
            needs = list(item.get("lifecycle_next_learning_need") or [])
            hypothesis = f"{target} is blocked because lifecycle evidence is incomplete; filling the missing fields can reopen Decision Engine evaluation."
            success_metrics = [
                "required quality/payback fields are populated",
                "fatigue evidence is refreshed for the same project window",
                "Decision Engine can reclassify the object without data_blocked",
            ]
            rollback_metrics = [
                "required evidence remains missing after the capture window",
                "new evidence confirms quality/payback gap is structural",
            ]
            if needs:
                success_metrics.append("learning needs addressed: " + " | ".join(needs[:3]))
        elif decision == "small_scale_up":
            experiment_type = "creative_copy_test" if item.get("entity_type") == "creative" or "复制" in action_text else "budget_scale_test"
            change = "+10% budget cap" if experiment_type == "budget_scale_test" else "3 new creative variants"
            hypothesis = f"{target} 已出现局部增长信号，小额验证不会显著拉低 ROI。"
            success_metrics = ["D3 ROI 不低于当前对象基线", "CTR 不下降超过 10%", "CPI 不上升超过 15%"]
            rollback_metrics = ["CTR 下降超过 15%", "CPI 上升超过 20%", "D3 ROI 低于基线 15%"]
        elif decision in {"downweight", "pause_or_review"}:
            experiment_type = "protective_monitor"
            change = "reduce or hold spend after human review"
            hypothesis = f"{target} 风险较高，先用保护性监控避免低效消耗扩大。"
            success_metrics = ["低效花费占比下降", "ROI 不继续恶化"]
            rollback_metrics = ["降权后核心量级异常下滑", "归因复核确认不是低效问题"]
        elif decision == "repair":
            experiment_type = "repair_validation"
            change = "repair targeting, attribution, or creative mix"
            hypothesis = f"{target} 更适合先修复结构或归因问题，再评估是否扩量。"
            success_metrics = ["归因或结构问题被复核", "D7 ROI 回升或低效段花费下降"]
            rollback_metrics = ["复核后仍无有效收入", "修复后 CPI 上升超过 20%"]
        else:
            experiment_type = "observation_hold"
            change = "no budget change"
            hypothesis = f"{target} 当前信号不足以扩量，继续观察更稳妥。"
            success_metrics = ["样本继续积累", "ROI 与 CTR 保持稳定"]
            rollback_metrics = ["ROI 下降超过 15%", "CTR 下降超过 15%"]

        return {
            "experiment_id": f"exp_{item.get('entity_type', 'entity')}_{index:03d}",
            "experiment_type": experiment_type,
            "target": target,
            "linked_decision": decision,
            "hypothesis": hypothesis,
            "change": change,
            "duration": "3d",
            "success_metrics": success_metrics,
            "rollback_metrics": rollback_metrics,
            "experiment_confidence": item.get("confidence", 0.0),
            "owner": owner,
            "mode": "parallel_validation",
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# V2.5 实验计划 | {payload['report_date']}",
            "",
            "- 模式：parallel_validation，不自动执行预算或广告平台写操作。",
            f"- 实验数：{summary['experiment_count']}；增长实验：{summary['growth_experiments']}；保护性监控：{summary['protective_monitors']}；证据补齐：{summary['evidence_capture']}。",
            "",
            "## 实验列表",
            "",
        ]
        for item in payload["experiments"]:
            lines.extend(
                [
                    f"### {item['experiment_id']} | {item['experiment_type']}",
                    f"- 对象：{item['target']}",
                    f"- 假设：{item['hypothesis']}",
                    f"- 变更：{item['change']}",
                    f"- 周期：{item['duration']}",
                    f"- 成功指标：{'；'.join(item['success_metrics'])}",
                    f"- 回滚指标：{'；'.join(item['rollback_metrics'])}",
                    f"- 负责人建议：{item['owner']}",
                    "",
                ]
            )
        if not payload["experiments"]:
            lines.append("- 暂无需要生成实验计划的决策。")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _discovery_experiment_id(project: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in str(project or "")).strip("_")
    slug = "_".join(part for part in slug.split("_") if part)
    return f"discovery_plan_{slug or 'backlog'}"


def _group_winner_hypotheses(items: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in items:
        project = str(item.get("project") or "").strip()
        test_type = str(item.get("test_type") or "").strip()
        test_plan = item.get("test_plan") or {}
        channel = str(test_plan.get("channel") or "Unknown").strip()
        country = str(test_plan.get("country") or "Global").strip()
        if not project or not test_type:
            continue
        grouped.setdefault((project, test_type, channel, country), []).append(item)
    return grouped


def _build_discovery_backlog_experiment(
    *,
    project_payload: dict[str, Any],
    hypotheses: list[dict[str, Any]],
    test_type: str,
    channel: str,
    country: str,
    slot_pattern: dict[str, Any],
    pattern_prior: dict[str, Any],
) -> dict[str, Any]:
    project = str(project_payload.get("project") or "")
    asset_count = len(hypotheses)
    creative_names = [str(item.get("creative_name") or item.get("creative_id") or "").strip() for item in hypotheses]
    creative_names = [item for item in creative_names if item]
    baseline_preview = creative_names[:3]
    avg_confidence = round(
        sum(float((item.get("source_signals") or {}).get("label_confidence") or 0.0) for item in hypotheses) / max(asset_count, 1),
        4,
    )
    avg_scalability = round(
        sum(float((item.get("source_signals") or {}).get("predicted_scalability") or 0.0) for item in hypotheses) / max(asset_count, 1),
        4,
    )
    discovery_prioritized_change_focuses = list(slot_pattern.get("change_focuses") or [])
    winner_structure_bias = list(slot_pattern.get("winner_structure_bias") or [])
    prior_strength = float(pattern_prior.get("prior_strength") or 0.0)
    learning_speed_bias = float(pattern_prior.get("learning_speed_bias") or 0.0)
    planning_priority_score = round(
        float(project_payload.get("signal_score") or 0.0) + (prior_strength * 0.10) + (learning_speed_bias * 0.05),
        4,
    )
    experiment_confidence = round(
        min(0.99, max(float(project_payload.get("signal_score") or 0.0), avg_confidence) + (prior_strength * 0.05)),
        4,
    )
    if test_type == "winner_image_to_motion_test":
        hypothesis = (
            f"{project} has {asset_count} image winners on {channel}/{country}; "
            "a motion-first variant set can validate whether image-to-motion is a scalable growth pattern."
        )
        change = f"Create image-to-motion variants for {asset_count} winner images."
        variant_count_target = min(max(asset_count, 2), 4)
        control_dimensions = ["targeting_constant", "budget_constant", "motion_only_change"]
        variant_plan_summary = f"{variant_count_target} motion variants from image winners"
        primary_test_axis = "motion treatment"
        baseline_asset_type = "image"
    else:
        hypothesis = (
            f"{project} has {asset_count} video winners on {channel}/{country}; "
            "first-3-second and CTA controlled variants can validate whether the winner hook is reusable."
        )
        change = f"Create first-3-second or CTA variants for {asset_count} winner videos."
        variant_count_target = min(max(asset_count, 3), 6)
        control_dimensions = ["targeting_constant", "budget_constant", "hook_or_cta_only_change"]
        variant_plan_summary = f"{variant_count_target} hook or CTA variants from video winners"
        primary_test_axis = "hook or CTA"
        baseline_asset_type = "video"
    return {
        "experiment_id": _discovery_backlog_experiment_id(project, test_type, channel, country),
        "experiment_type": "discovery_creative_test_plan",
        "target": " / ".join(part for part in (project, channel, country, test_type) if part),
        "linked_decision": str(project_payload.get("recommended_action") or "discovery_backlog"),
        "hypothesis": hypothesis,
        "change": change,
        "duration": "3d",
        "success_metrics": [
            "post_action_ctr",
            "post_action_cpi",
            "post_action_roi_or_roas",
            "created_variant_count",
        ],
        "rollback_metrics": [
            "CTR declines more than 15% versus the baseline winner direction",
            "CPI rises more than 20% without ROI improvement",
            "fatigue risk increases before the pattern is clarified",
        ],
        "experiment_confidence": experiment_confidence,
        "planning_priority_score": planning_priority_score,
        "owner": "discovery_manual_owner",
        "mode": "parallel_validation",
        "source": "discovery_backlog",
        "creative_id": "",
        "creative_name": project,
        "project": project,
        "pattern_families": [test_type],
        "winner_material_asset_count": asset_count,
        "discovery_stage": str(project_payload.get("stage") or ""),
        "channel": channel,
        "country": country,
        "learning_goal": str(((hypotheses[0].get("expected_impact") or {}).get("learning_goal")) or ""),
        "baseline_creative_names": creative_names,
        "baseline_creative_ids": [str(item.get("creative_id") or "") for item in hypotheses if str(item.get("creative_id") or "").strip()],
        "baseline_asset_preview": baseline_preview,
        "baseline_asset_type": baseline_asset_type,
        "variant_count_target": variant_count_target,
        "control_dimensions": control_dimensions,
        "primary_test_axis": primary_test_axis,
        "variant_plan_summary": variant_plan_summary,
        "avg_predicted_scalability": avg_scalability,
        "avg_label_confidence": avg_confidence,
        "test_type": test_type,
        "discovery_prioritized_change_focuses": discovery_prioritized_change_focuses,
        "winner_structure_bias": winner_structure_bias,
        "structural_test_rationale": _structural_test_rationale(winner_structure_bias),
        "discovery_pattern_prior_strength": round(prior_strength, 4),
        "discovery_pattern_prior_state": str(pattern_prior.get("prior_state") or ""),
        "discovery_pattern_prior_reason": str(pattern_prior.get("recommendation") or ""),
        "discovery_pattern_prioritized_change_focuses": list(pattern_prior.get("prioritized_change_focuses") or []),
        "discovery_pattern_prioritized_keys": list(pattern_prior.get("prioritized_pattern_keys") or []),
        "discovery_pattern_learning_speed_bias": round(learning_speed_bias, 4),
        "discovery_pattern_prior_approval_ids": list(pattern_prior.get("approval_ids") or []),
        "discovery_pattern_prior_current_blockers": list(pattern_prior.get("current_blockers") or []),
        "discovery_pattern_prior_manual_input_file": str(pattern_prior.get("manual_input_file") or ""),
        "discovery_pattern_prior_result_template_file": str(pattern_prior.get("result_template_file") or ""),
    }


def _discovery_backlog_experiment_id(project: str, test_type: str, channel: str, country: str) -> str:
    parts = [project, test_type, channel, country]
    slug = "".join(char.lower() if char.isalnum() else "_" for char in "_".join(parts)).strip("_")
    slug = "_".join(part for part in slug.split("_") if part)
    return f"discovery_plan_{slug or 'backlog'}"


def _structural_test_rationale(winner_structure_bias: list[dict[str, Any]]) -> str:
    if not winner_structure_bias:
        return ""
    parts: list[str] = []
    for item in winner_structure_bias:
        bias_type = str(item.get("bias_type") or "").strip()
        value = str(item.get("value") or "").strip()
        recommended_focus = str(item.get("recommended_focus") or "").strip()
        if not bias_type or not value:
            continue
        if recommended_focus:
            parts.append(f"{bias_type}={value} -> {recommended_focus}")
        else:
            parts.append(f"{bias_type}={value}")
    return " | ".join(parts)


def _owner_for_item(item: dict[str, Any]) -> str:
    actions = item.get("management_action_signals") or []
    if actions and actions[0].get("owner"):
        return str(actions[0]["owner"])
    if item.get("entity_type") == "creative":
        return "素材负责人"
    return "投放负责人"
