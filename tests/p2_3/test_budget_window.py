"""P0 ApprovalGate V2 — BudgetWindowTracker 单元测试。

Spec: docs/p0_approval_gate_v2_spec.md §5.1, §6, §10.1 (场景 5 超日累计), §12 (跨重启)

覆盖：
- 基础记账：record → get_cumulative
- 多 (game_id, action_type, day) 隔离
- 金额绝对值（负数记账）
- 持久化 JSONL（append-only，文件可读回）
- 跨重启重建（新实例 load 当日）
- IO 失败 fail-safe（不中断主流程）
- reset() 清内存不清文件
- 惰性加载（首次 get_cumulative 触发 load）
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.execution.approval.budget_window import (
    DEFAULT_BUDGET_WINDOW_FILENAME,
    BudgetWindowEntry,
    BudgetWindowTracker,
)


# ──────────────────────────────────────────────
# fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def tmp_tracker(tmp_path: Path) -> BudgetWindowTracker:
    """每个测试用独立临时目录的 tracker。"""
    return BudgetWindowTracker(audit_log_dir=str(tmp_path))


@pytest.fixture
def fixed_day() -> date:
    """固定日期，避免跨日测试 flaky。"""
    return date(2026, 8, 6)


# ──────────────────────────────────────────────
# 基础记账
# ──────────────────────────────────────────────


class TestBasicRecord:
    """record → get_cumulative 基础闭环。"""

    def test_empty_tracker_returns_zero(self, tmp_tracker, fixed_day):
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 0.0

    def test_single_record_accumulates(self, tmp_tracker, fixed_day):
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0

    def test_multiple_records_accumulate(self, tmp_tracker, fixed_day):
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tmp_tracker.record("g1", "SCALE_BUDGET", 50.0, "a2", day=fixed_day)
        tmp_tracker.record("g1", "SCALE_BUDGET", 20.0, "a3", day=fixed_day)
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 100.0

    def test_negative_amount_absoluted(self, tmp_tracker, fixed_day):
        """负数金额取绝对值记账（budget_impact 正=增负=减，但累计看绝对量）。"""
        tmp_tracker.record("g1", "SCALE_BUDGET", -40.0, "a1", day=fixed_day)
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 40.0

    def test_zero_amount_recorded(self, tmp_tracker, fixed_day):
        """0 金额也记账（PAUSE_CAMPAIGN 等 0 金额动作）。"""
        tmp_tracker.record("g1", "PAUSE_CAMPAIGN", 0.0, "a1", day=fixed_day)
        assert tmp_tracker.get_cumulative("g1", "PAUSE_CAMPAIGN", fixed_day) == 0.0


# ──────────────────────────────────────────────
# 维度隔离
# ──────────────────────────────────────────────


class TestDimensionIsolation:
    """(game_id, action_type, day) 三维度独立累计。"""

    def test_different_game_isolated(self, tmp_tracker, fixed_day):
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tmp_tracker.record("g2", "SCALE_BUDGET", 50.0, "a2", day=fixed_day)
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0
        assert tmp_tracker.get_cumulative("g2", "SCALE_BUDGET", fixed_day) == 50.0

    def test_different_action_isolated(self, tmp_tracker, fixed_day):
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tmp_tracker.record("g1", "PAUSE_CAMPAIGN", 0.0, "a2", day=fixed_day)
        tmp_tracker.record("g1", "DISABLE_NETWORK", 0.0, "a3", day=fixed_day)
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0
        assert tmp_tracker.get_cumulative("g1", "PAUSE_CAMPAIGN", fixed_day) == 0.0
        assert tmp_tracker.get_cumulative("g1", "DISABLE_NETWORK", fixed_day) == 0.0

    def test_different_day_isolated(self, tmp_tracker, fixed_day):
        other_day = fixed_day - timedelta(days=1)
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tmp_tracker.record("g1", "SCALE_BUDGET", 50.0, "a2", day=other_day)
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", other_day) == 50.0


# ──────────────────────────────────────────────
# 持久化
# ──────────────────────────────────────────────


class TestPersistence:
    """JSONL append-only 持久化。"""

    def test_record_creates_file(self, tmp_tracker, fixed_day, tmp_path):
        assert not os.path.exists(tmp_tracker.path)
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        assert os.path.exists(tmp_tracker.path)

    def test_file_path_under_audit_dir(self, tmp_path):
        tracker = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        assert tracker.path == os.path.join(str(tmp_path), DEFAULT_BUDGET_WINDOW_FILENAME)

    def test_jsonl_format(self, tmp_tracker, fixed_day):
        """每行是一条合法 JSON，含必需字段。"""
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        with open(tmp_tracker.path, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.readlines() if ln.strip()]
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["game_id"] == "g1"
        assert record["action_type"] == "SCALE_BUDGET"
        assert record["day"] == "2026-08-06"
        assert record["amount_usd"] == 30.0
        assert record["action_id"] == "a1"
        assert "ts" in record and record["ts"]

    def test_append_only_multiple_lines(self, tmp_tracker, fixed_day):
        """多次 record 追加多行，不覆盖。"""
        for i in range(5):
            tmp_tracker.record("g1", "SCALE_BUDGET", 10.0, f"a{i}", day=fixed_day)
        with open(tmp_tracker.path, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.readlines() if ln.strip()]
        assert len(lines) == 5
        # 每行都是合法 JSON
        for ln in lines:
            json.loads(ln)


# ──────────────────────────────────────────────
# 跨重启重建
# ──────────────────────────────────────────────


class TestReloadAcrossRestart:
    """Spec §12：新实例从 JSONL 重建当日累计。"""

    def test_new_instance_reloads_today(self, tmp_path, fixed_day):
        """进程 A record → 进程 B get_cumulative 应能读到。"""
        tracker_a = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        tracker_a.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tracker_a.record("g1", "SCALE_BUDGET", 50.0, "a2", day=fixed_day)
        # 模拟进程重启：新建实例（内存空）
        tracker_b = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        assert tracker_b.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 80.0

    def test_new_instance_isolates_other_day(self, tmp_path, fixed_day):
        """重启后 load 当日，不应把其它日数据算进来。"""
        other_day = fixed_day - timedelta(days=1)
        tracker_a = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        tracker_a.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tracker_a.record("g1", "SCALE_BUDGET", 999.0, "a2", day=other_day)
        tracker_b = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        assert tracker_b.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0
        assert tracker_b.get_cumulative("g1", "SCALE_BUDGET", other_day) == 999.0

    def test_corrupt_line_skipped(self, tmp_path, fixed_day):
        """JSONL 含损坏行时跳过，不抛异常。"""
        tracker_a = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        tracker_a.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        # 手动追加一行损坏 JSON
        with open(tracker_a.path, "a", encoding="utf-8") as f:
            f.write("not_a_json_line\n")
            f.write("{broken json\n")
        tracker_b = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        assert tracker_b.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0

    def test_missing_file_silent(self, tmp_path, fixed_day):
        """文件不存在时 get_cumulative 返回 0，不抛异常。"""
        tracker = BudgetWindowTracker(audit_log_dir=str(tmp_path / "nonexistent"))
        assert tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 0.0


# ──────────────────────────────────────────────
# IO 失败 fail-safe
# ──────────────────────────────────────────────


class TestIOFailSafe:
    """持久化失败不中断主流程（Spec §1 纪律）。"""

    def test_record_with_unwritable_dir_still_updates_memory(
        self, fixed_day, monkeypatch
    ):
        """目录不可写时，内存索引仍更新，仅 log warning。"""
        # 用一个不可能创建的路径（Windows 下空字符串或非法字符）
        tracker = BudgetWindowTracker(audit_log_dir="/nonexistent_root_xyz/path")
        # monkeypatch os.makedirs 抛异常模拟权限失败
        original_makedirs = os.makedirs

        def fake_makedirs(path, exist_ok=True):
            raise OSError("simulated permission denied")

        monkeypatch.setattr(os, "makedirs", fake_makedirs)
        # 不应抛异常
        tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        # 内存索引应已更新
        assert tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0
        # 恢复 makedirs 避免影响后续测试
        monkeypatch.setattr(os, "makedirs", original_makedirs)


# ──────────────────────────────────────────────
# reset
# ──────────────────────────────────────────────


class TestReset:
    """reset() 清内存不清文件。"""

    def test_reset_clears_memory(self, tmp_tracker, fixed_day):
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0
        tmp_tracker.reset()
        # reset 后内存空，但文件仍在；惰性 load 会重新读到
        # 这里 day 已被 _loaded_days 标记，reset 清掉了，所以会重新 load
        assert tmp_tracker.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0

    def test_reset_does_not_truncate_file(self, tmp_tracker, fixed_day):
        tmp_tracker.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        file_size_before = os.path.getsize(tmp_tracker.path)
        tmp_tracker.reset()
        file_size_after = os.path.getsize(tmp_tracker.path)
        assert file_size_before == file_size_after


# ──────────────────────────────────────────────
# 惰性加载
# ──────────────────────────────────────────────


class TestLazyLoad:
    """首次 get_cumulative 触发 load（Spec §12）。"""

    def test_first_get_triggers_load(self, tmp_path, fixed_day):
        """新建 tracker 直接 get_cumulative 应能读到既有文件。"""
        tracker_a = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        tracker_a.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tracker_b = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        # 未调用任何 load 方法，直接 get 应惰性加载
        assert tracker_b.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0

    def test_repeated_get_does_not_redouble(self, tmp_path, fixed_day):
        """重复 get_cumulative 不应重复累加（_loaded_days 防重）。"""
        tracker_a = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        tracker_a.record("g1", "SCALE_BUDGET", 30.0, "a1", day=fixed_day)
        tracker_b = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        for _ in range(5):
            assert tracker_b.get_cumulative("g1", "SCALE_BUDGET", fixed_day) == 30.0


# ──────────────────────────────────────────────
# BudgetWindowEntry 序列化
# ──────────────────────────────────────────────


class TestEntrySerialization:
    """BudgetWindowEntry to_dict / from_dict 往返。"""

    def test_roundtrip(self):
        entry = BudgetWindowEntry(
            game_id="g1",
            action_type="SCALE_BUDGET",
            day="2026-08-06",
            amount_usd=30.0,
            action_id="a1",
            ts="2026-08-06T14:30:00+00:00",
        )
        d = entry.to_dict()
        restored = BudgetWindowEntry.from_dict(d)
        assert restored.game_id == entry.game_id
        assert restored.action_type == entry.action_type
        assert restored.day == entry.day
        assert restored.amount_usd == entry.amount_usd
        assert restored.action_id == entry.action_id
        assert restored.ts == entry.ts

    def test_from_dict_missing_fields_uses_defaults(self):
        """缺失字段回退默认值，不抛异常。"""
        entry = BudgetWindowEntry.from_dict({})
        assert entry.game_id == ""
        assert entry.action_type == ""
        assert entry.day == ""
        assert entry.amount_usd == 0.0
        assert entry.action_id == ""

    def test_from_dict_invalid_amount_falls_back(self):
        """非法金额字段回退 0.0。"""
        entry = BudgetWindowEntry.from_dict({"amount_usd": "not_a_number"})
        assert entry.amount_usd == 0.0

    def test_post_init_fills_ts(self):
        entry = BudgetWindowEntry(
            game_id="g1",
            action_type="SCALE_BUDGET",
            day="2026-08-06",
            amount_usd=30.0,
            action_id="a1",
        )
        assert entry.ts != ""  # __post_init__ 自动填充
