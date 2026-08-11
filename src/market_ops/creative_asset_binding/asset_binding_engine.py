"""E11 Phase 3 — Asset Binding Engine。

编排完整的素材绑定流程：
  1. 加载 Eagle 索引
  2. 加载 CreativeEntity
  3. 视频匹配（VideoMatcher）
  4. 图片匹配（ImageMatcher）
  5. 更新 CreativeAsset 字段
  6. 回写 entity.json
  7. 生成绑定报告
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .eagle_indexer import EagleIndex, EagleIndexer
from .video_matcher import VideoMatcher, VideoMatchResult
from .image_matcher import ImageMatcher, ImageMatchResult, LovartAsset
from .models import AssetBindingResult, AssetSourceType, BindingMethod

if TYPE_CHECKING:
    from market_ops.creative_repository import CreativeEntity
    from market_ops.facebook_ingestion.storage import CreativeStorage


@dataclass
class AssetBindingReport:
    """素材绑定报告。"""

    total_entities: int = 0
    total_matched: int = 0
    total_missing: int = 0
    video_total: int = 0
    video_matched: int = 0
    video_match_rate: float = 0.0
    image_total: int = 0
    image_matched: int = 0
    image_match_rate: float = 0.0
    by_method: dict[str, int] = field(default_factory=dict)
    results: list[AssetBindingResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def overall_match_rate(self) -> float:
        if self.total_entities == 0:
            return 0.0
        return round(self.total_matched / self.total_entities, 4)

    def to_summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "  Creative Asset Binding Report",
            "=" * 60,
            "",
            f"  Total Creative Entities: {self.total_entities}",
            f"  Matched: {self.total_matched}",
            f"  Missing: {self.total_missing}",
            f"  Overall Match Rate: {self.overall_match_rate:.1%}",
            "",
            "  --- By Type ---",
            f"  Video: {self.video_matched}/{self.video_total} ({self.video_match_rate:.1%})",
            f"  Image: {self.image_matched}/{self.image_total} ({self.image_match_rate:.1%})",
            "",
            "  --- By Method ---",
        ]

        for method, count in sorted(self.by_method.items()):
            lines.append(f"  {method}: {count}")

        if self.errors:
            lines.append(f"\n  Errors: {len(self.errors)}")
            for err in self.errors[:5]:
                lines.append(f"    - {err}")

        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "total_matched": self.total_matched,
            "total_missing": self.total_missing,
            "overall_match_rate": self.overall_match_rate,
            "video_total": self.video_total,
            "video_matched": self.video_matched,
            "video_match_rate": self.video_match_rate,
            "image_total": self.image_total,
            "image_matched": self.image_matched,
            "image_match_rate": self.image_match_rate,
            "by_method": self.by_method,
            "results": [r.to_dict() for r in self.results],
            "errors": self.errors,
        }


class AssetBindingEngine:
    """素材绑定引擎。

    编排完整绑定流程：Eagle 索引 → 视频匹配 → 图片匹配 → 更新 CreativeEntity。

    Usage:
        engine = AssetBindingEngine(
            eagle_root="D:/eagle",
            creative_storage=storage,
        )
        report = engine.bind_all()
        print(report.to_summary())
    """

    def __init__(
        self,
        eagle_root: str = "",
        creative_storage: CreativeStorage | None = None,
        lovart_assets: list[LovartAsset] | None = None,
    ) -> None:
        self._eagle_root = eagle_root
        self._creative_storage = creative_storage
        self._lovart_assets = lovart_assets or []

        # 延迟初始化
        self._eagle_index: EagleIndex | None = None
        self._video_matcher: VideoMatcher | None = None
        self._image_matcher: ImageMatcher | None = None

    # ── Public API ───────────────────────────────────────

    def bind_all(self) -> AssetBindingReport:
        """执行完整绑定流程。

        Returns:
            AssetBindingReport
        """
        self._ensure_initialized()

        report = AssetBindingReport()
        errors: list[str] = []

        # 1. 加载 CreativeEntity
        entities = self._load_entities()
        if not entities:
            report.errors.append("No CreativeEntities loaded")
            return report

        report.total_entities = len(entities)

        # 2. 分类：视频 vs 图片
        videos = [e for e in entities if e.is_video]
        images = [e for e in entities if e.is_image]

        report.video_total = len(videos)
        report.image_total = len(images)

        # 3. 视频匹配
        for entity in videos:
            try:
                result = self._video_matcher.match(
                    entity.creative_asset_id,
                    entity.identity.name,
                )
                self._apply_video_binding(entity, result)
                if result.best_result:
                    report.results.append(result.best_result)
                    method = result.best_result.method.value
                    report.by_method[method] = report.by_method.get(method, 0) + 1
            except Exception as e:
                errors.append(f"Video binding failed for {entity.creative_asset_id}: {e}")

        # 4. 图片匹配
        for entity in images:
            try:
                result = self._image_matcher.match(
                    entity.creative_asset_id,
                    entity.identity.name,
                    entity.sources.lovart_id,
                )
                self._apply_image_binding(entity, result)
                if result.best_result:
                    report.results.append(result.best_result)
                    method = result.best_result.method.value
                    report.by_method[method] = report.by_method.get(method, 0) + 1
            except Exception as e:
                errors.append(f"Image binding failed for {entity.creative_asset_id}: {e}")

        # 5. 统计
        report.total_matched = len(report.results)
        report.total_missing = report.total_entities - report.total_matched
        report.video_matched = sum(
            1 for r in report.results if r.source == AssetSourceType.EAGLE
        )
        report.image_matched = sum(
            1 for r in report.results if r.source == AssetSourceType.LOVART
        )
        report.video_match_rate = (
            round(report.video_matched / report.video_total, 4)
            if report.video_total > 0 else 0.0
        )
        report.image_match_rate = (
            round(report.image_matched / report.image_total, 4)
            if report.image_total > 0 else 0.0
        )
        report.errors = errors

        # 6. 回写 entity.json
        if self._creative_storage:
            for entity in entities:
                try:
                    if entity.asset.has_eagle or entity.asset.has_lovart:
                        self._creative_storage.save_existing_entity(entity)
                except Exception as e:
                    errors.append(f"Save failed for {entity.creative_asset_id}: {e}")

        return report

    # ── Internal ────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        if self._eagle_index is None:
            indexer = EagleIndexer(self._eagle_root)
            self._eagle_index = indexer.build_index()
            self._video_matcher = VideoMatcher(self._eagle_index)

        if self._image_matcher is None:
            self._image_matcher = ImageMatcher(self._lovart_assets)

    def _load_entities(self) -> list[CreativeEntity]:
        if self._creative_storage:
            return self._creative_storage.list_all_creative_entities()
        return []

    def _apply_video_binding(
        self,
        entity: CreativeEntity,
        result: VideoMatchResult,
    ) -> None:
        """将视频匹配结果应用到 CreativeEntity。"""
        if result.best_result and result.best_result.matched:
            entity.asset.eagle_path = result.best_result.asset_path
            entity.asset.video_path = result.best_result.asset_path
            entity.asset.source_type = AssetSourceType.EAGLE.value
            entity.asset.matched_confidence = result.best_result.confidence
            entity.sources.eagle_path = result.best_result.asset_path

    def _apply_image_binding(
        self,
        entity: CreativeEntity,
        result: ImageMatchResult,
    ) -> None:
        """将图片匹配结果应用到 CreativeEntity。"""
        if result.best_result and result.best_result.matched:
            entity.asset.image_path = result.best_result.asset_path
            entity.asset.source_type = AssetSourceType.LOVART.value
            entity.asset.matched_confidence = result.best_result.confidence
            if result.lovart_asset:
                entity.asset.lovart_generation_id = result.lovart_asset.generation_id
                entity.sources.lovart_id = result.lovart_asset.generation_id

    def __repr__(self) -> str:
        return f"AssetBindingEngine(eagle={self._eagle_root!r})"