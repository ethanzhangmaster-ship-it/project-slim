"""P4 Canary + Readiness + Agent 安全封套单元测试.

测试覆盖:
  1. CanaryCoordinator 单动作生产灰度
  2. CanaryCoordinator 监控+回滚
  3. CanaryCoordinator 幂等性
  4. CanaryCoordinator 审计日志
  5. ProductionReadinessGate 启动门
  6. AutonomousGrowthAgent 安全封套
  7. AutonomousGrowthAgent 熔断器
  8. AgentConfig 校验
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.autonomous_growth.agent import AutonomousGrowthAgent
from src.autonomous_growth.canary import CanaryCoordinator, CanaryResult
from src.autonomous_growth.models import AgentConfig, AgentStatus, ReadinessReport
from src.autonomous_growth.readiness import ProductionReadinessGate


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def audit_path(tmp_path: Path) -> str:
    """临时审计文件路径."""
    return str(tmp_path / "canary_audit.jsonl")


@pytest.fixture
def healthy_canary(audit_path: str) -> CanaryCoordinator:
    """健康监控的 Canary (execute 成功 + monitor 健康)."""
    execute_fn = MagicMock(return_value={"success": True, "real_api_called": True, "evidence_ref": "exec-1"})
    monitor_fn = MagicMock(return_value={"healthy": True, "evidence_ref": "monitor-1"})
    rollback_fn = MagicMock(return_value={"success": True, "evidence_ref": "rollback-1"})
    return CanaryCoordinator(execute=execute_fn, monitor=monitor_fn,
                             rollback=rollback_fn, audit_path=audit_path)


@pytest.fixture
def unhealthy_canary(audit_path: str) -> CanaryCoordinator:
    """不健康监控的 Canary (execute 成功 + monitor 不健康 + rollback)."""
    execute_fn = MagicMock(return_value={"success": True, "real_api_called": True, "evidence_ref": "exec-1"})
    monitor_fn = MagicMock(return_value={"healthy": False, "evidence_ref": "monitor-1"})
    rollback_fn = MagicMock(return_value={"success": True, "evidence_ref": "rollback-1"})
    return CanaryCoordinator(execute=execute_fn, monitor=monitor_fn,
                             rollback=rollback_fn, audit_path=audit_path)


# ═══════════════════════════════════════════════════════════════
# 1. CanaryCoordinator 单动作生产灰度
# ═══════════════════════════════════════════════════════════════


class TestCanaryExecute:
    """CanaryCoordinator 执行."""

    def test_successful_canary(self, healthy_canary: CanaryCoordinator):
        """成功 canary: execute + monitor healthy."""
        result = healthy_canary.run(
            canary_id="c1", game_id="g1",
            action={"type": "budget_increase"}, approval_id="appr-1",
        )
        assert result.success is True
        assert result.executed is True
        assert result.monitored is True
        assert result.rolled_back is False
        assert result.real_api_called is True
        assert "canary healthy" in result.reason

    def test_canary_requires_approval(self, audit_path: str):
        """无 approval_id 拒绝执行."""
        execute_fn = MagicMock()
        canary = CanaryCoordinator(execute=execute_fn, monitor=lambda **kw: {},
                                   rollback=lambda **kw: {}, audit_path=audit_path)
        result = canary.run(
            canary_id="c1", game_id="g1", action={"type": "test"}, approval_id="",
        )
        assert result.success is False
        assert result.executed is False
        assert "approval" in result.reason
        execute_fn.assert_not_called()

    def test_canary_requires_game_id(self, audit_path: str):
        """无 game_id 拒绝执行."""
        canary = CanaryCoordinator(
            execute=lambda **kw: {}, monitor=lambda **kw: {},
            rollback=lambda **kw: {}, audit_path=audit_path,
        )
        result = canary.run(canary_id="c1", game_id="", action={"type": "test"}, approval_id="a1")
        assert result.success is False
        assert result.executed is False

    def test_canary_requires_action(self, audit_path: str):
        """无 action 拒绝执行."""
        canary = CanaryCoordinator(
            execute=lambda **kw: {}, monitor=lambda **kw: {},
            rollback=lambda **kw: {}, audit_path=audit_path,
        )
        result = canary.run(canary_id="c1", game_id="g1", action={}, approval_id="a1")
        assert result.success is False

    def test_canary_requires_canary_id(self, audit_path: str):
        """无 canary_id 拒绝执行."""
        canary = CanaryCoordinator(
            execute=lambda **kw: {}, monitor=lambda **kw: {},
            rollback=lambda **kw: {}, audit_path=audit_path,
        )
        result = canary.run(canary_id="", game_id="g1", action={"type": "t"}, approval_id="a1")
        assert result.success is False


# ═══════════════════════════════════════════════════════════════
# 2. CanaryCoordinator 监控+回滚
# ═══════════════════════════════════════════════════════════════


class TestCanaryMonitorRollback:
    """CanaryCoordinator 监控与回滚."""

    def test_unhealthy_triggers_rollback(self, unhealthy_canary: CanaryCoordinator):
        """监控不健康触发回滚."""
        result = unhealthy_canary.run(
            canary_id="c2", game_id="g1",
            action={"type": "budget_increase"}, approval_id="appr-1",
        )
        assert result.success is False
        assert result.executed is True
        assert result.monitored is True
        assert result.rolled_back is True
        assert "rollback" in result.reason.lower()

    def test_execution_failure_no_monitor(self, audit_path: str):
        """execute 失败不进入 monitor."""
        execute_fn = MagicMock(return_value={"success": False})
        monitor_fn = MagicMock()
        canary = CanaryCoordinator(execute=execute_fn, monitor=monitor_fn,
                                   rollback=lambda **kw: {}, audit_path=audit_path)
        result = canary.run(canary_id="c3", game_id="g1", action={"type": "t"}, approval_id="a1")
        assert result.executed is False
        assert result.monitored is False
        assert "execution failed" in result.reason
        monitor_fn.assert_not_called()

    def test_rollback_failure_recorded(self, audit_path: str):
        """回滚失败被记录."""
        execute_fn = MagicMock(return_value={"success": True, "real_api_called": True})
        monitor_fn = MagicMock(return_value={"healthy": False})
        rollback_fn = MagicMock(return_value={"success": False})
        canary = CanaryCoordinator(execute=execute_fn, monitor=monitor_fn,
                                   rollback=rollback_fn, audit_path=audit_path)
        result = canary.run(canary_id="c4", game_id="g1", action={"type": "t"}, approval_id="a1")
        assert result.rolled_back is False
        assert "rollback failed" in result.reason

    def test_execute_exception_handled(self, audit_path: str):
        """execute 抛异常被捕获."""
        execute_fn = MagicMock(side_effect=RuntimeError("api down"))
        canary = CanaryCoordinator(execute=execute_fn, monitor=lambda **kw: {},
                                   rollback=lambda **kw: {}, audit_path=audit_path)
        result = canary.run(canary_id="c5", game_id="g1", action={"type": "t"}, approval_id="a1")
        assert result.success is False
        assert "canary error" in result.reason
        assert "RuntimeError" in result.reason


# ═══════════════════════════════════════════════════════════════
# 3. CanaryCoordinator 幂等性
# ═══════════════════════════════════════════════════════════════


class TestCanaryIdempotency:
    """CanaryCoordinator 幂等性."""

    def test_duplicate_canary_id_rejected(self, healthy_canary: CanaryCoordinator):
        """重复 canary_id 拒绝执行."""
        # 第一次成功
        result1 = healthy_canary.run(
            canary_id="c6", game_id="g1", action={"type": "t"}, approval_id="a1",
        )
        assert result1.success is True
        # 第二次拒绝
        result2 = healthy_canary.run(
            canary_id="c6", game_id="g1", action={"type": "t"}, approval_id="a1",
        )
        assert result2.success is False
        assert "already used" in result2.reason


# ═══════════════════════════════════════════════════════════════
# 4. CanaryCoordinator 审计日志
# ═══════════════════════════════════════════════════════════════


class TestCanaryAudit:
    """CanaryCoordinator 审计日志."""

    def test_audit_written(self, healthy_canary: CanaryCoordinator, audit_path: str):
        """审计日志写入文件."""
        healthy_canary.run(
            canary_id="c7", game_id="g1", action={"type": "t"}, approval_id="a1",
        )
        path = Path(audit_path)
        assert path.exists()
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["canary_id"] == "c7"
        assert record["success"] is True
        assert record["executed"] is True

    def test_audit_appends_multiple(self, healthy_canary: CanaryCoordinator, audit_path: str):
        """多次 canary 追加写入."""
        for i in range(3):
            healthy_canary.run(
                canary_id=f"c{i}", game_id="g1", action={"type": "t"}, approval_id="a1",
            )
        lines = [l for l in Path(audit_path).read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3

    def test_evidence_chain_collected(self, healthy_canary: CanaryCoordinator):
        """evidence 链收集."""
        result = healthy_canary.run(
            canary_id="c8", game_id="g1", action={"type": "t"}, approval_id="a1",
        )
        assert len(result.evidence) >= 2  # execute + monitor
        assert "exec-1" in result.evidence
        assert "monitor-1" in result.evidence


# ═══════════════════════════════════════════════════════════════
# 5. ProductionReadinessGate
# ═══════════════════════════════════════════════════════════════


class TestProductionReadinessGate:
    """ProductionReadinessGate 启动门."""

    def test_dry_run_ready(self, tmp_path: Path):
        """dry_run 模式就绪."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", required_env=[])
        report = gate.check(config)
        assert report.ready is True
        assert report.checks["dry_run_default"] is True

    def test_production_missing_env_blocks(self, tmp_path: Path):
        """production 缺少环境变量阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="production", required_env=["META_TOKEN"])
        report = gate.check(config)
        assert report.ready is False
        assert any("META_TOKEN" in b for b in report.blockers)

    def test_production_placeholder_env_blocks(self, tmp_path: Path):
        """production 占位符环境变量阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={"META_TOKEN": "your_token"})
        config = AgentConfig(mode="production", required_env=["META_TOKEN"])
        report = gate.check(config)
        assert report.ready is False

    def test_production_no_approval_blocks(self, tmp_path: Path):
        """production 未启用 approval 阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="production", require_approval_in_production=False, required_env=[])
        report = gate.check(config)
        assert report.ready is False
        assert any("approval" in b for b in report.blockers)

    def test_missing_project_root_blocks(self, tmp_path: Path):
        """缺少 pyproject.toml 阻塞."""
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run")
        report = gate.check(config)
        assert report.ready is False
        assert any("project_root" in b for b in report.blockers)

    def test_missing_tests_dir_blocks(self, tmp_path: Path):
        """缺少 tests 目录阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run")
        report = gate.check(config)
        assert report.ready is False
        assert any("tests_present" in b for b in report.blockers)


# ═══════════════════════════════════════════════════════════════
# 6. AutonomousGrowthAgent 安全封套
# ═══════════════════════════════════════════════════════════════


class TestAutonomousGrowthAgent:
    """AutonomousGrowthAgent 安全封套."""

    def test_dry_run_success(self, tmp_path: Path):
        """dry_run 成功执行."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(return_value={"real_api_called": False})
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        agent = AutonomousGrowthAgent(operator=operator, config=AgentConfig(mode="dry_run"), readiness=gate)
        run = agent.run("2026-08-10", ["g1", "g2"], proposed_actions=5, requested_budget=100)
        assert run.status == AgentStatus.COMPLETED
        assert run.games_requested == 2
        assert run.actions_executed == 0  # dry_run 不执行
        assert run.real_api_called is False

    def test_production_executes_actions(self, tmp_path: Path):
        """production 模式执行 actions."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(return_value={"real_api_called": True})
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="production", require_approval_in_production=True, required_env=[])
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)
        run = agent.run("2026-08-10", ["g1"], proposed_actions=3,
                        requested_budget=50, approval_present=True)
        assert run.status == AgentStatus.COMPLETED
        assert run.actions_executed == 3
        assert run.real_api_called is True

    def test_production_without_approval_blocks(self, tmp_path: Path):
        """production 无 approval 阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="production", require_approval_in_production=True, required_env=[])
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)
        run = agent.run("2026-08-10", ["g1"], proposed_actions=1, approval_present=False)
        assert run.status == AgentStatus.BLOCKED
        assert "approval" in run.reason
        operator.assert_not_called()

    def test_exceeds_max_games_blocks(self, tmp_path: Path):
        """超过 max_games 阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", max_games=5)
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)
        run = agent.run("2026-08-10", ["g1", "g2", "g3", "g4", "g5", "g6"])
        assert run.status == AgentStatus.BLOCKED
        assert "game limit" in run.reason

    def test_exceeds_max_actions_blocks(self, tmp_path: Path):
        """超过 max_actions 阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", max_actions=10)
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)
        run = agent.run("2026-08-10", ["g1"], proposed_actions=15)
        assert run.status == AgentStatus.BLOCKED
        assert "action limit" in run.reason

    def test_exceeds_budget_blocks(self, tmp_path: Path):
        """超过 budget 阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", max_daily_budget=100.0)
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)
        run = agent.run("2026-08-10", ["g1"], requested_budget=200.0)
        assert run.status == AgentStatus.BLOCKED
        assert "budget" in run.reason

    def test_low_confidence_blocks(self, tmp_path: Path):
        """置信度低于阈值阻塞."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock()
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", min_confidence=0.8)
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)
        run = agent.run("2026-08-10", ["g1"], confidence=0.5)
        assert run.status == AgentStatus.BLOCKED
        assert "confidence" in run.reason


# ═══════════════════════════════════════════════════════════════
# 7. AutonomousGrowthAgent 熔断器
# ═══════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    """AutonomousGrowthAgent 熔断器."""

    def test_circuit_opens_after_consecutive_failures(self, tmp_path: Path):
        """连续失败后熔断器打开."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(side_effect=RuntimeError("api down"))
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", max_consecutive_failures=3)
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)

        # 前 3 次失败
        for i in range(3):
            run = agent.run(f"2026-08-1{i}", ["g1"])
            assert run.status == AgentStatus.FAILED

        # 第 4 次熔断
        assert agent.circuit_open is True
        run = agent.run("2026-08-20", ["g1"])
        assert run.status == AgentStatus.CIRCUIT_OPEN
        assert "consecutive failure" in run.reason

    def test_circuit_resets_on_success(self, tmp_path: Path):
        """成功后熔断器重置."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(side_effect=[RuntimeError("fail"), {"real_api_called": False}])
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", max_consecutive_failures=3)
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)

        run1 = agent.run("2026-08-10", ["g1"])
        assert run1.status == AgentStatus.FAILED
        assert agent.consecutive_failures == 1

        run2 = agent.run("2026-08-11", ["g2"])
        assert run2.status == AgentStatus.COMPLETED
        assert agent.consecutive_failures == 0

    def test_circuit_reset_requires_authorization(self, tmp_path: Path):
        """熔断器重置需要授权."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(side_effect=RuntimeError("fail"))
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        config = AgentConfig(mode="dry_run", max_consecutive_failures=1)
        agent = AutonomousGrowthAgent(operator=operator, config=config, readiness=gate)

        agent.run("2026-08-10", ["g1"])  # 失败, 熔断
        assert agent.circuit_open is True

        # 未授权重置失败
        assert agent.reset_circuit(authorized=False) is False
        assert agent.circuit_open is True

        # 授权重置成功
        assert agent.reset_circuit(authorized=True) is True
        assert agent.circuit_open is False


# ═══════════════════════════════════════════════════════════════
# 8. AgentConfig 校验
# ═══════════════════════════════════════════════════════════════


class TestAgentConfig:
    """AgentConfig 校验."""

    def test_default_config_valid(self):
        """默认配置合法."""
        config = AgentConfig()
        assert config.validate() == []
        assert config.mode == "dry_run"

    def test_invalid_mode(self):
        """非法 mode."""
        config = AgentConfig(mode="invalid")
        errors = config.validate()
        assert any("mode" in e for e in errors)

    def test_zero_max_games_invalid(self):
        """max_games=0 非法."""
        config = AgentConfig(max_games=0)
        assert any("max_games" in e for e in config.validate())

    def test_negative_budget_invalid(self):
        """负 budget 非法."""
        config = AgentConfig(max_daily_budget=-1)
        assert any("budget" in e for e in config.validate())

    def test_confidence_out_of_range(self):
        """confidence 超范围非法."""
        config = AgentConfig(min_confidence=1.5)
        assert any("confidence" in e for e in config.validate())

    def test_zero_failures_invalid(self):
        """max_consecutive_failures=0 非法."""
        config = AgentConfig(max_consecutive_failures=0)
        assert any("consecutive_failures" in e for e in config.validate())


# ═══════════════════════════════════════════════════════════════
# 9. AgentRun 幂等性
# ═══════════════════════════════════════════════════════════════


class TestAgentRunIdempotency:
    """AutonomousGrowthAgent 幂等性."""

    def test_same_input_returns_same_run_id(self, tmp_path: Path):
        """相同输入返回相同 run_id (幂等)."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(return_value={"real_api_called": False})
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        agent = AutonomousGrowthAgent(operator=operator, config=AgentConfig(mode="dry_run"), readiness=gate)

        run1 = agent.run("2026-08-10", ["g1", "g2"])
        run2 = agent.run("2026-08-10", ["g1", "g2"])
        assert run1.run_id == run2.run_id

    def test_different_games_different_run_id(self, tmp_path: Path):
        """不同游戏列表不同 run_id."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(return_value={"real_api_called": False})
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})
        agent = AutonomousGrowthAgent(operator=operator, config=AgentConfig(mode="dry_run"), readiness=gate)

        run1 = agent.run("2026-08-10", ["g1"])
        run2 = agent.run("2026-08-10", ["g2"])
        assert run1.run_id != run2.run_id

    def test_different_mode_different_run_id(self, tmp_path: Path):
        """不同 mode 不同 run_id."""
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        operator = MagicMock(return_value={"real_api_called": False})
        gate = ProductionReadinessGate(root=str(tmp_path), environ={})

        agent_dry = AutonomousGrowthAgent(operator=operator, config=AgentConfig(mode="dry_run"), readiness=gate)
        agent_prod = AutonomousGrowthAgent(operator=operator,
                                           config=AgentConfig(mode="production", required_env=[]),
                                           readiness=gate)
        run1 = agent_dry.run("2026-08-10", ["g1"])
        run2 = agent_prod.run("2026-08-10", ["g1"], approval_present=True)
        assert run1.run_id != run2.run_id
