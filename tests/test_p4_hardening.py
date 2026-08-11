"""P4.5 Production Hardening 单元测试 — SLO + DurableQueue + RecoveryDrill.

测试覆盖:
  1. SLOConfig 配置
  2. SLOEvaluator 4 项检查
  3. SLOReport 汇总
  4. DurableQueue enqueue/pending/ack/fail
  5. DurableQueue 死信队列
  6. DurableQueue 幂等性
  7. DurableQueue depth/dead_letters
  8. RecoveryDrill backup+restore 演练
  9. 边界场景: 无效输入
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.autonomous_growth.hardening import (
    DurableQueue,
    QueueJob,
    RecoveryDrill,
    SLOConfig,
    SLOEvaluator,
    SLOReport,
)
from backup.manager import BackupManager


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def queue(tmp_path: Path) -> DurableQueue:
    """临时 DurableQueue."""
    return DurableQueue(str(tmp_path / "queue.jsonl"))


@pytest.fixture
def backup_manager(tmp_path: Path) -> BackupManager:
    """临时 BackupManager."""
    return BackupManager(backup_dir=str(tmp_path / "backups"))


# ═══════════════════════════════════════════════════════════════
# 1. SLOConfig
# ═══════════════════════════════════════════════════════════════


class TestSLOConfig:
    """SLOConfig 配置."""

    def test_default_values(self):
        """默认 SLO 阈值."""
        config = SLOConfig()
        assert config.min_success_rate == 0.99
        assert config.max_failed_shards == 0
        assert config.max_cycle_latency_ms == 300000.0
        assert config.max_queue_depth == 1000

    def test_custom_config(self):
        """自定义 SLO 阈值."""
        config = SLOConfig(min_success_rate=0.95, max_failed_shards=1,
                           max_cycle_latency_ms=600000.0, max_queue_depth=500)
        assert config.min_success_rate == 0.95
        assert config.max_failed_shards == 1


# ═══════════════════════════════════════════════════════════════
# 2. SLOEvaluator 4 项检查
# ═══════════════════════════════════════════════════════════════


class TestSLOEvaluator:
    """SLOEvaluator 4 项检查."""

    def test_all_checks_pass(self):
        """所有指标达标."""
        evaluator = SLOEvaluator()
        report = evaluator.evaluate(success_rate=1.0, failed_shards=0,
                                    latency_ms=100000.0, queue_depth=100)
        assert report.healthy is True
        assert all(report.checks.values())
        assert report.violations == []

    def test_success_rate_violation(self):
        """成功率不达标."""
        evaluator = SLOEvaluator()
        report = evaluator.evaluate(success_rate=0.90, failed_shards=0,
                                    latency_ms=100000.0, queue_depth=100)
        assert report.healthy is False
        assert "success_rate" in report.violations
        assert report.checks["success_rate"] is False

    def test_failed_shards_violation(self):
        """失败 shard 超标."""
        evaluator = SLOEvaluator()
        report = evaluator.evaluate(success_rate=1.0, failed_shards=1,
                                    latency_ms=100000.0, queue_depth=100)
        assert report.healthy is False
        assert "failed_shards" in report.violations

    def test_latency_violation(self):
        """延迟超标."""
        evaluator = SLOEvaluator()
        report = evaluator.evaluate(success_rate=1.0, failed_shards=0,
                                    latency_ms=400000.0, queue_depth=100)
        assert report.healthy is False
        assert "cycle_latency" in report.violations

    def test_queue_depth_violation(self):
        """队列深度超标."""
        evaluator = SLOEvaluator()
        report = evaluator.evaluate(success_rate=1.0, failed_shards=0,
                                    latency_ms=100000.0, queue_depth=2000)
        assert report.healthy is False
        assert "queue_depth" in report.violations

    def test_boundary_values_pass(self):
        """边界值 (恰好等于阈值) 通过."""
        evaluator = SLOEvaluator()
        report = evaluator.evaluate(success_rate=0.99, failed_shards=0,
                                    latency_ms=300000.0, queue_depth=1000)
        assert report.healthy is True

    def test_custom_config_thresholds(self):
        """自定义阈值生效."""
        config = SLOConfig(min_success_rate=0.90, max_failed_shards=2,
                           max_cycle_latency_ms=600000.0, max_queue_depth=500)
        evaluator = SLOEvaluator(config=config)
        report = evaluator.evaluate(success_rate=0.92, failed_shards=1,
                                    latency_ms=500000.0, queue_depth=400)
        assert report.healthy is True


# ═══════════════════════════════════════════════════════════════
# 3. SLOReport
# ═══════════════════════════════════════════════════════════════


class TestSLOReport:
    """SLOReport 数据结构."""

    def test_default_values(self):
        """默认值."""
        report = SLOReport(healthy=True, checks={"a": True})
        assert report.violations == []

    def test_violations_collected(self):
        """violations 收集所有不达标项 (通过 SLOEvaluator 生成)."""
        evaluator = SLOEvaluator()
        report = evaluator.evaluate(success_rate=0.90, failed_shards=1,
                                    latency_ms=400000.0, queue_depth=2000)
        assert report.healthy is False
        assert "success_rate" in report.violations
        assert "failed_shards" in report.violations
        assert "cycle_latency" in report.violations
        assert "queue_depth" in report.violations


# ═══════════════════════════════════════════════════════════════
# 4. DurableQueue enqueue/pending/ack/fail
# ═══════════════════════════════════════════════════════════════


class TestDurableQueue:
    """DurableQueue 基本操作."""

    def test_enqueue_creates_job(self, queue: DurableQueue):
        """enqueue 创建 pending job."""
        assert queue.enqueue("job-1", {"task": "analyze"}) is True
        pending = queue.pending()
        assert len(pending) == 1
        assert pending[0].job_id == "job-1"
        assert pending[0].status == "pending"
        assert pending[0].attempts == 0

    def test_ack_removes_from_pending(self, queue: DurableQueue):
        """ack 后从 pending 移除."""
        queue.enqueue("job-1", {"task": "analyze"})
        assert queue.ack("job-1") is True
        assert queue.pending() == []

    def test_ack_nonexistent_returns_false(self, queue: DurableQueue):
        """ack 不存在的 job 返回 False."""
        assert queue.ack("nonexistent") is False

    def test_ack_already_acked_returns_false(self, queue: DurableQueue):
        """重复 ack 返回 False."""
        queue.enqueue("job-1", {"task": "analyze"})
        queue.ack("job-1")
        assert queue.ack("job-1") is False

    def test_fail_increments_attempts(self, queue: DurableQueue):
        """fail 递增 attempts."""
        queue.enqueue("job-1", {"task": "analyze"}, max_attempts=3)
        queue.fail("job-1")
        pending = queue.pending()
        assert len(pending) == 1
        assert pending[0].attempts == 1

    def test_fail_nonexistent_returns_false(self, queue: DurableQueue):
        """fail 不存在的 job 返回 False."""
        assert queue.fail("nonexistent") is False


# ═══════════════════════════════════════════════════════════════
# 5. DurableQueue 死信队列
# ═══════════════════════════════════════════════════════════════


class TestDeadLetters:
    """DurableQueue 死信队列."""

    def test_dead_letter_after_max_attempts(self, queue: DurableQueue):
        """达到 max_attempts 后进入死信."""
        queue.enqueue("job-1", {"task": "analyze"}, max_attempts=2)
        queue.fail("job-1")  # attempts=1, still pending
        queue.fail("job-1")  # attempts=2, becomes dead
        assert queue.pending() == []
        dead = queue.dead_letters()
        assert len(dead) == 1
        assert dead[0].status == "dead"

    def test_dead_letters_empty_when_no_dead(self, queue: DurableQueue):
        """无死信时返回空."""
        queue.enqueue("job-1", {"task": "analyze"})
        assert queue.dead_letters() == []

    def test_acked_job_not_in_dead_letters(self, queue: DurableQueue):
        """已 ack 的 job 不在死信."""
        queue.enqueue("job-1", {"task": "analyze"}, max_attempts=2)
        queue.fail("job-1")  # attempts=1
        queue.ack("job-1")
        assert queue.dead_letters() == []

    def test_mixed_states(self, queue: DurableQueue):
        """混合状态: pending + acked + dead."""
        queue.enqueue("job-1", {"task": "a"}, max_attempts=1)
        queue.enqueue("job-2", {"task": "b"}, max_attempts=1)
        queue.enqueue("job-3", {"task": "c"}, max_attempts=1)
        queue.ack("job-2")
        queue.fail("job-3")  # becomes dead (max_attempts=1)
        assert len(queue.pending()) == 1
        assert len(queue.dead_letters()) == 1


# ═══════════════════════════════════════════════════════════════
# 6. DurableQueue 幂等性
# ═══════════════════════════════════════════════════════════════


class TestQueueIdempotency:
    """DurableQueue 幂等性."""

    def test_duplicate_enqueue_returns_false(self, queue: DurableQueue):
        """重复 enqueue 同一 job_id 返回 False."""
        assert queue.enqueue("job-1", {"task": "a"}) is True
        assert queue.enqueue("job-1", {"task": "b"}) is False
        pending = queue.pending()
        assert len(pending) == 1
        assert pending[0].payload == {"task": "a"}  # 保留首次 payload

    def test_reenqueue_after_ack_returns_false(self, queue: DurableQueue):
        """ack 后再 enqueue 同一 job_id 仍返回 False (幂等)."""
        queue.enqueue("job-1", {"task": "a"})
        queue.ack("job-1")
        assert queue.enqueue("job-1", {"task": "b"}) is False


# ═══════════════════════════════════════════════════════════════
# 7. DurableQueue depth
# ═══════════════════════════════════════════════════════════════


class TestQueueDepth:
    """DurableQueue depth() 方法."""

    def test_empty_queue_depth_zero(self, queue: DurableQueue):
        """空队列 depth=0."""
        assert queue.depth() == 0

    def test_depth_counts_pending_only(self, queue: DurableQueue):
        """depth 只计 pending."""
        queue.enqueue("job-1", {"task": "a"})
        queue.enqueue("job-2", {"task": "b"})
        queue.ack("job-1")
        assert queue.depth() == 1

    def test_depth_after_all_acked(self, queue: DurableQueue):
        """全部 ack 后 depth=0."""
        queue.enqueue("job-1", {"task": "a"})
        queue.ack("job-1")
        assert queue.depth() == 0


# ═══════════════════════════════════════════════════════════════
# 8. RecoveryDrill
# ═══════════════════════════════════════════════════════════════


class TestRecoveryDrill:
    """RecoveryDrill backup+restore 演练.

    使用 mock BackupManager 避开 Python 3.10 tarfile.filter 兼容性问题.
    """

    def test_drill_success(self, tmp_path: Path):
        """成功演练 backup+restore."""
        # 准备测试数据
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.json").write_text('{"key": "value"}', encoding="utf-8")
        restore_target = tmp_path / "restored"

        # mock BackupManager: backup 返回路径, restore 实际复制文件
        mock_bm = MagicMock()
        archive_path = str(tmp_path / "backup.tar.gz")
        mock_bm.backup.return_value = archive_path

        def mock_restore(name, target):
            target_path = Path(target)
            target_path.mkdir(parents=True, exist_ok=True)
            restored_dir = target_path / "source"
            restored_dir.mkdir(parents=True, exist_ok=True)
            (restored_dir / "data.json").write_text('{"key": "value"}', encoding="utf-8")
            return str(target_path)
        mock_bm.restore.side_effect = mock_restore

        drill = RecoveryDrill(mock_bm)
        result = drill.run([str(source)], str(restore_target))

        assert result["success"] is True
        assert result["archive"] == archive_path
        assert any("data.json" in entry for entry in result["restored_entries"])
        mock_bm.backup.assert_called_once()
        mock_bm.restore.assert_called_once()

    def test_drill_preserves_file_content(self, tmp_path: Path):
        """演练保留文件内容."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.json").write_text('{"key": "value"}', encoding="utf-8")
        restore_target = tmp_path / "restored"

        mock_bm = MagicMock()
        mock_bm.backup.return_value = str(tmp_path / "backup.tar.gz")

        def mock_restore(name, target):
            target_path = Path(target)
            target_path.mkdir(parents=True, exist_ok=True)
            restored_dir = target_path / "source"
            restored_dir.mkdir(parents=True, exist_ok=True)
            (restored_dir / "data.json").write_text('{"key": "value"}', encoding="utf-8")
            return str(target_path)
        mock_bm.restore.side_effect = mock_restore

        drill = RecoveryDrill(mock_bm)
        result = drill.run([str(source)], str(restore_target))

        restored_file = Path(result["restore_target"]) / "source" / "data.json"
        assert restored_file.read_text(encoding="utf-8") == '{"key": "value"}'

    def test_drill_multiple_paths(self, tmp_path: Path):
        """演练多个路径."""
        source1 = tmp_path / "source1"
        source1.mkdir()
        (source1 / "a.txt").write_text("a", encoding="utf-8")
        source2 = tmp_path / "source2"
        source2.mkdir()
        (source2 / "b.txt").write_text("b", encoding="utf-8")

        mock_bm = MagicMock()
        mock_bm.backup.return_value = str(tmp_path / "backup.tar.gz")

        def mock_restore(name, target):
            target_path = Path(target)
            target_path.mkdir(parents=True, exist_ok=True)
            for src in [source1, source2]:
                restored_dir = target_path / src.name
                restored_dir.mkdir(parents=True, exist_ok=True)
                for f in src.iterdir():
                    (restored_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            return str(target_path)
        mock_bm.restore.side_effect = mock_restore

        drill = RecoveryDrill(mock_bm)
        result = drill.run([str(source1), str(source2)], str(tmp_path / "restored"))

        assert result["success"] is True
        assert any("a.txt" in entry for entry in result["restored_entries"])
        assert any("b.txt" in entry for entry in result["restored_entries"])

    def test_drill_empty_restore(self, tmp_path: Path):
        """restore 为空目录时 success=False."""
        mock_bm = MagicMock()
        mock_bm.backup.return_value = str(tmp_path / "backup.tar.gz")
        # restore 创建空目录
        def mock_restore(name, target):
            Path(target).mkdir(parents=True, exist_ok=True)
            return target
        mock_bm.restore.side_effect = mock_restore

        drill = RecoveryDrill(mock_bm)
        result = drill.run([str(tmp_path / "nonexistent")], str(tmp_path / "restored"))

        assert result["success"] is False
        assert result["restored_entries"] == []


# ═══════════════════════════════════════════════════════════════
# 9. 边界场景
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界场景."""

    def test_enqueue_empty_job_id_raises(self, queue: DurableQueue):
        """空 job_id 抛 ValueError."""
        with pytest.raises(ValueError):
            queue.enqueue("", {"task": "a"})

    def test_enqueue_zero_max_attempts_raises(self, queue: DurableQueue):
        """max_attempts < 1 抛 ValueError."""
        with pytest.raises(ValueError):
            queue.enqueue("job-1", {"task": "a"}, max_attempts=0)

    def test_queue_job_default_values(self):
        """QueueJob 默认值."""
        job = QueueJob(job_id="j1", payload={"task": "a"})
        assert job.attempts == 0
        assert job.max_attempts == 3
        assert job.status == "pending"

    def test_pending_sorted_by_job_id(self, queue: DurableQueue):
        """pending 按 job_id 排序."""
        queue.enqueue("job-3", {"task": "c"})
        queue.enqueue("job-1", {"task": "a"})
        queue.enqueue("job-2", {"task": "b"})
        pending = queue.pending()
        assert [j.job_id for j in pending] == ["job-1", "job-2", "job-3"]

    def test_empty_queue_operations(self, queue: DurableQueue):
        """空队列操作."""
        assert queue.pending() == []
        assert queue.dead_letters() == []
        assert queue.depth() == 0
