"""E11.3.3 — Vision Feature Store 测试。

测试范围：
  - VisionFeatureRecord: 数据模型 + 序列化
  - VisionFrameFeature: 帧级特征 + 序列化
  - VisionFeatureRepository: JSON 持久化 CRUD
  - VisionFeatureStore: 保存/查询/筛选/删除
  - Integration: FrameSequence → Store → Query
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_ops.creative_vision_runtime.feature_store.models import (
    VisionFeatureRecord,
    VisionFrameFeature,
    EXTRACTOR_VERSION,
)
from market_ops.creative_vision_runtime.feature_store.repository import (
    VisionFeatureRepository,
)
from market_ops.creative_vision_runtime.feature_store.store import (
    VisionFeatureStore,
)
from market_ops.creative_vision_runtime.feature_store import (
    VisionFeatureStore as StoreExport,
    VisionFeatureRepository as RepoExport,
    VisionFeatureRecord as RecordExport,
    VisionFrameFeature as FrameExport,
)
from market_ops.creative_vision_runtime.frame_extraction.models import (
    FrameSequence,
    VisionFrame,
)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _make_frame(index: int, brightness: float = 0.5) -> VisionFrame:
    return VisionFrame(
        frame_index=index,
        frame_path=f"/tmp/frame_{index:03d}.jpg",
        timestamp_sec=index * 5.0,
        ratio=index * 0.2,
        brightness=brightness,
        contrast=0.3 + index * 0.05,
        edge_density=0.15,
        text_density=0.1,
        color_entropy=6.0,
        saturation=0.5,
        top_color_ratio=0.4,
        center_brightness=0.55,
        center_contrast=0.35,
    )


def _make_sequence(creative_asset_id: str = "MW_VID_001") -> FrameSequence:
    frames = [_make_frame(i, brightness=0.4 + i * 0.1) for i in range(6)]
    return FrameSequence(
        creative_id="111",
        creative_asset_id=creative_asset_id,
        video_path="Y:/Eagle/test.mp4",
        eagle_filename="P4-v2601536-mg-2d.mp4",
        frames=frames,
        duration_sec=30.0,
        resolution=(1920, 1080),
        frame_count=6,
        hook_score=0.82,
        comprehension_score=0.65,
        reward_score=0.71,
        status="extracted",
    )


# ════════════════════════════════════════════════════════════════════
# VisionFeatureRecord
# ════════════════════════════════════════════════════════════════════

class TestVisionFeatureRecord:
    """VisionFeatureRecord 数据模型测试。"""

    def test_create_minimal(self):
        record = VisionFeatureRecord(creative_asset_id="MW_VID_001")
        assert record.creative_asset_id == "MW_VID_001"
        assert record.feature_id.startswith("vfr_")
        assert record.extractor_version == EXTRACTOR_VERSION
        assert record.created_at != ""

    def test_create_full(self):
        record = VisionFeatureRecord(
            creative_asset_id="MW_VID_001",
            video_path="Y:/Eagle/test.mp4",
            eagle_filename="P4-v2601536.mp4",
            frame_count=6,
            duration_seconds=30.0,
            resolution=(1920, 1080),
            hook_score=0.82,
            comprehension_score=0.65,
            reward_score=0.71,
            avg_brightness=0.61,
            avg_contrast=0.45,
            avg_edge_density=0.33,
            avg_saturation=0.55,
            avg_color_entropy=6.2,
            metric={"spend": 5000, "revenue": 15000, "roas": 3.0},
            lifecycle_status="WINNER",
            is_winner=True,
        )
        assert record.hook_score == 0.82
        assert record.is_winner is True
        assert record.avg_brightness == 0.61
        assert record.metric["roas"] == 3.0

    def test_to_dict(self):
        record = VisionFeatureRecord(
            creative_asset_id="MW_VID_001",
            hook_score=0.82,
            avg_brightness=0.61,
            is_winner=True,
            metric={"roas": 3.0},
        )
        d = record.to_dict()
        assert d["creative_asset_id"] == "MW_VID_001"
        assert d["hook_score"] == 0.82
        assert d["is_winner"] is True
        assert d["metric"]["roas"] == 3.0
        assert d["resolution"] == [0, 0]

    def test_from_dict(self):
        data = {
            "feature_id": "vfr_test_001",
            "creative_asset_id": "MW_VID_002",
            "hook_score": 0.75,
            "avg_brightness": 0.55,
            "avg_contrast": 0.40,
            "avg_edge_density": 0.30,
            "avg_saturation": 0.50,
            "avg_color_entropy": 5.8,
            "is_winner": False,
            "metric": {"spend": 1000},
            "resolution": [1280, 720],
        }
        record = VisionFeatureRecord.from_dict(data)
        assert record.feature_id == "vfr_test_001"
        assert record.creative_asset_id == "MW_VID_002"
        assert record.hook_score == 0.75
        assert record.avg_brightness == 0.55
        assert record.resolution == (1280, 720)

    def test_repr(self):
        record = VisionFeatureRecord(
            creative_asset_id="MW_VID_001",
            hook_score=0.82,
            is_winner=True,
        )
        r = repr(record)
        assert "MW_VID_001" in r
        assert "0.82" in r
        assert "winner=True" in r

    def test_feature_id_stable(self):
        record = VisionFeatureRecord(
            feature_id="vfr_custom",
            creative_asset_id="MW_VID_001",
        )
        assert record.feature_id == "vfr_custom"


# ════════════════════════════════════════════════════════════════════
# VisionFrameFeature
# ════════════════════════════════════════════════════════════════════

class TestVisionFrameFeature:
    """VisionFrameFeature 数据模型测试。"""

    def test_create_minimal(self):
        ff = VisionFrameFeature(feature_id="vfr_001", frame_index=0)
        assert ff.frame_id.startswith("vff_")
        assert ff.feature_id == "vfr_001"
        assert ff.frame_index == 0
        assert ff.tags == []

    def test_create_with_tags(self):
        ff = VisionFrameFeature(
            feature_id="vfr_001",
            frame_index=2,
            brightness=0.65,
            contrast=0.42,
            edge_density=0.15,
            saturation=0.35,
            color_entropy=7.5,
            tags=["gameplay", "action"],
        )
        assert ff.brightness == 0.65
        assert ff.tags == ["gameplay", "action"]

    def test_to_dict(self):
        ff = VisionFrameFeature(
            feature_id="vfr_001",
            frame_index=1,
            brightness=0.7,
            tags=["hook"],
        )
        d = ff.to_dict()
        assert d["frame_index"] == 1
        assert d["brightness"] == 0.7
        assert d["tags"] == ["hook"]

    def test_from_dict(self):
        data = {
            "frame_id": "vff_test",
            "feature_id": "vfr_001",
            "frame_index": 3,
            "timestamp_sec": 15.0,
            "brightness": 0.5,
            "contrast": 0.35,
            "edge_density": 0.12,
            "saturation": 0.45,
            "color_entropy": 6.0,
            "tags": ["mid", "gameplay"],
        }
        ff = VisionFrameFeature.from_dict(data)
        assert ff.frame_id == "vff_test"
        assert ff.frame_index == 3
        assert ff.brightness == 0.5
        assert ff.tags == ["mid", "gameplay"]

    def test_repr(self):
        ff = VisionFrameFeature(
            frame_index=0,
            timestamp_sec=1.5,
            brightness=0.7,
        )
        r = repr(ff)
        assert "idx=0" in r
        assert "1.5" in r


# ════════════════════════════════════════════════════════════════════
# VisionFeatureRepository
# ════════════════════════════════════════════════════════════════════

class TestVisionFeatureRepository:
    """VisionFeatureRepository JSON 持久化测试。"""

    @pytest.fixture
    def repo(self, tmp_path):
        return VisionFeatureRepository(data_dir=str(tmp_path / "vision_features"))

    def _make_record(self, asset_id: str = "MW_VID_001") -> VisionFeatureRecord:
        return VisionFeatureRecord(
            creative_asset_id=asset_id,
            video_path="Y:/Eagle/test.mp4",
            hook_score=0.82,
            avg_brightness=0.61,
            is_winner=True,
        )

    def test_save_and_load(self, repo):
        record = self._make_record("MW_VID_001")
        repo.save_record(record)

        loaded = repo.load_record(record.feature_id)
        assert loaded is not None
        assert loaded.creative_asset_id == "MW_VID_001"
        assert loaded.hook_score == 0.82

    def test_find_by_asset_id(self, repo):
        record = self._make_record("MW_VID_001")
        repo.save_record(record)

        found = repo.find_by_asset_id("MW_VID_001")
        assert found is not None
        assert found.feature_id == record.feature_id

    def test_find_not_found(self, repo):
        found = repo.find_by_asset_id("NONEXISTENT")
        assert found is None

    def test_list_all(self, repo):
        r1 = self._make_record("MW_VID_001")
        r2 = self._make_record("MW_VID_002")
        repo.save_record(r1)
        repo.save_record(r2)

        all_records = repo.list_all_records()
        assert len(all_records) == 2
        ids = {r.creative_asset_id for r in all_records}
        assert ids == {"MW_VID_001", "MW_VID_002"}

    def test_save_frames_and_load(self, repo):
        frames = [
            VisionFrameFeature(
                feature_id="vfr_001",
                frame_index=i,
                brightness=0.5 + i * 0.1,
            )
            for i in range(3)
        ]
        repo.save_frames("vfr_001", frames)

        loaded = repo.load_frames("vfr_001")
        assert len(loaded) == 3
        assert loaded[0].frame_index == 0
        assert loaded[2].frame_index == 2

    def test_load_frames_empty(self, repo):
        frames = repo.load_frames("nonexistent")
        assert frames == []

    def test_delete_record(self, repo):
        record = self._make_record("MW_VID_001")
        repo.save_record(record)

        # 也存帧
        frames = [VisionFrameFeature(feature_id=record.feature_id, frame_index=0)]
        repo.save_frames(record.feature_id, frames)

        result = repo.delete_record("MW_VID_001")
        assert result is True

        # 记录已删除
        assert repo.find_by_asset_id("MW_VID_001") is None
        assert repo.load_record(record.feature_id) is None

        # 帧已删除
        assert repo.load_frames(record.feature_id) == []

    def test_delete_nonexistent(self, repo):
        result = repo.delete_record("NONEXISTENT")
        assert result is False

    def test_json_files_exist(self, repo, tmp_path):
        record = self._make_record("MW_VID_001")
        repo.save_record(record)

        record_path = tmp_path / "vision_features" / "records" / f"{record.feature_id}.json"
        assert record_path.exists()

        index_path = tmp_path / "vision_features" / "index.json"
        assert index_path.exists()

    def test_record_count(self, repo):
        assert repo.record_count == 0
        repo.save_record(self._make_record("MW_VID_001"))
        assert repo.record_count == 1
        repo.save_record(self._make_record("MW_VID_002"))
        assert repo.record_count == 2

    def test_persistence_across_instances(self, tmp_path):
        data_dir = str(tmp_path / "vision_features")
        repo1 = VisionFeatureRepository(data_dir=data_dir)
        record = self._make_record("MW_VID_001")
        repo1.save_record(record)

        # 新实例加载
        repo2 = VisionFeatureRepository(data_dir=data_dir)
        found = repo2.find_by_asset_id("MW_VID_001")
        assert found is not None
        assert found.hook_score == 0.82


# ════════════════════════════════════════════════════════════════════
# VisionFeatureStore
# ════════════════════════════════════════════════════════════════════

class TestVisionFeatureStore:
    """VisionFeatureStore API 测试。"""

    @pytest.fixture
    def store(self, tmp_path):
        return VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))

    @pytest.fixture
    def seq(self):
        return _make_sequence("MW_VID_001")

    def test_save(self, store, seq):
        record = store.save(seq, metric={"roas": 3.0}, lifecycle_status="WINNER", is_winner=True)
        assert record.creative_asset_id == "MW_VID_001"
        assert record.hook_score == 0.82
        assert record.comprehension_score == 0.65
        assert record.reward_score == 0.71
        assert record.is_winner is True
        assert record.metric["roas"] == 3.0
        assert record.frame_count == 6
        assert record.duration_seconds == 30.0
        assert record.resolution == (1920, 1080)
        assert record.extractor_version == EXTRACTOR_VERSION

    def test_save_aggregate_features(self, store, seq):
        record = store.save(seq)
        # 6 frames: brightness [0.4, 0.5, 0.6, 0.7, 0.8, 0.9] → avg = 0.65
        assert record.avg_brightness == pytest.approx(0.65, abs=0.01)
        assert record.avg_edge_density > 0
        assert record.avg_saturation > 0

    def test_get(self, store, seq):
        store.save(seq)
        found = store.get("MW_VID_001")
        assert found is not None
        assert found.creative_asset_id == "MW_VID_001"
        assert found.hook_score == 0.82

    def test_get_not_found(self, store):
        found = store.get("NONEXISTENT")
        assert found is None

    def test_get_frames(self, store, seq):
        record = store.save(seq)
        frames = store.get_frames(record.feature_id)
        assert len(frames) == 6
        for i, ff in enumerate(frames):
            assert ff.frame_index == i
            assert ff.feature_id == record.feature_id
            assert ff.brightness > 0

    def test_list_all(self, store, seq):
        seq2 = _make_sequence("MW_VID_002")
        store.save(seq)
        store.save(seq2)

        all_records = store.list_all()
        assert len(all_records) == 2

    def test_query_by_hook_score(self, store, seq):
        seq2 = _make_sequence("MW_VID_002")
        # seq has hook=0.82, seq2 has hook=0.82 too (same)
        store.save(seq)
        store.save(seq2)

        results = store.query({"hook_score": 0.8})
        assert len(results) == 2

        results = store.query({"hook_score": 0.9})
        assert len(results) == 0

    def test_query_by_is_winner(self, store, seq):
        seq2 = _make_sequence("MW_VID_002")
        store.save(seq, is_winner=True)
        store.save(seq2, is_winner=False)

        winners = store.query({"is_winner": True})
        assert len(winners) == 1
        assert winners[0].creative_asset_id == "MW_VID_001"

    def test_query_by_lifecycle_status(self, store, seq):
        seq2 = _make_sequence("MW_VID_002")
        store.save(seq, lifecycle_status="WINNER")
        store.save(seq2, lifecycle_status="TESTING")

        results = store.query({"lifecycle_status": "WINNER"})
        assert len(results) == 1
        assert results[0].lifecycle_status == "WINNER"

    def test_query_combined(self, store, seq):
        seq2 = _make_sequence("MW_VID_002")
        store.save(seq, is_winner=True)
        store.save(seq2, is_winner=True)

        results = store.query({"hook_score": 0.8, "is_winner": True})
        assert len(results) == 2

        results = store.query({"hook_score": 0.8, "is_winner": False})
        assert len(results) == 0

    def test_query_min_frame_count(self, store, seq):
        store.save(seq)
        results = store.query({"min_frame_count": 6})
        assert len(results) == 1

        results = store.query({"min_frame_count": 10})
        assert len(results) == 0

    def test_delete(self, store, seq):
        record = store.save(seq)
        assert store.get("MW_VID_001") is not None

        result = store.delete("MW_VID_001")
        assert result is True
        assert store.get("MW_VID_001") is None
        assert store.get_frames(record.feature_id) == []

    def test_save_batch(self, store):
        seq1 = _make_sequence("MW_VID_001")
        seq2 = _make_sequence("MW_VID_002")
        seq3 = _make_sequence("MW_VID_003")

        records = store.save_batch(
            [seq1, seq2, seq3],
            metrics=[{"roas": 1.0}, {"roas": 2.0}, {"roas": 3.0}],
            lifecycle_statuses=["WINNER", "TESTING", "WINNER"],
            is_winner_flags=[True, False, True],
        )
        assert len(records) == 3
        assert records[0].is_winner is True
        assert records[1].is_winner is False
        assert records[2].metric["roas"] == 3.0

        assert store.record_count == 3

    def test_saved_count(self, store, seq):
        assert store.saved_count == 0
        store.save(seq)
        assert store.saved_count == 1
        store.save(_make_sequence("MW_VID_002"))
        assert store.saved_count == 2

    def test_repr(self, store):
        assert "VisionFeatureStore" in repr(store)


# ════════════════════════════════════════════════════════════════════
# Integration: FrameSequence → Store → Query
# ════════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试：FrameSequence → Store → Query 完整流程。"""

    def test_full_workflow(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))

        # 1. 创建多个 FrameSequence
        seq_winner = _make_sequence("MW_WINNER_001")
        seq_loser = _make_sequence("MW_LOSER_001")

        # 2. 保存
        store.save(seq_winner, metric={"roas": 3.5}, lifecycle_status="WINNER", is_winner=True)
        store.save(seq_loser, metric={"roas": 0.5}, lifecycle_status="TESTING", is_winner=False)

        # 3. 查询 WINNER
        winners = store.query({"is_winner": True})
        assert len(winners) == 1
        assert winners[0].creative_asset_id == "MW_WINNER_001"
        assert winners[0].metric["roas"] == 3.5

        # 4. 查询帧
        frames = store.get_frames(winners[0].feature_id)
        assert len(frames) == 6

        # 5. 序列化往返
        d = winners[0].to_dict()
        restored = VisionFeatureRecord.from_dict(d)
        assert restored.creative_asset_id == "MW_WINNER_001"
        assert restored.hook_score == winners[0].hook_score

    def test_persistence_after_new_store(self, tmp_path):
        data_dir = str(tmp_path / "vision_features")

        store1 = VisionFeatureStore(data_dir=data_dir)
        seq = _make_sequence("MW_VID_001")
        store1.save(seq, is_winner=True)

        # 新 store 实例
        store2 = VisionFeatureStore(data_dir=data_dir)
        found = store2.get("MW_VID_001")
        assert found is not None
        assert found.is_winner is True
        assert found.hook_score == 0.82

        frames = store2.get_frames(found.feature_id)
        assert len(frames) == 6

    def test_winner_loser_comparison(self, tmp_path):
        store = VisionFeatureStore(data_dir=str(tmp_path / "vision_features"))

        # 创建不同视觉特征的素材
        frames_winner = [_make_frame(i, brightness=0.7 + i * 0.05) for i in range(6)]
        seq_winner = FrameSequence(
            creative_id="111",
            creative_asset_id="MW_WINNER_001",
            video_path="Y:/Eagle/winner.mp4",
            eagle_filename="winner.mp4",
            frames=frames_winner,
            duration_sec=30.0,
            resolution=(1920, 1080),
            hook_score=0.85,
            comprehension_score=0.70,
            reward_score=0.75,
            status="extracted",
        )

        frames_loser = [_make_frame(i, brightness=0.3 + i * 0.05) for i in range(6)]
        seq_loser = FrameSequence(
            creative_id="222",
            creative_asset_id="MW_LOSER_001",
            video_path="Y:/Eagle/loser.mp4",
            eagle_filename="loser.mp4",
            frames=frames_loser,
            duration_sec=25.0,
            resolution=(1280, 720),
            hook_score=0.45,
            comprehension_score=0.50,
            reward_score=0.40,
            status="extracted",
        )

        store.save(seq_winner, metric={"roas": 3.0}, is_winner=True)
        store.save(seq_loser, metric={"roas": 0.8}, is_winner=False)

        # 高 hook_score 素材
        high_hook = store.query({"hook_score": 0.8})
        assert len(high_hook) == 1
        assert high_hook[0].creative_asset_id == "MW_WINNER_001"

        # 高亮度素材
        bright = store.query({"avg_brightness": 0.7})
        assert len(bright) == 1

    def test_package_exports(self):
        assert StoreExport is VisionFeatureStore
        assert RepoExport is VisionFeatureRepository
        assert RecordExport is VisionFeatureRecord
        assert FrameExport is VisionFrameFeature