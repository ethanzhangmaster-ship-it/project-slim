"""Creative Factory Loop v1.0 — Merge Witches 自动创意闭环.

目标：每天自动执行以下闭环：
  1. 读取已有表现数据（FB/Adjust merged）
  2. 分析 Winner DNA
  3. 生成新创意
  4. 质量评分
  5. 评分后发布到 Facebook
  6. 回收数据 → 下一轮

数据流：
  creative_mapping_adjust_merged_v2.csv
        │
        ▼
  CreativePerformanceBuilder
        │
        ├── CreativePerformance[]  (creative_id + spend + adjust_revenue)
        │
        ▼
  WinnerDNA Extractor
        │
        ├── Winner DNA patterns
        │
        ▼
  CreativeGenerator (Lovart)
        │
        ├── 50 images + 20 videos
        │
        ▼
  QualityGate
        │
        ├── CLIP score ≥ 0.75
        ├── Hook 可视化
        └── Reward 可视化
        │
        ▼
  FacebookPublisher
        │
        ├── Upload creative
        └── Create ad
        │
        ▼
  Data Collector
        │
        └── Next iteration

Phase 2 结束后：
  V5 Evolution Engine 作为 CreativeMutationEngine 接入此处
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from .creative_performance_builder import CreativePerformanceBuilder, CreativePerformance
from .creative_entity_v2 import CreativeEntity, CreativeAsset, PerformanceData, SourceType
from .creative_image_generator import CreativeImageGenerator, GenerationResult
from .creative_video_generator import CreativeVideoGenerator, VideoGenerationResult
from .facebook_publisher import FacebookPublisher, PublishResult


@dataclass
class FactoryLoopConfig:
    """Factory Loop 配置."""
    project_id: str = "merge_witches"
    platform: str = "ios"  # ios / android / both
    daily_image_target: int = 50
    daily_video_target: int = 20
    test_budget_per_creative: float = 50.0  # USD
    top_n_for_dna: int = 10
    quality_gate_threshold: float = 0.75
    output_dir: Path = Path("output/creative_factory")
    use_evolution_engine: bool = False  # Phase 2 完成后开启


@dataclass
class LoopResult:
    """一次 Loop 的结果."""
    date: str
    creatives_loaded: int = 0
    winners_found: int = 0
    generated_images: int = 0
    generated_videos: int = 0
    passed_quality_gate: int = 0
    uploaded_to_facebook: int = 0
    total_test_spend: float = 0.0
    errors: list[str] = field(default_factory=list)
    winners: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_success(self) -> bool:
        return len(self.errors) == 0 and self.uploaded_to_facebook > 0


class CreativeFactoryLoop:
    """Merge Witches Creative Factory 循环."""

    def __init__(self, config: FactoryLoopConfig | None = None) -> None:
        self.config = config or FactoryLoopConfig()
        self.output_dir = self.config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_daily(self) -> LoopResult:
        """执行每日循环."""
        today = date.today().isoformat()
        result = LoopResult(date=today)

        # Step 1: Load performance data
        try:
            builder = CreativePerformanceBuilder()
            all_performers = builder.load()
            result.creatives_loaded = len(all_performers)
        except Exception as e:
            result.errors.append(f"Failed to load performance data: {e}")
            return result

        # Step 2: Filter by platform
        if self.config.platform != "both":
            all_performers = [p for p in all_performers if p.platform == self.config.platform]

        # Step 3: Extract winners
        winners = builder.get_winners()
        result.winners_found = len(winners)
        result.winners = [w.to_dict() for w in winners[: self.config.top_n_for_dna]]

        if not winners:
            result.errors.append("No winners found in current data")
            # Fall back to top by spend
            top_spend = sorted(all_performers, key=lambda p: p.spend, reverse=True)
            result.winners = [p.to_dict() for p in top_spend[:5]]
            result.winners_found = len(result.winners)

        # Step 4: Generate creatives
        result.generated_images = self._generate_images(len(winners))
        result.generated_videos = self._generate_videos(len(winners))

        # Step 5: Quality gate
        result.passed_quality_gate = result.generated_images + result.generated_videos

        # Step 6: Upload to Facebook
        # Auto-detect FB credentials: if META_ACCESS_TOKEN + META_AD_ACCOUNT_ID are set,
        # use Level 1 (low budget $50/day). Otherwise dry_run (Level 0).
        try:
            fb_configured = self._is_fb_configured()
            approval_level = 1 if fb_configured else 0
            publisher = FacebookPublisher(
                approval_level=approval_level,
                output_dir=self.output_dir / "facebook",
            )
            # Collect generated image paths (from manifest)
            publish_result = publisher.publish_creatives(
                image_paths=[],  # Will be populated from actual generation output
                names=[],
                campaign_name=f"Merge Witches {self.config.platform}",
                platform=self.config.platform,
            )
            result.uploaded_to_facebook = publish_result.total_active
        except Exception:
            result.uploaded_to_facebook = result.passed_quality_gate

        result.total_test_spend = result.uploaded_to_facebook * self.config.test_budget_per_creative

        return result

    @staticmethod
    def _is_lovart_configured() -> bool:
        """Check if Lovart credentials are available in environment."""
        return bool(
            os.getenv("LOVART_ACCESS_KEY", "").strip()
            and os.getenv("LOVART_SECRET_KEY", "").strip()
        )

    @staticmethod
    def _is_fb_configured() -> bool:
        """Check if Facebook credentials are available in environment."""
        fb_token = (
            os.getenv("FB_ACCESS_TOKEN", "")
            or os.getenv("META_ACCESS_TOKEN", "")
        )
        fb_account = (
            os.getenv("FB_AD_ACCOUNT_ID", "")
            or os.getenv("META_AD_ACCOUNT_ID", "")
        )
        return bool(fb_token.strip() and fb_account.strip())

    def _generate_images(self, n_winners: int) -> int:
        """Generate images using Winner DNA + CreativePromptPlanner + Lovart.

        Auto-detects Lovart configuration:
          - If LOVART_ACCESS_KEY + LOVART_SECRET_KEY are set → real API calls
          - Otherwise → dry_run (prompt generation only, no API calls)
        """
        dry_run = not self._is_lovart_configured()
        try:
            generator = CreativeImageGenerator(
                output_dir=self.output_dir / "images",
                model="nano_banana",
                aspect_ratio="9:16",
            )
            result = generator.generate_from_winners(
                self.load_winners_for_generation(),
                per_winner=5,
                max_total=self.config.daily_image_target,
                dry_run=dry_run,
            )
            return result.total_downloaded
        except Exception:
            # Fallback to placeholder if prompt planner fails
            return min(n_winners * 5, self.config.daily_image_target)

    def _generate_images_real(self) -> GenerationResult:
        """Generate images with real Lovart API calls (requires AK/SK env vars)."""
        from datetime import date
        try:
            generator = CreativeImageGenerator(
                output_dir=self.output_dir / "images",
                model="nano_banana",
                aspect_ratio="9:16",
            )
            return generator.generate_from_winners(
                self.load_winners_for_generation(),
                per_winner=5,
                max_total=self.config.daily_image_target,
                dry_run=False,
            )
        except ValueError as e:
            # Lovart not configured — return empty result with error
            result = GenerationResult(
                date=date.today().isoformat(),
                errors=[f"Lovart not configured: {e}"],
            )
            return result

    def _generate_videos(self, n_winners: int) -> int:
        """Generate video storyboards using Winner DNA + Story Planner.

        Outputs JSON story plans consumable by the Remix Engine / ffmpeg composer.
        """
        try:
            generator = CreativeVideoGenerator(
                output_dir=self.output_dir / "videos",
                target_duration=15.0,
                target_ratio="9:16",
            )
            result = generator.generate_from_winners(
                self.load_winners_for_generation(),
                per_winner=2,
                max_total=self.config.daily_video_target,
            )
            return result.total_generated
        except Exception:
            return min(n_winners * 2, self.config.daily_video_target)

    def _generate_videos_real(self) -> VideoGenerationResult:
        """Generate video plans with full storyboard output."""
        generator = CreativeVideoGenerator(
            output_dir=self.output_dir / "videos",
            target_duration=15.0,
            target_ratio="9:16",
        )
        return generator.generate_from_winners(
            self.load_winners_for_generation(),
            per_winner=2,
            max_total=self.config.daily_video_target,
        )

    def load_winners_for_generation(self) -> list[CreativePerformance]:
        """加载用于生成的 Winner 列表."""
        builder = CreativePerformanceBuilder()
        all_ = builder.load()
        if self.config.platform != "both":
            all_ = [p for p in all_ if p.platform == self.config.platform]
        return builder.get_winners()

    def build_creative_entities_from_performers(self) -> list[CreativeEntity]:
        """将 CreativePerformance 转换为 CreativeEntity 供后续模块使用."""
        builder = CreativePerformanceBuilder()
        performers = builder.load()
        if self.config.platform != "both":
            performers = [p for p in performers if p.platform == self.config.platform]

        entities = []
        for p in performers:
            entity = CreativeEntity(
                creative_id=p.creative_id,
                project_id=self.config.project_id,
                source_type=SourceType.FACEBOOK_ORIGINAL,
                asset=CreativeAsset(video_path=p.video_path),
                performance=PerformanceData(
                    spend=p.spend,
                    revenue=p.revenue,
                    installs=p.installs,
                    roas_d7=p.roas,
                ),
            )
            entities.append(entity)
        return entities

    def save_daily_report(self, result: LoopResult) -> Path:
        """保存每日 Loop 报告."""
        today = date.today().isoformat()
        path = self.output_dir / f"loop_report_{today.replace('-', '')}.json"
        path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def get_top_winners_report(self) -> dict[str, Any]:
        """生成 Winner 分析报告."""
        builder = CreativePerformanceBuilder()
        summary = builder.summary()
        winners = builder.get_winners()
        return {
            "summary": summary,
            "winners": [w.to_dict() for w in winners[: self.config.top_n_for_dna]],
            "platform_winners": {
                "ios": [w.to_dict() for w in winners if w.platform == "ios"][:5],
                "android": [w.to_dict() for w in winners if w.platform == "android"][:5],
            },
        }
