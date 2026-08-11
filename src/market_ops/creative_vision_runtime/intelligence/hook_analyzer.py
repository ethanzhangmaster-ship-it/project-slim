"""E11.3.5 — Hook Analyzer。

分析视频前 3 帧（开头 0%, 20%, 40%），识别 Hook 模式。

基于 VisionFrameFeature[] 的帧级特征进行规则分析。
"""

from __future__ import annotations

from typing import Any

from ..feature_store.models import VisionFrameFeature
from .models import HookAnalysis


class HookAnalyzer:
    """开头 Hook 分析器。

    分析前 3 帧的视觉特征变化，识别 Hook 类型和强度。
    """

    HOOK_FRAME_COUNT = 3  # 分析前 3 帧

    def analyze(self, frames: list[VisionFrameFeature]) -> HookAnalysis:
        """分析开头帧的 Hook 特征。

        Args:
            frames: 帧级特征列表（至少 3 帧）

        Returns:
            HookAnalysis
        """
        if len(frames) < 2:
            return HookAnalysis(
                hook_strength=0.0,
                opening_type="calm",
                description="Insufficient frames for hook analysis",
            )

        hook_frames = frames[: self.HOOK_FRAME_COUNT]

        # 提取特征
        brightness_values = [f.brightness for f in hook_frames]
        contrast_values = [f.contrast for f in hook_frames]
        edge_values = [f.edge_density for f in hook_frames]
        saturation_values = [f.saturation for f in hook_frames]

        # 判断趋势
        brightness_trend = self._trend(brightness_values)
        contrast_trend = self._trend(contrast_values)
        edge_trend = self._trend(edge_values)

        # 判断开头类型
        opening_type = self._classify_opening(
            brightness_values, contrast_values, edge_values
        )

        # 计算视觉变化程度
        visual_transition = self._transition_level(
            brightness_values, contrast_values, edge_values
        )

        # 计算 Hook 强度
        hook_strength = self._compute_hook_strength(
            brightness_values, contrast_values, edge_values, saturation_values
        )

        # 逐帧数据
        frame_by_frame = self._build_frame_data(hook_frames)

        # 生成描述
        description = self._describe(
            hook_strength, opening_type, visual_transition, brightness_values
        )

        return HookAnalysis(
            hook_strength=round(hook_strength, 3),
            opening_type=opening_type,
            visual_transition=visual_transition,
            first_frame_brightness=brightness_values[0] if brightness_values else 0.0,
            brightness_trend=brightness_trend,
            contrast_trend=contrast_trend,
            edge_density_trend=edge_trend,
            frame_by_frame=frame_by_frame,
            description=description,
        )

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _trend(values: list[float]) -> str:
        if len(values) < 2:
            return "stable"
        if values[-1] > values[0] * 1.15:
            return "rising"
        if values[-1] < values[0] * 0.85:
            return "falling"
        return "stable"

    @staticmethod
    def _classify_opening(
        brightness: list[float],
        contrast: list[float],
        edge: list[float],
    ) -> str:
        """分类开头类型。"""
        if not brightness:
            return "calm"

        avg_brightness = sum(brightness) / len(brightness)
        avg_contrast = sum(contrast) / len(contrast)
        avg_edge = sum(edge) / len(edge)

        # instant_reward: 高亮 + 高对比度 + 中等边缘（直接展示核心内容）
        if avg_brightness > 0.6 and avg_contrast > 0.45:
            return "instant_reward"

        # motion: 高边缘密度（快速变化）
        if avg_edge > 0.35:
            return "motion"

        # curiosity: 中等亮度 + 低对比度（悬念感）
        if 0.3 <= avg_brightness <= 0.6 and avg_contrast < 0.4:
            return "curiosity"

        return "calm"

    @staticmethod
    def _transition_level(
        brightness: list[float],
        contrast: list[float],
        edge: list[float],
    ) -> str:
        """判断视觉变化程度。"""
        ranges = []
        if len(brightness) >= 2:
            ranges.append(max(brightness) - min(brightness))
        if len(contrast) >= 2:
            ranges.append(max(contrast) - min(contrast))
        if len(edge) >= 2:
            ranges.append(max(edge) - min(edge))

        if not ranges:
            return "low"

        avg_range = sum(ranges) / len(ranges)
        if avg_range > 0.2:
            return "high"
        if avg_range > 0.1:
            return "medium"
        return "low"

    @staticmethod
    def _compute_hook_strength(
        brightness: list[float],
        contrast: list[float],
        edge: list[float],
        saturation: list[float],
    ) -> float:
        """计算 Hook 强度 (0-1)。

        基于：
          - 亮度变化：变化越大，Hook 越强
          - 对比度水平：越高越强
          - 饱和度水平：越高越强
        """
        if not brightness:
            return 0.0

        avg_brightness = sum(brightness) / len(brightness)
        avg_contrast = sum(contrast) / len(contrast)
        avg_saturation = sum(saturation) / len(saturation)

        brightness_range = max(brightness) - min(brightness) if len(brightness) >= 2 else 0
        contrast_range = max(contrast) - min(contrast) if len(contrast) >= 2 else 0

        # 加权：亮度变化 30% + 对比度 30% + 饱和度 20% + 变化幅度 20%
        strength = (
            avg_brightness * 0.20
            + avg_contrast * 0.30
            + avg_saturation * 0.20
            + brightness_range * 0.15
            + contrast_range * 0.15
        )

        return min(max(strength, 0.0), 1.0)

    @staticmethod
    def _build_frame_data(
        frames: list[VisionFrameFeature],
    ) -> list[dict[str, Any]]:
        return [
            {
                "frame_index": f.frame_index,
                "timestamp_sec": f.timestamp_sec,
                "brightness": f.brightness,
                "contrast": f.contrast,
                "edge_density": f.edge_density,
                "saturation": f.saturation,
            }
            for f in frames
        ]

    @staticmethod
    def _describe(
        strength: float,
        opening_type: str,
        transition: str,
        brightness: list[float],
    ) -> str:
        type_desc = {
            "instant_reward": "immediate visual reward with bright, high-contrast opening",
            "curiosity": "curiosity-driven opening with moderate brightness and mystery",
            "motion": "fast-paced opening with high visual activity",
            "calm": "calm, gradual opening",
        }

        parts = [type_desc.get(opening_type, "")]
        if transition == "high":
            parts.append("rapid visual transitions")
        elif transition == "medium":
            parts.append("moderate visual changes")

        return "; ".join(parts) if parts else "standard opening"

    def __repr__(self) -> str:
        return f"HookAnalyzer(frames={self.HOOK_FRAME_COUNT})"