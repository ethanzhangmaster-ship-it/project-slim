from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.data_quality_audit import DataQualityAuditBuilder
from market_ops.growth_priorities import GrowthPrioritiesBuilder
from market_ops.lifecycle_prediction import LifecyclePredictionBuilder
from market_ops.management_action_list import ManagementActionListBuilder
from market_ops.strategy_context import StrategyContextBuilder


DECISION_WEIGHTS = {
    "growth": 0.35,
    "roi_payback": 0.25,
    "quality_confidence": 0.20,
    "fatigue_risk": -0.15,
    "attribution_confidence": 0.05,
    "lifecycle_potential": 0.12,
    "lifecycle_risk": -0.10,
    "strategy_alignment": 0.08,
    "strategy_guardrail_risk": -0.08,
    "playbook_growth_bias": 0.10,
    "playbook_risk_bias": -0.10,
    "playbook_candidate_growth_bias": 0.04,
    "playbook_candidate_risk_bias": -0.04,
}

DECISION_ENUM = {
    "small_scale_up",
    "hold",
    "repair",
    "downweight",
    "pause_or_review",
    "data_blocked",
}


@dataclass(slots=True)
class DecisionEngineResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class DecisionEngineBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DecisionEngineResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"decision_engine_{suffix}.md"
        json_path = output_dir / f"decision_engine_{suffix}.json"
        csv_path = output_dir / f"decision_engine_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["items"])
        return DecisionEngineResult(
            markdown_path=markdown_path,
            json_path=json_path,
            csv_path=csv_path,
            passed=bool(payload["passed"]),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        growth_payload = GrowthPrioritiesBuilder(self._settings).build_payload(report_date)
        management_payload = ManagementActionListBuilder(self._settings).build_payload(report_date)
        data_quality_payload = self._load_or_build_data_quality(report_date)
        attribution_payload = self._load_json(report_date, "creative_attribution_audit")
        source_readiness_payload = self._load_json(report_date, "creative_source_readiness")
        lifecycle_payload = self._load_or_build_lifecycle(report_date)
        strategy_payload = self._load_or_build_strategy(report_date)
        playbook_payload = self._load_json(report_date, "growth_playbook")

        quality_score, quality_level, quality_notes = self._quality_signal(data_quality_payload)
        attribution_score, attribution_level, attribution_notes = self._attribution_signal(
            attribution_payload,
            source_readiness_payload,
        )
        management_index = self._index_management_actions(management_payload.get("items") or [])
        lifecycle_index = self._index_lifecycle(lifecycle_payload.get("items") or [])
        strategy_priorities = [item for item in strategy_payload.get("priorities") or [] if item.get("status") == "active"]
        strategy_guardrails = [str(item) for item in strategy_payload.get("guardrails") or [] if str(item).strip()]
        playbook_rules = list(playbook_payload.get("decision_rules") or [])
        playbook_candidates = list(playbook_payload.get("candidate_rules") or [])

        items: list[dict[str, Any]] = []
        for raw in growth_payload.get("items") or []:
            lifecycle_signal = self._matching_lifecycle(raw, lifecycle_index)
            strategy_signal = self._strategy_signal(raw, lifecycle_signal, strategy_priorities, strategy_guardrails)
            playbook_signal = self._playbook_signal(raw, playbook_rules)
            playbook_candidate_signal = self._playbook_candidate_signal(raw, playbook_candidates)
            item = self._decision_item(
                raw=raw,
                quality_score=quality_score,
                quality_level=quality_level,
                quality_notes=quality_notes,
                attribution_score=attribution_score,
                attribution_level=attribution_level,
                attribution_notes=attribution_notes,
                lifecycle_signal=lifecycle_signal,
                strategy_signal=strategy_signal,
                playbook_signal=playbook_signal,
                playbook_candidate_signal=playbook_candidate_signal,
                management_actions=self._matching_management_actions(raw, management_index),
            )
            items.append(item)

        items.sort(key=lambda item: (item["final_growth_score"], -item["final_risk_score"], item["spend"]), reverse=True)
        scale_items = [item for item in items if item["decision"] == "small_scale_up"]
        blocked_items = [item for item in items if item["decision"] == "data_blocked"]
        payload = {
            "report_date": report_date.isoformat(),
            "window_start": growth_payload.get("window_start"),
            "window_end": growth_payload.get("window_end"),
            "mode": "parallel_validation",
            "passed": True,
            "decision_enum": sorted(DECISION_ENUM),
            "weights": dict(DECISION_WEIGHTS),
            "source_modules": {
                "growth_priorities": "signal_source",
                "management_action_list": "signal_source",
                "data_quality_audit": quality_level,
                "creative_attribution_audit": attribution_level,
                "creative_source_readiness": attribution_level,
                "lifecycle_prediction": "signal_source",
                "strategy_context": "signal_source" if strategy_payload.get("strategy_input_ready") else "missing_or_incomplete",
                "growth_playbook": "signal_source" if playbook_rules else "no_validated_rules",
            },
            "summary": {
                "total_items": len(items),
                "small_scale_up": len(scale_items),
                "data_blocked": len(blocked_items),
                "quality_level": quality_level,
                "attribution_level": attribution_level,
                "lifecycle_items": len(lifecycle_index),
                "lifecycle_data_gap_decisions": sum(1 for item in items if item.get("lifecycle_stage") == "data_gap"),
                "lifecycle_fatigue_risk_decisions": sum(1 for item in items if item.get("lifecycle_stage") == "fatigue_risk"),
                "strategy_input_ready": bool(strategy_payload.get("strategy_input_ready")),
                "strategy_active_priorities": len(strategy_priorities),
                "strategy_guardrails": len(strategy_guardrails),
                "strategy_aligned_decisions": sum(1 for item in items if item.get("strategy_alignment_score", 0) > 0),
                "strategy_guardrail_blocked_decisions": sum(1 for item in items if item.get("strategy_blocked_by_guardrail")),
                "playbook_rule_count": len(playbook_rules),
                "playbook_matched_decisions": sum(1 for item in items if item.get("playbook_rule_ids")),
                "playbook_candidate_count": len(playbook_candidates),
                "playbook_candidate_matched_decisions": sum(1 for item in items if item.get("playbook_candidate_ids")),
            },
            "items": items,
        }
        return payload

    def _decision_item(
        self,
        *,
        raw: dict[str, Any],
        quality_score: float,
        quality_level: str,
        quality_notes: list[str],
        attribution_score: float,
        attribution_level: str,
        attribution_notes: list[str],
        lifecycle_signal: dict[str, Any],
        strategy_signal: dict[str, Any],
        playbook_signal: dict[str, Any],
        playbook_candidate_signal: dict[str, Any],
        management_actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        growth_score = _clamp(float(raw.get("growth_priority") or 0.0))
        risk_score = _clamp(float(raw.get("risk_priority") or 0.0))
        roi = float(raw.get("roi") or 0.0)
        roi_score = _clamp(roi / 1.5)
        lifecycle_potential = _clamp(float(lifecycle_signal.get("predicted_growth_potential") or 0.0))
        lifecycle_risk = _clamp(float(lifecycle_signal.get("lifecycle_risk_score") or 0.0))
        lifecycle_stage = str(lifecycle_signal.get("lifecycle_stage") or "unknown")
        strategy_alignment = _clamp(float(strategy_signal.get("alignment_score") or 0.0))
        strategy_guardrail_risk = _clamp(float(strategy_signal.get("guardrail_risk") or 0.0))
        playbook_growth_bias = _clamp(float(playbook_signal.get("growth_bias") or 0.0), -1.0, 1.0)
        playbook_risk_bias = _clamp(float(playbook_signal.get("risk_bias") or 0.0), -1.0, 1.0)
        playbook_candidate_growth_bias = _clamp(float(playbook_candidate_signal.get("growth_bias") or 0.0), -1.0, 1.0)
        playbook_candidate_risk_bias = _clamp(float(playbook_candidate_signal.get("risk_bias") or 0.0), -1.0, 1.0)
        final_growth = _clamp(
            DECISION_WEIGHTS["growth"] * growth_score
            + DECISION_WEIGHTS["roi_payback"] * roi_score
            + DECISION_WEIGHTS["quality_confidence"] * quality_score
            + DECISION_WEIGHTS["fatigue_risk"] * risk_score
            + DECISION_WEIGHTS["attribution_confidence"] * attribution_score
            + DECISION_WEIGHTS["lifecycle_potential"] * lifecycle_potential
            + DECISION_WEIGHTS["lifecycle_risk"] * lifecycle_risk
            + DECISION_WEIGHTS["strategy_alignment"] * strategy_alignment
            + DECISION_WEIGHTS["strategy_guardrail_risk"] * strategy_guardrail_risk
            + DECISION_WEIGHTS["playbook_growth_bias"] * playbook_growth_bias
            + DECISION_WEIGHTS["playbook_risk_bias"] * playbook_risk_bias
            + DECISION_WEIGHTS["playbook_candidate_growth_bias"] * playbook_candidate_growth_bias
            + DECISION_WEIGHTS["playbook_candidate_risk_bias"] * playbook_candidate_risk_bias
        )
        final_risk = _clamp(
            (risk_score * 0.50)
            + ((1.0 - quality_score) * 0.20)
            + ((1.0 - attribution_score) * 0.08)
            + (lifecycle_risk * 0.22)
            + (strategy_guardrail_risk * 0.15)
            + max(playbook_risk_bias, 0.0) * 0.12
        )
        decision = self._classify_decision(
            raw=raw,
            final_growth=final_growth,
            final_risk=final_risk,
            quality_level=quality_level,
            attribution_level=attribution_level,
            lifecycle_stage=lifecycle_stage,
            strategy_signal=strategy_signal,
        )
        confidence = _clamp((quality_score * 0.45) + (attribution_score * 0.25) + ((1.0 - final_risk) * 0.30))
        positives, negatives = self._signals(
            raw=raw,
            final_growth=final_growth,
            final_risk=final_risk,
            quality_level=quality_level,
            quality_notes=quality_notes,
            attribution_level=attribution_level,
            attribution_notes=attribution_notes,
            lifecycle_signal=lifecycle_signal,
            strategy_signal=strategy_signal,
            playbook_signal=playbook_signal,
            playbook_candidate_signal=playbook_candidate_signal,
            management_actions=management_actions,
        )

        return {
            "entity_type": str(raw.get("entity_type") or ""),
            "entity_id": str(raw.get("entity_id") or ""),
            "project": str(raw.get("project") or ""),
            "scope": str(raw.get("scope") or ""),
            "final_growth_score": round(final_growth, 4),
            "final_risk_score": round(final_risk, 4),
            "decision": decision,
            "confidence": round(confidence, 4),
            "top_positive_signals": positives[:5],
            "top_negative_signals": negatives[:5],
            "source_modules": self._source_modules(
                management_actions,
                quality_level,
                attribution_level,
                lifecycle_signal,
                strategy_signal,
                playbook_signal,
                playbook_candidate_signal,
            ),
            "mode": "parallel_validation",
            "lifecycle_stage": lifecycle_stage,
            "lifecycle_growth_potential": round(lifecycle_potential, 4),
            "lifecycle_risk_score": round(lifecycle_risk, 4),
            "lifecycle_decision_input": str(lifecycle_signal.get("recommended_decision_input") or ""),
            "lifecycle_next_learning_need": list(lifecycle_signal.get("next_learning_need") or []),
            "strategy_alignment_score": round(strategy_alignment, 4),
            "strategy_priority_ids": list(strategy_signal.get("matched_priority_ids") or []),
            "strategy_guardrail_risk": round(strategy_guardrail_risk, 4),
            "strategy_blocked_by_guardrail": bool(strategy_signal.get("blocked_by_guardrail")),
            "strategy_guardrail_matches": list(strategy_signal.get("guardrail_matches") or []),
            "playbook_rule_ids": list(playbook_signal.get("rule_ids") or []),
            "playbook_match_types": list(playbook_signal.get("match_types") or []),
            "playbook_pattern_keys": list(playbook_signal.get("pattern_keys") or []),
            "playbook_contextual_pattern_keys": list(playbook_signal.get("contextual_pattern_keys") or []),
            "playbook_growth_bias": round(playbook_growth_bias, 4),
            "playbook_risk_bias": round(playbook_risk_bias, 4),
            "playbook_candidate_ids": list(playbook_candidate_signal.get("rule_ids") or []),
            "playbook_candidate_match_types": list(playbook_candidate_signal.get("match_types") or []),
            "playbook_candidate_pattern_keys": list(playbook_candidate_signal.get("pattern_keys") or []),
            "playbook_candidate_contextual_pattern_keys": list(playbook_candidate_signal.get("contextual_pattern_keys") or []),
            "playbook_candidate_growth_bias": round(playbook_candidate_growth_bias, 4),
            "playbook_candidate_risk_bias": round(playbook_candidate_risk_bias, 4),
            "growth_stage": str(raw.get("growth_stage") or ""),
            "growth_priority": round(growth_score, 4),
            "risk_priority": round(risk_score, 4),
            "spend": round(float(raw.get("spend") or 0.0), 2),
            "revenue": round(float(raw.get("revenue") or 0.0), 2),
            "roi": round(roi, 4),
            "recommended_action_signal": str(raw.get("recommended_action") or ""),
            "budget_change_signal": str(raw.get("budget_change") or ""),
            "management_action_signals": management_actions,
        }

    @staticmethod
    def _classify_decision(
        *,
        raw: dict[str, Any],
        final_growth: float,
        final_risk: float,
        quality_level: str,
        attribution_level: str,
        lifecycle_stage: str,
        strategy_signal: dict[str, Any],
    ) -> str:
        entity_type = str(raw.get("entity_type") or "")
        action_text = str(raw.get("recommended_action") or "")
        budget_change = str(raw.get("budget_change") or "")
        roi = float(raw.get("roi") or 0.0)
        risk_priority = float(raw.get("risk_priority") or 0.0)
        growth_priority = float(raw.get("growth_priority") or 0.0)
        low_confidence = quality_level == "low" or (entity_type == "creative" and attribution_level == "low")
        strategy_blocked = bool(strategy_signal.get("blocked_by_guardrail"))

        if strategy_blocked and (growth_priority >= 0.55 or "+" in budget_change):
            return "data_blocked"
        if lifecycle_stage == "data_gap" and (growth_priority >= 0.55 or "+" in budget_change):
            return "data_blocked"
        if lifecycle_stage == "fatigue_risk" and ("+" in budget_change or final_growth >= 0.62):
            return "repair"
        if low_confidence and (growth_priority >= 0.65 or "+" in budget_change):
            return "data_blocked"
        if any(token in action_text for token in ("暂停", "停测")) or (risk_priority >= 0.85 and roi < 0.35):
            return "pause_or_review"
        if "降权" in action_text or (risk_priority >= 0.70 and roi < 0.75):
            return "downweight"
        if "修复" in action_text or (risk_priority >= 0.55 and final_growth < 0.55):
            return "repair"
        if final_growth >= 0.62 and final_risk <= 0.55 and ("+" in budget_change or "复制" in action_text or "扩量" in action_text):
            return "small_scale_up"
        return "hold"

    @staticmethod
    def _signals(
        *,
        raw: dict[str, Any],
        final_growth: float,
        final_risk: float,
        quality_level: str,
        quality_notes: list[str],
        attribution_level: str,
        attribution_notes: list[str],
        lifecycle_signal: dict[str, Any],
        strategy_signal: dict[str, Any],
        playbook_signal: dict[str, Any],
        playbook_candidate_signal: dict[str, Any],
        management_actions: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        positives: list[str] = []
        negatives: list[str] = []
        roi = float(raw.get("roi") or 0.0)
        spend = float(raw.get("spend") or 0.0)
        growth_stage = str(raw.get("growth_stage") or "")
        lifecycle_stage = str(lifecycle_signal.get("lifecycle_stage") or "")
        lifecycle_potential = float(lifecycle_signal.get("predicted_growth_potential") or 0.0)
        lifecycle_risk = float(lifecycle_signal.get("lifecycle_risk_score") or 0.0)
        strategy_alignment = float(strategy_signal.get("alignment_score") or 0.0)
        strategy_priority_ids = list(strategy_signal.get("matched_priority_ids") or [])
        strategy_guardrail_matches = list(strategy_signal.get("guardrail_matches") or [])
        playbook_rule_ids = list(playbook_signal.get("rule_ids") or [])
        playbook_candidate_ids = list(playbook_candidate_signal.get("rule_ids") or [])
        if final_growth >= 0.62:
            positives.append(f"统一增长分达到 {final_growth:.2f}")
        if roi >= 1.0:
            positives.append(f"ROI={roi:.2f}，具备继续观察或小额验证基础")
        if spend > 0:
            positives.append(f"样本花费={spend:.0f}")
        if growth_stage:
            positives.append(f"增长阶段信号：{growth_stage}")
        if lifecycle_stage in {"scale_candidate", "validation"}:
            positives.append(f"生命周期={lifecycle_stage}，增长潜力={lifecycle_potential:.2f}")
        if management_actions:
            positives.append("现有管理动作清单中存在同对象候选")
        if strategy_alignment > 0:
            positives.append(f"Strategy alignment={strategy_alignment:.2f}; priorities={','.join(strategy_priority_ids)}")
        if playbook_rule_ids:
            positives.append(f"Growth playbook matched rules={','.join(playbook_rule_ids)}")
        if playbook_candidate_ids:
            positives.append(f"Discovery candidate patterns={','.join(playbook_candidate_ids[:3])}")
        positives.extend(str(item) for item in raw.get("reason") or [])

        if final_risk >= 0.55:
            negatives.append(f"统一风险分达到 {final_risk:.2f}")
        if quality_level == "low":
            negatives.append("数据质量低，禁止输出强扩量")
        elif quality_level == "medium":
            negatives.append("数据质量中等，扩量需先做限额验证")
        if attribution_level == "low":
            negatives.append("素材归因可信度低，素材类动作只能并行观察")
        if lifecycle_stage == "data_gap":
            negatives.append("生命周期=data_gap，项目级用户质量/回本证据缺口阻断扩量")
        elif lifecycle_stage == "fatigue_risk":
            negatives.append(f"生命周期=fatigue_risk，风险={lifecycle_risk:.2f}，扩量前先验证疲劳")
        if strategy_signal.get("blocked_by_guardrail"):
            negatives.append(f"Strategy guardrail blocked scaling: {' | '.join(strategy_guardrail_matches)}")
        negatives.extend(str(item) for item in lifecycle_signal.get("next_learning_need") or [])
        negatives.extend(quality_notes[:2])
        negatives.extend(attribution_notes[:2])
        negatives.extend(str(item) for item in raw.get("guardrails") or [])
        return positives, negatives

    @staticmethod
    def _source_modules(
        management_actions: list[dict[str, Any]],
        quality_level: str,
        attribution_level: str,
        lifecycle_signal: dict[str, Any],
        strategy_signal: dict[str, Any],
        playbook_signal: dict[str, Any],
        playbook_candidate_signal: dict[str, Any],
    ) -> list[str]:
        modules = [
            "growth_priorities",
            f"data_quality_audit:{quality_level}",
            f"creative_attribution:{attribution_level}",
        ]
        if lifecycle_signal:
            modules.append(f"lifecycle_prediction:{lifecycle_signal.get('lifecycle_stage', 'unknown')}")
        if strategy_signal.get("strategy_input_ready"):
            modules.append(f"strategy_context:{strategy_signal.get('alignment_state', 'unmatched')}")
        if playbook_signal.get("rule_ids"):
            modules.append("growth_playbook:matched")
        if playbook_candidate_signal.get("rule_ids"):
            modules.append("growth_playbook:candidate_matched")
        if management_actions:
            modules.append("management_action_list")
        return modules

    def _load_or_build_data_quality(self, report_date: date) -> dict[str, Any]:
        try:
            result = DataQualityAuditBuilder(self._settings).build(report_date)
            return json.loads(result.json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"passed": False, "modules": [], "top_risks": [f"data_quality_audit failed: {exc}"]}

    def _load_or_build_lifecycle(self, report_date: date) -> dict[str, Any]:
        path = self._settings.active_output_dir / f"lifecycle_prediction_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            try:
                LifecyclePredictionBuilder(self._settings).build(report_date)
            except Exception as exc:
                return {"passed": False, "items": [], "error": f"lifecycle_prediction failed: {exc}"}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"passed": False, "items": [], "json_error": str(path)}

    def _load_or_build_strategy(self, report_date: date) -> dict[str, Any]:
        path = self._settings.active_output_dir / f"strategy_context_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            try:
                StrategyContextBuilder(self._settings).build(report_date)
            except Exception as exc:
                return {"passed": False, "priorities": [], "guardrails": [], "error": f"strategy_context failed: {exc}"}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"passed": False, "priorities": [], "guardrails": [], "json_error": str(path)}

    def _load_json(self, report_date: date, stem: str) -> dict[str, Any]:
        path = self._settings.active_output_dir / f"{stem}_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"json_error": str(path)}

    @staticmethod
    def _quality_signal(payload: dict[str, Any]) -> tuple[float, str, list[str]]:
        modules = payload.get("modules") or []
        core_modules = {"花费", "收入", "ROI", "公司盈利结构", "鑺辫垂", "鏀跺叆", "鍏徃鐩堝埄缁撴瀯"}
        levels = [
            str(item.get("level") or "")
            for item in modules
            if isinstance(item, dict) and str(item.get("module") or "") in core_modules
        ]
        low_count = sum(1 for level in levels if level in {"低", "low", "浣?"})
        medium_count = sum(1 for level in levels if level in {"中", "medium", "涓?"})
        if payload.get("passed") and low_count == 0:
            score = 0.85 if medium_count <= 1 else 0.70
            level = "high" if medium_count <= 1 else "medium"
        elif low_count <= 1 and levels:
            score = 0.55
            level = "medium"
        else:
            score = 0.25
            level = "low"
        notes = []
        for risk in payload.get("top_risks") or []:
            notes.append(str(risk.get("message") if isinstance(risk, dict) else risk))
        return score, level, [note for note in notes if note]

    @staticmethod
    def _attribution_signal(attribution_payload: dict[str, Any], source_payload: dict[str, Any]) -> tuple[float, str, list[str]]:
        notes: list[str] = []
        readiness = attribution_payload.get("readiness") or {}
        summary = source_payload.get("summary") or {}
        creative_ready = bool(readiness.get("creative_analysis_ready"))
        campaign_ready = bool(readiness.get("campaign_analysis_ready"))
        source_ready = bool(summary.get("meta_can_run_now") or summary.get("google_can_run_now"))
        if creative_ready:
            return 0.85, "high", notes
        if campaign_ready or source_ready:
            return 0.60, "medium", notes
        for warning in attribution_payload.get("warnings") or []:
            notes.append(str(warning))
        for blocker in source_payload.get("blockers") or []:
            notes.append(str(blocker))
        return 0.35, "low", notes

    @staticmethod
    def _index_management_actions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _index_lifecycle(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for item in items:
            key = _project_key(item.get("project_key") or item.get("project"))
            if key:
                index[key] = item
        return index

    @staticmethod
    def _matching_lifecycle(raw: dict[str, Any], lifecycle_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return lifecycle_index.get(_project_key(raw.get("project")), {})

    @staticmethod
    def _strategy_signal(
        raw: dict[str, Any],
        lifecycle_signal: dict[str, Any],
        priorities: list[dict[str, Any]],
        guardrails: list[str],
    ) -> dict[str, Any]:
        raw_project_key = _project_key(raw.get("project"))
        raw_scope = _norm(raw.get("scope"))
        matched_priority_ids: list[str] = []
        alignment_score = 0.0
        for priority in priorities:
            priority_score = 0.0
            priority_project = _project_key(priority.get("project"))
            if priority_project and raw_project_key and priority_project == raw_project_key:
                priority_score += 0.45
            country = _norm(priority.get("country"))
            if country and raw_scope and (country in raw_scope or raw_scope in country):
                priority_score += 0.20
            platform = _norm(priority.get("platform"))
            if platform and raw_scope and (platform in raw_scope or raw_scope in platform):
                priority_score += 0.20
            objective = _norm(priority.get("objective"))
            if objective and any(token in objective for token in ("learning", "exploration", "roi", "scale")):
                priority_score += 0.05
            if priority_score > 0:
                weight = _clamp(float(priority.get("priority_weight") or 1.0), 0.0, 2.0)
                alignment_score = max(alignment_score, _clamp(priority_score * weight))
                matched_priority_ids.append(str(priority.get("priority_id") or priority.get("name") or "strategy"))

        lifecycle_stage = str(lifecycle_signal.get("lifecycle_stage") or "")
        guardrail_matches: list[str] = []
        for guardrail in guardrails:
            guardrail_norm = _norm(guardrail)
            if "data_gap" in guardrail_norm and lifecycle_stage == "data_gap":
                guardrail_matches.append(guardrail)
            elif "fatigue" in guardrail_norm and lifecycle_stage == "fatigue_risk":
                guardrail_matches.append(guardrail)

        return {
            "strategy_input_ready": bool(priorities),
            "alignment_state": "aligned" if matched_priority_ids else "unmatched",
            "alignment_score": round(alignment_score, 4),
            "matched_priority_ids": matched_priority_ids[:5],
            "guardrail_risk": 1.0 if guardrail_matches else 0.0,
            "blocked_by_guardrail": bool(guardrail_matches),
            "guardrail_matches": guardrail_matches[:5],
        }

    @staticmethod
    def _playbook_signal(raw: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
        matched, match_types, pattern_keys, contextual_pattern_keys = DecisionEngineBuilder._playbook_matches(raw, rules)
        growth_bias = sum(float(item.get("growth_bias") or 0.0) for item in matched[:5])
        risk_bias = sum(float(item.get("risk_bias") or 0.0) for item in matched[:5])
        return {
            "rule_ids": [str(item.get("rule_id") or "") for item in matched[:5] if item.get("rule_id")],
            "match_types": match_types[:5],
            "pattern_keys": pattern_keys[:5],
            "contextual_pattern_keys": contextual_pattern_keys[:5],
            "growth_bias": _clamp(growth_bias, -1.0, 1.0),
            "risk_bias": _clamp(risk_bias, -1.0, 1.0),
        }

    @staticmethod
    def _playbook_candidate_signal(raw: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        filtered = [
            item for item in candidates
            if str(item.get("memory_scope") or "") == "discovery_pattern"
        ]
        matched, match_types, pattern_keys, contextual_pattern_keys = DecisionEngineBuilder._playbook_matches(raw, filtered)
        matched = matched[:5]
        match_strength = min(len(matched) * 0.08, 0.20)
        return {
            "rule_ids": [str(item.get("candidate_id") or "") for item in matched if item.get("candidate_id")],
            "match_types": match_types[:5],
            "pattern_keys": pattern_keys[:5],
            "contextual_pattern_keys": contextual_pattern_keys[:5],
            "growth_bias": match_strength,
            "risk_bias": 0.0,
        }

    @staticmethod
    def _playbook_matches(raw: dict[str, Any], rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
        raw_project = _project_key(raw.get("project"))
        raw_scope = _norm(raw.get("scope"))
        raw_entity = _norm(raw.get("entity_id"))
        matched: list[dict[str, Any]] = []
        match_types: list[str] = []
        pattern_keys: list[str] = []
        contextual_pattern_keys: list[str] = []
        for rule in rules:
            rule_project = _project_key(rule.get("target_project"))
            signature = _norm(rule.get("target_signature"))
            if rule_project and raw_project and rule_project != raw_project:
                continue
            if signature and raw_entity and raw_entity in signature:
                matched.append(rule)
                match_types.append("target_signature")
            elif signature and raw_scope and any(part and part in signature for part in raw_scope.split("/")):
                matched.append(rule)
                match_types.append("scope_overlap")
            elif DecisionEngineBuilder._eligible_for_pattern_bias(raw, rule):
                matched.append(rule)
                match_types.append("pattern_family")
            else:
                continue
            reusable_key = str(rule.get("reusable_pattern_key") or "").strip()
            contextual_key = str(rule.get("contextual_pattern_key") or "").strip()
            if reusable_key:
                pattern_keys.append(reusable_key)
            if contextual_key:
                contextual_pattern_keys.append(contextual_key)
        return matched, match_types, pattern_keys, contextual_pattern_keys

    @staticmethod
    def _eligible_for_pattern_bias(raw: dict[str, Any], rule: dict[str, Any]) -> bool:
        if str(raw.get("entity_type") or "") != "creative":
            return False
        learning_pattern = rule.get("learning_pattern") or {}
        pattern_family = str(learning_pattern.get("pattern_family") or "").strip()
        if not pattern_family:
            return False

        growth_stage = str(raw.get("growth_stage") or "")
        action_text = str(raw.get("recommended_action") or "")
        opportunity_text = _norm(" ".join([growth_stage, action_text]))
        if not any(
            token in opportunity_text
            for token in (
                "复制",
                "变体",
                "测试",
                "素材复制候选",
                "hook",
                "cta",
                "前三秒",
                "前3秒",
                "image_to_motion",
                "motion",
            )
        ):
            return False

        if pattern_family == "winner_hook_clone":
            return any(token in opportunity_text for token in ("复制", "变体", "hook", "cta", "前三秒", "前3秒"))
        if pattern_family == "winner_image_to_motion":
            return any(token in opportunity_text for token in ("复制", "变体", "测试", "motion", "image_to_motion"))
        return False

    @staticmethod
    def _matching_management_actions(raw: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        project = _norm(raw.get("project"))
        scope = _norm(raw.get("scope"))
        matches: list[dict[str, Any]] = []
        for action in actions:
            action_project = _norm(action.get("project"))
            action_scope = _norm(action.get("scope"))
            if project and action_project and project != action_project:
                continue
            if scope and action_scope and (scope in action_scope or action_scope in scope):
                matches.append(
                    {
                        "project": action.get("project"),
                        "scope": action.get("scope"),
                        "action": action.get("action"),
                        "owner": action.get("owner"),
                    }
                )
        return matches[:3]

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# V2.5 决策引擎并行验证 | {payload['report_date']}",
            "",
            f"- 窗口：{payload.get('window_start')} 至 {payload.get('window_end')}",
            "- 模式：parallel_validation，仅生成统一决策，不替换周报动作，不自动改预算。",
            f"- 决策对象：{summary['total_items']} 个；小额扩量/复制验证：{summary['small_scale_up']} 个；数据阻断：{summary['data_blocked']} 个。",
            f"- 数据质量：{summary['quality_level']}；素材归因：{summary['attribution_level']}。",
            "",
            "## 权重",
            "",
        ]
        lines.extend(f"- {key}: {value}" for key, value in payload["weights"].items())
        lines.extend(["", "## Top 决策", ""])
        lines.extend(_render_decision_table(payload["items"][:20]))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fields = [
            "entity_type",
            "entity_id",
            "project",
            "scope",
            "final_growth_score",
            "final_risk_score",
            "decision",
            "confidence",
            "lifecycle_stage",
            "lifecycle_growth_potential",
            "lifecycle_risk_score",
            "lifecycle_decision_input",
            "strategy_alignment_score",
            "strategy_priority_ids",
            "strategy_guardrail_risk",
            "strategy_blocked_by_guardrail",
            "strategy_guardrail_matches",
            "playbook_rule_ids",
            "playbook_match_types",
            "playbook_pattern_keys",
            "playbook_contextual_pattern_keys",
            "playbook_growth_bias",
            "playbook_risk_bias",
            "playbook_candidate_ids",
            "playbook_candidate_match_types",
            "playbook_candidate_pattern_keys",
            "playbook_candidate_contextual_pattern_keys",
            "playbook_candidate_growth_bias",
            "playbook_candidate_risk_bias",
            "top_positive_signals",
            "top_negative_signals",
            "source_modules",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for item in items:
                row = dict(item)
                for key in (
                    "strategy_priority_ids",
                    "strategy_guardrail_matches",
                    "playbook_rule_ids",
                    "playbook_match_types",
                    "playbook_pattern_keys",
                    "playbook_contextual_pattern_keys",
                    "playbook_candidate_ids",
                    "playbook_candidate_match_types",
                    "playbook_candidate_pattern_keys",
                    "playbook_candidate_contextual_pattern_keys",
                    "top_positive_signals",
                    "top_negative_signals",
                    "source_modules",
                ):
                    row[key] = " | ".join(str(part) for part in row.get(key) or [])
                writer.writerow({field: row.get(field, "") for field in fields})


def _render_decision_table(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- 暂无决策对象。"]
    lines = [
        "| 对象 | 项目 | 范围 | 增长分 | 风险分 | 决策 | 置信度 | 主要原因 |",
        "|---|---|---|---:|---:|---|---:|---|",
    ]
    for item in items:
        reason = "；".join((item.get("top_positive_signals") or [])[:2])
        lines.append(
            f"| {item['entity_type']}:{item['entity_id']} | {item['project']} | {item['scope']} | "
            f"{item['final_growth_score']:.2f} | {item['final_risk_score']:.2f} | {item['decision']} | "
            f"{item['confidence']:.2f} | {reason} |"
        )
    return lines


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _project_key(value: Any) -> str:
    text = str(value or "").strip()
    for token in text.replace("/", " ").replace("-", " ").split():
        upper = token.upper()
        if len(upper) == 3 and upper.startswith("P") and upper[1:].isdigit():
            return upper
    return text.upper()


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("／", "/").split())
