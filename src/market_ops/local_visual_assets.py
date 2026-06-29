from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import cv2
from PIL import Image

from market_ops.config import Settings


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass(slots=True)
class LocalVisualAssetManifestResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class LocalVisualAssetManifestBuilder:
    """Scans configured local folders and produces a real visual-asset manifest."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> LocalVisualAssetManifestResult:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"local_visual_asset_manifest_{suffix}.md"
        json_path = output_dir / f"local_visual_asset_manifest_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return LocalVisualAssetManifestResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        workspace_root = self._settings.output_dir.parent
        input_path = workspace_root / "input" / "local_visual_asset_sources.json"
        configured_sources = _load_sources(input_path)

        assets: list[dict[str, Any]] = []
        source_rows: list[dict[str, Any]] = []
        missing_sources: list[str] = []

        for source in configured_sources:
            raw_path = str(source.get("path") or "").strip()
            root = Path(raw_path)
            files: list[Path] = []
            if root.exists() and root.is_dir():
                files = [item for item in sorted(root.iterdir()) if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS]
            else:
                if raw_path:
                    missing_sources.append(raw_path)

            source_rows.append(
                {
                    "project": str(source.get("project") or "").strip(),
                    "channel": str(source.get("channel") or "").strip() or "Unknown",
                    "country": str(source.get("country") or "").strip() or "Global",
                    "path": raw_path,
                    "exists": bool(root.exists() and root.is_dir()),
                    "asset_count": len(files),
                    "note": str(source.get("note") or "").strip(),
                }
            )

            for file_path in files:
                assets.append(_asset_row(source, file_path))

        video_count = sum(1 for item in assets if item.get("video_path"))
        image_count = sum(1 for item in assets if item.get("image_path"))
        return {
            "report_date": report_date.isoformat(),
            "mode": "local_visual_asset_manifest",
            "passed": True,
            "source_file": str(input_path),
            "summary": {
                "configured_source_count": len(configured_sources),
                "existing_source_count": sum(1 for item in source_rows if item["exists"]),
                "missing_source_count": len(missing_sources),
                "asset_count": len(assets),
                "video_count": video_count,
                "image_count": image_count,
                "visual_asset_ready_count": len(assets),
            },
            "missing_sources": missing_sources,
            "sources": source_rows,
            "assets": assets,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Local Visual Asset Manifest | {payload['report_date']}",
            "",
            f"- Source file: {payload['source_file']}",
            f"- Configured sources: {summary['configured_source_count']}",
            f"- Existing sources: {summary['existing_source_count']}",
            f"- Missing sources: {summary['missing_source_count']}",
            f"- Total assets: {summary['asset_count']}",
            f"- Videos: {summary['video_count']}",
            f"- Images: {summary['image_count']}",
            "",
            "## Sources",
            "",
        ]
        if not payload["sources"]:
            lines.append("- None.")
        for item in payload["sources"]:
            lines.append(
                f"- {item['project'] or 'Unknown project'} | path={item['path']} | exists={item['exists']} | "
                f"assets={item['asset_count']} | channel={item['channel']} | country={item['country']}"
            )

        lines.extend(["", "## Sample Assets", ""])
        if not payload["assets"]:
            lines.append("- None.")
        for item in payload["assets"][:20]:
            asset_path = item.get("video_path") or item.get("image_path") or ""
            lines.append(
                f"- {item['creative_id']} | {item['project']} | {item['channel']} | "
                f"{item['video_structure']} | path={asset_path}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_sources(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        sources = payload.get("sources") or []
        if isinstance(sources, list):
            return [item for item in sources if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _asset_row(source: dict[str, Any], file_path: Path) -> dict[str, Any]:
    suffix = file_path.suffix.lower()
    is_video = suffix in VIDEO_EXTENSIONS
    project = str(source.get("project") or "").strip() or "Unknown"
    channel = str(source.get("channel") or "").strip() or "Unknown"
    country = str(source.get("country") or "").strip() or "Global"
    creative_id = str(source.get("asset_prefix") or "").strip() + file_path.stem if str(source.get("asset_prefix") or "").strip() else file_path.stem
    metadata = _extract_asset_metadata(file_path, is_video=is_video)
    return {
        "creative_id": creative_id,
        "project": project,
        "channel": channel,
        "country": country,
        "creative_name": file_path.name,
        "video_path": str(file_path) if is_video else "",
        "image_path": str(file_path) if not is_video else "",
        "asset_type": "video" if is_video else "image",
        "file_extension": suffix,
        "file_size_bytes": int(file_path.stat().st_size),
        "file_size_mb": round(float(file_path.stat().st_size) / (1024 * 1024), 4),
        "asset_width": int(metadata.get("asset_width") or 0),
        "asset_height": int(metadata.get("asset_height") or 0),
        "asset_orientation": str(metadata.get("asset_orientation") or "unknown"),
        "asset_aspect_ratio": str(metadata.get("asset_aspect_ratio") or "unknown"),
        "asset_duration_seconds": round(float(metadata.get("asset_duration_seconds") or 0.0), 4),
        "visual_asset_ready": True,
        "visual_evidence_level": "local_file",
        "label_source": "local_visual_asset_manifest",
        "label_confidence": 0.75,
        "hook_type": "unknown",
        "emotion": "unknown",
        "video_structure": "video" if is_video else "image",
    }


SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


def _extract_asset_metadata(file_path: Path, *, is_video: bool) -> dict[str, Any]:
    if is_video:
        capture = cv2.VideoCapture(str(file_path))
        if not capture.isOpened():
            return _asset_shape_payload(0, 0, 0.0)
        try:
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            duration_seconds = (frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
            return _asset_shape_payload(width, height, duration_seconds)
        finally:
            capture.release()
    try:
        with Image.open(file_path) as image:
            width, height = image.size
    except Exception:
        width, height = 0, 0
    return _asset_shape_payload(width, height, 0.0)


def _asset_shape_payload(width: int, height: int, duration_seconds: float) -> dict[str, Any]:
    orientation = "unknown"
    aspect_ratio = "unknown"
    if width > 0 and height > 0:
        if height > width:
            orientation = "portrait"
        elif width > height:
            orientation = "landscape"
        else:
            orientation = "square"
        ratio = width / height if height else 0.0
        if ratio >= 1.7:
            aspect_ratio = "16:9_like"
        elif ratio <= 0.62:
            aspect_ratio = "9:16_like"
        elif 0.9 <= ratio <= 1.1:
            aspect_ratio = "1:1_like"
        else:
            aspect_ratio = "custom"
    return {
        "asset_width": width,
        "asset_height": height,
        "asset_orientation": orientation,
        "asset_aspect_ratio": aspect_ratio,
        "asset_duration_seconds": duration_seconds,
    }
