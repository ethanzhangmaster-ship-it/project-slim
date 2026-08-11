"""E11.2 — Creative Mapping Loader。

从 creative_mapping_v2.json 批量迁移匹配记录到 E11 Asset Binding Layer。

流程：
  creative_mapping_v2.json
        │
        │ parse each record
        ▼
  CreativeAssetReference (list)
        │
        │ save via AssetBindingRepository
        ▼
  data/creatives/{creative_id}/assets.json

Usage:
    loader = CreativeMappingLoader()
    refs = loader.load("output/video_intelligence/p04/creative_mapping_v2.json")
    print(f"Loaded {len(refs)} references")

    repo = AssetBindingRepository("data/creatives")
    report = loader.migrate(mapping_path, repo)
    print(report["summary"])
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .asset_reference import (
    CreativeAssetReference,
    AssetSource,
    AssetType,
    MatchMethod,
)
from .asset_binding_repository import AssetBindingRepository


class CreativeMappingLoader:
    """从 creative_mapping_v2.json 加载并迁移资产绑定记录。

    识别两种匹配方法：
      - A-number:   ad_name "P4-IOS-T1-A536-0707" → A536 → Eagle v2601536
      - video_number: 视频编号匹配（视频2/视频3/视频4/视频5/视频6）
    """

    def __init__(self) -> None:
        self._loaded_count = 0
        self._errors: list[str] = []

    # ── Public API ───────────────────────────────────────

    def load(self, mapping_path: str) -> list[CreativeAssetReference]:
        """加载 creative_mapping_v2.json 并转换为 AssetReference 列表。

        Args:
            mapping_path: creative_mapping_v2.json 文件路径

        Returns:
            CreativeAssetReference 列表
        """
        self._errors = []

        if not os.path.exists(mapping_path):
            self._errors.append(f"File not found: {mapping_path}")
            return []

        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        refs: list[CreativeAssetReference] = []
        for record in data.get("match_records", []):
            try:
                ref = self._parse_record(record)
                refs.append(ref)
            except Exception as e:
                self._errors.append(
                    f"Parse error for {record.get('creative_id', 'unknown')}: {e}"
                )

        self._loaded_count = len(refs)
        return refs

    def migrate(
        self,
        mapping_path: str,
        repository: AssetBindingRepository,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """完整迁移流程：加载 → 转换 → 写入。

        Args:
            mapping_path: creative_mapping_v2.json 路径
            repository:  AssetBindingRepository 实例
            dry_run:     如果 True，只分析不写入

        Returns:
            {
                "summary": str,
                "total": int,
                "written": int,
                "skipped": int,
                "errors": int,
                "elapsed_seconds": float,
            }
        """
        started = datetime.now()

        refs = self.load(mapping_path)
        written = 0
        skipped = 0

        if not dry_run:
            for ref in refs:
                if repository.exists(ref.creative_id):
                    skipped += 1
                else:
                    repository.save(ref)
                    written += 1

        elapsed = (datetime.now() - started).total_seconds()

        summary_lines = [
            "=" * 60,
            "  Creative Mapping Migration Report",
            "=" * 60,
            "",
            f"  Source:    {mapping_path}",
            f"  Mode:      {'DRY RUN' if dry_run else 'WRITE'}",
            f"  Total:     {len(refs)} records",
            f"  Written:   {written} (new)",
            f"  Skipped:   {skipped} (already exists)",
            f"  Errors:    {len(self._errors)}",
            f"  Elapsed:   {elapsed:.1f}s",
            "",
        ]

        if self._errors:
            summary_lines.append("  Errors:")
            for err in self._errors[:10]:
                summary_lines.append(f"    - {err}")
            summary_lines.append("")

        summary_lines.append("=" * 60)

        return {
            "summary": "\n".join(summary_lines),
            "total": len(refs),
            "written": written,
            "skipped": skipped,
            "errors": len(self._errors),
            "error_details": self._errors,
            "elapsed_seconds": round(elapsed, 1),
        }

    # ── Internal ────────────────────────────────────────

    def _parse_record(self, record: dict[str, Any]) -> CreativeAssetReference:
        """解析单条 creative_mapping_v2 记录。"""
        creative_id = record.get("creative_id", "")
        creative_type = record.get("creative_type", "video")
        match_method_raw = record.get("match_method", "")

        asset_type = AssetType.VIDEO if creative_type == "video" else AssetType.IMAGE

        # 解析匹配方法
        if "A-number" in match_method_raw:
            match_method = MatchMethod.A_NUMBER
        elif "video_number" in match_method_raw:
            match_method = MatchMethod.VIDEO_NUMBER
        elif "filename" in match_method_raw.lower():
            match_method = MatchMethod.FILENAME
        elif "exact" in match_method_raw.lower():
            match_method = MatchMethod.EXACT_ID
        else:
            match_method = MatchMethod.UNKNOWN

        return CreativeAssetReference(
            creative_id=creative_id,
            asset_type=asset_type,
            source=AssetSource.EAGLE,
            eagle_filename=record.get("eagle_filename", ""),
            local_path=record.get("eagle_filepath", ""),
            match_method=match_method,
            confidence=float(record.get("confidence", 1.0)),
            spend=float(record.get("spend", 0.0)),
            revenue=float(record.get("revenue", 0.0)),
            roas=float(record.get("roas", 0.0)),
            impressions=float(record.get("impressions", 0.0)),
            clicks=float(record.get("clicks", 0.0)),
            installs=int(record.get("installs", 0)),
            ad_name=record.get("ad_name", ""),
            a_number=record.get("a_number", ""),
            eagle_v_number=record.get("eagle_v_number", ""),
        )

    @property
    def error_count(self) -> int:
        return len(self._errors)