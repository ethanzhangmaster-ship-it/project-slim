from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.pipeline import DataRepository


@dataclass(slots=True)
class NewProductStageResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class NewProductStageBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> NewProductStageResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"new_product_stage_{suffix}.md"
        json_path = output_dir / f"new_product_stage_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return NewProductStageResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        lookback_start = report_date - timedelta(days=70)
        week_start = report_date - timedelta(days=6)
        cached_payload = self._build_payload_from_adjust_cache(report_date, lookback_start, week_start)
        if cached_payload is not None:
            return cached_payload

        rows = self._repo.load_adjust_revenue_breakdown(lookback_start, report_date)

        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            project = project_label(row.game)
            if not project:
                continue
            bucket = buckets.setdefault(
                project,
                {
                    "project": project,
                    "first_seen": row.date,
                    "last_seen": row.date,
                    "total_spend": 0.0,
                    "recent_spend": 0.0,
                    "recent_revenue": 0.0,
                    "recent_installs": 0.0,
                    "channels": set(),
                    "geos": set(),
                },
            )
            bucket["first_seen"] = min(bucket["first_seen"], row.date)
            bucket["last_seen"] = max(bucket["last_seen"], row.date)
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            installs = float(getattr(row, "installs", 0.0) or 0.0)
            bucket["total_spend"] += cost
            if week_start <= row.date <= report_date:
                bucket["recent_spend"] += cost
                bucket["recent_revenue"] += revenue
                bucket["recent_installs"] += installs
            channel = normalize_channel(row.partner)
            if channel:
                bucket["channels"].add(channel)
            geo = str(getattr(row, "country", "") or "").strip()
            if geo:
                bucket["geos"].add(geo)

        items = [self._stage_item(bucket, report_date) for bucket in buckets.values()]
        items.sort(key=lambda item: (stage_order(item["stage"]), -float(item["recent_spend"] or 0.0), item["project"]))
        return {
            "report_date": report_date.isoformat(),
            "lookback_start": lookback_start.isoformat(),
            "window_start": week_start.isoformat(),
            "window_end": report_date.isoformat(),
            "passed": True,
            "stage_rules": {
                "Discovery": "first_seen_age_days <= 7",
                "Validation": "8 <= first_seen_age_days <= 30",
                "Scaling": "first_seen_age_days > 30",
            },
            "summary": {
                "project_count": len(items),
                "discovery_count": sum(1 for item in items if item["stage"] == "Discovery"),
                "validation_count": sum(1 for item in items if item["stage"] == "Validation"),
                "scaling_count": sum(1 for item in items if item["stage"] == "Scaling"),
            },
            "items": items,
        }

    def _build_payload_from_adjust_cache(
        self,
        report_date: date,
        lookback_start: date,
        week_start: date,
    ) -> dict[str, Any] | None:
        path = self._settings.active_output_dir / f"adjust_creative_analysis_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        rows = payload.get("project_channel_summary") or []
        if not rows:
            return None

        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            project = project_label(str(row.get("project") or ""))
            if not project:
                continue
            bucket = buckets.setdefault(
                project,
                {
                    "project": project,
                    "first_seen": week_start,
                    "last_seen": report_date,
                    "total_spend": 0.0,
                    "recent_spend": 0.0,
                    "recent_revenue": 0.0,
                    "recent_installs": 0.0,
                    "channels": set(),
                    "geos": set(),
                },
            )
            spend = float(row.get("spend") or 0.0)
            bucket["total_spend"] += spend
            bucket["recent_spend"] += spend
            bucket["recent_revenue"] += float(row.get("revenue") or 0.0)
            bucket["recent_installs"] += float(row.get("installs") or 0.0)
            channel = normalize_channel(str(row.get("channel") or ""))
            if channel:
                bucket["channels"].add(channel)

        items = [self._stage_item_from_cache(bucket, report_date) for bucket in buckets.values()]
        items.sort(key=lambda item: (stage_order(item["stage"]), -float(item["recent_spend"] or 0.0), item["project"]))
        return {
            "report_date": report_date.isoformat(),
            "lookback_start": lookback_start.isoformat(),
            "window_start": week_start.isoformat(),
            "window_end": report_date.isoformat(),
            "source": str(path),
            "passed": True,
            "stage_rules": {
                "Discovery": "first_seen_age_days <= 7",
                "Validation": "8 <= first_seen_age_days <= 30",
                "Scaling": "first_seen_age_days > 30",
                "cache_note": "缓存只有周级窗口时，已知老项目按 Scaling 处理；疑似 P09+ 新项目按 Discovery 处理。",
            },
            "summary": {
                "project_count": len(items),
                "discovery_count": sum(1 for item in items if item["stage"] == "Discovery"),
                "validation_count": sum(1 for item in items if item["stage"] == "Validation"),
                "scaling_count": sum(1 for item in items if item["stage"] == "Scaling"),
            },
            "items": items,
        }

    @staticmethod
    def _stage_item(bucket: dict[str, Any], report_date: date) -> dict[str, Any]:
        first_seen = bucket["first_seen"]
        age_days = max(0, (report_date - first_seen).days)
        if age_days <= 7:
            stage = "Discovery"
            engine = "Discovery Engine"
            goal = "找方向"
        elif age_days <= 30:
            stage = "Validation"
            engine = "Discovery Engine"
            goal = "验证模式"
        else:
            stage = "Scaling"
            engine = "Optimization Engine"
            goal = "ROI优化"
        spend = float(bucket.get("recent_spend") or 0.0)
        revenue = float(bucket.get("recent_revenue") or 0.0)
        return {
            "project": bucket["project"],
            "project_code": project_code(bucket["project"]),
            "stage": stage,
            "engine": engine,
            "stage_goal": goal,
            "first_seen": first_seen.isoformat(),
            "last_seen": bucket["last_seen"].isoformat(),
            "first_seen_age_days": age_days,
            "recent_spend": round(spend, 2),
            "recent_revenue": round(revenue, 2),
            "recent_roi": round(revenue / spend, 4) if spend else 0.0,
            "recent_installs": round(float(bucket.get("recent_installs") or 0.0), 2),
            "channels": sorted(bucket.get("channels") or []),
            "geos": sorted(bucket.get("geos") or []),
            "decision_rule": "新品阶段优先看信号和学习速度" if stage != "Scaling" else "进入ROI、回本、疲劳和扩量判断",
        }

    @staticmethod
    def _stage_item_from_cache(bucket: dict[str, Any], report_date: date) -> dict[str, Any]:
        project = str(bucket["project"])
        code = project_code(project)
        numeric_code = _project_number(code)
        if numeric_code >= 9:
            stage = "Discovery"
            engine = "Discovery Engine"
            goal = "找方向"
            age_days = max(0, (report_date - bucket["first_seen"]).days)
            decision_rule = "缓存识别为疑似新品，优先看信号和学习速度"
        else:
            stage = "Scaling"
            engine = "Optimization Engine"
            goal = "ROI优化"
            age_days = 31
            decision_rule = "缓存无法证明为新品，默认进入ROI、回本、疲劳和扩量判断"
        spend = float(bucket.get("recent_spend") or 0.0)
        revenue = float(bucket.get("recent_revenue") or 0.0)
        return {
            "project": project,
            "project_code": code,
            "stage": stage,
            "engine": engine,
            "stage_goal": goal,
            "first_seen": bucket["first_seen"].isoformat(),
            "last_seen": bucket["last_seen"].isoformat(),
            "first_seen_age_days": age_days,
            "recent_spend": round(spend, 2),
            "recent_revenue": round(revenue, 2),
            "recent_roi": round(revenue / spend, 4) if spend else 0.0,
            "recent_installs": round(float(bucket.get("recent_installs") or 0.0), 2),
            "channels": sorted(bucket.get("channels") or []),
            "geos": sorted(bucket.get("geos") or []),
            "decision_rule": decision_rule,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 新品阶段识别 | {payload['report_date']}",
            "",
            f"- 近7日窗口：{payload['window_start']} 至 {payload['window_end']}",
            f"- 项目数：{summary['project_count']}；Discovery：{summary['discovery_count']}；Validation：{summary['validation_count']}；Scaling：{summary['scaling_count']}。",
            "- 规则：Discovery/Validation 进入 Discovery Engine；Scaling 进入 Optimization Engine。",
            "",
            "| 项目 | 阶段 | 引擎 | 首次出现 | 天数 | 近7日花费 | 近7日ROI | 判断口径 |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
        for item in payload["items"]:
            lines.append(
                f"| {item['project']} | {item['stage']} | {item['engine']} | {item['first_seen']} | "
                f"{item['first_seen_age_days']} | {item['recent_spend']:.0f} | {item['recent_roi']:.2f} | {item['decision_rule']} |"
            )
        if not payload["items"]:
            lines.append("| 暂无 | - | - | - | 0 | 0 | 0 | 无可识别项目 |")
        lines.append("")
        return "\n".join(lines)


def project_label(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"\bP0*([0-9]+)\b", text.upper())
    if not match:
        return text
    code = f"P{int(match.group(1)):02d}"
    suffix = re.sub(r"(?i)^.*?\bP0*[0-9]+\b", "", text).strip(" -_/")
    return f"{code} {suffix}".strip()


def project_code(value: str) -> str:
    match = re.search(r"\bP0*([0-9]+)\b", str(value or "").upper())
    return f"P{int(match.group(1)):02d}" if match else str(value or "").strip()


def normalize_channel(value: str) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if "facebook" in lowered or "meta" in lowered or "instagram" in lowered:
        return "Facebook"
    if "google" in lowered or "adwords" in lowered:
        return "Google"
    if "apple" in lowered or "search ads" in lowered:
        return "Apple Search"
    if "applovin" in lowered:
        return "Applovin"
    if "unity" in lowered:
        return "Unity Ads"
    if "tiktok" in lowered or "tik tok" in lowered:
        return "TikTok"
    return text


def stage_order(stage: str) -> int:
    return {"Discovery": 0, "Validation": 1, "Scaling": 2}.get(stage, 9)


def _project_number(code: str) -> int:
    match = re.search(r"\bP0*([0-9]+)\b", str(code or "").upper())
    return int(match.group(1)) if match else 0
