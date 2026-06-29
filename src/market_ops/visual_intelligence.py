from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.creative_dna import CreativeDnaBuilder
from market_ops.creative_source_readiness import CreativeSourceReadinessBuilder
from market_ops.local_visual_assets import LocalVisualAssetManifestBuilder


@dataclass(slots=True)
class VisualIntelligenceResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class VisualIntelligenceBuilder:
    """Audits whether creative intelligence is based on visual assets or proxy labels."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> VisualIntelligenceResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"visual_intelligence_{suffix}.md"
        json_path = output_dir / f"visual_intelligence_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return VisualIntelligenceResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        source_path = output_dir / f"creative_source_readiness_{suffix}.json"
        dna_path = output_dir / f"creative_dna_{suffix}.json"
        local_manifest_path = output_dir / f"local_visual_asset_manifest_{suffix}.json"
        if not source_path.exists():
            CreativeSourceReadinessBuilder(self._settings).build(report_date)
        if not dna_path.exists():
            CreativeDnaBuilder(self._settings).build(report_date)
        if not local_manifest_path.exists():
            LocalVisualAssetManifestBuilder(self._settings).build(report_date)
        source_payload = _load_json(source_path)
        dna_payload = _load_json(dna_path)
        local_manifest_payload = _load_json(local_manifest_path)
        dna_summary = dna_payload.get("summary") or {}
        dna_items = list(dna_payload.get("low_confidence") or []) + list(dna_payload.get("top_scalable") or [])
        asset_rows = [_asset_row(item) for item in dna_items]
        local_assets = [_asset_row(item) for item in (local_manifest_payload.get("assets") or [])]
        combined_assets = _dedupe_assets(asset_rows + local_assets)
        visual_ready_rows = [item for item in combined_assets if item["visual_asset_ready"]]
        creative_count = int(dna_summary.get("creative_count") or len(asset_rows))
        low_confidence_count = int(dna_summary.get("low_confidence_count") or sum(1 for item in asset_rows if item["label_confidence"] < 0.65))
        local_summary = local_manifest_payload.get("summary") or {}
        total_checked_count = max(creative_count, len(combined_assets))
        proxy_count = max(0, total_checked_count - len(visual_ready_rows))

        providers = source_payload.get("providers") or {}
        provider_rows = [_provider_row(name, item) for name, item in providers.items()]
        if local_summary.get("existing_source_count"):
            provider_rows.append(
                {
                    "provider": "local_folder_manifest",
                    "can_run_now": True,
                    "asset_level": "visual_asset_candidate",
                    "output_fields": ["creative_id", "creative_name", "video_path", "image_path", "project", "channel", "country"],
                    "visual_gaps": [],
                }
            )
        blocking_gaps = _blocking_gaps(provider_rows, len(visual_ready_rows), creative_count)

        return {
            "report_date": report_date.isoformat(),
            "mode": "visual_intelligence_readiness",
            "passed": True,
            "rules": {
                "paid_calls": "none",
                "no_visual_claim_without_asset": True,
                "proxy_labels_are_not_visual_understanding": True,
            },
            "summary": {
                "creative_rows_checked": total_checked_count,
                "sample_rows_checked": len(combined_assets),
                "visual_asset_ready_count": len(visual_ready_rows),
                "proxy_only_count": proxy_count,
                "low_confidence_count": low_confidence_count,
                "provider_count": len(provider_rows),
                "blocking_gap_count": len(blocking_gaps),
                "visual_intelligence_ready": bool(visual_ready_rows) and low_confidence_count < creative_count,
                "local_asset_count": int(local_summary.get("asset_count") or 0),
                "local_existing_source_count": int(local_summary.get("existing_source_count") or 0),
            },
            "providers": provider_rows,
            "blocking_gaps": blocking_gaps,
            "sample_assets": combined_assets[:30],
            "local_manifest_source_file": local_manifest_payload.get("source_file", ""),
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Visual Intelligence Readiness | {payload['report_date']}",
            "",
            "- Mode: visual_intelligence_readiness",
            "- Purpose: separate true visual asset understanding from name/proxy-based creative labels.",
            "- Paid calls: none",
            "",
            "## Summary",
            "",
            f"- Creative rows checked: {summary['creative_rows_checked']}",
            f"- Visual asset ready: {summary['visual_asset_ready_count']}",
            f"- Proxy only: {summary['proxy_only_count']}",
            f"- Low confidence: {summary['low_confidence_count']}",
            f"- Visual intelligence ready: {summary['visual_intelligence_ready']}",
            "",
            "## Providers",
            "",
        ]
        for item in payload["providers"]:
            gaps = ", ".join(item["visual_gaps"]) if item["visual_gaps"] else "none"
            lines.append(f"- {item['provider']} | can_run={item['can_run_now']} | asset_level={item['asset_level']} | gaps={gaps}")

        lines.extend(["", "## Blocking Gaps", ""])
        if not payload["blocking_gaps"]:
            lines.append("- None.")
        for item in payload["blocking_gaps"]:
            lines.append(f"- {item}")

        lines.extend(["", "## Sample Assets", ""])
        if not payload["sample_assets"]:
            lines.append("- None.")
        for item in payload["sample_assets"][:20]:
            lines.append(
                f"- {item['creative_id']} | {item['project']} | {item['channel']} | "
                f"asset_ready={item['visual_asset_ready']} | evidence={item['visual_evidence_level']} | confidence={item['label_confidence']}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _asset_row(item: dict[str, Any]) -> dict[str, Any]:
    video_path = str(item.get("video_path") or item.get("asset_url") or item.get("image_path") or "")
    visual_ready = bool(video_path and Path(video_path).exists())
    duration_seconds = float(item.get("asset_duration_seconds") or 0.0)
    return {
        "creative_id": str(item.get("creative_id") or ""),
        "project": str(item.get("project") or ""),
        "channel": str(item.get("channel") or ""),
        "country": str(item.get("country") or ""),
        "creative_name": str(item.get("creative_name") or ""),
        "video_path": video_path,
        "asset_type": str(item.get("asset_type") or ("video" if str(item.get("video_structure") or "") == "video" else "image" if str(item.get("video_structure") or "") == "image" else "unknown")),
        "asset_orientation": str(item.get("asset_orientation") or "unknown"),
        "asset_aspect_ratio": str(item.get("asset_aspect_ratio") or "unknown"),
        "asset_duration_bucket": str(item.get("asset_duration_bucket") or _duration_bucket(duration_seconds)),
        "asset_duration_seconds": duration_seconds,
        "visual_asset_ready": visual_ready,
        "visual_evidence_level": "asset_available" if visual_ready else "proxy_only",
        "label_source": str(item.get("label_source") or ""),
        "label_confidence": float(item.get("label_confidence") or 0.0),
        "hook_type": str(item.get("hook_type") or "unknown"),
        "emotion": str(item.get("emotion") or "unknown"),
        "video_structure": str(item.get("video_structure") or "unknown"),
    }


def _dedupe_assets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (
            str(item.get("creative_id") or "").strip(),
            str(item.get("video_path") or item.get("image_path") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _provider_row(name: str, item: dict[str, Any]) -> dict[str, Any]:
    output_fields = item.get("output_fields") or []
    has_video_path = any("video_path" in str(field) or "asset_url" in str(field) or "image" in str(field) for field in output_fields)
    gaps = list(item.get("gaps") or [])
    if not has_video_path:
        gaps.append("provider_output_has_no_visual_asset_path")
    return {
        "provider": name,
        "can_run_now": bool(item.get("can_run_now")),
        "asset_level": "visual_asset_candidate" if has_video_path else "metadata_or_ad_proxy",
        "output_fields": output_fields,
        "visual_gaps": gaps,
    }


def _blocking_gaps(provider_rows: list[dict[str, Any]], ready_asset_count: int, checked_count: int) -> list[str]:
    gaps: list[str] = []
    if checked_count == 0:
        gaps.append("no_creative_rows_available")
    if ready_asset_count == 0:
        gaps.append("no_local_or_remote_visual_asset_paths_available")
    if not any(item["asset_level"] == "visual_asset_candidate" and item["can_run_now"] for item in provider_rows):
        gaps.append("no_runnable_provider_with_visual_asset_output")
    gaps.append("creative_dna_currently_rule_or_proxy_based")
    return gaps


def _duration_bucket(duration_seconds: float) -> str:
    if duration_seconds <= 0:
        return "unknown"
    if duration_seconds < 10:
        return "short"
    if duration_seconds < 25:
        return "mid"
    return "long"
