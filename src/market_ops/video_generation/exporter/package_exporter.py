"""Package Exporter - 交付包导出器"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class DeliveryManifest:
    """交付清单"""
    variant_id: str
    blueprint_files: List[str] = field(default_factory=list)
    prompt_files: List[str] = field(default_factory=list)
    video_files: List[str] = field(default_factory=list)
    review_files: List[str] = field(default_factory=list)
    report_files: List[str] = field(default_factory=list)
    log_files: List[str] = field(default_factory=list)


class PackageExporter:
    """交付包导出器"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def export(self, variant_id: str, blueprint_dir: str, video_generation_dir: str) -> DeliveryManifest:
        """导出完整交付包"""
        manifest = DeliveryManifest(variant_id=variant_id)

        delivery_root = self.output_dir / variant_id
        delivery_root.mkdir(parents=True, exist_ok=True)

        subdirs = ["blueprint", "prompts", "videos", "review", "reports", "logs"]
        for subdir in subdirs:
            (delivery_root / subdir).mkdir(exist_ok=True)

        blueprint_path = Path(blueprint_dir)
        video_gen_path = Path(video_generation_dir)

        blueprint_files = [
            "blueprint.json",
            "shot_list.json",
            "camera_spec.json",
            "asset_spec.json",
            "editing_spec.json",
            "subtitle_spec.json",
            "music_spec.json",
            "prompt_package.json",
            "creative_review.json",
            "quality_report.json",
            "creative_blueprint.md",
        ]
        for fname in blueprint_files:
            src = blueprint_path / fname
            dst = delivery_root / "blueprint" / fname
            if src.exists():
                shutil.copy2(src, dst)
                manifest.blueprint_files.append(f"blueprint/{fname}")

        prompt_files = [
            "master_prompt.json",
            "platform_prompt.json",
        ]
        for fname in prompt_files:
            src = video_gen_path / fname
            dst = delivery_root / "prompts" / fname
            if src.exists():
                shutil.copy2(src, dst)
                manifest.prompt_files.append(f"prompts/{fname}")

        for src in video_gen_path.glob("*.mp4"):
            dst = delivery_root / "videos" / src.name
            shutil.copy2(src, dst)
            manifest.video_files.append(f"videos/{src.name}")

        review_files = [
            "review.json",
            "consistency_report.json",
        ]
        for fname in review_files:
            src = video_gen_path / fname
            dst = delivery_root / "review" / fname
            if src.exists():
                shutil.copy2(src, dst)
                manifest.review_files.append(f"review/{fname}")

        report_files = [
            "cost_report.json",
        ]
        for fname in report_files:
            src = video_gen_path / fname
            dst = delivery_root / "reports" / fname
            if src.exists():
                shutil.copy2(src, dst)
                manifest.report_files.append(f"reports/{fname}")

        log_files = [
            "generation_log.json",
        ]
        for fname in log_files:
            src = video_gen_path / fname
            dst = delivery_root / "logs" / fname
            if src.exists():
                shutil.copy2(src, dst)
                manifest.log_files.append(f"logs/{fname}")

        self._save_manifest(manifest, delivery_root)

        return manifest

    def _save_manifest(self, manifest: DeliveryManifest, delivery_root: Path) -> None:
        """保存交付清单"""
        data = {
            "variant_id": manifest.variant_id,
            "blueprint_files": manifest.blueprint_files,
            "prompt_files": manifest.prompt_files,
            "video_files": manifest.video_files,
            "review_files": manifest.review_files,
            "report_files": manifest.report_files,
            "log_files": manifest.log_files,
            "total_files": len(manifest.blueprint_files) + len(manifest.prompt_files) +
                          len(manifest.video_files) + len(manifest.review_files) +
                          len(manifest.report_files) + len(manifest.log_files),
        }
        with open(delivery_root / "delivery_manifest.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)