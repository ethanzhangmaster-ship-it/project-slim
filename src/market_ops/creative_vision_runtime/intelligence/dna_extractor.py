"""E11.3.5 — Winner DNA Extractor。

从多个 Winner 素材中提取聚合的视觉 DNA。

输入: 多个 Winner 的 VisionFeatureRecord + VisionFrameFeature[]
输出: WinnerVisualDNA（聚合视觉特征）
"""

from __future__ import annotations

from typing import Any

from ..feature_store.models import VisionFeatureRecord, VisionFrameFeature
from .models import VisualPattern, WinnerVisualDNA
from .pattern_miner import PatternMiner


class WinnerDNAExtractor:
    """Winner 视觉 DNA 提取器。

    聚合多个 Winner 的视觉特征，提取共性模式。
    """

    def __init__(self) -> None:
        self._miner = PatternMiner()

    def extract(
        self,
        winner_records: list[VisionFeatureRecord],
        frames_map: dict[str, list[VisionFrameFeature]] | None = None,
    ) -> WinnerVisualDNA:
        """从多个 Winner 中提取视觉 DNA。

        Args:
            winner_records: Winner 的 VisionFeatureRecord 列表
            frames_map:     feature_id → 帧特征列表（可选）

        Returns:
            WinnerVisualDNA
        """
        if not winner_records:
            return WinnerVisualDNA(
                source_count=0,
                description="No winner records provided",
            )

        source_assets = [r.creative_asset_id for r in winner_records]

        # 挖掘所有 Winner 的模式
        all_patterns: list[VisualPattern] = []
        for record in winner_records:
            frames = None
            if frames_map and record.feature_id in frames_map:
                frames = frames_map[record.feature_id]
            patterns = self._miner.mine(record, frames)
            all_patterns.extend(patterns)

        # 聚合模式
        aggregated = self._miner.aggregate_patterns(all_patterns, min_confidence=0.3)

        # 分类推断
        opening = self._infer_opening(aggregated)
        composition = self._infer_composition(aggregated)
        color = self._infer_color(aggregated)
        motion = self._infer_motion(aggregated)

        # 聚合指标
        metrics = self._aggregate_metrics(winner_records)

        # 描述
        description = self._build_description(
            opening, composition, color, motion, metrics
        )

        return WinnerVisualDNA(
            source_count=len(winner_records),
            source_assets=source_assets,
            opening=opening,
            composition=composition,
            color=color,
            motion=motion,
            patterns=aggregated,
            aggregated_metrics=metrics,
            description=description,
        )

    # ── Inference ────────────────────────────────────────

    @staticmethod
    def _infer_opening(patterns: list[VisualPattern]) -> str:
        names = {p.name for p in patterns}
        if "high_contrast_opening" in names and "bright_visual" in names:
            return "high_contrast_center_focus"
        if "high_contrast_opening" in names:
            return "high_contrast"
        if "bright_visual" in names:
            return "bright_opening"
        if "dark_visual" in names:
            return "dark_opening"
        return "standard_opening"

    @staticmethod
    def _infer_composition(patterns: list[VisualPattern]) -> str:
        names = {p.name for p in patterns}
        if "clean_composition" in names:
            return "single_subject"
        if "complex_scene" in names:
            return "multi_subject"
        return "varied"

    @staticmethod
    def _infer_color(patterns: list[VisualPattern]) -> str:
        names = {p.name for p in patterns}
        if "high_saturation" in names and "bright_visual" in names:
            return "bright_saturated"
        if "high_saturation" in names:
            return "saturated"
        if "dark_visual" in names:
            return "dark_muted"
        if "bright_visual" in names:
            return "bright"
        return "neutral"

    @staticmethod
    def _infer_motion(patterns: list[VisualPattern]) -> str:
        names = {p.name for p in patterns}
        if "fast_visual_change" in names:
            return "fast_transition"
        if "rising_brightness" in names:
            return "slow_reveal"
        return "static"

    @staticmethod
    def _aggregate_metrics(
        records: list[VisionFeatureRecord],
    ) -> dict[str, Any]:
        n = len(records)
        return {
            "avg_hook_score": round(sum(r.hook_score for r in records) / n, 3),
            "avg_reward_score": round(sum(r.reward_score for r in records) / n, 3),
            "avg_brightness": round(sum(r.avg_brightness for r in records) / n, 3),
            "avg_contrast": round(sum(r.avg_contrast for r in records) / n, 3),
            "avg_edge_density": round(sum(r.avg_edge_density for r in records) / n, 3),
            "avg_saturation": round(sum(r.avg_saturation for r in records) / n, 3),
            "avg_color_entropy": round(sum(r.avg_color_entropy for r in records) / n, 3),
            "avg_duration": round(sum(r.duration_seconds for r in records) / n, 1),
        }

    @staticmethod
    def _build_description(
        opening: str,
        composition: str,
        color: str,
        motion: str,
        metrics: dict[str, Any],
    ) -> str:
        return (
            f"Winner DNA: {opening} opening, {composition} composition, "
            f"{color} color palette, {motion} motion. "
            f"Avg hook={metrics['avg_hook_score']:.2f}, "
            f"reward={metrics['avg_reward_score']:.2f}"
        )

    def __repr__(self) -> str:
        return "WinnerDNAExtractor()"