"""ConflictDetector 冲突检测器单元测试.

覆盖:
  - 版本管理 (register_change / get_version)
  - 版本冲突检测 (check_before_modify - version)
  - 并发冲突检测 (check_before_modify - concurrent)
  - 参数冲突检测 (detect_parameter_conflict)
  - 持久化与查询 (list / get / stats / scan_recent)
  - API 端点集成
  - 边界场景
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.market_ops.workspace.conflict_detector import (
    ConflictDetector,
    Conflict,
    MetricVersion,
    get_conflict_detector,
    reset_conflict_detector,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def detector(tmp_path: Path) -> ConflictDetector:
    """创建独立的 ConflictDetector (临时目录)."""
    return ConflictDetector(data_dir=str(tmp_path))


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前后重置单例."""
    reset_conflict_detector()
    yield
    reset_conflict_detector()


# ═══════════════════════════════════════════════════════════════
# 1. 版本管理测试
# ═══════════════════════════════════════════════════════════════


class TestVersionManagement:
    def test_initial_version_is_1(self, detector):
        """未注册的指标版本为 1 (默认值)."""
        version = detector.get_version("game_001", "retention_d1")
        assert version["version"] == 1
        assert version["last_modified_by"] == ""

    def test_register_change_increments_version(self, detector):
        """注册变更后版本号 +1."""
        v1 = detector.register_change(
            game_id="game_001",
            metric="retention_d1",
            agent_id="numerical_designer",
            new_value=0.45,
            base_version=1,
        )
        assert v1.version == 2
        assert v1.current_value == 0.45
        assert v1.last_modified_by == "numerical_designer"

        v2 = detector.register_change(
            game_id="game_001",
            metric="retention_d1",
            agent_id="data_analyst",
            new_value=0.48,
            base_version=2,
        )
        assert v2.version == 3
        assert v2.current_value == 0.48

    def test_get_version_after_register(self, detector):
        """注册后查询版本."""
        detector.register_change(
            game_id="game_001",
            metric="arpu",
            agent_id="numerical",
            new_value=1.5,
            base_version=1,
        )
        version = detector.get_version("game_001", "arpu")
        assert version["version"] == 2
        assert version["current_value"] == 1.5
        assert version["last_modified_by"] == "numerical"

    def test_get_all_versions(self, detector):
        """查询所有游戏的版本表."""
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        detector.register_change("game_001", "arpu", "agent_b", 1.5, 1)
        detector.register_change("game_002", "retention_d1", "agent_a", 0.40, 1)

        all_versions = detector.get_all_versions()
        assert "game_001" in all_versions
        assert "game_002" in all_versions
        assert len(all_versions["game_001"]) == 2

        # 按 game_id 过滤
        game1_only = detector.get_all_versions(game_id="game_001")
        assert "game_001" in game1_only
        assert "game_002" not in game1_only


# ═══════════════════════════════════════════════════════════════
# 2. 版本冲突检测
# ═══════════════════════════════════════════════════════════════


class TestVersionConflict:
    def test_no_conflict_when_version_matches(self, detector):
        """版本匹配且同一 Agent 连续修改时无冲突."""
        # Agent A 注册变更 v1 → v2
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        # Agent A 基于最新版本 v2 继续修改 → 无冲突 (同 Agent 不触发并发冲突)
        conflict = detector.check_before_modify(
            game_id="game_001",
            metric="retention_d1",
            agent_id="agent_a",
            proposed_value=0.48,
            base_version=2,
        )
        assert conflict is None

    def test_version_conflict_when_base_outdated(self, detector):
        """基于过期版本修改 → 版本冲突."""
        # Agent A 注册变更 v1 → v2
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        # Agent B 基于旧版本 v1 修改 → 冲突
        conflict = detector.check_before_modify(
            game_id="game_001",
            metric="retention_d1",
            agent_id="agent_b",
            proposed_value=0.50,
            base_version=1,  # 过期
        )
        assert conflict is not None
        assert conflict.conflict_type == "version"
        assert conflict.severity == "critical"
        assert conflict.agent_a == "agent_b"
        assert conflict.agent_b == "agent_a"
        assert conflict.version_a == 1
        assert conflict.version_b == 2

    def test_version_conflict_persisted(self, detector, tmp_path):
        """版本冲突持久化到 JSONL."""
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        detector.check_before_modify(
            game_id="game_001",
            metric="retention_d1",
            agent_id="agent_b",
            proposed_value=0.50,
            base_version=1,
        )
        conflicts_path = tmp_path / "collaboration" / "conflicts.jsonl"
        assert conflicts_path.exists()
        lines = conflicts_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["conflict_type"] == "version"
        assert record["severity"] == "critical"

    def test_version_conflict_suggestion(self, detector):
        """版本冲突的建议包含最新版本号."""
        detector.register_change("game_001", "arpu", "agent_a", 1.5, 1)
        conflict = detector.check_before_modify(
            game_id="game_001",
            metric="arpu",
            agent_id="agent_b",
            proposed_value=1.8,
            base_version=1,
        )
        assert conflict is not None
        assert "v2" in conflict.suggestion
        assert "1.5" in conflict.suggestion


# ═══════════════════════════════════════════════════════════════
# 3. 并发冲突检测
# ═══════════════════════════════════════════════════════════════


class TestConcurrentConflict:
    def test_concurrent_conflict_within_window(self, detector):
        """时间窗口内同一指标被多个 Agent 修改 → 并发冲突."""
        # Agent A 刚注册变更 (版本 v1 → v2)
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        # Agent B 基于最新版本 v2 修改, 但在时间窗口内 → 并发冲突
        conflict = detector.check_before_modify(
            game_id="game_001",
            metric="retention_d1",
            agent_id="agent_b",
            proposed_value=0.48,
            base_version=2,  # 版本匹配
        )
        assert conflict is not None
        assert conflict.conflict_type == "concurrent"
        assert conflict.severity == "warning"
        assert conflict.agent_a == "agent_b"
        assert conflict.agent_b == "agent_a"

    def test_no_concurrent_conflict_same_agent(self, detector):
        """同一 Agent 的连续修改不触发并发冲突."""
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        conflict = detector.check_before_modify(
            game_id="game_001",
            metric="retention_d1",
            agent_id="agent_a",  # 同一 Agent
            proposed_value=0.48,
            base_version=2,
        )
        assert conflict is None

    def test_no_concurrent_conflict_different_metric(self, detector):
        """不同指标不触发并发冲突."""
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        conflict = detector.check_before_modify(
            game_id="game_001",
            metric="arpu",  # 不同指标
            agent_id="agent_b",
            proposed_value=1.5,
            base_version=1,
        )
        assert conflict is None


# ═══════════════════════════════════════════════════════════════
# 4. 参数冲突检测
# ═══════════════════════════════════════════════════════════════


class TestParameterConflict:
    def test_opposite_direction_conflict(self, detector):
        """方向相反的调优建议 → 参数冲突."""
        recommendations = [
            {"agent_id": "agent_a", "adjustment_pct": 50.0, "suggested_param": 150.0},
            {"agent_id": "agent_b", "adjustment_pct": -20.0, "suggested_param": 80.0},
        ]
        conflicts = detector.detect_parameter_conflict(
            "game_001", "retention_d1", recommendations
        )
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "parameter"
        assert conflicts[0].agent_a == "agent_a"
        assert conflicts[0].agent_b == "agent_b"

    def test_same_direction_no_conflict(self, detector):
        """方向相同的调优建议无冲突."""
        recommendations = [
            {"agent_id": "agent_a", "adjustment_pct": 50.0, "suggested_param": 150.0},
            {"agent_id": "agent_b", "adjustment_pct": 30.0, "suggested_param": 130.0},
        ]
        conflicts = detector.detect_parameter_conflict(
            "game_001", "retention_d1", recommendations
        )
        assert len(conflicts) == 0

    def test_small_difference_no_conflict(self, detector):
        """差异不足阈值无冲突."""
        recommendations = [
            {"agent_id": "agent_a", "adjustment_pct": 5.0, "suggested_param": 105.0},
            {"agent_id": "agent_b", "adjustment_pct": -5.0, "suggested_param": 95.0},
        ]
        # 差异 10%, 阈值 10% → 不触发
        conflicts = detector.detect_parameter_conflict(
            "game_001", "retention_d1", recommendations
        )
        assert len(conflicts) == 0

    def test_single_recommendation_no_conflict(self, detector):
        """单条建议无冲突."""
        recommendations = [
            {"agent_id": "agent_a", "adjustment_pct": 50.0, "suggested_param": 150.0},
        ]
        conflicts = detector.detect_parameter_conflict(
            "game_001", "retention_d1", recommendations
        )
        assert len(conflicts) == 0

    def test_multiple_conflicts(self, detector):
        """3 条建议两两冲突 → 3 条冲突."""
        recommendations = [
            {"agent_id": "agent_a", "adjustment_pct": 50.0, "suggested_param": 150.0},
            {"agent_id": "agent_b", "adjustment_pct": -30.0, "suggested_param": 70.0},
            {"agent_id": "agent_c", "adjustment_pct": -20.0, "suggested_param": 80.0},
        ]
        conflicts = detector.detect_parameter_conflict(
            "game_001", "retention_d1", recommendations
        )
        # A vs B, A vs C → 2 条 (B vs C 方向相同)
        assert len(conflicts) == 2


# ═══════════════════════════════════════════════════════════════
# 5. 持久化与查询测试
# ═══════════════════════════════════════════════════════════════


class TestPersistenceAndQuery:
    def test_list_conflicts_empty(self, detector):
        """空状态查询返回空列表."""
        assert detector.list_conflicts() == []

    def test_list_conflicts_with_records(self, detector):
        """多条冲突查询."""
        # 制造版本冲突
        detector.register_change("game_001", "retention_d1", "agent_a", 0.45, 1)
        detector.check_before_modify("game_001", "retention_d1", "agent_b", 0.50, 1)
        # 制造参数冲突
        detector.detect_parameter_conflict(
            "game_001", "arpu",
            [
                {"agent_id": "a", "adjustment_pct": 50.0, "suggested_param": 150.0},
                {"agent_id": "b", "adjustment_pct": -20.0, "suggested_param": 80.0},
            ],
        )
        conflicts = detector.list_conflicts()
        assert len(conflicts) == 2

    def test_list_conflicts_filter_by_game(self, detector):
        """按 game_id 过滤."""
        detector.register_change("game_001", "m", "a", 1.0, 1)
        detector.check_before_modify("game_001", "m", "b", 2.0, 1)
        detector.register_change("game_002", "m", "a", 1.0, 1)
        detector.check_before_modify("game_002", "m", "b", 2.0, 1)

        game1_conflicts = detector.list_conflicts(game_id="game_001")
        assert len(game1_conflicts) == 1
        assert game1_conflicts[0]["game_id"] == "game_001"

    def test_list_conflicts_filter_by_type(self, detector):
        """按 conflict_type 过滤."""
        detector.register_change("game_001", "m", "a", 1.0, 1)
        detector.check_before_modify("game_001", "m", "b", 2.0, 1)  # version + concurrent
        detector.detect_parameter_conflict(
            "game_001", "arpu",
            [
                {"agent_id": "a", "adjustment_pct": 50.0, "suggested_param": 150.0},
                {"agent_id": "b", "adjustment_pct": -20.0, "suggested_param": 80.0},
            ],
        )
        version_conflicts = detector.list_conflicts(conflict_type="version")
        assert all(c["conflict_type"] == "version" for c in version_conflicts)

    def test_get_conflict_by_id(self, detector):
        """按 ID 查询单条冲突."""
        detector.register_change("game_001", "m", "a", 1.0, 1)
        conflict = detector.check_before_modify("game_001", "m", "b", 2.0, 1)
        assert conflict is not None
        found = detector.get_conflict(conflict.conflict_id)
        assert found is not None
        assert found["conflict_id"] == conflict.conflict_id

    def test_get_conflict_not_found(self, detector):
        """查询不存在的 ID 返回 None."""
        assert detector.get_conflict("nonexistent") is None

    def test_get_stats(self, detector):
        """统计信息."""
        detector.register_change("game_001", "m", "a", 1.0, 1)
        detector.check_before_modify("game_001", "m", "b", 2.0, 1)
        stats = detector.get_stats()
        assert stats["total_conflicts"] >= 1
        assert "version" in stats["type_counts"]
        assert stats["tracked_games"] == 1
        assert stats["tracked_metrics"] == 1

    def test_scan_recent_conflicts(self, detector):
        """扫描最近时间窗口内的冲突."""
        detector.register_change("game_001", "m", "a", 1.0, 1)
        detector.check_before_modify("game_001", "m", "b", 2.0, 1)
        recent = detector.scan_recent_conflicts(window_hours=24)
        assert len(recent) >= 1


# ═══════════════════════════════════════════════════════════════
# 6. API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestConflictAPI:
    @pytest.fixture
    def client(self):
        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_list_conflicts_endpoint(self, client):
        """测试冲突列表端点."""
        resp = client.get("/api/collaboration/conflicts")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_conflict_stats_endpoint(self, client):
        """测试冲突统计端点."""
        resp = client.get("/api/collaboration/conflicts/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_conflicts" in data
        assert "tracked_games" in data

    def test_versions_endpoint(self, client):
        """测试版本表查询端点."""
        resp = client.get("/api/collaboration/conflicts/versions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_check_endpoint_no_conflict(self, client):
        """测试冲突预检端点 (无冲突)."""
        resp = client.post(
            "/api/collaboration/conflicts/check",
            json={
                "game_id": "test_game",
                "metric": "retention_d1",
                "agent_id": "agent_a",
                "proposed_value": 0.45,
                "base_version": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_conflict"] is False

    def test_check_endpoint_with_conflict(self, client):
        """测试冲突预检端点 (有冲突)."""
        # 先注册一个变更
        client.post(
            "/api/collaboration/conflicts/register",
            json={
                "game_id": "test_conflict_game",
                "metric": "retention_d1",
                "agent_id": "agent_a",
                "new_value": 0.45,
                "base_version": 1,
            },
        )
        # 基于旧版本修改 → 冲突
        resp = client.post(
            "/api/collaboration/conflicts/check",
            json={
                "game_id": "test_conflict_game",
                "metric": "retention_d1",
                "agent_id": "agent_b",
                "proposed_value": 0.50,
                "base_version": 1,  # 过期
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_conflict"] is True
        assert data["conflict"]["conflict_type"] == "version"

    def test_register_endpoint(self, client):
        """测试注册变更端点."""
        resp = client.post(
            "/api/collaboration/conflicts/register",
            json={
                "game_id": "test_register_game",
                "metric": "arpu",
                "agent_id": "numerical_designer",
                "new_value": 1.5,
                "base_version": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 2
        assert data["current_value"] == 1.5
        assert data["last_modified_by"] == "numerical_designer"

    def test_conflict_detail_not_found(self, client):
        """测试不存在的冲突 ID 返回 404."""
        resp = client.get("/api/collaboration/conflicts/nonexistent-id")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 7. 边界场景测试
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_reset_clears_version_table(self, detector):
        """reset 清空版本表 (不删冲突记录)."""
        detector.register_change("game_001", "m", "a", 1.0, 1)
        assert len(detector.get_all_versions()) == 1
        detector.reset()
        assert len(detector.get_all_versions()) == 0

    def test_multiple_games_independent(self, detector):
        """不同游戏的版本独立."""
        detector.register_change("game_001", "m", "a", 1.0, 1)
        detector.register_change("game_002", "m", "b", 2.0, 1)
        v1 = detector.get_version("game_001", "m")
        v2 = detector.get_version("game_002", "m")
        assert v1["version"] == 2
        assert v2["version"] == 2
        assert v1["last_modified_by"] == "a"
        assert v2["last_modified_by"] == "b"

    def test_same_game_different_metrics_independent(self, detector):
        """同一游戏不同指标独立."""
        detector.register_change("game_001", "m1", "a", 1.0, 1)
        detector.register_change("game_001", "m2", "b", 2.0, 1)
        v1 = detector.get_version("game_001", "m1")
        v2 = detector.get_version("game_001", "m2")
        assert v1["last_modified_by"] == "a"
        assert v2["last_modified_by"] == "b"

    def test_singleton(self):
        """单例模式测试."""
        d1 = get_conflict_detector(data_dir="/tmp/test_conflict_singleton")
        d2 = get_conflict_detector()
        assert d1 is d2

    def test_singleton_force_reinit(self):
        """force=True 重新初始化."""
        d1 = get_conflict_detector(data_dir="/tmp/test_conflict_force")
        d2 = get_conflict_detector(force=True)
        assert d1 is not d2


# ═══════════════════════════════════════════════════════════════
# 8. 完整冲突场景集成测试
# ═══════════════════════════════════════════════════════════════


class TestIntegrationScenarios:
    def test_full_conflict_scenario(self, detector):
        """完整冲突场景: Agent A 修改 → Agent B 基于旧版本修改 → 冲突."""
        # Step 1: Agent A 修改 retention_d1 (v1 → v2)
        detector.register_change(
            game_id="merge_game_001",
            metric="retention_d1",
            agent_id="numerical_designer",
            new_value=0.45,
            base_version=1,
            source_event="tuning_recommended",
        )

        # Step 2: Agent B (LiveOps) 基于旧版本 v1 修改同一指标
        conflict = detector.check_before_modify(
            game_id="merge_game_001",
            metric="retention_d1",
            agent_id="liveops_executor",
            proposed_value=0.40,
            base_version=1,  # 过期
            source_event="budget_adjustment",
        )

        # Step 3: 验证冲突
        assert conflict is not None
        assert conflict.conflict_type == "version"
        assert conflict.severity == "critical"
        assert conflict.agent_a == "liveops_executor"
        assert conflict.agent_b == "numerical_designer"

        # Step 4: 查询冲突记录
        conflicts = detector.list_conflicts(game_id="merge_game_001")
        assert len(conflicts) >= 1

    def test_parameter_conflict_scenario(self, detector):
        """参数冲突场景: 两个 Agent 对同一指标给出相反建议."""
        recommendations = [
            {
                "agent_id": "numerical_designer",
                "adjustment_pct": 50.0,
                "suggested_param": 150.0,
                "current_param": 100.0,
            },
            {
                "agent_id": "data_analyst",
                "adjustment_pct": -30.0,
                "suggested_param": 70.0,
                "current_param": 100.0,
            },
        ]
        conflicts = detector.detect_parameter_conflict(
            "merge_game_001", "onboarding_reward", recommendations
        )
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "parameter"
        assert "numerical_designer" in conflicts[0].description
        assert "data_analyst" in conflicts[0].description
