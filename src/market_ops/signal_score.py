from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from market_ops.config import Settings
from market_ops.models import AdsPerformanceRow
from market_ops.new_product_stage import NewProductStageBuilder, normalize_channel, project_label
from market_ops.pipeline import DataRepository


@dataclass(slots=True)
class SignalScoreResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class SignalScoreBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> SignalScoreResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_signal_{suffix}.md"
        json_path = output_dir / f"discovery_signal_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return SignalScoreResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        week_start = report_date - timedelta(days=6)
        stage_payload = NewProductStageBuilder(self._settings).build_payload(report_date)
        stage_index = {item["project"]: item for item in stage_payload.get("items") or []}
        active_projects = {
            item["project"]
            for item in stage_payload.get("items") or []
            if item.get("stage") in {"Discovery", "Validation"}
        }

        cached_project_metrics, cached_ads_metrics = self._metrics_from_adjust_cache(report_date)
        if cached_project_metrics:
            project_metrics = cached_project_metrics
            ads_metrics = cached_ads_metrics
        else:
            breakdown_rows = self._repo.load_adjust_revenue_breakdown(week_start, report_date)
            try:
                ads_rows = self._repo.load_ads_performance()
            except Exception:
                ads_rows = []
            ads_rows = [row for row in ads_rows if week_start <= row.date <= report_date]
            project_metrics = self._breakdown_metrics(breakdown_rows)
            ads_metrics = self._ads_metrics(ads_rows)
        projects = active_projects
        items: list[dict[str, Any]] = []
        for project in sorted(projects):
            item = self._score_item(
                project=project,
                metrics=project_metrics.get(project, {}),
                ads_metrics=ads_metrics.get(project, {}),
                stage=stage_index.get(project, {}),
            )
            items.append(item)
        items.sort(key=lambda item: (item["stage_order"], item["signal_score"], item["recent_spend"]), reverse=False)
        return {
            "report_date": report_date.isoformat(),
            "window_start": week_start.isoformat(),
            "window_end": report_date.isoformat(),
            "passed": True,
            "weights": {
                "ctr_score": 0.25,
                "retention_score": 0.20,
                "session_score": 0.20,
                "ipm_score": 0.15,
                "hold_rate_score": 0.10,
                "cpi_score": 0.10,
            },
            "summary": {
                "project_count": len(items),
                "high_signal": sum(1 for item in items if item["signal_level"] == "high"),
                "medium_signal": sum(1 for item in items if item["signal_level"] == "medium"),
                "low_signal": sum(1 for item in items if item["signal_level"] == "low"),
            },
            "items": items,
        }

    def _metrics_from_adjust_cache(self, report_date: date) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, float]]]:
        path = self._settings.active_output_dir / f"adjust_creative_analysis_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            return {}, {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}, {}

        project_metrics: dict[str, dict[str, Any]] = {}
        for row in payload.get("project_channel_summary") or []:
            project = project_label(str(row.get("project") or ""))
            if not project:
                continue
            bucket = project_metrics.setdefault(
                project,
                {"spend": 0.0, "revenue": 0.0, "installs": 0.0, "channels": set(), "geos": set()},
            )
            bucket["spend"] += float(row.get("spend") or 0.0)
            bucket["revenue"] += float(row.get("revenue") or 0.0)
            bucket["installs"] += float(row.get("installs") or 0.0)
            channel = normalize_channel(str(row.get("channel") or ""))
            if channel:
                bucket["channels"].add(channel)

        for row in payload.get("project_channel_country_summary") or []:
            project = project_label(str(row.get("project") or ""))
            if not project:
                continue
            bucket = project_metrics.setdefault(
                project,
                {"spend": 0.0, "revenue": 0.0, "installs": 0.0, "channels": set(), "geos": set()},
            )
            geo = str(row.get("country") or "").strip()
            if geo:
                bucket["geos"].add(geo)

        ads_metrics: dict[str, dict[str, float]] = {}
        for project, metrics in project_metrics.items():
            spend = float(metrics.get("spend") or 0.0)
            installs = float(metrics.get("installs") or 0.0)
            if spend and installs:
                ads_metrics[project] = {"cpi": spend / installs}
        return project_metrics, ads_metrics

    @staticmethod
    def _breakdown_metrics(rows: list[Any]) -> dict[str, dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            project = project_label(row.game)
            if not project:
                continue
            bucket = buckets.setdefault(
                project,
                {"spend": 0.0, "revenue": 0.0, "installs": 0.0, "channels": set(), "geos": set()},
            )
            bucket["spend"] += float(getattr(row, "cost", 0.0) or 0.0)
            bucket["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            bucket["installs"] += float(getattr(row, "installs", 0.0) or 0.0)
            channel = normalize_channel(getattr(row, "partner", ""))
            if channel:
                bucket["channels"].add(channel)
            geo = str(getattr(row, "country", "") or "").strip()
            if geo:
                bucket["geos"].add(geo)
        return buckets

    @staticmethod
    def _ads_metrics(rows: list[AdsPerformanceRow]) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, list[float]]] = {}
        for row in rows:
            project = project_label(row.game)
            if not project:
                continue
            bucket = buckets.setdefault(project, {"ctr": [], "cpi": [], "roas": [], "retention_d1": []})
            if float(row.ctr or 0.0) > 0:
                bucket["ctr"].append(float(row.ctr))
            if float(row.cpi or 0.0) > 0:
                bucket["cpi"].append(float(row.cpi))
            if float(row.roas or 0.0) > 0:
                bucket["roas"].append(float(row.roas))
            if float(row.retention_d1 or 0.0) > 0:
                bucket["retention_d1"].append(float(row.retention_d1))
        return {
            project: {key: mean(values) for key, values in bucket.items() if values}
            for project, bucket in buckets.items()
        }

    def _score_item(
        self,
        *,
        project: str,
        metrics: dict[str, Any],
        ads_metrics: dict[str, float],
        stage: dict[str, Any],
    ) -> dict[str, Any]:
        spend = float(metrics.get("spend") or stage.get("recent_spend") or 0.0)
        revenue = float(metrics.get("revenue") or stage.get("recent_revenue") or 0.0)
        installs = float(metrics.get("installs") or stage.get("recent_installs") or 0.0)
        roi = revenue / spend if spend else 0.0
        cpi = float(ads_metrics.get("cpi") or (spend / installs if installs else 0.0))
        ctr = float(ads_metrics.get("ctr") or 0.0)
        retention_d1 = float(ads_metrics.get("retention_d1") or 0.0)
        ipm = installs / spend * 100.0 if spend else 0.0

        components = {
            "ctr_score": score_high_better(ctr, good=0.02, excellent=0.05) if ctr else 0.0,
            "retention_score": score_high_better(retention_d1, good=0.25, excellent=0.40) if retention_d1 else 0.0,
            "session_score": 0.0,
            "ipm_score": score_high_better(ipm, good=1.0, excellent=4.0) if ipm else 0.0,
            "hold_rate_score": 0.0,
            "cpi_score": score_low_better(cpi, good=2.0, weak=6.0) if cpi else 0.0,
        }
        weights = {
            "ctr_score": 0.25,
            "retention_score": 0.20,
            "session_score": 0.20,
            "ipm_score": 0.15,
            "hold_rate_score": 0.10,
            "cpi_score": 0.10,
        }
        observed_weight = sum(weights[key] for key, value in components.items() if value > 0)
        raw_score = sum(components[key] * weights[key] for key in components)
        signal_score = raw_score / observed_weight if observed_weight else 0.0
        confidence = "medium" if observed_weight >= 0.50 else ("low" if observed_weight else "blocked")
        if signal_score >= 0.70 and confidence != "blocked":
            level = "high"
            action = "continue_exploration"
        elif signal_score >= 0.45 and confidence != "blocked":
            level = "medium"
            action = "continue_limited_exploration"
        else:
            level = "low"
            action = "collect_more_signals"

        positives: list[str] = []
        negatives: list[str] = []
        missing: list[str] = []
        if ctr:
            (positives if components["ctr_score"] >= 0.60 else negatives).append(f"CTR={ctr:.3f}")
        else:
            missing.append("CTR")
        if retention_d1:
            (positives if components["retention_score"] >= 0.60 else negatives).append(f"D1留存={retention_d1:.3f}")
        else:
            missing.append("D1留存")
        if ipm:
            (positives if components["ipm_score"] >= 0.60 else negatives).append(f"IPM代理={ipm:.2f}")
        else:
            missing.append("IPM")
        if cpi:
            (positives if components["cpi_score"] >= 0.60 else negatives).append(f"CPI代理={cpi:.2f}")
        else:
            missing.append("CPI")
        missing.extend(["Session时长", "Hold Rate"])

        return {
            "project": project,
            "stage": stage.get("stage") or "Unknown",
            "stage_order": {"Discovery": 0, "Validation": 1, "Scaling": 2}.get(str(stage.get("stage") or ""), 9),
            "signal_score": round(signal_score, 4),
            "signal_level": level,
            "recommended_action": action,
            "confidence": confidence,
            "observed_weight": round(observed_weight, 4),
            "recent_spend": round(spend, 2),
            "recent_revenue": round(revenue, 2),
            "recent_roi": round(roi, 4),
            "installs": round(installs, 2),
            "ctr": round(ctr, 4),
            "d1_retention": round(retention_d1, 4),
            "ipm_proxy": round(ipm, 4),
            "cpi_proxy": round(cpi, 4),
            "component_scores": {key: round(value, 4) for key, value in components.items()},
            "positive_signals": positives,
            "negative_signals": negatives,
            "missing_signals": missing,
            "channels": sorted(metrics.get("channels") or stage.get("channels") or []),
            "geos": sorted(metrics.get("geos") or stage.get("geos") or []),
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 新品信号评分 | {payload['report_date']}",
            "",
            f"- 窗口：{payload['window_start']} 至 {payload['window_end']}",
            f"- 项目数：{summary['project_count']}；高信号：{summary['high_signal']}；中信号：{summary['medium_signal']}；低信号：{summary['low_signal']}。",
            "- 口径：新品阶段优先看 Signal Score、学习速度和测试假设质量，不用 ROI 强停测。",
            "",
            "| 项目 | 阶段 | 信号分 | 等级 | 置信度 | 花费 | ROI | 正信号 | 缺失信号 |",
            "|---|---|---:|---|---|---:|---:|---|---|",
        ]
        for item in payload["items"]:
            positives = "；".join(item["positive_signals"][:3]) or "暂无"
            missing = "；".join(item["missing_signals"][:4]) or "无"
            lines.append(
                f"| {item['project']} | {item['stage']} | {item['signal_score']:.2f} | {item['signal_level']} | "
                f"{item['confidence']} | {item['recent_spend']:.0f} | {item['recent_roi']:.2f} | {positives} | {missing} |"
            )
        if not payload["items"]:
            lines.append("| 暂无 | - | 0 | low | blocked | 0 | 0 | 暂无 | 无项目 |")
        lines.append("")
        return "\n".join(lines)


def score_high_better(value: float, *, good: float, excellent: float) -> float:
    if value <= 0:
        return 0.0
    if value <= good:
        return max(0.0, value / good * 0.6)
    if value >= excellent:
        return 1.0
    return 0.6 + ((value - good) / (excellent - good)) * 0.4


def score_low_better(value: float, *, good: float, weak: float) -> float:
    if value <= 0:
        return 0.0
    if value <= good:
        return 1.0
    if value >= weak:
        return 0.2
    return 1.0 - ((value - good) / (weak - good)) * 0.8
