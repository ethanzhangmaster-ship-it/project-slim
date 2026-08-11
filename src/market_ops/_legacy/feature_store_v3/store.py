"""E11.3.3 — Vision Feature Store。

FrameSequence → VisionFeatureRecord + VisionFrameFeature[] → JSON 持久化。

Usage:
    store = VisionFeatureStore(data_dir="data/vision_features")
    record = store.save(frame_sequence)
    # → VisionFeatureRecord

    found = store.get(creative_asset_id="MW_VID_001")
    frames = store.get_frames(found.feature_id)
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..frame_extraction.models import FrameSequence, VisionFrame
from .models import (
    VisionFeatureRecord,
    VisionFrameFeature,
    EXTRACTOR_VERSION,
)
from .repository import VisionFeatureRepository

logger = logging.getLogger(__name__)


class VisionFeatureStore:
    """Vision Feature Store — 视觉特征存储与查询。

    Attributes:
        repo:      底层持久化仓库
        saved_count: 已保存记录数
    """

    def __init__(self, data_dir: str = "data/vision_features") -> None:
        self._repo = VisionFeatureRepository(data_dir=data_dir)
        self._saved_count: int = 0

    # ── Save ─────────────────────────────────────────────

    def save(
        self,
        sequence: FrameSequence,
        metric: dict[str, Any] | None = None,
        lifecycle_status: str = "",
        is_winner: bool = False,
    ) -> VisionFeatureRecord:
        """将 FrameSequence 保存为 VisionFeatureRecord。

        Args:
            sequence:         帧序列
            metric:           投放效果数据 (spend/revenue/roas)
            lifecycle_status: 素材生命周期状态
            is_winner:        是否为 WINNER

        Returns:
            VisionFeatureRecord
        """
        record = VisionFeatureRecord(
            creative_asset_id=sequence.creative_asset_id,
            video_path=sequence.video_path,
            eagle_filename=sequence.eagle_filename,
            frame_count=sequence.frame_count,
            duration_seconds=sequence.duration_sec,
            resolution=sequence.resolution,
            hook_score=sequence.hook_score,
            comprehension_score=sequence.comprehension_score,
            reward_score=sequence.reward_score,
            avg_brightness=sequence.avg_brightness,
            avg_contrast=sequence.avg_contrast,
            avg_edge_density=sequence.avg_edge_density,
            avg_saturation=sequence.avg_saturation,
            avg_color_entropy=sequence.avg_color_entropy,
            metric=metric or {},
            lifecycle_status=lifecycle_status,
            is_winner=is_winner,
            extractor_version=EXTRACTOR_VERSION,
        )

        self._repo.save_record(record)

        # 保存帧级特征
        frame_features = self._frames_from_sequence(
            record.feature_id, sequence.frames
        )
        self._repo.save_frames(record.feature_id, frame_features)

        self._saved_count += 1
        logger.info(
            f"VisionFeatureStore: saved {record.creative_asset_id} "
            f"→ {record.feature_id} ({len(frame_features)} frames)"
        )

        return record

    def save_batch(
        self,
        sequences: list[FrameSequence],
        metrics: list[dict[str, Any]] | None = None,
        lifecycle_statuses: list[str] | None = None,
        is_winner_flags: list[bool] | None = None,
    ) -> list[VisionFeatureRecord]:
        """批量保存 FrameSequence 列表。

        Args:
            sequences:         FrameSequence 列表
            metrics:           投放效果数据列表（与 sequences 对齐）
            lifecycle_statuses: 生命周期状态列表
            is_winner_flags:   WINNER 标记列表

        Returns:
            VisionFeatureRecord 列表
        """
        records: list[VisionFeatureRecord] = []
        for i, seq in enumerate(sequences):
            metric = (metrics or [])[i] if metrics and i < len(metrics) else {}
            status = (lifecycle_statuses or [])[i] if lifecycle_statuses and i < len(lifecycle_statuses) else ""
            winner = (is_winner_flags or [])[i] if is_winner_flags and i < len(is_winner_flags) else False

            record = self.save(seq, metric=metric, lifecycle_status=status, is_winner=winner)
            records.append(record)

        return records

    # ── Query ────────────────────────────────────────────

    def get(self, creative_asset_id: str) -> VisionFeatureRecord | None:
        """通过 creative_asset_id 查询特征记录。"""
        return self._repo.find_by_asset_id(creative_asset_id)

    def get_frames(self, feature_id: str) -> list[VisionFrameFeature]:
        """获取帧级特征。"""
        return self._repo.load_frames(feature_id)

    def list_all(self) -> list[VisionFeatureRecord]:
        """列出所有特征记录。"""
        return self._repo.list_all_records()

    def query(self, filters: dict[str, Any]) -> list[VisionFeatureRecord]:
        """按条件筛选特征记录。

        Supported filter keys:
            - hook_score:        float (>= threshold)
            - comprehension_score: float
            - reward_score:      float
            - avg_brightness:    float
            - avg_contrast:      float
            - avg_edge_density:  float
            - avg_saturation:    float
            - avg_color_entropy: float
            - is_winner:         bool
            - lifecycle_status:  str (exact match)
            - min_frame_count:   int
            - min_duration:      float

        All numeric filters use >= comparison.
        Multiple filters are combined with AND.

        Example:
            store.query({
                "hook_score": 0.8,
                "is_winner": True,
            })
        """
        records = self._repo.list_all_records()
        results: list[VisionFeatureRecord] = []

        for record in records:
            if self._matches(record, filters):
                results.append(record)

        return results

    def delete(self, creative_asset_id: str) -> bool:
        """删除特征记录。"""
        return self._repo.delete_record(creative_asset_id)

    # ── Stats ────────────────────────────────────────────

    @property
    def saved_count(self) -> int:
        return self._saved_count

    @property
    def record_count(self) -> int:
        return self._repo.record_count

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _frames_from_sequence(
        feature_id: str,
        frames: list[VisionFrame],
    ) -> list[VisionFrameFeature]:
        """VisionFrame → VisionFrameFeature 转换。"""
        return [
            VisionFrameFeature(
                frame_id=vf.frame_id,
                feature_id=feature_id,
                frame_index=vf.frame_index,
                timestamp_sec=vf.timestamp_sec,
                frame_path=vf.frame_path,
                brightness=vf.brightness,
                contrast=vf.contrast,
                edge_density=vf.edge_density,
                saturation=vf.saturation,
                color_entropy=vf.color_entropy,
            )
            for vf in frames
        ]

    @staticmethod
    def _matches(record: VisionFeatureRecord, filters: dict[str, Any]) -> bool:
        """检查记录是否匹配筛选条件。"""
        for key, value in filters.items():
            if key == "is_winner":
                if record.is_winner != value:
                    return False
            elif key == "lifecycle_status":
                if record.lifecycle_status != value:
                    return False
            elif key == "min_frame_count":
                if record.frame_count < value:
                    return False
            elif key == "min_duration":
                if record.duration_seconds < value:
                    return False
            else:
                # Numeric field: >= comparison
                record_value = getattr(record, key, None)
                if record_value is None:
                    return False
                if not isinstance(record_value, (int, float)):
                    return False
                if record_value < value:
                    return False
        return True

    def __repr__(self) -> str:
        return (
            f"VisionFeatureStore(records={self.record_count}, "
            f"saved={self._saved_count})"
        )