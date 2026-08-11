from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.local_visual_assets import LocalVisualAssetManifestBuilder
from market_ops.models import CreativeAssetRow
from market_ops.pipeline import DataRepository


FIELDS = [
    "creative_id",
    "project",
    "channel",
    "country",
    "campaign",
    "creative_name",
    "hook_type",
    "emotion",
    "pace",
    "ui_type",
    "copy_style",
    "cta_strength",
    "video_structure",
    "subtitle_style",
    "first_3s_density",
    "conflict_strength",
    "asset_type",
    "asset_orientation",
    "asset_aspect_ratio",
    "asset_duration_bucket",
    "label_source",
    "label_confidence",
    "predicted_scalability",
]

MIN_STRONG_SPEND = 100.0
MIN_STRONG_INSTALLS = 30.0


@dataclass(slots=True)
class CreativeDnaItem:
    creative_id: str
    project: str
    channel: str
    country: str
    campaign: str
    creative_name: str
    hook_type: str
    emotion: str
    pace: str
    ui_type: str
    copy_style: str
    cta_strength: str
    video_structure: str
    subtitle_style: str
    first_3s_density: str
    conflict_strength: str
    asset_type: str
    asset_orientation: str
    asset_aspect_ratio: str
    asset_duration_bucket: str
    label_source: str
    label_confidence: float
    predicted_scalability: float
    spend: float
    installs: float
    revenue: float
    roi: float


@dataclass(slots=True)
class CreativeDnaResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class CreativeDnaBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> CreativeDnaResult:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"creative_dna_{suffix}.md"
        json_path = output_dir / f"creative_dna_{suffix}.json"
        csv_path = output_dir / f"creative_dna_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["items"])
        return CreativeDnaResult(markdown_path, json_path, csv_path, True)

    def build_payload(self, report_date: date) -> dict[str, Any]:
        window_start = report_date - timedelta(days=6)
        rows, source = self._load_creative_rows(report_date=report_date, window_start=window_start)
        labels = self._load_manual_labels()
        items = [self._build_item(row, labels) for row in rows if float(row.spend or 0.0) > 0]
        local_winner_items = self._load_local_winner_items(report_date=report_date, existing_items=items)
        items.extend(local_winner_items)
        items.sort(key=lambda item: (item.predicted_scalability, item.roi, item.spend), reverse=True)
        confident = [item for item in items if item.label_confidence >= 0.65]
        scalable = [
            item
            for item in confident
            if item.predicted_scalability >= 0.65 and (item.spend >= MIN_STRONG_SPEND or item.installs >= MIN_STRONG_INSTALLS)
        ]
        return {
            "report_date": report_date.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": report_date.isoformat(),
            "source": source,
            "rules": {
                "manual_labels_priority": True,
                "cache_priority": "reuse output/active/adjust_creative_analysis_YYYYMMDD.json when the window matches; fall back to repository if missing",
                "low_confidence_policy": "unknown fields and confidence < 0.65 only enter observation, not strong copy conclusions",
                "paid_calls": "none",
                "local_real_asset_winner_prior": "user-supplied recent winning assets can enter Creative DNA as real-asset learning priors even before platform metrics are rejoined",
            },
            "summary": {
                "creative_count": len(items),
                "manual_label_count": sum(1 for item in items if item.label_source == "manual"),
                "rule_label_count": sum(1 for item in items if item.label_source == "rule"),
                "local_winner_prior_count": sum(1 for item in items if item.label_source == "local_winner_prior"),
                "low_confidence_count": sum(1 for item in items if item.label_confidence < 0.65),
                "scalable_pattern_candidates": len(scalable),
            },
            "top_scalable": [asdict(item) for item in scalable[:20]],
            "local_winner_priors": [asdict(item) for item in items if item.label_source == "local_winner_prior"][:20],
            "low_confidence": [asdict(item) for item in items if item.label_confidence < 0.65][:30],
            "items": [asdict(item) for item in items],
        }

    def _load_creative_rows(self, *, report_date: date, window_start: date) -> tuple[list[CreativeAssetRow], str]:
        cache_path = self._settings.active_output_dir / f"adjust_creative_analysis_{report_date.strftime('%Y%m%d')}.json"
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if payload.get("window_start") == window_start.isoformat() and payload.get("window_end") == report_date.isoformat():
                cached_items = payload.get("all_items") or payload.get("top_effective_creatives") or []
                rows = [_creative_row_from_adjust_cache(item) for item in cached_items]
                return rows, f"Cached Adjust creative analysis: {cache_path}"
        rows = self._repo.load_adjust_creative_library(window_start, report_date)
        return rows, "Adjust creative aggregates + optional input/creative_dna_labels.csv"

    def _build_item(self, row: CreativeAssetRow, labels: dict[str, dict[str, str]]) -> CreativeDnaItem:
        creative_id = str(row.asset_id or row.creative_name or "").strip()
        text = " ".join(
            str(value or "")
            for value in (
                row.creative_name,
                row.hook_type,
                row.campaign,
                row.adgroup,
                row.ad_name,
                row.source_name,
                row.creative_type,
            )
        )
        manual = self._match_manual_label(creative_id, row.creative_name, labels)
        rule_labels, rule_hits = _infer_labels(text)
        merged = dict(rule_labels)
        label_source = "rule"
        if manual:
            merged.update({field: value for field, value in manual.items() if field in FIELDS and value})
            label_source = "manual"
        unknown_count = sum(1 for field in _DNA_ONLY_FIELDS if merged.get(field, "unknown") == "unknown")
        confidence = 0.35 + min(rule_hits, 5) * 0.08
        if manual:
            confidence = max(confidence, 0.86)
        if unknown_count >= 8:
            confidence = min(confidence, 0.55)
        spend = float(row.spend or 0.0)
        installs = float(row.installs or 0.0)
        revenue = float(row.revenue_value or 0.0)
        roi = revenue / spend if spend else float(row.roas or 0.0)
        sample_boost = 0.10 if spend >= MIN_STRONG_SPEND or installs >= MIN_STRONG_INSTALLS else -0.08
        scalability = max(0.0, min(0.95, (roi / 2.0) * 0.45 + confidence * 0.35 + sample_boost))
        if confidence < 0.65:
            scalability = min(scalability, 0.49)
        values = {field: merged.get(field, "unknown") or "unknown" for field in _DNA_ONLY_FIELDS}
        return CreativeDnaItem(
            creative_id=creative_id,
            project=_project_label(row.game),
            channel=_normalize_channel(row.channel),
            country=row.country or "Global",
            campaign=row.campaign or row.campaign_id,
            creative_name=row.creative_name or creative_id,
            label_source=label_source,
            label_confidence=round(confidence, 4),
            predicted_scalability=round(scalability, 4),
            spend=round(spend, 2),
            installs=round(installs, 2),
            revenue=round(revenue, 2),
            roi=round(roi, 4),
            asset_type=_asset_type_from_row(row),
            asset_orientation="unknown",
            asset_aspect_ratio="unknown",
            asset_duration_bucket=_duration_bucket(float(row.duration or 0.0)),
            **values,
        )

    @staticmethod
    def _match_manual_label(creative_id: str, creative_name: str, labels: dict[str, dict[str, str]]) -> dict[str, str] | None:
        for key in (creative_id, creative_name):
            normalized = str(key or "").strip()
            if normalized and normalized in labels:
                return labels[normalized]
        return None

    def _load_manual_labels(self) -> dict[str, dict[str, str]]:
        path = Path("input") / "creative_dna_labels.csv"
        if not path.exists():
            return {}
        result: dict[str, dict[str, str]] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = str(row.get("creative_id") or row.get("creative_name") or "").strip()
                if key:
                    result[key] = {field: str(row.get(field) or "").strip() for field in FIELDS}
        return result

    def _load_local_winner_items(self, *, report_date: date, existing_items: list[CreativeDnaItem]) -> list[CreativeDnaItem]:
        suffix = report_date.strftime("%Y%m%d")
        manifest_path = self._settings.active_output_dir / f"local_visual_asset_manifest_{suffix}.json"
        if not manifest_path.exists():
            LocalVisualAssetManifestBuilder(self._settings).build(report_date)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []

        existing_keys = {
            (str(item.creative_id or "").strip(), str(item.creative_name or "").strip())
            for item in existing_items
        }
        local_items: list[CreativeDnaItem] = []
        for asset in payload.get("assets") or []:
            creative_id = str(asset.get("creative_id") or "").strip()
            creative_name = str(asset.get("creative_name") or creative_id).strip()
            key = (creative_id, creative_name)
            if not creative_id or key in existing_keys:
                continue

            merged, rule_hits = _infer_labels(
                " ".join(
                    [
                        creative_name,
                        str(asset.get("project") or ""),
                        str(asset.get("channel") or ""),
                        str(asset.get("video_structure") or ""),
                    ]
                )
            )
            merged["ui_type"] = _project_ui_type(str(asset.get("project") or ""))
            merged["video_structure"] = str(asset.get("video_structure") or merged.get("video_structure") or "unknown")
            unknown_count = sum(1 for field in _DNA_ONLY_FIELDS if merged.get(field, "unknown") == "unknown")
            confidence = 0.72 if unknown_count <= 7 else 0.66
            if rule_hits >= 2:
                confidence = max(confidence, 0.78)
            local_items.append(
                CreativeDnaItem(
                    creative_id=creative_id,
                    project=str(asset.get("project") or "Unknown"),
                    channel=_normalize_channel(str(asset.get("channel") or "")),
                    country=str(asset.get("country") or "Global"),
                    campaign="local_real_asset_winner_prior",
                    creative_name=creative_name,
                    hook_type=merged.get("hook_type", "unknown"),
                    emotion=merged.get("emotion", "unknown"),
                    pace=merged.get("pace", "unknown"),
                    ui_type=merged.get("ui_type", "unknown"),
                    copy_style=merged.get("copy_style", "unknown"),
                    cta_strength=merged.get("cta_strength", "unknown"),
                    video_structure=merged.get("video_structure", "unknown"),
                    subtitle_style=merged.get("subtitle_style", "unknown"),
                    first_3s_density=merged.get("first_3s_density", "unknown"),
                    conflict_strength=merged.get("conflict_strength", "unknown"),
                    asset_type=str(asset.get("asset_type") or merged.get("video_structure") or "unknown"),
                    asset_orientation=str(asset.get("asset_orientation") or "unknown"),
                    asset_aspect_ratio=str(asset.get("asset_aspect_ratio") or "unknown"),
                    asset_duration_bucket=_duration_bucket(float(asset.get("asset_duration_seconds") or 0.0)),
                    label_source="local_winner_prior",
                    label_confidence=round(confidence, 4),
                    predicted_scalability=0.72,
                    spend=0.0,
                    installs=0.0,
                    revenue=0.0,
                    roi=0.0,
                )
            )
        return local_items

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fieldnames = FIELDS + ["spend", "installs", "revenue", "roi"]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow({field: item.get(field, "") for field in fieldnames})

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 素材 DNA 识别 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} 至 {payload['window_end']}",
            "- 数据源：现有素材聚合、素材名、Campaign 名和可选手工标签表；不调用多模态模型，不产生额外付费。",
            "- 低置信度规则：无法识别的字段写 unknown，低于 0.65 的结果只进入观察，不进入强复制结论。",
            "",
            "## 概览",
            "",
            f"- 素材数：{summary['creative_count']}",
            f"- 手工标签：{summary['manual_label_count']}；规则识别：{summary['rule_label_count']}",
            f"- 低置信度：{summary['low_confidence_count']}",
            f"- 可进入复制/变体候选：{summary['scalable_pattern_candidates']}",
            "",
            "## 可复制候选",
            "",
        ]
        lines.extend(_render_dna_table(payload.get("top_scalable") or []))
        lines.extend(["", "## 低置信度观察", ""])
        lines.extend(_render_dna_table((payload.get("low_confidence") or [])[:15]))
        lines.append("")
        return "\n".join(lines)


_DNA_ONLY_FIELDS = [
    "hook_type",
    "emotion",
    "pace",
    "ui_type",
    "copy_style",
    "cta_strength",
    "video_structure",
    "subtitle_style",
    "first_3s_density",
    "conflict_strength",
]


def _asset_type_from_row(row: CreativeAssetRow) -> str:
    creative_type = str(row.creative_type or "").strip().lower()
    creative_name = str(row.creative_name or row.asset_id or "").strip().lower()
    video_path = str(row.video_path or "").strip().lower()
    text = " ".join([creative_type, creative_name, video_path])
    if any(ext in text for ext in (".mp4", ".mov", ".m4v", ".avi", ".webm")):
        return "video"
    if any(ext in text for ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return "image"
    if "video" in text:
        return "video"
    if "image" in text or "picture" in text:
        return "image"
    return "unknown"


def _duration_bucket(duration_seconds: float) -> str:
    if duration_seconds <= 0:
        return "unknown"
    if duration_seconds < 10:
        return "short"
    if duration_seconds < 25:
        return "mid"
    return "long"


def _infer_labels(text: str) -> tuple[dict[str, str], int]:
    normalized = text.lower()
    labels = {field: "unknown" for field in _DNA_ONLY_FIELDS}
    hits = 0
    rules: list[tuple[str, str, str, list[str]]] = [
        ("hook_type", "危机", "crisis", ["危机", "rescue", "save", "help", "困", "danger", "crisis"]),
        ("hook_type", "爽点", "reward", ["爽", "win", "level", "reward", "bonus"]),
        ("hook_type", "反转", "twist", ["反转", "unexpected", "fail", "wrong"]),
        ("emotion", "焦虑", "anxiety", ["焦虑", "urgent", "快", "danger", "救"]),
        ("emotion", "爽感", "satisfaction", ["爽", "win", "clear", "success"]),
        ("emotion", "治愈", "healing", ["治愈", "home", "garden", "cozy", "relax"]),
        ("pace", "快", "fast", ["fast", "quick", "快切", "short", "秒"]),
        ("pace", "慢", "slow", ["slow", "story", "剧情", "铺垫"]),
        ("ui_type", "Merge", "merge", ["merge", "合成", "mermaid", "witch", "vampire"]),
        ("ui_type", "Build", "build", ["build", "home", "装修", "建造"]),
        ("ui_type", "Battle", "battle", ["battle", "fight", "attack", "boss"]),
        ("copy_style", "强标题", "strong_title", ["big text", "title", "headline", "大字", "标题"]),
        ("copy_style", "弱标题", "soft_title", ["ugc", "native", "story"]),
        ("cta_strength", "强", "strong_cta", ["install", "download", "play now", "立即", "马上"]),
        ("cta_strength", "弱", "soft_cta", ["try", "看看", "story"]),
        ("video_structure", "UGC", "ugc", ["ugc", "creator", "真人", "口播"]),
        ("video_structure", "游戏录屏", "gameplay", ["gameplay", "录屏", "screen", "playable"]),
        ("video_structure", "图片", "image", ["image", "图片", "素材"]),
        ("subtitle_style", "大字", "large_subtitle", ["大字", "big text", "caption"]),
        ("subtitle_style", "悬疑", "suspense_subtitle", ["悬疑", "why", "secret", "mystery"]),
        ("subtitle_style", "高密度", "dense_subtitle", ["dense", "多字幕", "高密度"]),
        ("first_3s_density", "高", "high_density", ["hook", "3s", "前三秒", "快切"]),
        ("first_3s_density", "低", "low_density", ["slow", "铺垫"]),
        ("conflict_strength", "强", "strong_conflict", ["危机", "救", "fail", "wrong", "fight", "danger"]),
        ("conflict_strength", "弱", "soft_conflict", ["cozy", "home", "治愈", "relax"]),
    ]
    for field, value, _tag, keywords in rules:
        if labels[field] != "unknown":
            continue
        if any(keyword.lower() in normalized for keyword in keywords):
            labels[field] = value
            hits += 1
    return labels, hits


def _render_dna_table(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- 暂无。"]
    lines = [
        "| 项目 | 渠道 | 国家 | 素材 | Hook | 情绪 | 节奏 | UI | 结构 | 置信度 | 可扩展性 | ROI |",
        "|---|---|---|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for item in items:
        lines.append(
            f"| {item.get('project', '')} | {item.get('channel', '')} | {item.get('country', '')} | `{item.get('creative_id', '')}` | "
            f"{item.get('hook_type', '')} | {item.get('emotion', '')} | {item.get('pace', '')} | {item.get('ui_type', '')} | "
            f"{item.get('video_structure', '')} | {float(item.get('label_confidence') or 0):.2f} | "
            f"{float(item.get('predicted_scalability') or 0):.2f} | {float(item.get('roi') or 0):.2f} |"
        )
    return lines


def _creative_row_from_adjust_cache(item: dict[str, Any]) -> CreativeAssetRow:
    spend = float(item.get("spend") or 0.0)
    installs = float(item.get("installs") or 0.0)
    revenue = float(item.get("revenue") or 0.0)
    return CreativeAssetRow(
        asset_id=str(item.get("creative_id") or item.get("creative_name") or "").strip(),
        creative_type=str(item.get("identity_level") or ""),
        video_path="",
        game=str(item.get("project") or ""),
        country=str(item.get("country") or "Global"),
        channel=str(item.get("channel") or ""),
        ctr=0.0,
        cvr=0.0,
        roas=revenue / spend if spend else 0.0,
        spend=spend,
        status="cached",
        creative_name=str(item.get("creative_name") or item.get("creative_id") or ""),
        campaign=str(item.get("campaign") or ""),
        campaign_id=str(item.get("campaign_id") or ""),
        adgroup=str(item.get("adgroup") or ""),
        adgroup_id=str(item.get("adgroup_id") or ""),
        source_name=str(item.get("source_name") or ""),
        source_id=str(item.get("source_id") or ""),
        installs=installs,
        revenue_value=revenue,
    )


def _project_label(value: str) -> str:
    text = (value or "").strip()
    match = re.search(r"\bP0*([0-9]+)\b", text.upper())
    if match:
        code = f"P{int(match.group(1)):02d}"
        if "witch" in text.lower():
            return f"{code} Witch"
        if "vampire" in text.lower():
            return f"{code} Vampire"
        if "mermaid" in text.lower():
            return f"{code} Mermaid"
        return code
    return text or "Unknown"


def _normalize_channel(value: str) -> str:
    normalized = (value or "").strip().lower()
    if "google" in normalized:
        return "Google"
    if "facebook" in normalized or "instagram" in normalized or "meta" in normalized:
        return "Facebook"
    if "apple" in normalized or "asa" in normalized:
        return "Apple Search"
    if "applovin" in normalized:
        return "Applovin"
    if "unity" in normalized:
        return "Unity Ads"
    if "tiktok" in normalized or "bytedance" in normalized:
        return "TikTok"
    return value or "Unknown"


def _project_ui_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    if "witch" in normalized or "vampire" in normalized or "mermaid" in normalized or "merge" in normalized:
        return "Merge"
    return "unknown"
