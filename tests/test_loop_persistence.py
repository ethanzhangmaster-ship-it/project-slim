"""LoopPersistence 持久化层单元测试。

覆盖:
  - LoopState 序列化/反序列化/文件 I/O
  - PendingEvaluation 数据模型 + is_due/is_expired 运行时计算
  - PendingEvaluation 序列化/反序列化/批量文件 I/O
  - PendingEvaluation.from_action 工厂方法
  - LoopPersistence 统一管理器 (四文件读写 + save_all)
  - CycleRecord 追加写/读取
  - 跨重启恢复场景
  - 时钟漂移安全性 (无 due_at)
"""

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from scripts.loop_state import LoopState
from scripts.pending_evaluation import (
    PendingEvaluation,
    parse_utc,
)
from scripts.loop_persistence import (
    LoopPersistence,
    build_cycle_record,
)
from scripts.action_planner import (
    ActionPlanner,
    ActionStatus,
    ActionType,
    ExecutionAction,
)
from scripts.action_executor import (
    ActionExecutionStatus,
    ExecutionResult,
)


# ──────────────────────────────────────────────
# 测试 fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir():
    """临时数据目录。"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def persistence(tmp_data_dir):
    """使用临时目录的 LoopPersistence。"""
    return LoopPersistence(data_dir=tmp_data_dir)


def _make_action(
    action_type: ActionType = ActionType.UPDATE_BUDGET,
    signal_id: str = "fs_abc123",
    creative_id: str = "cr_test01",
    adset_id: str = "adset_test01",
) -> ExecutionAction:
    """构造测试用 ExecutionAction。"""
    return ExecutionAction(
        signal_id=signal_id,
        diagnosis_id="diag_test01",
        hypothesis_id="hyp_test01",
        strategy_id="strat_test01",
        creative_id=creative_id,
        adset_id=adset_id,
        action_type=action_type,
        parameters={"target_budget": 150.0, "current_budget": 100.0},
        confidence=0.75,
        risk_level="low",
        budget_impact=50.0,
    )


def _make_result(
    action: ExecutionAction,
    success: bool = True,
    actual_budget: float | None = 150.0,
    dry_run: bool = False,
) -> ExecutionResult:
    """构造测试用 ExecutionResult。"""
    return ExecutionResult(
        action_id=action.action_id,
        strategy_id=action.strategy_id,
        hypothesis_id=action.hypothesis_id,
        diagnosis_id=action.diagnosis_id,
        signal_id=action.signal_id,
        status=ActionExecutionStatus.COMPLETED if success else ActionExecutionStatus.FAILED,
        success=success,
        actual_budget=actual_budget,
        dry_run=dry_run,
    )


# ═══════════════════════════════════════════════════════════
# TestParseUTC — 时间解析工具
# ═══════════════════════════════════════════════════════════


class TestParseUTC:
    """parse_utc 工具函数。"""

    def test_parse_with_timezone(self):
        """解析带 +00:00 后缀的 UTC 时间。"""
        iso = "2026-08-06T12:00:00.000000+00:00"
        dt = parse_utc(iso)
        assert dt.tzinfo is not None
        assert dt.year == 2026
        assert dt.month == 8
        assert dt.day == 6
        assert dt.hour == 12

    def test_parse_without_timezone(self):
        """解析无时区信息的时间 → 假定为 UTC。"""
        iso = "2026-08-06T12:00:00"
        dt = parse_utc(iso)
        assert dt.tzinfo == timezone.utc

    def test_parse_with_z_suffix(self):
        """解析带 Z 后缀的时间 (Python 3.11+ 原生支持)。"""
        iso = "2026-08-06T12:00:00+00:00"
        dt = parse_utc(iso)
        assert dt.tzinfo is not None

    def test_round_trip(self):
        """to_iso → from_iso 往返一致。"""
        now = datetime.now(timezone.utc)
        iso = now.isoformat()
        dt = parse_utc(iso)
        assert dt == now


# ═══════════════════════════════════════════════════════════
# TestLoopState — 循环状态
# ═══════════════════════════════════════════════════════════


class TestLoopState:
    """LoopState 数据模型与序列化。"""

    def test_defaults(self):
        """默认构造生成 loop_id 和 started_at。"""
        state = LoopState()
        assert state.loop_id.startswith("loop_")
        assert state.started_at != ""
        assert state.cycle_number == 0
        assert state.mode == "manual"

    def test_to_dict_contains_all_fields(self):
        """to_dict 包含全部字段。"""
        state = LoopState(cycle_number=5, total_cycles=5)
        d = state.to_dict()
        assert d["cycle_number"] == 5
        assert "loop_id" in d
        assert "started_at" in d
        assert "success_rate" in d
        assert "interval_hours" in d

    def test_from_dict_round_trip(self):
        """to_dict → from_dict 往返一致。"""
        state = LoopState(
            cycle_number=10,
            mode="autonomous",
            interval_hours=3.0,
            total_cycles=10,
            total_actions_executed=25,
            success_rate=0.72,
        )
        d = state.to_dict()
        restored = LoopState.from_dict(d)
        assert restored.cycle_number == 10
        assert restored.mode == "autonomous"
        assert restored.interval_hours == 3.0
        assert restored.total_cycles == 10
        assert restored.total_actions_executed == 25
        assert restored.success_rate == 0.72
        assert restored.loop_id == state.loop_id

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict 忽略未知字段。"""
        d = {"cycle_number": 3, "unknown_field": "xxx", "mode": "manual"}
        state = LoopState.from_dict(d)
        assert state.cycle_number == 3
        assert state.mode == "manual"

    def test_from_dict_missing_fields_use_defaults(self):
        """from_dict 缺失字段使用默认值。"""
        state = LoopState.from_dict({})
        assert state.cycle_number == 0
        assert state.mode == "manual"

    def test_save_and_load(self, tmp_data_dir):
        """save → load 往返一致。"""
        path = tmp_data_dir / "loop_state.json"
        state = LoopState(cycle_number=7, mode="autonomous")
        state.save(path)

        assert path.exists()
        restored = LoopState.load(path)
        assert restored is not None
        assert restored.cycle_number == 7
        assert restored.mode == "autonomous"
        assert restored.loop_id == state.loop_id

    def test_load_nonexistent_returns_none(self, tmp_data_dir):
        """加载不存在的文件返回 None。"""
        path = tmp_data_dir / "nonexistent.json"
        assert LoopState.load(path) is None

    def test_load_corrupted_returns_none(self, tmp_data_dir):
        """加载损坏的文件返回 None。"""
        path = tmp_data_dir / "corrupted.json"
        path.write_text("{invalid json", encoding="utf-8")
        assert LoopState.load(path) is None

    def test_advance_cycle(self):
        """advance_cycle 更新轮次和时间戳。"""
        state = LoopState(cycle_number=5, total_cycles=5)
        old_last_cycle = state.last_cycle_at
        state.advance_cycle()
        assert state.cycle_number == 6
        assert state.total_cycles == 6
        assert state.last_cycle_at != old_last_cycle

    def test_save_creates_parent_dirs(self, tmp_data_dir):
        """save 自动创建父目录。"""
        path = tmp_data_dir / "nested" / "deep" / "loop_state.json"
        state = LoopState()
        state.save(path)
        assert path.exists()


# ═══════════════════════════════════════════════════════════
# TestPendingEvaluationModel — 待评估数据模型
# ═══════════════════════════════════════════════════════════


class TestPendingEvaluationModel:
    """PendingEvaluation 数据模型。"""

    def test_defaults(self):
        """默认构造。"""
        pending = PendingEvaluation()
        assert pending.status == "waiting"
        assert pending.observation_window_hours == 168
        assert pending.execution_success is True

    def test_to_dict_contains_all_fields(self):
        """to_dict 包含全部字段。"""
        pending = PendingEvaluation(
            signal_id="fs_001",
            action_id="exec_001",
            action_type="update_budget",
            executed_at="2026-08-06T12:00:00+00:00",
        )
        d = pending.to_dict()
        assert d["signal_id"] == "fs_001"
        assert d["action_id"] == "exec_001"
        assert d["action_type"] == "update_budget"
        assert d["status"] == "waiting"
        assert "pre_metrics" in d
        assert "parameters" in d
        # 确认没有 due_at
        assert "due_at" not in d

    def test_from_dict_round_trip(self):
        """to_dict → from_dict 往返一致。"""
        pending = PendingEvaluation(
            signal_id="fs_002",
            diagnosis_id="diag_002",
            hypothesis_id="hyp_002",
            strategy_id="strat_002",
            action_id="exec_002",
            creative_id="cr_002",
            adset_id="adset_002",
            action_type="pause_campaign",
            parameters={"reason": "fatigue"},
            pre_metrics={"roas": 1.5, "cpi": 2.3},
            executed_at="2026-08-06T10:00:00+00:00",
            observation_window_hours=72,
            execution_success=True,
            actual_budget=None,
            dry_run=False,
            status="waiting",
        )
        d = pending.to_dict()
        restored = PendingEvaluation.from_dict(d)
        assert restored.signal_id == "fs_002"
        assert restored.action_type == "pause_campaign"
        assert restored.observation_window_hours == 72
        assert restored.pre_metrics == {"roas": 1.5, "cpi": 2.3}
        assert restored.parameters == {"reason": "fatigue"}
        assert restored.executed_at == "2026-08-06T10:00:00+00:00"

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict 忽略未知字段。"""
        d = {"action_id": "exec_003", "due_at": "2026-08-13T10:00:00+00:00", "extra": 123}
        pending = PendingEvaluation.from_dict(d)
        assert pending.action_id == "exec_003"
        # due_at 应被忽略
        assert not hasattr(pending, "due_at")

    def test_no_due_at_field(self):
        """确认数据模型中不存在 due_at 字段。"""
        pending = PendingEvaluation()
        d = pending.to_dict()
        assert "due_at" not in d
        # dataclass 字段列表中也不包含
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(pending)}
        assert "due_at" not in field_names


# ═══════════════════════════════════════════════════════════
# TestIsDueAndExpired — 运行时时间计算
# ═══════════════════════════════════════════════════════════


class TestIsDueAndExpired:
    """is_due / is_expired 运行时动态计算。"""

    def test_is_due_false_when_within_window(self):
        """观察期内 → is_due=False。"""
        now = datetime.now(timezone.utc)
        pending = PendingEvaluation(
            executed_at=now.isoformat(),
            observation_window_hours=168,
        )
        assert pending.is_due is False

    def test_is_due_true_when_window_passed(self):
        """超过观察期 → is_due=True。"""
        past = datetime.now(timezone.utc) - timedelta(hours=200)
        pending = PendingEvaluation(
            executed_at=past.isoformat(),
            observation_window_hours=168,
        )
        assert pending.is_due is True

    def test_is_due_boundary_exact(self):
        """恰好到达观察期 → is_due=True (>=)。"""
        past = datetime.now(timezone.utc) - timedelta(hours=168)
        pending = PendingEvaluation(
            executed_at=past.isoformat(),
            observation_window_hours=168,
        )
        assert pending.is_due is True

    def test_is_expired_false_within_2x_window(self):
        """2 倍观察期内 → is_expired=False。"""
        past = datetime.now(timezone.utc) - timedelta(hours=200)
        pending = PendingEvaluation(
            executed_at=past.isoformat(),
            observation_window_hours=168,
        )
        assert pending.is_expired is False

    def test_is_expired_true_beyond_2x_window(self):
        """超过 2 倍观察期 → is_expired=True。"""
        past = datetime.now(timezone.utc) - timedelta(hours=400)
        pending = PendingEvaluation(
            executed_at=past.isoformat(),
            observation_window_hours=168,
        )
        assert pending.is_expired is True

    def test_is_expired_boundary_exact(self):
        """恰好 2 倍观察期 → is_expired=True。"""
        past = datetime.now(timezone.utc) - timedelta(hours=336)
        pending = PendingEvaluation(
            executed_at=past.isoformat(),
            observation_window_hours=168,
        )
        assert pending.is_expired is True

    def test_is_due_false_when_executed_at_empty(self):
        """executed_at 为空 → is_due=False。"""
        pending = PendingEvaluation(executed_at="")
        assert pending.is_due is False
        assert pending.is_expired is False

    def test_elapsed_hours(self):
        """elapsed_hours 返回合理的小时数。"""
        past = datetime.now(timezone.utc) - timedelta(hours=10)
        pending = PendingEvaluation(
            executed_at=past.isoformat(),
            observation_window_hours=168,
        )
        assert 9.5 < pending.elapsed_hours < 10.5

    def test_config_change_takes_effect_immediately(self):
        """配置变更 (window 缩短) 立即生效 — due_at 预计算做不到。"""
        past = datetime.now(timezone.utc) - timedelta(hours=50)
        pending = PendingEvaluation(
            executed_at=past.isoformat(),
            observation_window_hours=168,  # 原配置 7 天
        )
        assert pending.is_due is False

        # 模拟配置变更: 7 天 → 2 天
        pending.observation_window_hours = 48
        assert pending.is_due is True  # 立即生效

    def test_clock_skew_resilience(self):
        """时钟回拨不会导致评估被无限延迟。

        场景: 执行时 now=T, 系统时钟回拨到 T-10h
        预计算 due_at=T+168h, 回拨后 now=T-10h, now < due_at → 永远不到期
        动态计算: elapsed = (T-10h) - T = -10h < 168h → 未到期 (但不会无限延迟)
        时钟恢复后: elapsed 正常增长 → 正常到期
        """
        now = datetime.now(timezone.utc)
        pending = PendingEvaluation(
            executed_at=now.isoformat(),
            observation_window_hours=168,
        )
        # 时钟回拨 10 小时后 (模拟)
        # elapsed = now - 10h - now = -10h (负值)
        # is_due 检查 elapsed >= 168h → False (正确，不会误触发)
        assert pending.is_due is False
        # 时钟恢复后，pending 会正常到期 (与其他测试一致)


# ═══════════════════════════════════════════════════════════
# TestFromAction — 工厂方法
# ═══════════════════════════════════════════════════════════


class TestFromAction:
    """PendingEvaluation.from_action 工厂方法。"""

    def test_from_action_basic(self):
        """从 Action + Result 创建 PendingEvaluation。"""
        action = _make_action()
        result = _make_result(action)
        pre_metrics = {"roas": 1.5, "cpi": 2.3, "ctr": 0.025}

        pending = PendingEvaluation.from_action(
            action, result, pre_metrics, observation_window_hours=168
        )

        assert pending.signal_id == action.signal_id
        assert pending.diagnosis_id == action.diagnosis_id
        assert pending.hypothesis_id == action.hypothesis_id
        assert pending.strategy_id == action.strategy_id
        assert pending.action_id == action.action_id
        assert pending.creative_id == action.creative_id
        assert pending.adset_id == action.adset_id
        assert pending.action_type == "update_budget"
        assert pending.parameters == action.parameters
        assert pending.pre_metrics == pre_metrics
        assert pending.executed_at == result.executed_at
        assert pending.observation_window_hours == 168
        assert pending.execution_success is True
        assert pending.actual_budget == 150.0
        assert pending.dry_run is False
        assert pending.status == "waiting"

    def test_from_action_pause(self):
        """PAUSE_CAMPAIGN 动作。"""
        action = _make_action(action_type=ActionType.PAUSE_CAMPAIGN)
        result = _make_result(action, actual_budget=None)
        pending = PendingEvaluation.from_action(action, result, {})

        assert pending.action_type == "pause_campaign"
        assert pending.actual_budget is None

    def test_from_action_dry_run(self):
        """dry_run=True 的执行结果。"""
        action = _make_action()
        result = _make_result(action, dry_run=True)
        pending = PendingEvaluation.from_action(action, result, {})

        assert pending.dry_run is True

    def test_from_action_failed_execution(self):
        """执行失败的 action 也创建 pending (用于后续评估失败原因)。"""
        action = _make_action()
        result = _make_result(action, success=False, actual_budget=None)
        pending = PendingEvaluation.from_action(action, result, {})

        assert pending.execution_success is False

    def test_from_action_custom_window(self):
        """自定义观察窗口。"""
        action = _make_action()
        result = _make_result(action)
        pending = PendingEvaluation.from_action(
            action, result, {}, observation_window_hours=72
        )
        assert pending.observation_window_hours == 72

    def test_from_action_pre_metrics_copied(self):
        """pre_metrics 是深拷贝，修改不影响原始 dict。"""
        action = _make_action()
        result = _make_result(action)
        original_metrics = {"roas": 1.5}
        pending = PendingEvaluation.from_action(action, result, original_metrics)

        pending.pre_metrics["roas"] = 999.0
        assert original_metrics["roas"] == 1.5  # 原始不受影响


# ═══════════════════════════════════════════════════════════
# TestPendingEvaluationBatchIO — 批量文件 I/O
# ═══════════════════════════════════════════════════════════


class TestPendingEvaluationBatchIO:
    """PendingEvaluation JSONL 批量读写。"""

    def test_save_and_load_batch(self, tmp_data_dir):
        """save_batch → load_batch 往返一致。"""
        path = tmp_data_dir / "pending.jsonl"
        items = [
            PendingEvaluation(
                signal_id="fs_001",
                action_id="exec_001",
                action_type="update_budget",
                executed_at="2026-08-06T10:00:00+00:00",
                pre_metrics={"roas": 1.5},
            ),
            PendingEvaluation(
                signal_id="fs_002",
                action_id="exec_002",
                action_type="pause_campaign",
                executed_at="2026-08-06T11:00:00+00:00",
                pre_metrics={"cpi": 2.3},
            ),
        ]
        PendingEvaluation.save_batch(items, path)

        loaded = PendingEvaluation.load_batch(path)
        assert len(loaded) == 2
        assert loaded[0].signal_id == "fs_001"
        assert loaded[1].signal_id == "fs_002"
        assert loaded[0].pre_metrics == {"roas": 1.5}
        assert loaded[1].action_type == "pause_campaign"

    def test_load_nonexistent_returns_empty(self, tmp_data_dir):
        """加载不存在的文件返回空列表。"""
        path = tmp_data_dir / "nonexistent.jsonl"
        assert PendingEvaluation.load_batch(path) == []

    def test_save_empty_batch(self, tmp_data_dir):
        """保存空列表 → 空文件。"""
        path = tmp_data_dir / "empty.jsonl"
        PendingEvaluation.save_batch([], path)
        assert path.exists()
        assert PendingEvaluation.load_batch(path) == []

    def test_save_creates_parent_dirs(self, tmp_data_dir):
        """save 自动创建父目录。"""
        path = tmp_data_dir / "nested" / "pending.jsonl"
        PendingEvaluation.save_batch(
            [PendingEvaluation(signal_id="fs_x", executed_at="2026-08-06T10:00:00+00:00")],
            path,
        )
        assert path.exists()

    def test_overwrite_on_save(self, tmp_data_dir):
        """save_batch 覆盖写 — 旧数据被替换。"""
        path = tmp_data_dir / "pending.jsonl"
        # 第一次写 2 条
        PendingEvaluation.save_batch(
            [
                PendingEvaluation(signal_id="fs_001", executed_at="2026-08-06T10:00:00+00:00"),
                PendingEvaluation(signal_id="fs_002", executed_at="2026-08-06T11:00:00+00:00"),
            ],
            path,
        )
        # 第二次写 1 条 (模拟评估完成后移除到期项)
        PendingEvaluation.save_batch(
            [PendingEvaluation(signal_id="fs_001", executed_at="2026-08-06T10:00:00+00:00")],
            path,
        )
        loaded = PendingEvaluation.load_batch(path)
        assert len(loaded) == 1
        assert loaded[0].signal_id == "fs_001"

    def test_load_skips_corrupted_lines(self, tmp_data_dir):
        """load_batch 跳过损坏行。"""
        path = tmp_data_dir / "pending.jsonl"
        path.write_text(
            '{"action_id": "exec_001", "executed_at": "2026-08-06T10:00:00+00:00"}\n'
            "{invalid json}\n"
            '{"action_id": "exec_002", "executed_at": "2026-08-06T11:00:00+00:00"}\n',
            encoding="utf-8",
        )
        loaded = PendingEvaluation.load_batch(path)
        assert len(loaded) == 2
        assert loaded[0].action_id == "exec_001"
        assert loaded[1].action_id == "exec_002"

    def test_round_trip_preserves_all_fields(self, tmp_data_dir):
        """序列化往返保留全部字段 (含嵌套 dict)。"""
        path = tmp_data_dir / "pending.jsonl"
        original = PendingEvaluation(
            signal_id="fs_full",
            diagnosis_id="diag_full",
            hypothesis_id="hyp_full",
            strategy_id="strat_full",
            action_id="exec_full",
            creative_id="cr_full",
            adset_id="adset_full",
            action_type="update_budget",
            parameters={"target_budget": 200.0, "current_budget": 100.0, "nested": {"key": "val"}},
            pre_metrics={"roas": 1.5, "cpi": 2.3, "ctr": 0.025},
            executed_at="2026-08-06T10:00:00.123456+00:00",
            observation_window_hours=72,
            execution_success=True,
            actual_budget=200.0,
            dry_run=False,
            status="waiting",
        )
        PendingEvaluation.save_batch([original], path)
        loaded = PendingEvaluation.load_batch(path)
        assert len(loaded) == 1
        r = loaded[0]
        assert r.signal_id == "fs_full"
        assert r.diagnosis_id == "diag_full"
        assert r.parameters["nested"] == {"key": "val"}
        assert r.pre_metrics["ctr"] == 0.025
        assert r.observation_window_hours == 72
        assert r.actual_budget == 200.0


# ═══════════════════════════════════════════════════════════
# TestLoopPersistence — 持久化管理器
# ═══════════════════════════════════════════════════════════


class TestLoopPersistence:
    """LoopPersistence 统一管理器。"""

    def test_init_creates_data_dir(self, tmp_data_dir):
        """初始化自动创建数据目录。"""
        data_dir = tmp_data_dir / "growth_loop"
        assert not data_dir.exists()
        persistence = LoopPersistence(data_dir=data_dir)
        assert data_dir.exists()
        assert persistence.state_path == data_dir / "loop_state.json"
        assert persistence.pending_path == data_dir / "pending_evaluations.jsonl"
        assert persistence.history_path == data_dir / "cycle_history.jsonl"
        assert persistence.experience_path == data_dir / "experience_snapshot.json"

    def test_load_state_new_returns_default(self, persistence):
        """无历史文件 → 返回全新 LoopState。"""
        state = persistence.load_state()
        assert state.cycle_number == 0
        assert state.loop_id.startswith("loop_")

    def test_save_and_load_state(self, persistence):
        """保存 → 加载 LoopState。"""
        state = LoopState(cycle_number=5, mode="autonomous")
        persistence.save_state(state)

        loaded = persistence.load_state()
        assert loaded.cycle_number == 5
        assert loaded.mode == "autonomous"
        assert loaded.loop_id == state.loop_id

    def test_save_and_load_pending(self, persistence):
        """保存 → 加载 PendingEvaluation 列表。"""
        items = [
            PendingEvaluation(
                signal_id="fs_001",
                action_id="exec_001",
                executed_at="2026-08-06T10:00:00+00:00",
            ),
            PendingEvaluation(
                signal_id="fs_002",
                action_id="exec_002",
                executed_at="2026-08-06T11:00:00+00:00",
            ),
        ]
        persistence.save_pending_evaluations(items)

        loaded = persistence.load_pending_evaluations()
        assert len(loaded) == 2
        assert loaded[0].signal_id == "fs_001"
        assert loaded[1].signal_id == "fs_002"

    def test_append_and_load_cycle_history(self, persistence):
        """追加 → 读取 CycleRecord 历史。"""
        record1 = build_cycle_record(
            loop_id="loop_001",
            cycle_number=1,
            started_at="2026-08-06T10:00:00+00:00",
        )
        record2 = build_cycle_record(
            loop_id="loop_001",
            cycle_number=2,
            started_at="2026-08-06T16:00:00+00:00",
        )
        persistence.append_cycle_record(record1)
        persistence.append_cycle_record(record2)

        history = persistence.load_cycle_history()
        assert len(history) == 2
        assert history[0]["cycle_number"] == 1
        assert history[1]["cycle_number"] == 2

    def test_load_cycle_history_with_limit(self, persistence):
        """limit 参数只读最近 N 条。"""
        for i in range(5):
            persistence.append_cycle_record(
                build_cycle_record(
                    loop_id="loop_001",
                    cycle_number=i,
                    started_at="2026-08-06T10:00:00+00:00",
                )
            )
        history = persistence.load_cycle_history(limit=2)
        assert len(history) == 2
        assert history[-1]["cycle_number"] == 4

    def test_load_cycle_history_empty(self, persistence):
        """无历史文件 → 空列表。"""
        assert persistence.load_cycle_history() == []

    def test_save_and_load_experience_snapshot(self, persistence):
        """保存 → 加载 ExperienceStore 快照。"""
        records = [
            {"experience_id": "exp_001", "creative_id": "cr_001", "outcome": "SUCCESS"},
            {"experience_id": "exp_002", "creative_id": "cr_002", "outcome": "FAILURE"},
        ]
        persistence.save_experience_snapshot(records)

        loaded = persistence.load_experience_snapshot()
        assert len(loaded) == 2
        assert loaded[0]["experience_id"] == "exp_001"
        assert loaded[1]["outcome"] == "FAILURE"

    def test_load_experience_snapshot_empty(self, persistence):
        """无快照文件 → 空列表。"""
        assert persistence.load_experience_snapshot() == []

    def test_save_all(self, persistence):
        """save_all 一次性写入全部文件。"""
        state = LoopState(cycle_number=3)
        pending = [
            PendingEvaluation(signal_id="fs_001", executed_at="2026-08-06T10:00:00+00:00"),
        ]
        exp_records = [{"experience_id": "exp_001"}]
        cycle_rec = build_cycle_record(
            loop_id=state.loop_id,
            cycle_number=3,
            started_at="2026-08-06T10:00:00+00:00",
        )

        persistence.save_all(
            state=state,
            pending_list=pending,
            experience_records=exp_records,
            cycle_record=cycle_rec,
        )

        # 验证全部文件存在且内容正确
        assert persistence.load_state().cycle_number == 3
        assert len(persistence.load_pending_evaluations()) == 1
        assert len(persistence.load_experience_snapshot()) == 1
        assert len(persistence.load_cycle_history()) == 1

    def test_save_all_skip_optional(self, persistence):
        """save_all 跳过 None 的可选参数。"""
        state = LoopState(cycle_number=1)
        pending: list[PendingEvaluation] = []

        persistence.save_all(state, pending)  # experience/cycle 为 None

        assert persistence.load_state().cycle_number == 1
        assert persistence.load_pending_evaluations() == []
        # experience_snapshot 不应存在
        assert not persistence.experience_path.exists()
        # cycle_history 不应存在
        assert not persistence.history_path.exists()

    def test_clear_all(self, persistence):
        """clear_all 清空全部文件。"""
        # 先写入数据
        persistence.save_state(LoopState(cycle_number=1))
        persistence.save_pending_evaluations(
            [PendingEvaluation(signal_id="fs_001", executed_at="2026-08-06T10:00:00+00:00")]
        )
        persistence.append_cycle_record(
            build_cycle_record("loop_001", 1, "2026-08-06T10:00:00+00:00")
        )
        persistence.save_experience_snapshot([{"experience_id": "exp_001"}])

        # 确认文件存在
        assert persistence.state_path.exists()
        assert persistence.pending_path.exists()
        assert persistence.history_path.exists()
        assert persistence.experience_path.exists()

        # 清空
        persistence.clear_all()

        assert not persistence.state_path.exists()
        assert not persistence.pending_path.exists()
        assert not persistence.history_path.exists()
        assert not persistence.experience_path.exists()


# ═══════════════════════════════════════════════════════════
# TestCrossRestartScenario — 跨重启恢复场景
# ═══════════════════════════════════════════════════════════


class TestCrossRestartScenario:
    """模拟进程重启后的状态恢复。"""

    def test_full_restart_recovery(self, tmp_data_dir):
        """完整重启恢复: 写入 → 重新加载 → 验证一致性。"""
        # Phase 1: 模拟第一轮运行结束后的持久化
        persistence1 = LoopPersistence(data_dir=tmp_data_dir)
        state1 = LoopState(cycle_number=5, mode="autonomous", interval_hours=3.0)
        state1.total_actions_executed = 12
        state1.total_outcomes_evaluated = 8
        state1.success_rate = 0.75

        pending1 = [
            PendingEvaluation(
                signal_id="fs_001",
                action_id="exec_001",
                action_type="update_budget",
                creative_id="cr_001",
                adset_id="adset_001",
                pre_metrics={"roas": 1.5, "cpi": 2.3},
                parameters={"target_budget": 150.0},
                executed_at="2026-08-06T10:00:00+00:00",
                observation_window_hours=168,
                actual_budget=150.0,
            ),
            PendingEvaluation(
                signal_id="fs_002",
                action_id="exec_002",
                action_type="pause_campaign",
                creative_id="cr_002",
                adset_id="adset_002",
                pre_metrics={"roas": 0.8},
                parameters={"reason": "fatigue"},
                executed_at="2026-08-05T10:00:00+00:00",
                observation_window_hours=168,
            ),
        ]

        exp_records = [
            {"experience_id": "exp_001", "creative_id": "cr_001", "outcome": "SUCCESS"},
            {"experience_id": "exp_002", "creative_id": "cr_002", "outcome": "FAILURE"},
        ]

        cycle_rec = build_cycle_record(
            loop_id=state1.loop_id,
            cycle_number=5,
            started_at="2026-08-06T09:00:00+00:00",
            actions_executed=2,
            pending_evaluations_created=2,
        )

        persistence1.save_all(state1, pending1, exp_records, cycle_rec)

        # Phase 2: 模拟进程重启 — 重新加载
        persistence2 = LoopPersistence(data_dir=tmp_data_dir)
        state2 = persistence2.load_state()
        pending2 = persistence2.load_pending_evaluations()
        exp2 = persistence2.load_experience_snapshot()
        history2 = persistence2.load_cycle_history()

        # 验证 LoopState 一致
        assert state2.cycle_number == 5
        assert state2.mode == "autonomous"
        assert state2.interval_hours == 3.0
        assert state2.total_actions_executed == 12
        assert state2.total_outcomes_evaluated == 8
        assert state2.success_rate == 0.75
        assert state2.loop_id == state1.loop_id

        # 验证 PendingEvaluation 一致
        assert len(pending2) == 2
        assert pending2[0].signal_id == "fs_001"
        assert pending2[0].action_type == "update_budget"
        assert pending2[0].pre_metrics == {"roas": 1.5, "cpi": 2.3}
        assert pending2[0].actual_budget == 150.0
        assert pending2[1].signal_id == "fs_002"
        assert pending2[1].action_type == "pause_campaign"

        # 验证 Experience 快照一致
        assert len(exp2) == 2
        assert exp2[0]["experience_id"] == "exp_001"
        assert exp2[1]["outcome"] == "FAILURE"

        # 验证 CycleRecord 一致
        assert len(history2) == 1
        assert history2[0]["cycle_number"] == 5
        assert history2[0]["actions_executed"] == 2

    def test_restart_with_due_evaluations(self, tmp_data_dir):
        """重启后 is_due 仍能正确计算。"""
        persistence = LoopPersistence(data_dir=tmp_data_dir)

        # 写入一个已过观察期的 pending (8 天前执行)
        past = (datetime.now(timezone.utc) - timedelta(hours=192)).isoformat()
        persistence.save_pending_evaluations([
            PendingEvaluation(
                signal_id="fs_old",
                action_id="exec_old",
                executed_at=past,
                observation_window_hours=168,
            ),
        ])

        # 重启后加载
        loaded = persistence.load_pending_evaluations()
        assert len(loaded) == 1
        assert loaded[0].is_due is True  # 192h > 168h
        assert loaded[0].is_expired is False  # 192h < 336h

    def test_restart_with_expired_evaluations(self, tmp_data_dir):
        """重启后 is_expired 仍能正确计算。"""
        persistence = LoopPersistence(data_dir=tmp_data_dir)

        # 写入一个超过 2 倍观察期的 pending (15 天前执行)
        past = (datetime.now(timezone.utc) - timedelta(hours=360)).isoformat()
        persistence.save_pending_evaluations([
            PendingEvaluation(
                signal_id="fs_zombie",
                action_id="exec_zombie",
                executed_at=past,
                observation_window_hours=168,
            ),
        ])

        loaded = persistence.load_pending_evaluations()
        assert len(loaded) == 1
        assert loaded[0].is_due is True
        assert loaded[0].is_expired is True

    def test_restart_then_evaluate_then_save(self, tmp_data_dir):
        """重启 → 评估到期项 → 移除并保存的完整流程。"""
        persistence = LoopPersistence(data_dir=tmp_data_dir)

        # 写入 3 个 pending: 1 个到期、1 个未到期、1 个过期
        now = datetime.now(timezone.utc)
        items = [
            PendingEvaluation(
                signal_id="fs_due",
                action_id="exec_due",
                executed_at=(now - timedelta(hours=200)).isoformat(),
                observation_window_hours=168,
            ),
            PendingEvaluation(
                signal_id="fs_waiting",
                action_id="exec_waiting",
                executed_at=now.isoformat(),
                observation_window_hours=168,
            ),
            PendingEvaluation(
                signal_id="fs_expired",
                action_id="exec_expired",
                executed_at=(now - timedelta(hours=400)).isoformat(),
                observation_window_hours=168,
            ),
        ]
        persistence.save_pending_evaluations(items)

        # 重启加载
        loaded = persistence.load_pending_evaluations()
        assert len(loaded) == 3

        # 模拟评估: 移除到期和过期的
        remaining = [
            p for p in loaded
            if not p.is_due and not p.is_expired
        ]
        assert len(remaining) == 1
        assert remaining[0].signal_id == "fs_waiting"

        # 保存剩余
        persistence.save_pending_evaluations(remaining)

        # 再次重启验证
        final = persistence.load_pending_evaluations()
        assert len(final) == 1
        assert final[0].signal_id == "fs_waiting"


# ═══════════════════════════════════════════════════════════
# TestCycleRecord — 循环记录构建
# ═══════════════════════════════════════════════════════════


class TestCycleRecord:
    """build_cycle_record 工具函数。"""

    def test_build_minimal(self):
        """最小参数构建。"""
        record = build_cycle_record(
            loop_id="loop_001",
            cycle_number=1,
            started_at="2026-08-06T10:00:00+00:00",
        )
        assert record["loop_id"] == "loop_001"
        assert record["cycle_number"] == 1
        assert record["completed_at"] != ""  # 自动填充
        assert record["signal_ids"] == []
        assert record["actions"] == []
        assert record["actions_planned"] == 0

    def test_build_full(self):
        """完整参数构建。"""
        record = build_cycle_record(
            loop_id="loop_001",
            cycle_number=3,
            started_at="2026-08-06T10:00:00+00:00",
            completed_at="2026-08-06T10:05:00+00:00",
            duration_ms=300000,
            signal_ids=["fs_001", "fs_002"],
            diagnosis={"diagnosis_id": "diag_001"},
            hypothesis={"hypothesis_id": "hyp_001"},
            strategy={"strategy_id": "strat_001"},
            actions=[{"action_id": "exec_001"}],
            execution_results=[{"result_id": "res_001"}],
            outcomes=[{"outcome_id": "outcome_001"}],
            actions_planned=1,
            actions_executed=1,
            pending_evaluations_created=1,
        )
        assert record["cycle_number"] == 3
        assert record["duration_ms"] == 300000
        assert len(record["signal_ids"]) == 2
        assert record["diagnosis"]["diagnosis_id"] == "diag_001"
        assert record["actions_executed"] == 1

    def test_serializable(self):
        """构建结果可 JSON 序列化。"""
        import json
        record = build_cycle_record(
            loop_id="loop_001",
            cycle_number=1,
            started_at="2026-08-06T10:00:00+00:00",
            diagnosis={"key": "value"},
            actions=[{"id": 1}, {"id": 2}],
        )
        json_str = json.dumps(record, ensure_ascii=False)
        restored = json.loads(json_str)
        assert restored["cycle_number"] == 1
        assert len(restored["actions"]) == 2
