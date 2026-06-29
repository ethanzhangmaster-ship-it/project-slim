from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.creative_clusters import CreativeClustersBuilder
from market_ops.creative_fatigue import CreativeFatigueBuilder
from market_ops.dynamic_payback import DynamicPaybackBuilder
from market_ops.early_prediction import EarlyPredictionBuilder
from market_ops.user_quality import UserQualityBuilder


@dataclass(slots=True)
class LifecyclePredictionResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class LifecyclePredictionBuilder:
    """Build project lifecycle and growth-potential signals from existing AI Media Buyer layers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> LifecyclePredictionResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"lifecycle_prediction_{suffix}.md"
        json_path = output_dir / f"lifecycle_prediction_{suffix}.json"
        csv_path = output_dir / f"lifecycle_prediction_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["items"])
        return LifecyclePredictionResult(markdown_path, json_path, csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        active = self._settings.active_output_dir
        paths = {
            "dynamic_payback": active / f"dynamic_payback_{suffix}.json",
            "user_quality": active / f"user_quality_{suffix}.json",
            "creative_clusters": active / f"creative_clusters_{suffix}.json",
            "creative_fatigue": active / f"creative_fatigue_{suffix}.json",
            "early_prediction": active / f"early_prediction_{suffix}.json",
        }
        self._ensure_inputs(report_date, paths)

        payback_payload = _load_json(paths["dynamic_payback"])
        quality_payload = _load_json(paths["user_quality"])
        cluster_payload = _load_json(paths["creative_clusters"])
        fatigue_payload = _load_json(paths["creative_fatigue"])
        early_payload = _load_json(paths["early_prediction"])

        payback_by_project = {_project_key(item.get("project")): item for item in payback_payload.get("items") or []}
        quality_by_project = {_project_key(item.get("project")): item for item in quality_payload.get("items") or []}
        early_by_project = {_project_key(item.get("project")): item for item in early_payload.get("items") or []}
        clusters_by_project = _clusters_by_project(cluster_payload.get("clusters") or [])
        fatigue_by_project = _fatigue_by_project(fatigue_payload.get("items") or [])

        project_keys = sorted(
            key
            for key in set(payback_by_project) | set(quality_by_project) | set(early_by_project) | set(clusters_by_project) | set(fatigue_by_project)
            if key
        )
        items = [
            _build_lifecycle_item(
                project_key=project_key,
                payback=payback_by_project.get(project_key, {}),
                quality=quality_by_project.get(project_key, {}),
                early=early_by_project.get(project_key, {}),
                clusters=clusters_by_project.get(project_key, []),
                fatigue=fatigue_by_project.get(project_key, []),
            )
            for project_key in project_keys
        ]
        items.sort(key=lambda item: (item["predicted_growth_potential"], -item["lifecycle_risk_score"]), reverse=True)

        return {
            "report_date": report_date.isoformat(),
            "window_start": fatigue_payload.get("window_start") or early_payload.get("window_start"),
            "window_end": fatigue_payload.get("window_end") or early_payload.get("window_end"),
            "mode": "signal_only_lifecycle_prediction",
            "passed": True,
            "source_paths": {name: str(path) for name, path in paths.items()},
            "rules": {
                "signal_only": True,
                "decision_engine_owns_actions": True,
                "no_platform_writes": True,
                "uses_proxy_creative_intelligence_until_visual_assets_are_ready": True,
            },
            "summary": {
                "project_count": len(items),
                "scale_candidate_count": sum(1 for item in items if item["lifecycle_stage"] == "scale_candidate"),
                "validation_count": sum(1 for item in items if item["lifecycle_stage"] == "validation"),
                "fatigue_risk_count": sum(1 for item in items if item["lifecycle_stage"] == "fatigue_risk"),
                "data_gap_count": sum(1 for item in items if item["lifecycle_stage"] == "data_gap"),
                "learning_required_count": sum(1 for item in items if item["lifecycle_stage"] == "learning_required"),
            },
            "items": items,
        }

    def _ensure_inputs(self, report_date: date, paths: dict[str, Path]) -> None:
        if not paths["dynamic_payback"].exists():
            DynamicPaybackBuilder(self._settings).build(report_date)
        if not paths["user_quality"].exists():
            UserQualityBuilder(self._settings).build(report_date)
        if not paths["creative_clusters"].exists():
            CreativeClustersBuilder(self._settings).build(report_date)
        if not paths["creative_fatigue"].exists():
            CreativeFatigueBuilder(self._settings).build(report_date)
        if not paths["early_prediction"].exists():
            EarlyPredictionBuilder(self._settings).build(report_date)

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fieldnames = [
            "project",
            "lifecycle_stage",
            "predicted_growth_potential",
            "lifecycle_risk_score",
            "predicted_ltv_curve",
            "payback_ratio",
            "quality_status",
            "creative_cluster_count",
            "fatigue_signal_count",
            "recommended_decision_input",
            "next_learning_need",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                row = {field: item.get(field, "") for field in fieldnames}
                row["next_learning_need"] = " | ".join(item.get("next_learning_need") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Lifecycle Prediction Layer | {payload['report_date']}",
            "",
            "- Mode: signal_only_lifecycle_prediction",
            "- Boundary: this layer predicts lifecycle stage and growth potential only; Decision Engine still owns actions.",
            "- Inputs: dynamic payback, user quality, creative clusters, creative fatigue, and early prediction.",
            "",
            "## Summary",
            "",
            f"- Projects: {summary['project_count']}",
            f"- Scale candidates: {summary['scale_candidate_count']}",
            f"- Validation: {summary['validation_count']}",
            f"- Fatigue risk: {summary['fatigue_risk_count']}",
            f"- Data gaps: {summary['data_gap_count']}",
            f"- Learning required: {summary['learning_required_count']}",
            "",
            "## Projects",
            "",
        ]
        if not payload["items"]:
            lines.append("- None.")
        for item in payload["items"]:
            needs = "; ".join(item["next_learning_need"]) if item["next_learning_need"] else "none"
            lines.append(
                f"- {item['project']} | {item['lifecycle_stage']} | potential={item['predicted_growth_potential']} | "
                f"risk={item['lifecycle_risk_score']} | curve={item['predicted_ltv_curve']} | "
                f"quality={item['quality_status']} | payback_ratio={item['payback_ratio']} | need={needs}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _project_key(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"\b(P\d{2})\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return text


def _clusters_by_project(clusters: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for cluster in clusters:
        keys = {_project_key(item.get("project")) for item in cluster.get("items") or []}
        keys = {key for key in keys if key}
        if not keys:
            keys = {_project_key(cluster.get("project") or cluster.get("cluster_name"))}
        for key in keys:
            grouped.setdefault(key, []).append(cluster)
    return grouped


def _fatigue_by_project(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = _project_key(item.get("project"))
        if key:
            grouped.setdefault(key, []).append(item)
    return grouped


def _build_lifecycle_item(
    *,
    project_key: str,
    payback: dict[str, Any],
    quality: dict[str, Any],
    early: dict[str, Any],
    clusters: list[dict[str, Any]],
    fatigue: list[dict[str, Any]],
) -> dict[str, Any]:
    current_d7 = float(payback.get("current_d7") or quality.get("current_d7") or 0.0)
    target_d7 = float(payback.get("dynamic_break_even_d7") or quality.get("dynamic_break_even_d7") or 0.0)
    payback_ratio = _ratio(current_d7, target_d7)
    quality_score = float(quality.get("quality_score") or 0.0)
    quality_status = str(quality.get("quality_status") or "unknown")
    early_potential = float(early.get("predicted_scale_potential") or 0.0)
    cluster_potential = max((float(item.get("predicted_scalability") or 0.0) for item in clusters), default=0.0)
    fatigue_signals = [item for item in fatigue if item.get("status") == "fatigue"]
    metric_missing = [item for item in fatigue if item.get("status") == "metric_missing"]
    fatigue_penalty = min(0.35, len(fatigue_signals) * 0.035 + len(metric_missing) * 0.005)

    normalized_payback = _clamp(payback_ratio / 1.2)
    predicted_growth_potential = _clamp(
        normalized_payback * 0.30
        + quality_score * 0.25
        + cluster_potential * 0.20
        + early_potential * 0.15
        + float(payback.get("confidence") or quality.get("confidence") or 0.0) * 0.10
        - fatigue_penalty
    )
    data_gap = quality_status == "quality_data_gap" or not payback or target_d7 <= 0
    payback_gap = bool(target_d7 and current_d7 and current_d7 < target_d7)
    lifecycle_risk_score = _clamp(
        (0.30 if data_gap else 0.0)
        + (0.25 if payback_gap else 0.0)
        + min(0.30, len(fatigue_signals) * 0.04)
        + (0.15 if cluster_potential == 0.0 else 0.0)
    )

    if data_gap:
        lifecycle_stage = "data_gap"
    elif fatigue_signals and lifecycle_risk_score >= 0.30:
        lifecycle_stage = "fatigue_risk"
    elif payback_ratio >= 1.0 and quality_status == "high_quality" and predicted_growth_potential >= 0.60:
        lifecycle_stage = "scale_candidate"
    elif predicted_growth_potential >= 0.45 or early_potential >= 0.55:
        lifecycle_stage = "validation"
    else:
        lifecycle_stage = "learning_required"

    if data_gap:
        predicted_ltv_curve = "unknown_data_gap"
    elif lifecycle_stage == "scale_candidate" and payback_ratio >= 1.15:
        predicted_ltv_curve = "healthy_scale_curve"
    elif lifecycle_stage == "fatigue_risk":
        predicted_ltv_curve = "short_cycle_fatigue_risk"
    elif early.get("predicted_ltv_curve"):
        predicted_ltv_curve = str(early.get("predicted_ltv_curve"))
    else:
        predicted_ltv_curve = "needs_more_lifecycle_evidence"

    next_learning_need = _next_learning_need(
        data_gap=data_gap,
        payback_gap=payback_gap,
        quality_status=quality_status,
        cluster_potential=cluster_potential,
        fatigue_signals=fatigue_signals,
        early=early,
    )

    return {
        "project": str(payback.get("project") or quality.get("project") or early.get("project") or project_key),
        "project_key": project_key,
        "lifecycle_stage": lifecycle_stage,
        "predicted_growth_potential": round(predicted_growth_potential, 4),
        "lifecycle_risk_score": round(lifecycle_risk_score, 4),
        "predicted_ltv_curve": predicted_ltv_curve,
        "payback_ratio": round(payback_ratio, 4),
        "current_d7": round(current_d7, 4),
        "dynamic_break_even_d7": round(target_d7, 4),
        "quality_status": quality_status,
        "quality_score": round(quality_score, 4),
        "early_scale_potential": round(early_potential, 4),
        "creative_cluster_count": len(clusters),
        "max_cluster_scalability": round(cluster_potential, 4),
        "fatigue_signal_count": len(fatigue_signals),
        "fatigue_metric_missing_count": len(metric_missing),
        "recommended_decision_input": _decision_input(lifecycle_stage),
        "next_learning_need": next_learning_need,
    }


def _next_learning_need(
    *,
    data_gap: bool,
    payback_gap: bool,
    quality_status: str,
    cluster_potential: float,
    fatigue_signals: list[dict[str, Any]],
    early: dict[str, Any],
) -> list[str]:
    needs: list[str] = []
    if data_gap:
        needs.append("fill CPI, retention, ARPU/ARPPU, and payback evidence before budget decisions")
    if quality_status == "mixed_quality":
        needs.append("separate high-quality cohorts from short-term ROAS signals")
    if payback_gap:
        needs.append("validate whether payback gap is caused by CPI, retention, or monetization")
    if cluster_potential <= 0:
        needs.append("connect creative clusters to this project")
    if fatigue_signals:
        needs.append("confirm fatigue with CTR/CPI/ROI trend and refresh creative pattern")
    if not early:
        needs.append("build early prediction signal for exploration ranking")
    return needs or ["record post-decision outcome so lifecycle prediction can learn"]


def _decision_input(stage: str) -> str:
    mapping = {
        "scale_candidate": "candidate_signal_for_decision_engine_scale_test",
        "validation": "candidate_signal_for_decision_engine_validation_test",
        "fatigue_risk": "risk_signal_for_decision_engine_refresh_or_limit",
        "data_gap": "blocker_signal_for_decision_engine_data_gap",
        "learning_required": "learning_signal_for_discovery_or_experiment_layer",
    }
    return mapping.get(stage, "signal_only")


def _ratio(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return value / target


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
