"""E11.3.3 — Vision Feature Store。

FrameSequence → VisionFeatureRecord + VisionFrameFeature[] → JSON 持久化。
"""

from __future__ import annotations

import logging
from typing import Any

from .models import VisionFeatureRecord, VisionFrameFeature, EXTRACTOR_VERSION
from .repository import VisionFeatureRepository

logger = logging.getLogger(__name__)


class VisionFeatureStore:
    """Vision Feature Store — 视觉特征存储与查询。"""

    def __init__(self, data_dir: str = "data/vision_features") -> None:
        self._repo = VisionFeatureRepository(data_dir=data_dir)
        self._saved_count: int = 0

    def save(
        self,
        sequence: Any,
        metric: dict[str, Any] | None = None,
        lifecycle_status: str = "",
        is_winner: bool = False,
    ) -> VisionFeatureRecord:
        """将 FrameSequence 保存为 VisionFeatureRecord。"""
        record = VisionFeatureRecord(
            creative_asset_id=getattr(sequence, "creative_asset_id", ""),
            video_path=getattr(sequence, "video_path", ""),
            eagle_filename=getattr(sequence, "eagle_filename", ""),
            frame_count=getattr(sequence, "frame_count", 0),
            duration_seconds=getattr(sequence, "duration_sec", 0.0),
            resolution=getattr(sequence, "resolution", (0, 0)),
            hook_score=getattr(sequence, "hook_score", 0.0),
            comprehension_score=getattr(sequence, "comprehension_score", 0.0),
            reward_score=getattr(sequence, "reward_score", 0.0),
            avg_brightness=getattr(sequence, "avg_brightness", 0.0),
            avg_contrast=getattr(sequence, "avg_contrast", 0.0),
            avg_edge_density=getattr(sequence, "avg_edge_density", 0.0),
            avg_saturation=getattr(sequence, "avg_saturation", 0.0),
            avg_color_entropy=getattr(sequence, "avg_color_entropy", 0.0),
            metric=metric or {},
            lifecycle_status=lifecycle_status,
            is_winner=is_winner,
            extractor_version=EXTRACTOR_VERSION,
        )
        self._repo.save_record(record)
        frames = getattr(sequence, "frames", [])
        if frames:
            frame_features = self._frames_from_sequence(record.feature_id, frames)
            self._repo.save_frames(record.feature_id, frame_features)
        self._saved_count += 1
        logger.info(
            f"VisionFeatureStore: saved {record.creative_asset_id} "
            f"→ {record.feature_id}"
        )
        return record

    def save_batch(
        self,
        sequences: list[Any],
        metrics: list[dict[str, Any]] | None = None,
        lifecycle_statuses: list[str] | None = None,
        is_winner_flags: list[bool] | None = None,
    ) -> list[VisionFeatureRecord]:
        records: list[VisionFeatureRecord] = []
        for i, seq in enumerate(sequences):
            metric = (metrics or [])[i] if metrics and i < len(metrics) else {}
            status = (lifecycle_statuses or [])[i] if lifecycle_statuses and i < len(lifecycle_statuses) else ""
            winner = (is_winner_flags or [])[i] if is_winner_flags and i < len(is_winner_flags) else False
            record = self.save(seq, metric=metric, lifecycle_status=status, is_winner=winner)
            records.append(record)
        return records

    def get(self, creative_asset_id: str) -> VisionFeatureRecord | None:
        return self._repo.find_by_asset_id(creative_asset_id)

    def get_frames(self, feature_id: str) -> list[VisionFrameFeature]:
        return self._repo.load_frames(feature_id)

    def list_all(self) -> list[VisionFeatureRecord]:
        return self._repo.list_all_records()

    def query(self, filters: dict[str, Any]) -> list[VisionFeatureRecord]:
        records = self._repo.list_all_records()
        results: list[VisionFeatureRecord] = []
        for record in records:
            if self._matches(record, filters):
                results.append(record)
        return results

    def delete(self, creative_asset_id: str) -> bool:
        return self._repo.delete_record(creative_asset_id)

    @property
    def saved_count(self) -> int:
        return self._saved_count

    @property
    def record_count(self) -> int:
        return self._repo.record_count

    @staticmethod
    def _frames_from_sequence(
        feature_id: str,
        frames: list[Any],
    ) -> list[VisionFrameFeature]:
        return [
            VisionFrameFeature(
                frame_id=getattr(vf, "frame_id", ""),
                feature_id=feature_id,
                frame_index=getattr(vf, "frame_index", 0),
                timestamp_sec=getattr(vf, "timestamp_sec", 0.0),
                frame_path=getattr(vf, "frame_path", ""),
                brightness=getattr(vf, "brightness", 0.0),
                contrast=getattr(vf, "contrast", 0.0),
                edge_density=getattr(vf, "edge_density", 0.0),
                saturation=getattr(vf, "saturation", 0.0),
                color_entropy=getattr(vf, "color_entropy", 0.0),
            )
            for vf in frames
        ]

    @staticmethod
    def _matches(record: VisionFeatureRecord, filters: dict[str, Any]) -> bool:
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