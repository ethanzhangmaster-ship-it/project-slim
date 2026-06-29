from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.creative_dna import CreativeDnaBuilder


@dataclass(slots=True)
class CreativeClustersResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class CreativeClustersBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> CreativeClustersResult:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = self.build_payload(report_date)
        markdown_path = output_dir / f"creative_clusters_{suffix}.md"
        json_path = output_dir / f"creative_clusters_{suffix}.json"
        csv_path = output_dir / f"creative_clusters_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["clusters"])
        return CreativeClustersResult(markdown_path, json_path, csv_path, True)

    def build_payload(self, report_date: date) -> dict[str, Any]:
        dna_payload = CreativeDnaBuilder(self._settings).build_payload(report_date)
        buckets: dict[str, dict[str, Any]] = {}
        for item in dna_payload.get("items") or []:
            key_parts = [
                item.get("hook_type") or "unknown",
                item.get("emotion") or "unknown",
                item.get("pace") or "unknown",
                item.get("ui_type") or "unknown",
                item.get("video_structure") or "unknown",
            ]
            cluster_key = " / ".join(key_parts)
            bucket = buckets.setdefault(
                cluster_key,
                {
                    "cluster_name": _cluster_name(key_parts),
                    "cluster_key": cluster_key,
                    "creative_count": 0,
                    "spend": 0.0,
                    "installs": 0.0,
                    "revenue": 0.0,
                    "weighted_scalability": 0.0,
                    "best_channel": "",
                    "best_geo": [],
                    "best_platform": "unknown",
                    "confidence": "low",
                    "variant_direction": "",
                    "items": [],
                    "_channel": {},
                    "_geo": {},
                },
            )
            spend = float(item.get("spend") or 0.0)
            revenue = float(item.get("revenue") or 0.0)
            installs = float(item.get("installs") or 0.0)
            scalability = float(item.get("predicted_scalability") or 0.0)
            bucket["creative_count"] += 1
            bucket["spend"] += spend
            bucket["installs"] += installs
            bucket["revenue"] += revenue
            bucket["weighted_scalability"] += scalability * max(spend, 1.0)
            bucket["items"].append(item)
            bucket["_channel"][item.get("channel") or "Unknown"] = bucket["_channel"].get(item.get("channel") or "Unknown", 0.0) + spend
            bucket["_geo"][item.get("country") or "Global"] = bucket["_geo"].get(item.get("country") or "Global", 0.0) + spend

        clusters = []
        for bucket in buckets.values():
            spend = float(bucket["spend"])
            revenue = float(bucket["revenue"])
            bucket["avg_roi"] = round(revenue / spend, 4) if spend else 0.0
            bucket["spend"] = round(spend, 2)
            bucket["installs"] = round(float(bucket["installs"]), 2)
            bucket["revenue"] = round(revenue, 2)
            bucket["predicted_scalability"] = round(bucket["weighted_scalability"] / max(spend, 1.0), 4)
            bucket["best_channel"] = _top_key(bucket.pop("_channel"))
            bucket["best_geo"] = [_top_key(bucket.pop("_geo"))]
            bucket["confidence"] = _confidence(bucket)
            bucket["variant_direction"] = _variant_direction(bucket)
            clusters.append(bucket)
        clusters.sort(key=lambda item: (item["predicted_scalability"], item["avg_roi"], item["spend"]), reverse=True)
        return {
            "report_date": report_date.isoformat(),
            "window_start": dna_payload["window_start"],
            "window_end": dna_payload["window_end"],
            "summary": {
                "cluster_count": len(clusters),
                "strong_clusters": sum(1 for item in clusters if item["confidence"] != "low" and item["predicted_scalability"] >= 0.65),
                "low_confidence_clusters": sum(1 for item in clusters if item["confidence"] == "low"),
            },
            "clusters": clusters,
        }

    @staticmethod
    def _write_csv(path: Path, clusters: list[dict[str, Any]]) -> None:
        fieldnames = [
            "cluster_name",
            "cluster_key",
            "creative_count",
            "spend",
            "installs",
            "revenue",
            "avg_roi",
            "best_channel",
            "best_geo",
            "best_platform",
            "confidence",
            "predicted_scalability",
            "variant_direction",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in clusters:
                row = {field: item.get(field, "") for field in fieldnames}
                row["best_geo"] = ",".join(item.get("best_geo") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 素材聚类 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} 至 {payload['window_end']}",
            "- 聚类口径：Hook + 情绪 + 节奏 + UI + 视频结构，并叠加 ROI、花费、安装和可扩展性。",
            "",
            "## 概览",
            "",
            f"- 模式数：{summary['cluster_count']}",
            f"- 强候选模式：{summary['strong_clusters']}",
            f"- 低置信度模式：{summary['low_confidence_clusters']}",
            "",
            "## 模式排行",
            "",
        ]
        if not payload["clusters"]:
            lines.append("- 暂无。")
        else:
            lines.extend(
                [
                    "| 模式 | 素材数 | 花费 | 安装 | ROI | 最佳渠道 | 最佳国家 | 置信度 | 可扩展性 | 变体方向 |",
                    "|---|---:|---:|---:|---:|---|---|---|---:|---|",
                ]
            )
            for item in payload["clusters"][:20]:
                lines.append(
                    f"| {item['cluster_name']} | {item['creative_count']} | {item['spend']:.2f} | {item['installs']:.0f} | "
                    f"{item['avg_roi']:.2f} | {item['best_channel']} | {', '.join(item['best_geo'])} | {item['confidence']} | "
                    f"{item['predicted_scalability']:.2f} | {item['variant_direction']} |"
                )
        lines.append("")
        return "\n".join(lines)


def _cluster_name(parts: list[str]) -> str:
    readable = [part for part in parts if part and part != "unknown"]
    return " / ".join(readable) if readable else "unknown pattern"


def _top_key(values: dict[str, float]) -> str:
    if not values:
        return "unknown"
    return max(values.items(), key=lambda item: item[1])[0]


def _confidence(bucket: dict[str, Any]) -> str:
    if bucket["creative_count"] >= 3 and bucket["spend"] >= 300:
        return "high"
    if bucket["creative_count"] >= 2 or bucket["spend"] >= 100:
        return "medium"
    return "low"


def _variant_direction(bucket: dict[str, Any]) -> str:
    if bucket["confidence"] == "low":
        return "先补样本，不进入强复制。"
    if bucket["avg_roi"] >= 1.15 and bucket["predicted_scalability"] >= 0.65:
        return "复制 Hook 和前 3 秒结构，测试字幕密度、CTA 强弱和国家拆分。"
    if bucket["avg_roi"] < 0.8:
        return "保留模式标签，优先改开头冲突和节奏，不扩大投放。"
    return "小样本扩展 2-3 个变体，观察 ROI 与 CPI 是否稳定。"
