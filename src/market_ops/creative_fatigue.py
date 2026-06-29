from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.models import CreativeAssetRow
from market_ops.pipeline import DataRepository


@dataclass(slots=True)
class CreativeFatigueResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class CreativeFatigueBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> CreativeFatigueResult:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = self.build_payload(report_date)
        markdown_path = output_dir / f"creative_fatigue_{suffix}.md"
        json_path = output_dir / f"creative_fatigue_{suffix}.json"
        csv_path = output_dir / f"creative_fatigue_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["items"])
        return CreativeFatigueResult(markdown_path, json_path, csv_path, True)

    def build_payload(self, report_date: date) -> dict[str, Any]:
        previous_start = report_date - timedelta(days=13)
        previous_end = report_date - timedelta(days=7)
        current_start = report_date - timedelta(days=6)
        previous, previous_source = self._load_bucket(previous_start, previous_end)
        current, current_source = self._load_bucket(current_start, report_date)

        items = []
        for key, cur in current.items():
            prev = previous.get(key)
            items.append(self._build_item(key, cur, prev))
        items.sort(key=lambda item: (item["status"] == "fatigue", item["spend"], abs(item["roi_change_pct"])), reverse=True)

        return {
            "report_date": report_date.isoformat(),
            "window_start": current_start.isoformat(),
            "window_end": report_date.isoformat(),
            "baseline_start": previous_start.isoformat(),
            "baseline_end": previous_end.isoformat(),
            "missing_metrics": ["frequency", "hold_rate"],
            "source": {
                "current": current_source,
                "baseline": previous_source,
                "cache_priority": "优先复用本地 adjust_creative_analysis 周缓存；缺少对应周聚合时才回落到底层数据源。",
            },
            "summary": {
                "creative_count": len(items),
                "fatigue_count": sum(1 for item in items if item["status"] == "fatigue"),
                "watch_count": sum(1 for item in items if item["status"] == "watch"),
                "metric_missing_count": sum(1 for item in items if item["status"] == "metric_missing"),
            },
            "items": items,
        }

    def _load_bucket(self, start_date: date, end_date: date) -> tuple[dict[tuple[str, str, str, str], dict[str, Any]], str]:
        cache_path = self._settings.active_output_dir / f"adjust_creative_analysis_{end_date.strftime('%Y%m%d')}.json"
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if payload.get("window_start") == start_date.isoformat() and payload.get("window_end") == end_date.isoformat():
                cached_items = payload.get("all_items") or payload.get("top_effective_creatives") or []
                return self._bucket_from_cached_items(cached_items), f"cached {cache_path}"

        rows = self._repo.load_adjust_creative_library(start_date, end_date)
        return self._bucket(rows), "repository fallback"

    @staticmethod
    def _bucket(rows: list[CreativeAssetRow]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
        buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in rows:
            key = (row.game, row.channel, row.country or "Global", row.asset_id or row.creative_name)
            bucket = buckets.setdefault(
                key,
                {
                    "project": row.game,
                    "channel": row.channel,
                    "country": row.country or "Global",
                    "creative_id": row.asset_id or row.creative_name,
                    "creative_name": row.creative_name,
                    "spend": 0.0,
                    "installs": 0.0,
                    "revenue": 0.0,
                    "ctr_weight": 0.0,
                    "cpi_weight": 0.0,
                    "ctr_source_missing": False,
                },
            )
            spend = float(row.spend or 0.0)
            installs = float(row.installs or 0.0)
            revenue = float(row.revenue_value or 0.0)
            bucket["spend"] += spend
            bucket["installs"] += installs
            bucket["revenue"] += revenue
            bucket["ctr_weight"] += float(row.ctr or 0.0) * max(spend, 1.0)
            bucket["cpi_weight"] += (spend / installs if installs else 0.0) * max(spend, 1.0)
        for bucket in buckets.values():
            spend = float(bucket["spend"])
            bucket["roi"] = bucket["revenue"] / spend if spend else 0.0
            bucket["ctr"] = bucket["ctr_weight"] / max(spend, 1.0)
            bucket["cpi"] = bucket["spend"] / bucket["installs"] if bucket["installs"] else 0.0
            bucket["cpm"] = 0.0
        return buckets

    @staticmethod
    def _bucket_from_cached_items(items: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
        buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for item in items:
            key = (
                str(item.get("project") or ""),
                str(item.get("channel") or ""),
                str(item.get("country") or "Global"),
                str(item.get("creative_id") or item.get("creative_name") or ""),
            )
            bucket = buckets.setdefault(
                key,
                {
                    "project": key[0],
                    "channel": key[1],
                    "country": key[2],
                    "creative_id": key[3],
                    "creative_name": str(item.get("creative_name") or key[3]),
                    "spend": 0.0,
                    "installs": 0.0,
                    "revenue": 0.0,
                    "ctr_weight": 0.0,
                    "cpi_weight": 0.0,
                    "ctr_source_missing": True,
                },
            )
            spend = float(item.get("spend") or 0.0)
            installs = float(item.get("installs") or 0.0)
            revenue = float(item.get("revenue") or 0.0)
            bucket["spend"] += spend
            bucket["installs"] += installs
            bucket["revenue"] += revenue
            bucket["cpi_weight"] += (spend / installs if installs else 0.0) * max(spend, 1.0)
        for bucket in buckets.values():
            spend = float(bucket["spend"])
            bucket["roi"] = bucket["revenue"] / spend if spend else 0.0
            bucket["ctr"] = 0.0
            bucket["cpi"] = bucket["spend"] / bucket["installs"] if bucket["installs"] else 0.0
            bucket["cpm"] = 0.0
        return buckets

    @staticmethod
    def _build_item(key: tuple[str, str, str, str], cur: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any]:
        if not prev or float(prev.get("spend") or 0.0) <= 0:
            status = "metric_missing"
            reason = ["缺少上一周同素材基线，不能判断疲劳。", "frequency/hold_rate 暂无来源，已标记缺口。"]
        else:
            ctr_missing = bool(cur.get("ctr_source_missing")) or bool(prev.get("ctr_source_missing"))
            ctr_drop = 0.0 if ctr_missing else _pct_drop(float(cur.get("ctr") or 0.0), float(prev.get("ctr") or 0.0))
            cpi_rise = _pct_rise(float(cur.get("cpi") or 0.0), float(prev.get("cpi") or 0.0))
            roi_drop = _pct_drop(float(cur.get("roi") or 0.0), float(prev.get("roi") or 0.0))
            spend_rise = _pct_rise(float(cur.get("spend") or 0.0), float(prev.get("spend") or 0.0))
            fatigue_reasons = []
            if not ctr_missing and ctr_drop > 0.15:
                fatigue_reasons.append(f"CTR 下降 {ctr_drop:.0%}")
            if cpi_rise > 0.20:
                fatigue_reasons.append(f"CPI 上涨 {cpi_rise:.0%}")
            if roi_drop > 0.20 and spend_rise >= 0:
                fatigue_reasons.append(f"ROI 下降 {roi_drop:.0%}")
            status = "fatigue" if fatigue_reasons else "watch"
            reason = fatigue_reasons or ["未触发 CTR/CPI/ROI 疲劳阈值，继续观察。"]
            if ctr_missing:
                reason.append("CTR 在本地周聚合缓存中缺失，未用于疲劳判断。")
            reason.append("frequency/hold_rate 暂无来源，未用于判断。")

        prev = prev or {}
        return {
            "project": cur["project"],
            "channel": cur["channel"],
            "country": cur["country"],
            "creative_id": cur["creative_id"],
            "creative_name": cur.get("creative_name") or cur["creative_id"],
            "status": status,
            "spend": round(float(cur.get("spend") or 0.0), 2),
            "installs": round(float(cur.get("installs") or 0.0), 2),
            "revenue": round(float(cur.get("revenue") or 0.0), 2),
            "roi": round(float(cur.get("roi") or 0.0), 4),
            "ctr": round(float(cur.get("ctr") or 0.0), 6),
            "cpi": round(float(cur.get("cpi") or 0.0), 4),
            "previous_spend": round(float(prev.get("spend") or 0.0), 2),
            "previous_roi": round(float(prev.get("roi") or 0.0), 4),
            "previous_ctr": round(float(prev.get("ctr") or 0.0), 6),
            "previous_cpi": round(float(prev.get("cpi") or 0.0), 4),
            "ctr_drop_pct": round(_pct_drop(float(cur.get("ctr") or 0.0), float(prev.get("ctr") or 0.0)), 4),
            "cpi_rise_pct": round(_pct_rise(float(cur.get("cpi") or 0.0), float(prev.get("cpi") or 0.0)), 4),
            "roi_change_pct": round(_pct_change(float(cur.get("roi") or 0.0), float(prev.get("roi") or 0.0)), 4),
            "reason": reason,
            "suggestion": _suggestion(status),
        }

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fieldnames = [
            "project",
            "channel",
            "country",
            "creative_id",
            "creative_name",
            "status",
            "spend",
            "installs",
            "revenue",
            "roi",
            "ctr",
            "cpi",
            "previous_spend",
            "previous_roi",
            "previous_ctr",
            "previous_cpi",
            "ctr_drop_pct",
            "cpi_rise_pct",
            "roi_change_pct",
            "reason",
            "suggestion",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                row = {field: item.get(field, "") for field in fieldnames}
                row["reason"] = "；".join(item.get("reason") or [])
                row["suggestion"] = "；".join(item.get("suggestion") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 素材疲劳检测 | {payload['report_date']}",
            "",
            f"- 当前窗口：{payload['window_start']} 至 {payload['window_end']}",
            f"- 对比基线：{payload['baseline_start']} 至 {payload['baseline_end']}",
            f"- 当前数据源：{payload['source']['current']}",
            f"- 基线数据源：{payload['source']['baseline']}",
            "- 判断指标：CTR、CPI、ROI、花费趋势；frequency/hold_rate 暂无来源，标记为缺口，不伪造证据。",
            "",
            "## 概览",
            "",
            f"- 素材数：{summary['creative_count']}",
            f"- 疲劳：{summary['fatigue_count']}；观察：{summary['watch_count']}；指标缺口：{summary['metric_missing_count']}",
            "",
            "## Top 疲劳/观察素材",
            "",
        ]
        if not payload["items"]:
            lines.append("- 暂无。")
        else:
            lines.extend(
                [
                    "| 项目 | 渠道 | 国家 | 素材 | 状态 | 花费 | ROI | CTR变化 | CPI变化 | 原因 | 建议 |",
                    "|---|---|---|---|---|---:|---:|---:|---:|---|---|",
                ]
            )
            for item in payload["items"][:30]:
                lines.append(
                    f"| {item['project']} | {item['channel']} | {item['country']} | `{item['creative_id']}` | {item['status']} | "
                    f"{item['spend']:.2f} | {item['roi']:.2f} | {item['ctr_drop_pct']:.0%} | {item['cpi_rise_pct']:.0%} | "
                    f"{'；'.join(item['reason'])} | {'；'.join(item['suggestion'])} |"
                )
        lines.append("")
        return "\n".join(lines)


def _pct_drop(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return max(0.0, (previous - current) / previous)


def _pct_rise(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return max(0.0, (current - previous) / previous)


def _pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return (current - previous) / previous


def _suggestion(status: str) -> list[str]:
    if status == "fatigue":
        return ["更换前 3 秒 Hook", "替换 BGM 或字幕密度", "增加冲突感后小样本复测"]
    if status == "metric_missing":
        return ["补齐上一周基线和 frequency/hold_rate 后再判断", "暂不做强停投结论"]
    return ["继续观察 3-7 天", "保持原预算或小样本变体测试"]
