"""E11.3.5 — Visual Pattern Miner。

基于规则从 VisionFeatureRecord + VisionFrameFeature[] 中挖掘视觉模式。

第一版：纯规则引擎，不使用 LLM/CLIP。
"""

from __future__ import annotations

import statistics
from typing import Any

from ..feature_store.models import VisionFeatureRecord, VisionFrameFeature
from .models import VisualPattern


class PatternMiner:
    """视觉模式挖掘器。

    基于结构特征的规则引擎，从视频级和帧级特征中检测视觉模式。

    Pattern 规则:
      - high_contrast_opening:  avg_contrast > 0.5
      - bright_visual:         avg_brightness > 0.6
      - fast_visual_change:    edge_density std > 0.1
      - clean_composition:     color_entropy < 6.0 AND edge_density 0.15-0.45
      - high_saturation:       avg_saturation > 0.5
      - rising_brightness:     首帧亮度 < 末帧亮度
      - dark_opening:          avg_brightness < 0.3
      - complex_scene:         edge_density > 0.4
    """

    # ── Thresholds ────────────────────────────────────────

    HIGH_CONTRAST_THRESHOLD = 0.5
    BRIGHT_THRESHOLD = 0.6
    DARK_THRESHOLD = 0.3
    HIGH_SATURATION_THRESHOLD = 0.5
    LOW_ENTROPY_THRESHOLD = 6.0
    EDGE_LOW = 0.15
    EDGE_HIGH = 0.45
    COMPLEX_EDGE_THRESHOLD = 0.4
    EDGE_STD_THRESHOLD = 0.1

    def mine(
        self,
        record: VisionFeatureRecord,
        frames: list[VisionFrameFeature] | None = None,
    ) -> list[VisualPattern]:
        """从单个素材中挖掘视觉模式。

        Args:
            record: 视频级特征记录
            frames: 帧级特征（可选，用于帧间分析）

        Returns:
            VisualPattern 列表
        """
        patterns: list[VisualPattern] = []

        # ── Opening patterns ──────────────────────────────
        self._check_high_contrast(patterns, record)
        self._check_bright_visual(patterns, record)
        self._check_dark_opening(patterns, record)

        # ── Composition patterns ──────────────────────────
        self._check_clean_composition(patterns, record)
        self._check_complex_scene(patterns, record)

        # ── Color patterns ────────────────────────────────
        self._check_high_saturation(patterns, record)

        # ── Motion patterns (requires frames) ─────────────
        if frames and len(frames) >= 2:
            self._check_fast_visual_change(patterns, record, frames)
            self._check_rising_brightness(patterns, frames)

        return patterns

    def mine_batch(
        self,
        records: list[VisionFeatureRecord],
        frames_map: dict[str, list[VisionFrameFeature]] | None = None,
    ) -> dict[str, list[VisualPattern]]:
        """批量挖掘模式。

        Args:
            records:    视频级特征记录列表
            frames_map: feature_id → 帧特征列表（可选）

        Returns:
            creative_asset_id → VisualPattern 列表
        """
        result: dict[str, list[VisualPattern]] = {}
        for record in records:
            frames = None
            if frames_map and record.feature_id in frames_map:
                frames = frames_map[record.feature_id]
            result[record.creative_asset_id] = self.mine(record, frames)
        return result

    def aggregate_patterns(
        self,
        all_patterns: list[VisualPattern],
        min_confidence: float = 0.5,
    ) -> list[VisualPattern]:
        """聚合多个素材的模式，按名称合并。

        Args:
            all_patterns:  所有检测到的模式
            min_confidence: 最低置信度阈值

        Returns:
            聚合后的模式列表（按置信度降序）
        """
        grouped: dict[str, list[VisualPattern]] = {}
        for p in all_patterns:
            if p.confidence < min_confidence:
                continue
            grouped.setdefault(p.name, []).append(p)

        aggregated: list[VisualPattern] = []
        for name, group in grouped.items():
            if not group:
                continue
            evidence = len(group)
            avg_conf = sum(p.confidence for p in group) / evidence
            all_assets = []
            for p in group:
                all_assets.extend(p.source_assets)

            aggregated.append(VisualPattern(
                name=name,
                description=group[0].description,
                confidence=round(avg_conf, 3),
                category=group[0].category,
                evidence_count=evidence,
                source_assets=all_assets,
                feature_values=group[0].feature_values,
            ))

        aggregated.sort(key=lambda p: p.confidence, reverse=True)
        return aggregated

    # ── Pattern Rules ────────────────────────────────────

    def _check_high_contrast(
        self, patterns: list[VisualPattern], record: VisionFeatureRecord
    ) -> None:
        if record.avg_contrast > self.HIGH_CONTRAST_THRESHOLD:
            patterns.append(VisualPattern(
                name="high_contrast_opening",
                description="High contrast visual opening",
                confidence=round(min(record.avg_contrast / 0.8, 1.0), 3),
                category="opening",
                evidence_count=1,
                source_assets=[record.creative_asset_id],
                feature_values={"avg_contrast": record.avg_contrast},
            ))

    def _check_bright_visual(
        self, patterns: list[VisualPattern], record: VisionFeatureRecord
    ) -> None:
        if record.avg_brightness > self.BRIGHT_THRESHOLD:
            patterns.append(VisualPattern(
                name="bright_visual",
                description="Bright visual style with high luminance",
                confidence=round(min(record.avg_brightness / 0.9, 1.0), 3),
                category="color",
                evidence_count=1,
                source_assets=[record.creative_asset_id],
                feature_values={"avg_brightness": record.avg_brightness},
            ))

    def _check_dark_opening(
        self, patterns: list[VisualPattern], record: VisionFeatureRecord
    ) -> None:
        if record.avg_brightness < self.DARK_THRESHOLD:
            patterns.append(VisualPattern(
                name="dark_visual",
                description="Dark visual style with low luminance",
                confidence=round(1.0 - record.avg_brightness / self.DARK_THRESHOLD, 3),
                category="color",
                evidence_count=1,
                source_assets=[record.creative_asset_id],
                feature_values={"avg_brightness": record.avg_brightness},
            ))

    def _check_clean_composition(
        self, patterns: list[VisualPattern], record: VisionFeatureRecord
    ) -> None:
        if (
            record.avg_color_entropy < self.LOW_ENTROPY_THRESHOLD
            and self.EDGE_LOW <= record.avg_edge_density <= self.EDGE_HIGH
        ):
            conf = (
                (1.0 - record.avg_color_entropy / self.LOW_ENTROPY_THRESHOLD) * 0.5
                + 0.5
            )
            patterns.append(VisualPattern(
                name="clean_composition",
                description="Clean composition with moderate detail",
                confidence=round(min(conf, 1.0), 3),
                category="composition",
                evidence_count=1,
                source_assets=[record.creative_asset_id],
                feature_values={
                    "avg_color_entropy": record.avg_color_entropy,
                    "avg_edge_density": record.avg_edge_density,
                },
            ))

    def _check_complex_scene(
        self, patterns: list[VisualPattern], record: VisionFeatureRecord
    ) -> None:
        if record.avg_edge_density > self.COMPLEX_EDGE_THRESHOLD:
            patterns.append(VisualPattern(
                name="complex_scene",
                description="Complex scene with high detail density",
                confidence=round(min(record.avg_edge_density / 0.6, 1.0), 3),
                category="composition",
                evidence_count=1,
                source_assets=[record.creative_asset_id],
                feature_values={"avg_edge_density": record.avg_edge_density},
            ))

    def _check_high_saturation(
        self, patterns: list[VisualPattern], record: VisionFeatureRecord
    ) -> None:
        if record.avg_saturation > self.HIGH_SATURATION_THRESHOLD:
            patterns.append(VisualPattern(
                name="high_saturation",
                description="Vibrant, highly saturated colors",
                confidence=round(min(record.avg_saturation / 0.8, 1.0), 3),
                category="color",
                evidence_count=1,
                source_assets=[record.creative_asset_id],
                feature_values={"avg_saturation": record.avg_saturation},
            ))

    def _check_fast_visual_change(
        self,
        patterns: list[VisualPattern],
        record: VisionFeatureRecord,
        frames: list[VisionFrameFeature],
    ) -> None:
        edge_densities = [f.edge_density for f in frames]
        if len(edge_densities) >= 2:
            std = statistics.stdev(edge_densities)
            if std > self.EDGE_STD_THRESHOLD:
                patterns.append(VisualPattern(
                    name="fast_visual_change",
                    description="Fast visual transitions between frames",
                    confidence=round(min(std / 0.2, 1.0), 3),
                    category="motion",
                    evidence_count=1,
                    source_assets=[record.creative_asset_id],
                    feature_values={"edge_density_std": std},
                ))

    def _check_rising_brightness(
        self,
        patterns: list[VisualPattern],
        frames: list[VisionFrameFeature],
    ) -> None:
        if len(frames) < 2:
            return
        first = frames[0].brightness
        last = frames[-1].brightness
        if last > first * 1.2:
            patterns.append(VisualPattern(
                name="rising_brightness",
                description="Brightness increases throughout the video",
                confidence=round(min((last - first) / 0.5, 1.0), 3),
                category="motion",
                evidence_count=1,
                source_assets=[],
                feature_values={"first_brightness": first, "last_brightness": last},
            ))

    def __repr__(self) -> str:
        return "PatternMiner()"