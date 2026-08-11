"""P4.1 FleetOrchestrator 单元测试 — 确定性分片与失败隔离编排.

测试覆盖:
  1. FleetConfig 校验
  2. shard() 确定性分片
  3. run() 并行执行 + 失败隔离
  4. AgentRole 枚举
  5. FleetRun 汇总属性
  6. 边界场景: 空游戏列表、超限、重复去重
"""
from __future__ import annotations

import pytest

from src.autonomous_growth.fleet import (
    AgentRole,
    FleetConfig,
    FleetOrchestrator,
    FleetRun,
    ShardResult,
)


# ═══════════════════════════════════════════════════════════════
# 1. FleetConfig 校验
# ═══════════════════════════════════════════════════════════════


class TestFleetConfig:
    """FleetConfig 参数校验."""

    def test_default_config_valid(self):
        """默认配置合法."""
        config = FleetConfig()
        assert config.validate() == []
        assert config.max_games == 200
        assert config.shard_size == 12
        assert config.max_workers == 8

    def test_max_games_below_minimum(self):
        """max_games < 1 非法."""
        errors = FleetConfig(max_games=0).validate()
        assert any("max_games" in e for e in errors)

    def test_max_games_above_maximum(self):
        """max_games > 200 非法."""
        errors = FleetConfig(max_games=201).validate()
        assert any("max_games" in e for e in errors)

    def test_shard_size_zero_invalid(self):
        """shard_size = 0 非法."""
        errors = FleetConfig(shard_size=0).validate()
        assert any("shard_size" in e for e in errors)

    def test_max_workers_below_minimum(self):
        """max_workers < 1 非法."""
        errors = FleetConfig(max_workers=0).validate()
        assert any("max_workers" in e for e in errors)

    def test_max_workers_above_maximum(self):
        """max_workers > 32 非法."""
        errors = FleetConfig(max_workers=33).validate()
        assert any("max_workers" in e for e in errors)

    def test_boundary_values_valid(self):
        """边界值合法 (1, 1, 1) 和 (200, 1, 32)."""
        assert FleetConfig(max_games=1, shard_size=1, max_workers=1).validate() == []
        assert FleetConfig(max_games=200, shard_size=1, max_workers=32).validate() == []


# ═══════════════════════════════════════════════════════════════
# 2. shard() 确定性分片
# ═══════════════════════════════════════════════════════════════


class TestShard:
    """shard() 确定性分片行为."""

    def test_shard_splits_by_shard_size(self):
        """按 shard_size 切分."""
        orchestrator = FleetOrchestrator(runner=lambda **kw: {}, config=FleetConfig(shard_size=3))
        shards = orchestrator.shard(["g1", "g2", "g3", "g4", "g5"])
        assert len(shards) == 2
        assert shards[0] == ["g1", "g2", "g3"]
        assert shards[1] == ["g4", "g5"]

    def test_shard_sorted_deterministic(self):
        """分片结果排序确定 (与输入顺序无关)."""
        orchestrator = FleetOrchestrator(runner=lambda **kw: {}, config=FleetConfig(shard_size=10))
        shards_a = orchestrator.shard(["g3", "g1", "g2"])
        shards_b = orchestrator.shard(["g1", "g2", "g3"])
        assert shards_a == shards_b
        assert shards_a[0] == ["g1", "g2", "g3"]

    def test_shard_deduplicates(self):
        """重复游戏去重."""
        orchestrator = FleetOrchestrator(runner=lambda **kw: {}, config=FleetConfig(shard_size=10))
        shards = orchestrator.shard(["g1", "g1", "g2", "g2", "g3"])
        assert len(shards) == 1
        assert shards[0] == ["g1", "g2", "g3"]

    def test_shard_strips_whitespace(self):
        """空白游戏 ID 被过滤."""
        orchestrator = FleetOrchestrator(runner=lambda **kw: {}, config=FleetConfig(shard_size=10))
        shards = orchestrator.shard(["g1", "  ", "", "g2"])
        assert shards == [["g1", "g2"]]

    def test_shard_empty_input(self):
        """空输入返回空分片列表."""
        orchestrator = FleetOrchestrator(runner=lambda **kw: {}, config=FleetConfig())
        assert orchestrator.shard([]) == []
        assert orchestrator.shard(None) == []

    def test_shard_single_game(self):
        """单游戏单分片."""
        orchestrator = FleetOrchestrator(runner=lambda **kw: {}, config=FleetConfig(shard_size=12))
        shards = orchestrator.shard(["only_game"])
        assert len(shards) == 1
        assert shards[0] == ["only_game"]

    def test_shard_exact_multiple(self):
        """游戏数正好是 shard_size 的整数倍."""
        orchestrator = FleetOrchestrator(runner=lambda **kw: {}, config=FleetConfig(shard_size=2))
        shards = orchestrator.shard(["g1", "g2", "g3", "g4"])
        assert len(shards) == 2
        assert all(len(s) == 2 for s in shards)

    def test_shard_raises_when_exceeds_max_games(self):
        """游戏数超过 max_games 抛出 ValueError."""
        orchestrator = FleetOrchestrator(
            runner=lambda **kw: {},
            config=FleetConfig(max_games=3, shard_size=1),
        )
        with pytest.raises(ValueError, match="game limit exceeded"):
            orchestrator.shard(["g1", "g2", "g3", "g4"])


# ═══════════════════════════════════════════════════════════════
# 3. run() 并行执行 + 失败隔离
# ═══════════════════════════════════════════════════════════════


def _success_runner(**kwargs) -> dict:
    """模拟成功 runner."""
    return {"shard_id": kwargs["shard_id"], "real_api_called": False}


def _failing_runner(**kwargs) -> dict:
    """模拟失败 runner (对特定 shard 抛异常)."""
    if "shard-001" in kwargs["shard_id"]:
        raise RuntimeError("shard 1 failure")
    return {"shard_id": kwargs["shard_id"]}


def _real_api_runner(**kwargs) -> dict:
    """模拟调用真实 API 的 runner."""
    return {"shard_id": kwargs["shard_id"], "real_api_called": True}


class TestFleetRun:
    """run() 并行执行与汇总."""

    def test_run_all_success(self):
        """所有 shard 成功."""
        orchestrator = FleetOrchestrator(
            runner=_success_runner, config=FleetConfig(shard_size=2, max_workers=4)
        )
        result = orchestrator.run("2026-08-10", ["g1", "g2", "g3", "g4"])
        assert result.business_date == "2026-08-10"
        assert result.total_games == 4
        assert result.successful_shards == 2
        assert result.failed_shards == 0
        assert result.completed is True
        assert len(result.shards) == 2

    def test_run_failure_isolation(self):
        """单个 shard 失败不影响其他 shard."""
        orchestrator = FleetOrchestrator(
            runner=_failing_runner, config=FleetConfig(shard_size=1, max_workers=4)
        )
        result = orchestrator.run("2026-08-10", ["g1", "g2", "g3"])
        assert result.successful_shards == 2
        assert result.failed_shards == 1
        assert result.completed is False
        failed = [s for s in result.shards if not s.success]
        assert len(failed) == 1
        assert failed[0].error_type == "RuntimeError"

    def test_run_records_real_api_called(self):
        """real_api_called 聚合."""
        orchestrator = FleetOrchestrator(
            runner=_real_api_runner, config=FleetConfig(shard_size=2)
        )
        result = orchestrator.run("2026-08-10", ["g1", "g2"])
        assert result.real_api_called is True
        assert all(s.real_api_called for s in result.shards)

    def test_run_no_real_api_when_dry_run(self):
        """dry_run 模式 real_api_called=False."""
        orchestrator = FleetOrchestrator(
            runner=_success_runner, config=FleetConfig(shard_size=2)
        )
        result = orchestrator.run("2026-08-10", ["g1", "g2"])
        assert result.real_api_called is False

    def test_run_invalid_config_raises(self):
        """非法配置抛 ValueError."""
        orchestrator = FleetOrchestrator(
            runner=_success_runner, config=FleetConfig(max_workers=0)
        )
        with pytest.raises(ValueError):
            orchestrator.run("2026-08-10", ["g1"])

    def test_run_roles_default_all(self):
        """默认使用所有 AgentRole."""
        orchestrator = FleetOrchestrator(
            runner=_success_runner, config=FleetConfig(shard_size=10)
        )
        result = orchestrator.run("2026-08-10", ["g1"])
        assert set(result.roles) == {role.value for role in AgentRole}

    def test_run_roles_custom_subset(self):
        """自定义 roles 子集."""
        orchestrator = FleetOrchestrator(
            runner=_success_runner, config=FleetConfig(shard_size=10)
        )
        result = orchestrator.run(
            "2026-08-10", ["g1"], roles=[AgentRole.GROWTH, AgentRole.UA]
        )
        assert set(result.roles) == {"growth", "ua"}

    def test_run_shards_sorted_by_id(self):
        """shards 按 shard_id 排序."""
        orchestrator = FleetOrchestrator(
            runner=_success_runner, config=FleetConfig(shard_size=1, max_workers=4)
        )
        result = orchestrator.run("2026-08-10", ["g3", "g1", "g2"])
        shard_ids = [s.shard_id for s in result.shards]
        assert shard_ids == sorted(shard_ids)

    def test_run_empty_games(self):
        """空游戏列表返回空 run."""
        orchestrator = FleetOrchestrator(
            runner=_success_runner, config=FleetConfig(shard_size=10)
        )
        result = orchestrator.run("2026-08-10", [])
        assert result.total_games == 0
        assert result.successful_shards == 0
        assert result.shards == []

    def test_run_runner_returns_non_dict(self):
        """runner 返回非 dict 视为空输出."""
        def runner(**kw):
            return None
        orchestrator = FleetOrchestrator(runner=runner, config=FleetConfig(shard_size=2))
        result = orchestrator.run("2026-08-10", ["g1", "g2"])
        assert result.successful_shards == 1
        assert result.shards[0].output == {}


# ═══════════════════════════════════════════════════════════════
# 4. AgentRole 枚举
# ═══════════════════════════════════════════════════════════════


class TestAgentRole:
    """AgentRole 枚举值."""

    def test_all_roles_present(self):
        """10 个角色全部存在."""
        assert len(AgentRole) == 10

    def test_role_values(self):
        """角色值正确."""
        assert AgentRole.STRATEGY.value == "strategy"
        assert AgentRole.GROWTH.value == "growth"
        assert AgentRole.PRODUCT.value == "product"
        assert AgentRole.UA.value == "ua"
        assert AgentRole.ASO.value == "aso"
        assert AgentRole.MONETIZATION.value == "monetization"
        assert AgentRole.CREATIVE.value == "creative"

    def test_role_is_string_enum(self):
        """AgentRole 是 str Enum."""
        assert isinstance(AgentRole.GROWTH, str)
        assert AgentRole.GROWTH == "growth"


# ═══════════════════════════════════════════════════════════════
# 5. ShardResult / FleetRun 数据结构
# ═══════════════════════════════════════════════════════════════


class TestShardResult:
    """ShardResult 数据结构."""

    def test_default_values(self):
        """默认值."""
        result = ShardResult(shard_id="s1", game_ids=["g1"], success=True)
        assert result.output == {}
        assert result.error_type == ""
        assert result.real_api_called is False

    def test_failed_shard_with_error(self):
        """失败 shard 记录错误类型."""
        result = ShardResult(
            shard_id="s1", game_ids=["g1"], success=False, error_type="RuntimeError"
        )
        assert result.success is False
        assert result.error_type == "RuntimeError"


class TestFleetRunCompleted:
    """FleetRun.completed 属性."""

    def test_completed_when_no_failures(self):
        """无失败时 completed=True."""
        run = FleetRun(
            business_date="2026-08-10", roles=["growth"],
            total_games=2, successful_shards=1, failed_shards=0, shards=[],
        )
        assert run.completed is True

    def test_not_completed_when_failures(self):
        """有失败时 completed=False."""
        run = FleetRun(
            business_date="2026-08-10", roles=["growth"],
            total_games=2, successful_shards=0, failed_shards=1, shards=[],
        )
        assert run.completed is False
