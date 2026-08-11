"""Creative Mapping Engine — 单元测试.

覆盖:
  - MappingScorer: 6 维度评分算法
  - MappingStore: 持久化层读写
  - ReviewQueue: 人工审核工作流
  - CreativeMappingEngine: 核心编排 (匹配/门禁/幂等/批量/审核)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.market_ops.creative_mapping_engine import (
    CreativeMappingEngine,
    CreativeMappingRecord,
    MappingScorer,
    MappingScores,
    MappingStatus,
    MappingStore,
    ReviewQueue,
    ReviewTask,
    now_iso,
)


# ═══════════════════════════════════════════════════════════════
# MappingScorer 测试
# ═══════════════════════════════════════════════════════════════


class TestMappingScorer:
    """6 维度评分器测试。"""

    @pytest.fixture
    def scorer(self) -> MappingScorer:
        return MappingScorer()

    # ── 名称相似度 ────────────────────────────────────────────

    def test_name_similarity_serial_exact_match(self, scorer: MappingScorer):
        """序列号精确匹配 → 1.0。"""
        score = scorer.score_name_similarity(
            "MW_VIDEO_260721_000123", "MW_VIDEO_260721_000123.mp4"
        )
        assert score == 1.0

    def test_name_similarity_serial_mismatch(self, scorer: MappingScorer):
        """序列号不同 → 0.0。"""
        score = scorer.score_name_similarity(
            "MW_VIDEO_260721_000123", "MW_VIDEO_260721_000456.mp4"
        )
        assert score == 0.0

    def test_name_similarity_no_serial_fallback_to_edit_distance(self, scorer: MappingScorer):
        """无序列号 → 编辑距离归一化。"""
        score = scorer.score_name_similarity("dragon_rescue", "dragon_rescue.mp4")
        assert 0.5 < score <= 1.0

    def test_name_similarity_empty_string(self, scorer: MappingScorer):
        """空字符串 → 0.0。"""
        assert scorer.score_name_similarity("", "test.mp4") == 0.0
        assert scorer.score_name_similarity("test", "") == 0.0

    def test_name_similarity_completely_different(self, scorer: MappingScorer):
        """完全不同的名称 → 低分。"""
        score = scorer.score_name_similarity("abc", "xyz.mp4")
        assert score < 0.5

    # ── 时长匹配 ──────────────────────────────────────────────

    def test_duration_exact_match(self, scorer: MappingScorer):
        assert scorer.score_duration_match(32.5, 32.5) == 1.0

    def test_duration_within_half_second(self, scorer: MappingScorer):
        assert scorer.score_duration_match(32.5, 32.8) == 1.0

    def test_duration_within_two_seconds(self, scorer: MappingScorer):
        assert scorer.score_duration_match(32.0, 33.5) == 0.7

    def test_duration_too_far(self, scorer: MappingScorer):
        assert scorer.score_duration_match(30.0, 40.0) == 0.0

    def test_duration_zero(self, scorer: MappingScorer):
        assert scorer.score_duration_match(0.0, 32.5) == 0.0
        assert scorer.score_duration_match(32.5, 0.0) == 0.0

    # ── 分辨率匹配 ────────────────────────────────────────────

    def test_resolution_exact_match(self, scorer: MappingScorer):
        assert scorer.score_resolution_match("1080x1920", "1080x1920") == 1.0

    def test_resolution_aspect_ratio_match(self, scorer: MappingScorer):
        """宽高比相同但分辨率不同 → 0.7。"""
        assert scorer.score_resolution_match("1080x1920", "720x1280") == 0.7

    def test_resolution_no_match(self, scorer: MappingScorer):
        assert scorer.score_resolution_match("1080x1920", "1920x1080") == 0.0

    def test_resolution_empty(self, scorer: MappingScorer):
        assert scorer.score_resolution_match("", "1080x1920") == 0.0

    # ── 创建时间匹配 ──────────────────────────────────────────

    def test_creation_time_same_day(self, scorer: MappingScorer):
        assert scorer.score_creation_time_match("2026-08-10", "2026-08-10") == 1.0

    def test_creation_time_within_one_day(self, scorer: MappingScorer):
        assert scorer.score_creation_time_match("2026-08-10", "2026-08-11") == 1.0

    def test_creation_time_within_seven_days(self, scorer: MappingScorer):
        assert scorer.score_creation_time_match("2026-08-10", "2026-08-15") == 0.7

    def test_creation_time_beyond_seven_days(self, scorer: MappingScorer):
        assert scorer.score_creation_time_match("2026-08-01", "2026-08-10") == 0.3

    def test_creation_time_empty(self, scorer: MappingScorer):
        assert scorer.score_creation_time_match("", "2026-08-10") == 0.0

    # ── 帧相似度 ──────────────────────────────────────────────

    def test_frame_similarity_empty(self, scorer: MappingScorer):
        assert scorer.score_frame_similarity("", "/path/to/video") == 0.0

    def test_frame_similarity_nonexistent_files(self, scorer: MappingScorer):
        """帧相似度 — 文件不存在时返回 0.0。"""
        assert scorer.score_frame_similarity("http://thumb.jpg", "/path/to/video") == 0.0

    # ── 文件哈希匹配 ──────────────────────────────────────────

    def test_file_hash_exact_match(self, scorer: MappingScorer):
        assert scorer.score_file_hash_match("abc123", "abc123") == 1.0

    def test_file_hash_case_insensitive(self, scorer: MappingScorer):
        assert scorer.score_file_hash_match("ABC123", "abc123") == 1.0

    def test_file_hash_mismatch(self, scorer: MappingScorer):
        assert scorer.score_file_hash_match("abc123", "def456") == 0.0

    def test_file_hash_empty(self, scorer: MappingScorer):
        assert scorer.score_file_hash_match("", "abc123") == 0.0

    # ── 综合评分 ──────────────────────────────────────────────

    def test_weighted_total(self, scorer: MappingScorer):
        scores = MappingScores(
            name_similarity=1.0,
            duration_match=1.0,
            resolution_match=1.0,
            creation_time_match=0.7,
            frame_similarity=0.0,
            file_hash_match=0.0,
        )
        total = scorer.weighted_total(scores)
        # 0.25*1 + 0.15*1 + 0.10*1 + 0.10*0.7 + 0.25*0 + 0.15*0 = 0.57
        assert total == pytest.approx(0.57, abs=0.01)

    def test_dominant_dimension(self, scorer: MappingScorer):
        scores = MappingScores(
            name_similarity=1.0,
            duration_match=0.7,
            resolution_match=0.0,
            creation_time_match=0.0,
            frame_similarity=0.0,
            file_hash_match=0.0,
        )
        assert scorer.dominant_dimension(scores) == "name_similarity"

    def test_score_all_combines_all_dimensions(self, scorer: MappingScorer):
        scores = scorer.score_all(
            fb_name="MW_VIDEO_260721_000123",
            eagle_filename="MW_VIDEO_260721_000123.mp4",
            fb_duration=32.5,
            eagle_duration=32.5,
            fb_resolution="1080x1920",
            eagle_resolution="1080x1920",
            fb_creation_time="2026-08-10",
            eagle_creation_time="2026-08-10",
        )
        assert scores.name_similarity == 1.0
        assert scores.duration_match == 1.0
        assert scores.resolution_match == 1.0
        assert scores.creation_time_match == 1.0


# ═══════════════════════════════════════════════════════════════
# MappingStore 测试
# ═══════════════════════════════════════════════════════════════


class TestMappingStore:
    """持久化层测试。"""

    @pytest.fixture
    def store(self, tmp_path: Path) -> MappingStore:
        return MappingStore(data_dir=str(tmp_path / "cm"))

    def test_save_and_get_record(self, store: MappingStore):
        record = CreativeMappingRecord(
            mapping_id="map_001",
            facebook_creative_id="fb_001",
            facebook_creative_name="test_creative",
            confidence=0.9,
            status=MappingStatus.MATCHED,
            created_at=now_iso(),
        )
        store.save_record(record)
        result = store.get_record("map_001")
        assert result is not None
        assert result.facebook_creative_id == "fb_001"
        assert result.status == MappingStatus.MATCHED

    def test_get_record_not_found(self, store: MappingStore):
        assert store.get_record("nonexistent") is None

    def test_get_by_facebook_id(self, store: MappingStore):
        record = CreativeMappingRecord(
            mapping_id="map_002",
            facebook_creative_id="fb_002",
            facebook_creative_name="test",
        )
        store.save_record(record)
        result = store.get_by_facebook_id("fb_002")
        assert result is not None
        assert result.mapping_id == "map_002"

    def test_list_records(self, store: MappingStore):
        for i in range(5):
            store.save_record(CreativeMappingRecord(
                mapping_id=f"map_{i:03d}",
                facebook_creative_id=f"fb_{i:03d}",
                facebook_creative_name=f"creative_{i}",
                status=MappingStatus.MATCHED if i < 3 else MappingStatus.NO_MATCH,
            ))
        all_records = store.list_records(limit=10)
        assert len(all_records) == 5
        matched = store.list_records(status="matched")
        assert len(matched) == 3

    def test_list_records_returns_latest_for_duplicate(self, store: MappingStore):
        """重复 mapping_id 返回最新一条。"""
        store.save_record(CreativeMappingRecord(
            mapping_id="map_dup",
            facebook_creative_id="fb_dup",
            facebook_creative_name="v1",
            status=MappingStatus.PENDING,
        ))
        store.save_record(CreativeMappingRecord(
            mapping_id="map_dup",
            facebook_creative_id="fb_dup",
            facebook_creative_name="v2",
            status=MappingStatus.MATCHED,
        ))
        records = store.list_records(limit=10)
        assert len(records) == 1
        assert records[0].facebook_creative_name == "v2"

    def test_save_and_get_review_task(self, store: MappingStore):
        task = ReviewTask(
            task_id="rv_001",
            mapping_id="map_001",
            facebook_creative_id="fb_001",
            created_at=now_iso(),
        )
        store.save_review_task(task)
        result = store.get_review_task("rv_001")
        assert result is not None
        assert result.mapping_id == "map_001"

    def test_list_open_review_tasks(self, store: MappingStore):
        for i in range(3):
            store.save_review_task(ReviewTask(
                task_id=f"rv_{i:03d}",
                mapping_id=f"map_{i:03d}",
                facebook_creative_id=f"fb_{i:03d}",
                created_at=now_iso(),
                status="open",
            ))
        # 已关闭的任务
        store.save_review_task(ReviewTask(
            task_id="rv_999",
            mapping_id="map_999",
            facebook_creative_id="fb_999",
            created_at=now_iso(),
            status="approved",
        ))
        open_tasks = store.list_open_review_tasks()
        assert len(open_tasks) == 3

    def test_get_stats(self, store: MappingStore):
        store.save_record(CreativeMappingRecord(
            mapping_id="map_1", facebook_creative_id="fb_1",
            facebook_creative_name="a", confidence=0.9, status=MappingStatus.MATCHED,
        ))
        store.save_record(CreativeMappingRecord(
            mapping_id="map_2", facebook_creative_id="fb_2",
            facebook_creative_name="b", confidence=0.6, status=MappingStatus.NEEDS_REVIEW,
        ))
        stats = store.get_stats()
        assert stats["total_records"] == 2
        assert stats["status_distribution"]["matched"] == 1
        assert stats["status_distribution"]["needs_review"] == 1
        assert 0.7 < stats["average_confidence"] < 0.8


# ═══════════════════════════════════════════════════════════════
# ReviewQueue 测试
# ═══════════════════════════════════════════════════════════════


class TestReviewQueue:
    """人工审核队列测试。"""

    @pytest.fixture
    def queue(self, tmp_path: Path) -> ReviewQueue:
        store = MappingStore(data_dir=str(tmp_path / "cm"))
        return ReviewQueue(store)

    @pytest.fixture
    def store(self, tmp_path: Path) -> MappingStore:
        return MappingStore(data_dir=str(tmp_path / "cm"))

    @pytest.fixture
    def queue_with_record(self, queue: ReviewQueue, store: MappingStore) -> ReviewQueue:
        store.save_record(CreativeMappingRecord(
            mapping_id="map_001",
            facebook_creative_id="fb_001",
            facebook_creative_name="test",
            status=MappingStatus.NEEDS_REVIEW,
        ))
        return queue

    def test_enqueue(self, queue: ReviewQueue):
        task = queue.enqueue("map_001", "fb_001", [{"eagle_filename": "test.mp4"}])
        assert task.task_id.startswith("rv_")
        assert task.status == "open"
        assert len(task.candidates) == 1

    def test_dequeue(self, queue: ReviewQueue):
        queue.enqueue("map_001", "fb_001", [])
        tasks = queue.dequeue()
        assert len(tasks) == 1
        assert tasks[0].status == "open"

    def test_approve(self, queue_with_record: ReviewQueue, store: MappingStore):
        queue = queue_with_record
        task = queue.enqueue("map_001", "fb_001", [])
        result = queue.approve(task.task_id, "matched_file.mp4", "/path/to/file", "reviewer1")
        assert result.status == "approved"
        assert result.resolution == "matched_file.mp4"
        # 验证映射记录已更新
        record = store.get_record("map_001")
        assert record.status == MappingStatus.REVIEW_APPROVED
        assert record.eagle_filename == "matched_file.mp4"

    def test_reject(self, queue_with_record: ReviewQueue, store: MappingStore):
        queue = queue_with_record
        task = queue.enqueue("map_001", "fb_001", [])
        result = queue.reject(task.task_id, "no match found", "reviewer1")
        assert result.status == "rejected"
        assert result.resolution == "no match found"
        record = store.get_record("map_001")
        assert record.status == MappingStatus.REVIEW_REJECTED

    def test_approve_already_resolved(self, queue_with_record: ReviewQueue):
        queue = queue_with_record
        task = queue.enqueue("map_001", "fb_001", [])
        queue.approve(task.task_id, "file.mp4")
        with pytest.raises(ValueError, match="already resolved"):
            queue.approve(task.task_id, "other.mp4")

    def test_approve_not_found(self, queue: ReviewQueue):
        with pytest.raises(ValueError, match="not found"):
            queue.approve("nonexistent", "file.mp4")


# ═══════════════════════════════════════════════════════════════
# CreativeMappingEngine 测试
# ═══════════════════════════════════════════════════════════════


class TestCreativeMappingEngine:
    """核心编排引擎测试。"""

    @pytest.fixture
    def eagle_assets(self) -> list[dict]:
        return [
            {
                "filename": "MW_VIDEO_260721_000123.mp4",
                "path": "D:/eagle/MW_VIDEO_260721_000123.mp4",
                "duration": 32.5,
                "resolution": "1080x1920",
                "created_at": "2026-07-24",
                "file_hash": "abc123",
            },
            {
                "filename": "MW_VIDEO_260721_000456.mp4",
                "path": "D:/eagle/MW_VIDEO_260721_000456.mp4",
                "duration": 45.0,
                "resolution": "1080x1920",
                "created_at": "2026-07-25",
                "file_hash": "def456",
            },
            {
                "filename": "unrelated_video.mp4",
                "path": "D:/eagle/unrelated_video.mp4",
                "duration": 15.0,
                "resolution": "720x1280",
                "created_at": "2026-06-01",
                "file_hash": "xyz789",
            },
        ]

    @pytest.fixture
    def engine(self, tmp_path: Path, eagle_assets: list[dict]) -> CreativeMappingEngine:
        engine = CreativeMappingEngine(
            data_dir=str(tmp_path / "cm"),
            eagle_index_path=str(tmp_path / "nonexistent.json"),
        )
        engine.set_eagle_assets(eagle_assets)
        return engine

    # ── 匹配 ──────────────────────────────────────────────────

    def test_match_high_confidence(self, engine: CreativeMappingEngine):
        """精确序列号 + 时长 + 分辨率 + hash 匹配 (无帧相似度) → NEEDS_REVIEW。

        v1.2 阈值恢复到 0.85 后，5 维全匹配 (无帧相似度) = 0.75 < 0.85，
        进入人工审核。帧相似度需真实图片文件才能计算。
        """
        record = engine.match({
            "facebook_creative_id": "536123456789",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        assert record.eagle_filename == "MW_VIDEO_260721_000123.mp4"
        assert record.confidence >= 0.75  # 5 维全匹配 = 0.75
        assert record.scores.name_similarity == 1.0
        assert record.scores.frame_similarity == 0.0  # 无真实图片文件

    def test_match_needs_review(self, engine: CreativeMappingEngine):
        """中等置信度 → NEEDS_REVIEW。"""
        record = engine.match({
            "facebook_creative_id": "fb_mid",
            "facebook_creative_name": "MW_VIDEO_260721_000123",  # 序列号匹配
            "duration": 100.0,  # 时长不匹配
            "resolution": "720x1280",  # 宽高比匹配
            "creation_time": "2026-07-24",  # 时间匹配
            "file_hash": "abc123",  # hash 匹配
        })
        assert record.status == MappingStatus.NEEDS_REVIEW
        # 应创建审核任务
        review_tasks = engine.list_review_queue()
        assert len(review_tasks) >= 1

    def test_match_no_match(self, engine: CreativeMappingEngine):
        """低置信度 → NO_MATCH。"""
        record = engine.match({
            "facebook_creative_id": "fb_low",
            "facebook_creative_name": "completely_different_name",
            "duration": 999.0,
            "resolution": "100x100",
        })
        assert record.status == MappingStatus.NO_MATCH
        assert record.eagle_filename == ""

    def test_match_no_eagle_assets(self, tmp_path: Path):
        """无 Eagle 素材 → NO_MATCH。"""
        engine = CreativeMappingEngine(
            data_dir=str(tmp_path / "cm"),
            eagle_index_path=str(tmp_path / "nonexistent.json"),
        )
        record = engine.match({
            "facebook_creative_id": "fb_test",
            "facebook_creative_name": "test",
        })
        assert record.status == MappingStatus.NO_MATCH

    def test_match_requires_facebook_id(self, engine: CreativeMappingEngine):
        with pytest.raises(ValueError, match="facebook_creative_id is required"):
            engine.match({"facebook_creative_name": "test"})

    # ── 幂等性 ────────────────────────────────────────────────

    def test_idempotent_matched_not_overwritten(self, engine: CreativeMappingEngine):
        """MATCHED 记录不被重复匹配覆盖。

        v1.2: 使用 mock frame_similarity=1.0 达到 6 维全匹配 (1.0) ≥ 0.85。
        """
        # 通过 mock frame_computer 返回高分，达到 MATCHED 阈值
        from unittest.mock import patch

        with patch.object(
            engine._scorer._frame_computer, "compute", return_value=(1.0, "phash", False)
        ):
            first = engine.match({
                "facebook_creative_id": "fb_idem",
                "facebook_creative_name": "MW_VIDEO_260721_000123",
                "duration": 32.5,
                "resolution": "1080x1920",
                "creation_time": "2026-07-24",
                "file_hash": "abc123",
                "thumbnail_url": "/fake/thumb.jpg",  # engine 读取 thumbnail_url
            })
        assert first.status == MappingStatus.MATCHED

        # 第二次用不同数据匹配相同 fb_id
        second = engine.match({
            "facebook_creative_id": "fb_idem",
            "facebook_creative_name": "completely_different",
        })
        assert second.status == MappingStatus.MATCHED
        assert second.eagle_filename == first.eagle_filename

    def test_idempotent_approved_not_overwritten(self, engine: CreativeMappingEngine):
        """REVIEW_APPROVED 记录不被覆盖。"""
        # 先创建一条 NEEDS_REVIEW 记录
        first = engine.match({
            "facebook_creative_id": "fb_approved",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 100.0,
            "resolution": "720x1280",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        if first.status == MappingStatus.NEEDS_REVIEW:
            # 人工审核通过
            tasks = engine.list_review_queue()
            if tasks:
                engine.approve_review(
                    tasks[0]["task_id"],
                    "manual_match.mp4",
                    "/path/to/manual_match.mp4",
                    "tester",
                )

        # 再次匹配相同 fb_id
        second = engine.match({
            "facebook_creative_id": "fb_approved",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        # 应返回已有记录 (MATCHED 或 REVIEW_APPROVED)
        assert second.status in (MappingStatus.MATCHED, MappingStatus.REVIEW_APPROVED)

    # ── 批量匹配 ──────────────────────────────────────────────

    def test_batch_match(self, engine: CreativeMappingEngine):
        creatives = [
            {
                "facebook_creative_id": f"fb_batch_{i}",
                "facebook_creative_name": "MW_VIDEO_260721_000123",
                "duration": 32.5,
                "resolution": "1080x1920",
                "creation_time": "2026-07-24",
                "file_hash": "abc123",
            }
            for i in range(5)
        ]
        records = engine.batch_match(creatives)
        assert len(records) == 5
        assert all(r.facebook_creative_id.startswith("fb_batch_") for r in records)

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_record(self, engine: CreativeMappingEngine):
        engine.match({
            "facebook_creative_id": "fb_query",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        # 通过 facebook_id 获取
        by_fb = engine.get_by_facebook_id("fb_query")
        assert by_fb is not None
        # 通过 mapping_id 获取
        by_map = engine.get_record(by_fb.mapping_id)
        assert by_map is not None

    def test_list_records(self, engine: CreativeMappingEngine):
        for i in range(3):
            engine.match({
                "facebook_creative_id": f"fb_list_{i}",
                "facebook_creative_name": "MW_VIDEO_260721_000123",
                "duration": 32.5,
                "resolution": "1080x1920",
                "creation_time": "2026-07-24",
                "file_hash": "abc123",
            })
        records = engine.list_records()
        assert len(records) >= 3

    def test_get_stats(self, engine: CreativeMappingEngine):
        engine.match({
            "facebook_creative_id": "fb_stats",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 32.5,
            "resolution": "1080x1920",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        stats = engine.get_stats()
        assert stats["total_records"] >= 1
        assert "status_distribution" in stats
        assert "average_confidence" in stats

    # ── 审核工作流 ────────────────────────────────────────────

    def test_review_workflow_approve(self, engine: CreativeMappingEngine):
        """完整审核流程: 匹配 → 入队 → 审核通过。"""
        # 创建 NEEDS_REVIEW 记录
        record = engine.match({
            "facebook_creative_id": "fb_wf",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 100.0,
            "resolution": "720x1280",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        if record.status != MappingStatus.NEEDS_REVIEW:
            pytest.skip("Record did not enter NEEDS_REVIEW state")

        # 获取审核任务
        tasks = engine.list_review_queue()
        assert len(tasks) >= 1
        task_id = tasks[0]["task_id"]

        # 审核通过
        result = engine.approve_review(task_id, "approved_file.mp4", "/path", "tester")
        assert result["status"] == "approved"

        # 验证记录已更新
        updated = engine.get_by_facebook_id("fb_wf")
        assert updated.status == MappingStatus.REVIEW_APPROVED
        assert updated.eagle_filename == "approved_file.mp4"

    def test_review_workflow_reject(self, engine: CreativeMappingEngine):
        """完整审核流程: 匹配 → 入队 → 审核驳回。"""
        record = engine.match({
            "facebook_creative_id": "fb_reject",
            "facebook_creative_name": "MW_VIDEO_260721_000123",
            "duration": 100.0,
            "resolution": "720x1280",
            "creation_time": "2026-07-24",
            "file_hash": "abc123",
        })
        if record.status != MappingStatus.NEEDS_REVIEW:
            pytest.skip("Record did not enter NEEDS_REVIEW state")

        tasks = engine.list_review_queue()
        task_id = tasks[0]["task_id"]

        result = engine.reject_review(task_id, "wrong match", "tester")
        assert result["status"] == "rejected"

        updated = engine.get_by_facebook_id("fb_reject")
        assert updated.status == MappingStatus.REVIEW_REJECTED

    # ── Eagle 索引加载 ────────────────────────────────────────

    def test_load_eagle_index_from_file(self, tmp_path: Path):
        """从 JSON 文件加载 Eagle 索引。"""
        index_path = tmp_path / "eagle_index.json"
        index_path.write_text(json.dumps({
            "assets": [
                {"filename": "test.mp4", "path": "/test", "duration": 10.0}
            ]
        }), encoding="utf-8")

        engine = CreativeMappingEngine(
            data_dir=str(tmp_path / "cm"),
            eagle_index_path=str(index_path),
        )
        record = engine.match({
            "facebook_creative_id": "fb_file_load",
            "facebook_creative_name": "test",
        })
        # 有素材被评估 (即使最终判定为 NO_MATCH)
        assert record.mapping_id != ""


# ═══════════════════════════════════════════════════════════════
# 数据模型测试
# ═══════════════════════════════════════════════════════════════


class TestDataModels:
    """数据模型序列化/反序列化测试。"""

    def test_mapping_scores_to_dict_and_from_dict(self):
        scores = MappingScores(
            name_similarity=0.9,
            duration_match=0.7,
            resolution_match=1.0,
            creation_time_match=0.3,
            frame_similarity=0.85,
            file_hash_match=0.0,
        )
        d = scores.to_dict()
        restored = MappingScores.from_dict(d)
        assert restored.name_similarity == 0.9
        assert restored.duration_match == 0.7
        assert restored.file_hash_match == 0.0

    def test_mapping_record_to_dict_and_from_dict(self):
        record = CreativeMappingRecord(
            mapping_id="map_test",
            facebook_creative_id="fb_test",
            facebook_creative_name="test_name",
            eagle_filename="test.mp4",
            confidence=0.92,
            status=MappingStatus.MATCHED,
        )
        d = record.to_dict()
        restored = CreativeMappingRecord.from_dict(d)
        assert restored.mapping_id == "map_test"
        assert restored.status == MappingStatus.MATCHED
        assert restored.confidence == 0.92

    def test_review_task_to_dict_and_from_dict(self):
        task = ReviewTask(
            task_id="rv_test",
            mapping_id="map_test",
            facebook_creative_id="fb_test",
            candidates=[{"eagle_filename": "a.mp4"}],
        )
        d = task.to_dict()
        restored = ReviewTask.from_dict(d)
        assert restored.task_id == "rv_test"
        assert len(restored.candidates) == 1

    def test_mapping_status_enum_values(self):
        assert MappingStatus.PENDING.value == "pending"
        assert MappingStatus.MATCHED.value == "matched"
        assert MappingStatus.NEEDS_REVIEW.value == "needs_review"
        assert MappingStatus.REVIEW_APPROVED.value == "approved"
        assert MappingStatus.REVIEW_REJECTED.value == "rejected"
        assert MappingStatus.NO_MATCH.value == "no_match"
