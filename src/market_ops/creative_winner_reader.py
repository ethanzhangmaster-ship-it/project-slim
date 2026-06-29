"""Read real winner creatives from a local folder and extract their visual DNA.

This is the "look at what actually won on Facebook" path that was missing from
the original closed loop. The previous CreativeDNA path could only guess labels
from file names via keyword rules (see creative_dna._infer_labels); this module
instead asks Lovart's multimodal model to actually look at each winner image and
describe its visual composition.

Scope (per project decision 2026-06-22):
- images only for now; video assets in the source folder are skipped
- one source folder, configured via input/local_visual_asset_sources.json
- results cached as winner_visual_dna.json so repeated runs don't re-spend credits
- does NOT touch the weekly report flow; called only by the creative closed loop

Typical use:

    reader = WinnerVisualDnaReader(settings)
    result = reader.read(limit=1)        # probe one image
    result = reader.read()               # read all images in the folder
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.config import Settings


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# Fields we expect Lovart's describe_image to return. Used to validate that a
# cached entry is structurally complete before reusing it.
EXPECTED_DNA_FIELDS = (
    "subject",
    "composition",
    "palette",
    "hook_type",
    "standout_features",
    "overall_summary",
)


@dataclass(slots=True)
class WinnerReadResult:
    """Outcome of a read() call."""

    cache_path: Path
    items: list[dict[str, Any]] = field(default_factory=list)
    newly_described: int = 0
    cached: int = 0
    skipped_videos: int = 0
    errors: list[str] = field(default_factory=list)
    source_path: str = ""


class WinnerVisualDnaReader:
    """Reads real winner images and extracts visual DNA via Lovart.

    Construction does no I/O. Call read() to do the work.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache_path = settings.output_dir / "creative_loop" / "winner_visual_dna.json"

    # ----- public API -----

    def read(
        self,
        *,
        limit: int | None = None,
        force_refresh: bool = False,
        lovar_client: Any = None,
    ) -> WinnerReadResult:
        """Read winner images, describe any not yet cached, return all DNA items.

        Args:
            limit: if set, describe at most this many NEW images (cache reuse is
                not capped). Useful for the "probe 1 image" validation step.
            force_refresh: if True, ignore cache and re-describe every image.
            lovar_client: inject a LovartClient (mainly for testing). If None,
                one is built lazily only when there's work to do.
        """
        source = self._source_folder()
        result = WinnerReadResult(cache_path=self._cache_path, source_path=str(source))

        if not source.exists() or not source.is_dir():
            result.errors.append(f"Source folder does not exist: {source}")
            return result

        cache = {} if force_refresh else self._load_cache()
        files = self._list_image_files(source)

        described_this_run = 0
        for file_path in files:
            entry = cache.get(self._cache_key(file_path))
            if entry and self._entry_is_complete(entry):
                result.items.append(entry)
                result.cached += 1
                continue

            if limit is not None and described_this_run >= limit:
                # Still keep partial cache entries visible to the caller.
                continue

            client = lovar_client or self._build_lovart()
            if client is None:
                result.errors.append(
                    "Lovart not configured (LOVART_ACCESS_KEY / LOVART_SECRET_KEY missing); "
                    "cannot describe new images."
                )
                break

            try:
                dna = client.describe_image(file_path, project=self._source_project())
            except Exception as exc:  # network/SSL/auth errors should not kill the whole run
                result.errors.append(f"{file_path.name}: {exc}")
                continue

            if "error" in dna:
                result.errors.append(f"{file_path.name}: {dna['error']}")
                continue

            entry = self._build_entry(file_path, dna)
            cache[self._cache_key(file_path)] = entry
            result.items.append(entry)
            result.newly_described += 1
            described_this_run += 1
            self._save_cache(cache)

        result.skipped_videos = self._count_skipped_videos(source)
        if cache:
            self._save_cache(cache)
        return result

    # ----- source resolution -----

    def _source_folder(self) -> Path:
        """Resolve the winner folder from input/local_visual_asset_sources.json.

        Returns the first source's `path`. If unresolvable, returns a Path that
        .exists() will report as False so the caller can surface a clean error.
        """
        sources_path = self._settings.output_dir.parent / "input" / "local_visual_asset_sources.json"
        try:
            payload = json.loads(sources_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return Path("__unresolvable__")
        sources = payload.get("sources") if isinstance(payload, dict) else payload
        if not isinstance(sources, list) or not sources:
            return Path("__unresolvable__")
        first = sources[0] if isinstance(sources[0], dict) else {}
        return Path(str(first.get("path") or "").strip())

    def _source_project(self) -> str:
        sources_path = self._settings.output_dir.parent / "input" / "local_visual_asset_sources.json"
        try:
            payload = json.loads(sources_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return ""
        sources = payload.get("sources") if isinstance(payload, dict) else payload
        if not isinstance(sources, list) or not sources:
            return ""
        first = sources[0] if isinstance(sources[0], dict) else {}
        return str(first.get("project") or "").strip()

    # ----- file listing -----

    @staticmethod
    def _list_image_files(folder: Path) -> list[Path]:
        return [
            p
            for p in sorted(folder.iterdir())
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ]

    @staticmethod
    def _count_skipped_videos(folder: Path) -> int:
        video_exts = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
        return sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() in video_exts)

    # ----- cache -----

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        if not self._cache_path.exists():
            return {}
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        items = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return {}
        return {
            str(item.get("cache_key") or ""): item
            for item in items
            if isinstance(item, dict) and item.get("cache_key")
        }

    def _save_cache(self, cache: dict[str, dict[str, Any]]) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_path": str(self._source_folder()),
            "item_count": len(cache),
            "items": list(cache.values()),
        }
        self._cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _cache_key(file_path: Path) -> str:
        """Stable key from path + size + mtime so edited/replaced images re-describe."""
        stat = file_path.stat()
        raw = f"{file_path.name}|{stat.st_size}|{int(stat.st_mtime)}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _entry_is_complete(entry: dict[str, Any]) -> bool:
        dna = entry.get("visual_dna") or {}
        return all(field in dna and dna[field] not in ("", None) for field in EXPECTED_DNA_FIELDS)

    # ----- entry building -----

    @staticmethod
    def _build_entry(file_path: Path, dna: dict[str, Any]) -> dict[str, Any]:
        return {
            "cache_key": WinnerVisualDnaReader._cache_key(file_path),
            "creative_id": file_path.stem,
            "creative_name": file_path.name,
            "image_path": str(file_path),
            "cdn_url": dna.get("_cdn_url", ""),
            "described_at": datetime.now().isoformat(timespec="seconds"),
            "visual_dna": {k: v for k, v in dna.items() if not k.startswith("_")},
        }

    # ----- lazy Lovart construction -----

    def _build_lovart(self) -> Any:
        try:
            from market_ops.clients.lovart import LovartClient
        except ImportError:
            return None
        try:
            return LovartClient()
        except ValueError:
            # AK/SK missing
            return None

    # ----- text fallback (降级模式) -----

    def read_textual(
        self, creative_rows: list, *, limit: int | None = None,
    ) -> WinnerReadResult:
        """文本降级模式：无本地图片时从 creative_name / creative_library 文本提取模式。

        不调用 Lovart 多模态模型，零 API 费用。基于 creative_dna._infer_labels 的
        关键词规则从 creative_name、campaign、adgroup 等文本字段中提取创意模式。

        Args:
            creative_rows: CreativeAssetRow 列表（来自 Adjust 或 creative_library）
            limit: 最多分析多少个 creative

        Returns:
            WinnerReadResult，items 中每个条目包含 textual_dna 字段而非 visual_dna
        """
        from market_ops.creative_dna import _infer_labels, _DNA_ONLY_FIELDS

        result = WinnerReadResult(
            cache_path=self._cache_path,
            source_path="text_fallback (creative_name + creative_library)",
        )

        if not creative_rows:
            result.errors.append("No creative rows provided for text fallback analysis.")
            return result

        rows = creative_rows[:limit] if limit else creative_rows

        for row in rows:
            text = " ".join(
                str(value or "")
                for value in (
                    getattr(row, "creative_name", ""),
                    getattr(row, "hook_type", ""),
                    getattr(row, "campaign", ""),
                    getattr(row, "adgroup", ""),
                    getattr(row, "ad_name", ""),
                    getattr(row, "source_name", ""),
                )
            )
            labels, hits = _infer_labels(text)

            # Only include those with at least 1 pattern hit
            if hits == 0:
                continue

            creative_id = str(getattr(row, "asset_id", "") or getattr(row, "creative_name", "") or "").strip()
            spend = float(getattr(row, "spend", 0) or 0)
            revenue = float(getattr(row, "revenue_value", 0) or 0)
            roi = revenue / spend if spend else 0.0

            result.items.append({
                "creative_id": creative_id,
                "creative_name": str(getattr(row, "creative_name", "")),
                "source": "text_fallback",
                "confidence": min(0.80, 0.30 + hits * 0.12),
                "pattern_hits": hits,
                "spend": spend,
                "roi": roi,
                "textual_dna": {
                    field: labels.get(field, "unknown") for field in _DNA_ONLY_FIELDS
                },
            })

        if not result.items:
            result.errors.append("No pattern hits from text fallback; creative names may be too generic.")

        return result
