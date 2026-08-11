"""E11.3.2 — Frame Extraction 测试。

测试范围：
  - VisionFrame: 数据模型 + 序列化
  - FrameSequence: 帧序列 + 视频级评分 + 聚合属性
  - VideoFrameExtractor: 帧提取 + 特征分析 + 批量处理
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from market_ops.creative_vision_runtime.frame_extraction.models import (
    VisionFrame,
    FrameSequence,
)
from market_ops.creative_vision_runtime.frame_extraction.extractor import (
    VideoFrameExtractor,
)
from market_ops.creative_vision_runtime.vision_asset.models import VisionAsset


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _create_test_video(path: Path, duration: float = 3.0) -> bool:
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=red:size=320x240:d={duration}",
            "-c:v", "libx264",
            "-t", str(duration),
            "-loglevel", "error",
            str(path),
        ], capture_output=True, timeout=15, check=True)
        return path.exists()
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════
# VisionFrame
# ════════════════════════════════════════════════════════════════════

class TestVisionFrame:
    """VisionFrame 数据模型测试。"""

    def test_create_minimal(self):
        frame = VisionFrame(frame_index=0, frame_path="/tmp/frame.jpg")
        assert frame.frame_index == 0
        assert frame.frame_path == "/tmp/frame.jpg"
        assert frame.frame_id.startswith("vf_")

    def test_create_with_features(self):
        frame = VisionFrame(
            frame_index=2,
            frame_path="/tmp/frame_002.jpg",
            timestamp_sec=1.5,
            ratio=0.4,
            brightness=0.65,
            contrast=0.42,
            edge_density=0.15,
            color_entropy=8.5,
            saturation=0.35,
        )
        assert frame.brightness == 0.65
        assert frame.edge_density == 0.15
        assert frame.timestamp_sec == 1.5

    def test_to_dict(self):
        frame = VisionFrame(
            frame_index=1,
            frame_path="/tmp/f.jpg",
            brightness=0.7,
            contrast=0.3,
        )
        d = frame.to_dict()
        assert d["frame_index"] == 1
        assert d["brightness"] == 0.7
        assert d["contrast"] == 0.3

    def test_from_dict(self):
        data = {
            "frame_id": "vf_test",
            "frame_index": 3,
            "frame_path": "/tmp/f3.jpg",
            "timestamp_sec": 2.0,
            "brightness": 0.5,
            "edge_density": 0.12,
        }
        frame = VisionFrame.from_dict(data)
        assert frame.frame_id == "vf_test"
        assert frame.frame_index == 3
        assert frame.brightness == 0.5

    def test_repr(self):
        frame = VisionFrame(frame_index=0, timestamp_sec=1.5)
        assert "idx=0" in repr(frame)
        assert "1.5" in repr(frame)


# ════════════════════════════════════════════════════════════════════
# FrameSequence
# ════════════════════════════════════════════════════════════════════

class TestFrameSequence:
    """FrameSequence 数据模型测试。"""

    def test_create_empty(self):
        seq = FrameSequence(
            creative_id="111",
            creative_asset_id="MW_VID_001",
            video_path="Y:/Eagle/test.mp4",
        )
        assert seq.creative_id == "111"
        assert seq.frame_count_loaded == 0
        assert seq.has_frames is False
        assert seq.sequence_id.startswith("fs_")

    def test_create_with_frames(self):
        frames = [
            VisionFrame(frame_index=i, brightness=0.5 + i * 0.1)
            for i in range(6)
        ]
        seq = FrameSequence(
            creative_id="111",
            video_path="Y:/Eagle/test.mp4",
            frames=frames,
            duration_sec=30.0,
            hook_score=0.8,
            comprehension_score=0.6,
            reward_score=0.7,
            status="extracted",
        )
        assert seq.frame_count_loaded == 6
        assert seq.has_frames is True
        assert seq.hook_score == 0.8
        assert seq.comprehension_score == 0.6
        assert seq.reward_score == 0.7
        assert seq.status == "extracted"

    def test_avg_properties(self):
        frames = [
            VisionFrame(frame_index=i, brightness=0.3 + i * 0.1, edge_density=0.1, saturation=0.4)
            for i in range(3)
        ]
        seq = FrameSequence(frames=frames)
        assert seq.avg_brightness == pytest.approx(0.4, abs=0.01)  # (0.3+0.4+0.5)/3
        assert seq.avg_edge_density == pytest.approx(0.1, abs=0.01)
        assert seq.avg_saturation == pytest.approx(0.4, abs=0.01)

    def test_to_dict(self):
        frames = [VisionFrame(frame_index=0, brightness=0.5)]
        seq = FrameSequence(
            creative_id="111",
            video_path="Y:/Eagle/test.mp4",
            frames=frames,
            duration_sec=10.0,
            resolution=(1920, 1080),
            hook_score=0.75,
            status="extracted",
        )
        d = seq.to_dict()
        assert len(d["frames"]) == 1
        assert d["resolution"] == [1920, 1080]
        assert d["hook_score"] == 0.75

    def test_from_dict(self):
        data = {
            "sequence_id": "fs_test",
            "creative_id": "222",
            "video_path": "Y:/Eagle/test.mp4",
            "frames": [
                {"frame_index": 0, "brightness": 0.6, "frame_path": "/tmp/f0.jpg"},
                {"frame_index": 1, "brightness": 0.7, "frame_path": "/tmp/f1.jpg"},
            ],
            "duration_sec": 15.0,
            "resolution": [1280, 720],
            "hook_score": 0.65,
            "status": "extracted",
        }
        seq = FrameSequence.from_dict(data)
        assert seq.sequence_id == "fs_test"
        assert seq.frame_count_loaded == 2
        assert seq.resolution == (1280, 720)

    def test_repr(self):
        seq = FrameSequence(
            creative_asset_id="MW_VID_001",
            frames=[VisionFrame(frame_index=0)],
            hook_score=0.55,
        )
        r = repr(seq)
        assert "MW_VID_001" in r
        assert "frames=1" in r


# ════════════════════════════════════════════════════════════════════
# VideoFrameExtractor
# ════════════════════════════════════════════════════════════════════

class TestVideoFrameExtractor:
    """VideoFrameExtractor 帧提取测试。"""

    @pytest.fixture
    def extractor(self, tmp_path):
        cache = tmp_path / "frames"
        return VideoFrameExtractor(cache_dir=str(cache))

    @pytest.fixture
    def test_video(self, tmp_path):
        video = tmp_path / "test_red.mp4"
        if _create_test_video(video, duration=3.0):
            return video
        pytest.skip("ffmpeg not available")

    @pytest.fixture
    def vision_asset(self, test_video):
        return VisionAsset(
            creative_id="111",
            creative_asset_id="MW_VID_TEST",
            video_path=str(test_video),
            eagle_filename="test_red.mp4",
            source_type="EAGLE",
            match_confidence=1.0,
            performance={"spend": 500, "revenue": 1000, "roas": 2.0},
        )

    def test_extract_single(self, extractor, vision_asset):
        seq = extractor.extract(vision_asset)
        assert seq is not None
        assert seq.frame_count_loaded == 6
        assert seq.duration_sec > 0
        assert seq.has_frames is True
        assert seq.status == "extracted"

        for i, frame in enumerate(seq.frames):
            assert frame.frame_index == i
            assert frame.ratio == pytest.approx(i * 0.2, abs=0.01)
            assert frame.frame_path.endswith(".jpg")
            assert frame.brightness > 0

    def test_extract_has_video_scores(self, extractor, vision_asset):
        seq = extractor.extract(vision_asset)
        assert seq is not None
        assert 0 <= seq.hook_score <= 1
        assert 0 <= seq.comprehension_score <= 1
        assert 0 <= seq.reward_score <= 1

    def test_extract_has_resolution(self, extractor, vision_asset):
        seq = extractor.extract(vision_asset)
        assert seq is not None
        assert seq.resolution[0] > 0
        assert seq.resolution[1] > 0

    def test_extract_batch(self, extractor, test_video, tmp_path):
        video2 = tmp_path / "test_blue.mp4"
        if not _create_test_video(video2, duration=2.0):
            pytest.skip("ffmpeg not available")

        assets = [
            VisionAsset(
                creative_id="111",
                creative_asset_id="MW_VID_001",
                video_path=str(test_video),
                eagle_filename="test_red.mp4",
                source_type="EAGLE",
                match_confidence=1.0,
            ),
            VisionAsset(
                creative_id="222",
                creative_asset_id="MW_VID_002",
                video_path=str(video2),
                eagle_filename="test_blue.mp4",
                source_type="EAGLE",
                match_confidence=1.0,
            ),
        ]

        sequences = extractor.extract_batch(assets)
        assert len(sequences) == 2
        assert extractor.extracted_count == 2

    def test_extract_file_not_found(self, extractor):
        asset = VisionAsset(
            creative_id="111",
            creative_asset_id="MW_VID_MISSING",
            video_path="Z:/nonexistent/video.mp4",
            eagle_filename="missing.mp4",
            source_type="EAGLE",
            match_confidence=1.0,
        )
        seq = extractor.extract(asset)
        assert seq is None
        assert extractor.failed_count == 1

    def test_is_cached(self, extractor, vision_asset):
        extractor.extract(vision_asset)
        assert extractor.is_cached(vision_asset.video_path) is True

    def test_get_frame_dir(self, extractor, vision_asset):
        extractor.extract(vision_asset)
        frame_dir = extractor.get_frame_dir(vision_asset.video_path)
        assert frame_dir.exists()
        assert frame_dir.is_dir()

    def test_extract_winners(self, extractor, test_video, tmp_path):
        video2 = tmp_path / "test_blue.mp4"
        if not _create_test_video(video2, duration=2.0):
            pytest.skip("ffmpeg not available")

        assets = [
            VisionAsset(
                creative_id="111",
                creative_asset_id="MW_VID_001",
                video_path=str(test_video),
                eagle_filename="test_red.mp4",
                source_type="EAGLE",
                match_confidence=1.0,
                lifecycle_status="WINNER",
            ),
            VisionAsset(
                creative_id="222",
                creative_asset_id="MW_VID_002",
                video_path=str(video2),
                eagle_filename="test_blue.mp4",
                source_type="EAGLE",
                match_confidence=1.0,
                lifecycle_status="TESTING",
            ),
        ]

        sequences = extractor.extract_winners(assets)
        assert len(sequences) == 1

    def test_sequence_frame_order(self, extractor, vision_asset):
        seq = extractor.extract(vision_asset)
        assert seq is not None
        for i, frame in enumerate(seq.frames):
            assert frame.frame_index == i
            assert frame.ratio == pytest.approx(i * 0.2, abs=0.01)

    def test_extractor_counts(self, extractor, vision_asset):
        extractor.extract(vision_asset)
        assert extractor.extracted_count == 1
        assert extractor.failed_count == 0

    def test_repr(self, extractor):
        assert "VideoFrameExtractor" in repr(extractor)


# ════════════════════════════════════════════════════════════════════
# Integration: VisionAsset → FrameSequence
# ════════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试：VisionAsset → FrameSequence 完整流程。"""

    def test_full_pipeline(self, tmp_path):
        video = tmp_path / "integration_test.mp4"
        if not _create_test_video(video, duration=3.0):
            pytest.skip("ffmpeg not available")

        cache = tmp_path / "frames"
        extractor = VideoFrameExtractor(cache_dir=str(cache))

        asset = VisionAsset(
            creative_id="111",
            creative_asset_id="MW_VID_INTEGRATION",
            video_path=str(video),
            eagle_filename="integration_test.mp4",
            source_type="EAGLE",
            match_confidence=1.0,
            performance={"spend": 1000, "revenue": 3000, "roas": 3.0},
            lifecycle_status="WINNER",
        )

        seq = extractor.extract(asset)
        assert seq is not None
        assert seq.frame_count_loaded == 6
        assert seq.status == "extracted"
        assert seq.duration_sec > 0
        assert seq.resolution[0] == 320
        assert seq.resolution[1] == 240

        for frame in seq.frames:
            assert frame.brightness > 0
            assert frame.frame_path.endswith(".jpg")

        assert 0 <= seq.hook_score <= 1
        assert 0 <= seq.comprehension_score <= 1
        assert 0 <= seq.reward_score <= 1

        d = seq.to_dict()
        restored = FrameSequence.from_dict(d)
        assert restored.frame_count_loaded == 6
        assert restored.hook_score == seq.hook_score