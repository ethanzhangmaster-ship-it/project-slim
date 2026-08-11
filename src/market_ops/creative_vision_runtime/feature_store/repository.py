"""E11.3.3 — Vision Feature Repository。

JSON 文件持久化层：
  data/vision_features/
      records/        {feature_id}.json
      frames/         {feature_id}/frame_{index}.json
      index.json      creative_asset_id → feature_id 映射
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import VisionFeatureRecord, VisionFrameFeature

logger = logging.getLogger(__name__)


class VisionFeatureRepository:
    """Vision Feature 持久化仓库。JSON 文件存储，零外部依赖。"""

    DEFAULT_DATA_DIR = "data/vision_features"

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR) -> None:
        self._data_dir = Path(data_dir)
        self._records_dir = self._data_dir / "records"
        self._frames_dir = self._data_dir / "frames"
        self._index_path = self._data_dir / "index.json"

        self._records_dir.mkdir(parents=True, exist_ok=True)
        self._frames_dir.mkdir(parents=True, exist_ok=True)

        self._index: dict[str, str] = self._load_index()

    def save_record(self, record: VisionFeatureRecord) -> None:
        path = self._records_dir / f"{record.feature_id}.json"
        path.write_text(
            json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._index[record.creative_asset_id] = record.feature_id
        self._save_index()

    def load_record(self, feature_id: str) -> VisionFeatureRecord | None:
        path = self._records_dir / f"{feature_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return VisionFeatureRecord.from_dict(data)

    def find_by_asset_id(self, creative_asset_id: str) -> VisionFeatureRecord | None:
        feature_id = self._index.get(creative_asset_id)
        if feature_id is None:
            return None
        return self.load_record(feature_id)

    def list_all_records(self) -> list[VisionFeatureRecord]:
        records: list[VisionFeatureRecord] = []
        for path in sorted(self._records_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(VisionFeatureRecord.from_dict(data))
            except Exception as e:
                logger.warning(f"VisionFeatureRepository: skip corrupt record {path}: {e}")
        return records

    def delete_record(self, creative_asset_id: str) -> bool:
        feature_id = self._index.pop(creative_asset_id, None)
        if feature_id is None:
            return False
        record_path = self._records_dir / f"{feature_id}.json"
        if record_path.exists():
            record_path.unlink()
        frame_dir = self._frames_dir / feature_id
        if frame_dir.exists():
            for f in frame_dir.iterdir():
                f.unlink()
            frame_dir.rmdir()
        self._save_index()
        return True

    def save_frames(self, feature_id: str, frames: list[VisionFrameFeature]) -> None:
        frame_dir = self._frames_dir / feature_id
        frame_dir.mkdir(parents=True, exist_ok=True)
        for ff in frames:
            path = frame_dir / f"frame_{ff.frame_index:03d}.json"
            path.write_text(
                json.dumps(ff.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def load_frames(self, feature_id: str) -> list[VisionFrameFeature]:
        frame_dir = self._frames_dir / feature_id
        if not frame_dir.exists():
            return []
        frames: list[VisionFrameFeature] = []
        for path in sorted(frame_dir.glob("frame_*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                frames.append(VisionFrameFeature.from_dict(data))
            except Exception as e:
                logger.warning(f"VisionFeatureRepository: skip corrupt frame {path}: {e}")
        return frames

    def _load_index(self) -> dict[str, str]:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self) -> None:
        self._index_path.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def record_count(self) -> int:
        return len(list(self._records_dir.glob("*.json")))

    @property
    def asset_count(self) -> int:
        return len(self._index)

    def __repr__(self) -> str:
        return (
            f"VisionFeatureRepository(records={self.record_count}, "
            f"assets={self.asset_count})"
        )