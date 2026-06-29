from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_pattern_prior import DiscoveryPatternPriorBuilder
from market_ops.hypothesis_generator import HypothesisGeneratorBuilder


ACTION_TYPES = {
    "scale_budget",
    "hold_budget",
    "repair_structure",
    "copy_creative_pattern",
    "downweight_campaign",
    "pause_candidate_review",
}


@dataclass(slots=True)
class AiMediaBuyerPlanResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class AiMediaBuyerPlanBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> AiMediaBuyerPlanResult:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = self.build_payload(report_date)
        markdown_path = output_dir / f"ai_media_buyer_plan_{suffix}.md"
        json_path = output_dir / f"ai_media_buyer_plan_{suffix}.json"
        csv_path = output_dir / f"ai_media_buyer_plan_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["actions"])
        return AiMediaBuyerPlanResult(markdown_path, json_path, csv_path, True)

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        active = self._settings.active_output_dir
        growth = _load_json(active / f"growth_priorities_{suffix}.json")
        dna = _load_json(active / f"creative_dna_{suffix}.json")
        clusters = _load_json(active / f"creative_clusters_{suffix}.json")
        fatigue = _load_json(active / f"creative_fatigue_{suffix}.json")
        payback = _load_json(active / f"dynamic_payback_{suffix}.json")
        discovery = _load_json(active / f"discovery_engine_{suffix}.json")
        discovery_pattern_prior = _load_or_build(
            active / f"discovery_pattern_prior_{suffix}.json",
            lambda: DiscoveryPatternPriorBuilder(self._settings).build(report_date),
        )
        hypothesis = _load_json(active / f"hypothesis_plan_{suffix}.json")
        actions: list[dict[str, Any]] = []
        actions.extend(_discovery_actions(discovery, discovery_pattern_prior, hypothesis))
        actions.extend(_growth_actions(growth))
        actions.extend(_cluster_actions(clusters))
        actions.extend(_fatigue_actions(fatigue))
        actions.extend(_payback_actions(payback))
        actions = _dedupe_actions(actions)
        return {
            "report_date": report_date.isoformat(),
            "source_files": {
                "growth_priorities": str(active / f"growth_priorities_{suffix}.json"),
                "creative_dna": str(active / f"creative_dna_{suffix}.json"),
                "creative_clusters": str(active / f"creative_clusters_{suffix}.json"),
                "creative_fatigue": str(active / f"creative_fatigue_{suffix}.json"),
                "dynamic_payback": str(active / f"dynamic_payback_{suffix}.json"),
                "discovery_engine": str(active / f"discovery_engine_{suffix}.json"),
                "discovery_pattern_prior": str(active / f"discovery_pattern_prior_{suffix}.json"),
                "hypothesis_plan": str(active / f"hypothesis_plan_{suffix}.json"),
            },
            "rules": {
                "allowed_actions": sorted(ACTION_TYPES),
                "execution": "advisory only; no Feishu send, no budget write, no platform write",
                "budget_guardrail": "all budget actions require approval_required=true, max_change_pct and rollback_conditions",
            },
            "summary": {
                "action_count": len(actions),
                "approval_required_count": sum(1 for item in actions if item["approval_required"]),
                "scale_budget_count": sum(1 for item in actions if item["action_type"] == "scale_budget"),
                "copy_pattern_count": sum(1 for item in actions if item["action_type"] == "copy_creative_pattern"),
                "discovery_test_plan_count": sum(1 for item in actions if item.get("source") == "discovery_engine"),
                "discovery_pattern_prior_action_count": sum(
                    1 for item in actions if float(item.get("discovery_pattern_prior_strength") or 0.0) > 0.0
                ),
            },
            "actions": actions,
        }

    @staticmethod
    def _write_csv(path: Path, actions: list[dict[str, Any]]) -> None:
        fieldnames = [
            "action_type",
            "target",
            "project",
            "priority",
            "recommendation",
            "max_change_pct",
            "approval_required",
            "rollback_conditions",
            "evidence",
            "confidence",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in actions:
                row = {field: item.get(field, "") for field in fieldnames}
                row["rollback_conditions"] = "；".join(item.get("rollback_conditions") or [])
                row["evidence"] = "；".join(item.get("evidence") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# AI Media Buyer Plan | {payload['report_date']}",
            "",
            "- 输出为投放建议和审批清单，不发送飞书、不改预算、不写广告平台。",
            "- 预算相关动作全部带 approval_required、最大变更幅度和回撤条件。",
            "",
            "## 概览",
            "",
            f"- 动作数：{summary['action_count']}",
            f"- 需要审批：{summary['approval_required_count']}",
            f"- 加预算候选：{summary['scale_budget_count']}；复制素材模式：{summary['copy_pattern_count']}",
            "",
            "## 动作清单",
            "",
        ]
        if not payload["actions"]:
            lines.append("- 暂无动作。")
        else:
            lines.extend(
                [
                    "| 动作 | 对象 | 项目 | 优先级 | 最大变更 | 需审批 | 置信度 | 建议 | 回撤条件 |",
                    "|---|---|---|---:|---:|---|---|---|---|",
                ]
            )
            for item in payload["actions"]:
                lines.append(
                    f"| {item['action_type']} | {item['target']} | {item['project']} | {item['priority']:.2f} | "
                    f"{item['max_change_pct']:.0%} | {item['approval_required']} | {item['confidence']} | {item['recommendation']} | "
                    f"{'；'.join(item['rollback_conditions'])} |"
                )
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_or_build(path: Path, builder: Any) -> dict[str, Any]:
    if not path.exists():
        builder()
    return _load_json(path)


def _growth_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in (payload.get("top_growth_candidates") or [])[:8]:
        confidence = str(item.get("confidence") or "low")
        if confidence == "low":
            continue
        entity_type = str(item.get("entity_type") or "")
        if entity_type == "campaign" and float(item.get("roi") or 0.0) >= 1.2:
            action_type = "scale_budget"
            max_change = 0.10
            recommendation = "小额扩量验证，保持局部突破护栏。"
        elif entity_type == "creative":
            action_type = "copy_creative_pattern"
            max_change = 0.0
            recommendation = "复制素材模式进入测试组，不直接替换预算判断。"
        else:
            action_type = "hold_budget"
            max_change = 0.0
            recommendation = "保持预算，向下层 Campaign/素材找局部赢家。"
        actions.append(_action(action_type, item.get("entity_id"), item.get("project"), item.get("growth_priority"), recommendation, max_change, confidence, item.get("reason") or []))
    for item in (payload.get("repair_or_downweight") or [])[:8]:
        if str(item.get("confidence") or "low") == "low":
            continue
        action_type = "downweight_campaign" if item.get("entity_type") == "campaign" else "repair_structure"
        actions.append(_action(action_type, item.get("entity_id"), item.get("project"), item.get("risk_priority"), "降权或修复低效结构，先复核归因和国家/素材构成。", 0.10, item.get("confidence"), item.get("reason") or []))
    return actions


def _discovery_actions(
    payload: dict[str, Any],
    discovery_pattern_prior_payload: dict[str, Any],
    hypothesis_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    grouped_hypotheses = _group_discovery_hypotheses(hypothesis_payload.get("hypotheses") or [])
    slot_patterns = {
        (
            str(item.get("project") or "").strip(),
            str(item.get("test_type") or "").strip(),
            str(item.get("channel") or "").strip(),
            str(item.get("country") or "").strip(),
        ): item
        for item in payload.get("discovery_slot_patterns") or []
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
    for item in payload.get("projects") or []:
        if item.get("discovery_source") != "winner_material_backlog":
            continue
        project = str(item.get("project") or "")
        signal_score = float(item.get("signal_score") or 0.0)
        if signal_score < 0.60:
            continue
        for key, hypotheses in grouped_hypotheses.items():
            if key[0] != project:
                continue
            test_type = key[1]
            channel = key[2]
            country = key[3]
            slot_pattern = slot_patterns.get((project, test_type, channel, country), {})
            pattern_prior = prior_index.get((project, test_type, channel, country), {})
            asset_count = len(hypotheses)
            if test_type == "winner_image_to_motion_test":
                variant_count_target = min(max(asset_count, 2), 4)
                primary_test_axis = "motion treatment"
                control_dimensions = ["targeting_constant", "budget_constant", "motion_only_change"]
                baseline_asset_preview = [
                    str(h.get("creative_name") or h.get("creative_id") or "").strip()
                    for h in hypotheses[:3]
                    if str(h.get("creative_name") or h.get("creative_id") or "").strip()
                ]
            else:
                variant_count_target = min(max(asset_count, 3), 6)
                primary_test_axis = "hook or CTA"
                control_dimensions = ["targeting_constant", "budget_constant", "hook_or_cta_only_change"]
                baseline_asset_preview = [
                    str(h.get("creative_name") or h.get("creative_id") or "").strip()
                    for h in hypotheses[:3]
                    if str(h.get("creative_name") or h.get("creative_id") or "").strip()
                ]
            prior_strength = float(pattern_prior.get("prior_strength") or 0.0)
            action_priority = signal_score + (prior_strength * 0.10)
            recommendation = f"{project} {channel}/{country} {test_type} controlled discovery test"
            if prior_strength > 0.0:
                recommendation = (
                    f"{project} {channel}/{country} {test_type} continue discovery pattern validation first"
                )
            action = _action(
                "copy_creative_pattern",
                " / ".join(part for part in (project, channel, country, test_type) if part),
                project,
                action_priority,
                recommendation,
                0.0,
                item.get("signal_level", "medium"),
                [
                    f"discovery_source={item.get('discovery_source')}",
                    f"winner_material_asset_count={asset_count}",
                    f"pattern_families={test_type}",
                    f"predicted_scale_potential={float(item.get('predicted_scale_potential') or 0.0):.2f}",
                    f"channel={channel}",
                    f"country={country}",
                    f"baseline_creative_ids={','.join(str(h.get('creative_id') or '') for h in hypotheses if str(h.get('creative_id') or '').strip())}",
                    f"active_discovery_slot_count={int(slot_pattern.get('pending_slot_count') or 0)}",
                    f"active_change_focuses={','.join(slot_pattern.get('change_focuses') or [])}",
                    f"approval_ids={','.join(slot_pattern.get('approval_ids') or [])}",
                    f"pattern_prior_strength={prior_strength:.2f}",
                    f"pattern_prior_state={str(pattern_prior.get('prior_state') or '')}",
                ],
            )
            action["source"] = "discovery_engine"
            action["discovery_stage"] = str(item.get("stage") or "")
            action["discovery_recommended_action"] = str(item.get("recommended_action") or "")
            action["discovery_test_type"] = test_type
            action["variant_count_target"] = variant_count_target
            action["primary_test_axis"] = primary_test_axis
            action["control_dimensions"] = control_dimensions
            action["baseline_asset_preview"] = baseline_asset_preview
            action["active_discovery_slot_count"] = int(slot_pattern.get("pending_slot_count") or 0)
            action["active_discovery_change_focuses"] = list(slot_pattern.get("change_focuses") or [])
            action["active_discovery_pattern_keys"] = list(slot_pattern.get("reusable_pattern_keys") or [])
            action["approval_ids"] = list(slot_pattern.get("approval_ids") or [])
            action["required_result_fields"] = list(slot_pattern.get("required_template_fields") or [])
            action["recommended_result_fields"] = list(slot_pattern.get("recommended_template_fields") or [])
            action["manual_input_file"] = str(slot_pattern.get("manual_input_file") or "")
            action["result_template_file"] = str(slot_pattern.get("result_template_file") or "")
            action["next_learning_step"] = str(slot_pattern.get("next_learning_step") or "")
            action["discovery_pattern_prior_strength"] = round(prior_strength, 4)
            action["discovery_pattern_prior_state"] = str(pattern_prior.get("prior_state") or "")
            action["discovery_pattern_prior_reason"] = str(pattern_prior.get("recommendation") or "")
            action["discovery_pattern_prioritized_change_focuses"] = list(pattern_prior.get("prioritized_change_focuses") or [])
            action["discovery_pattern_prioritized_keys"] = list(pattern_prior.get("prioritized_pattern_keys") or [])
            action["slot_packets"] = [
                {
                    "slot_id": slot.get("slot_id", ""),
                    "variant_name": slot.get("variant_name", ""),
                    "change_focus": slot.get("change_focus", ""),
                    "primary_test_axis": slot.get("primary_test_axis", ""),
                    "reusable_pattern_key": slot.get("reusable_pattern_key", ""),
                    "missing_evidence": list(slot.get("missing_evidence") or []),
                }
                for slot in list(slot_pattern.get("slots") or [])
            ]
            actions.append(action)
    return actions


def _group_discovery_hypotheses(items: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in items:
        if item.get("source") != "local_winner_prior":
            continue
        project = str(item.get("project") or "").strip()
        test_type = str(item.get("test_type") or "").strip()
        test_plan = item.get("test_plan") or {}
        channel = str(test_plan.get("channel") or "Unknown").strip()
        country = str(test_plan.get("country") or "Global").strip()
        if not project or not test_type:
            continue
        grouped.setdefault((project, test_type, channel, country), []).append(item)
    return grouped


def _cluster_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in (payload.get("clusters") or [])[:5]:
        if item.get("confidence") == "low" or float(item.get("predicted_scalability") or 0.0) < 0.65:
            continue
        actions.append(_action("copy_creative_pattern", item.get("cluster_name"), "", item.get("predicted_scalability"), item.get("variant_direction"), 0.0, item.get("confidence"), [f"cluster ROI={float(item.get('avg_roi') or 0):.2f}", f"spend={float(item.get('spend') or 0):.0f}"]))
    return actions


def _fatigue_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in (payload.get("items") or [])[:10]:
        if item.get("status") != "fatigue":
            continue
        actions.append(_action("pause_candidate_review", item.get("creative_id"), item.get("project"), 0.68, "复核疲劳素材，优先替换前三秒或暂停候选评审。", 0.0, "medium", item.get("reason") or []))
    return actions


def _payback_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in payload.get("items") or []:
        if item.get("judgement") == "dynamic_line_gap" and float(item.get("confidence") or 0.0) >= 0.65:
            actions.append(_action("repair_structure", item.get("project"), item.get("project"), item.get("confidence"), "动态回本线未过，优先修复 CPI/留存/ARPU 结构。", 0.0, "medium", item.get("quality_signals") or []))
    return actions


def _action(action_type: str, target: Any, project: Any, priority: Any, recommendation: Any, max_change: float, confidence: Any, evidence: list[Any]) -> dict[str, Any]:
    action_type = action_type if action_type in ACTION_TYPES else "hold_budget"
    return {
        "action_type": action_type,
        "target": str(target or ""),
        "project": str(project or ""),
        "source": "",
        "priority": round(float(priority or 0.0), 4),
        "recommendation": str(recommendation or ""),
        "max_change_pct": float(max_change),
        "approval_required": True,
        "rollback_conditions": [
            "连续 2 天 D3/D7 代理 ROI 恶化超过 15%",
            "CPI 上涨超过 20% 且 ROI 未改善",
            "素材疲劳状态变为 high 或归因可信度下降",
        ],
        "evidence": [str(item) for item in evidence],
        "confidence": str(confidence or "low"),
    }


def _dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in sorted(actions, key=lambda row: (row["priority"], row["action_type"]), reverse=True):
        key = (item["action_type"], item["target"], item["project"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result[:30]
