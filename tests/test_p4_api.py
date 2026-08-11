"""P4 API 端点集成测试 — 验证 HTTP 接口暴露.

测试覆盖:
  1. /api/p4/readiness — 启动就绪检查
  2. /api/p4/agent/status — Agent 状态
  3. /api/p4/agent/run — Agent 运行 (dry_run + production + 幂等)
  4. /api/p4/agent/circuit/reset — 熔断器重置
  5. /api/p4/fleet/run — Fleet 分片编排
  6. /api/p4/cycle/run + /api/p4/cycle/{id} — Cycle 运行与查询
  7. /api/p4/product/advance — 产品生命周期推进
  8. /api/p4/governance/arbitrate — 多 Agent 仲裁
  9. /api/p4/governance/takeover + release — 人工接管
  10. /api/p4/governance/permissions — 权限矩阵
  11. /api/p4/slo/evaluate — SLO 评估
  12. /api/p4/queue/* — DurableQueue 操作
  13. /api/p4/canary/run — Canary 灰度
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from src.market_ops.workspace.app import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient."""
    return TestClient(app)


def _unique_id(prefix: str = "id") -> str:
    """生成唯一 ID (避免全局状态污染)."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ═══════════════════════════════════════════════════════════════
# 1. Readiness
# ═══════════════════════════════════════════════════════════════


class TestP4Readiness:
    """P4 启动就绪检查."""

    def test_readiness_returns_200(self, client: TestClient):
        """readiness 返回 200."""
        response = client.get("/api/p4/readiness")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "checks" in data
        assert "blockers" in data

    def test_readiness_includes_checks(self, client: TestClient):
        """readiness 包含 5 项检查."""
        data = client.get("/api/p4/readiness").json()
        assert "project_root" in data["checks"]
        assert "tests_present" in data["checks"]
        assert "data_writable" in data["checks"]
        assert "logs_writable" in data["checks"]
        assert "dry_run_default" in data["checks"]


# ═══════════════════════════════════════════════════════════════
# 2. Agent Status
# ═══════════════════════════════════════════════════════════════


class TestP4AgentStatus:
    """P4 Agent 状态查询."""

    def test_status_returns_200(self, client: TestClient):
        """status 返回 200."""
        response = client.get("/api/p4/agent/status")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "dry_run"
        assert data["circuit_open"] is False
        assert "consecutive_failures" in data
        assert "max_consecutive_failures" in data


# ═══════════════════════════════════════════════════════════════
# 3. Agent Run
# ═══════════════════════════════════════════════════════════════


class TestP4AgentRun:
    """P4 Agent 运行."""

    def test_dry_run_success(self, client: TestClient):
        """dry_run 模式成功运行."""
        response = client.post("/api/p4/agent/run", json={
            "business_date": "2026-08-10",
            "game_ids": ["g1", "g2"],
            "mode": "dry_run",
            "proposed_actions": 3,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["games_requested"] == 2
        assert data["actions_executed"] == 0  # dry_run 不执行

    def test_idempotent_same_input(self, client: TestClient):
        """相同输入返回相同 run_id (幂等)."""
        req = {
            "business_date": "2026-08-10",
            "game_ids": ["g1", "g2"],
            "mode": "dry_run",
        }
        r1 = client.post("/api/p4/agent/run", json=req).json()
        r2 = client.post("/api/p4/agent/run", json=req).json()
        assert r1["run_id"] == r2["run_id"]

    def test_missing_business_date_returns_400(self, client: TestClient):
        """缺 business_date 返回 400."""
        response = client.post("/api/p4/agent/run", json={"game_ids": ["g1"]})
        assert response.status_code == 400

    def test_missing_game_ids_returns_400(self, client: TestClient):
        """缺 game_ids 返回 400."""
        response = client.post("/api/p4/agent/run", json={"business_date": "2026-08-10"})
        assert response.status_code == 400

    def test_invalid_mode_returns_400(self, client: TestClient):
        """非法 mode 返回 400."""
        response = client.post("/api/p4/agent/run", json={
            "business_date": "2026-08-10",
            "game_ids": ["g1"],
            "mode": "invalid",
        })
        assert response.status_code == 400

    def test_production_without_approval_blocked(self, client: TestClient):
        """production 无 approval 被阻塞."""
        response = client.post("/api/p4/agent/run", json={
            "business_date": "2026-08-10",
            "game_ids": ["g1"],
            "mode": "production",
            "approval_present": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"


# ═══════════════════════════════════════════════════════════════
# 4. Circuit Reset
# ═══════════════════════════════════════════════════════════════


class TestP4CircuitReset:
    """P4 熔断器重置."""

    def test_unauthorized_reset_fails(self, client: TestClient):
        """未授权重置失败."""
        response = client.post("/api/p4/agent/circuit/reset", json={"authorized": False})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_authorized_reset_succeeds(self, client: TestClient):
        """授权重置成功."""
        response = client.post("/api/p4/agent/circuit/reset", json={"authorized": True})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["circuit_open"] is False


# ═══════════════════════════════════════════════════════════════
# 5. Fleet Run
# ═══════════════════════════════════════════════════════════════


class TestP4FleetRun:
    """P4.1 Fleet 分片编排."""

    def test_fleet_run_success(self, client: TestClient):
        """Fleet 成功运行."""
        response = client.post("/api/p4/fleet/run", json={
            "business_date": "2026-08-10",
            "game_ids": ["g1", "g2", "g3", "g4"],
            "shard_size": 2,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["business_date"] == "2026-08-10"
        assert data["total_games"] == 4
        assert data["successful_shards"] == 2
        assert data["failed_shards"] == 0
        assert data["completed"] is True

    def test_fleet_missing_params_400(self, client: TestClient):
        """缺参数返回 400."""
        response = client.post("/api/p4/fleet/run", json={"game_ids": ["g1"]})
        assert response.status_code == 400

    def test_fleet_invalid_config_400(self, client: TestClient):
        """非法配置返回 400."""
        response = client.post("/api/p4/fleet/run", json={
            "business_date": "2026-08-10",
            "game_ids": ["g1"],
            "max_workers": 0,
        })
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════
# 6. Cycle
# ═══════════════════════════════════════════════════════════════


class TestP4Cycle:
    """P4.2 Cycle 运行与查询."""

    def test_cycle_run_success(self, client: TestClient):
        """Cycle 成功运行到 COMPLETE."""
        cycle_id = _unique_id("cycle")
        response = client.post("/api/p4/cycle/run", json={
            "cycle_id": cycle_id,
            "business_date": "2026-08-10",
            "production": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["cycle_id"] == cycle_id
        assert data["stage"] == "complete"

    def test_cycle_get_existing(self, client: TestClient):
        """查询已存在的 cycle."""
        cycle_id = _unique_id("cycle")
        # 先运行
        client.post("/api/p4/cycle/run", json={
            "cycle_id": cycle_id,
            "business_date": "2026-08-10",
        })
        # 再查询
        response = client.get(f"/api/p4/cycle/{cycle_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["cycle_id"] == cycle_id

    def test_cycle_get_nonexistent_404(self, client: TestClient):
        """查询不存在的 cycle 返回 404."""
        response = client.get("/api/p4/cycle/nonexistent")
        assert response.status_code == 404

    def test_cycle_missing_params_400(self, client: TestClient):
        """缺参数返回 400."""
        response = client.post("/api/p4/cycle/run", json={"cycle_id": "c1"})
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════
# 7. Product Advance
# ═══════════════════════════════════════════════════════════════


class TestP4ProductAdvance:
    """P4.3 产品生命周期推进."""

    def test_idea_to_prototype(self, client: TestClient):
        """IDEA → PROTOTYPE."""
        response = client.post("/api/p4/product/advance", json={
            "product_id": "p1",
            "stage": "idea",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "prototype"
        assert "idea->prototype" in data["history"][0]

    def test_prototype_build_passed(self, client: TestClient):
        """PROTOTYPE build passed → MARKET_TEST."""
        response = client.post("/api/p4/product/advance", json={
            "product_id": "p1",
            "stage": "prototype",
            "metrics": {"build_passed": 1},
        })
        assert response.status_code == 200
        assert response.json()["stage"] == "market_test"

    def test_market_test_to_live(self, client: TestClient):
        """MARKET_TEST → LIVE (KPI 达标)."""
        response = client.post("/api/p4/product/advance", json={
            "product_id": "p1",
            "stage": "market_test",
            "metrics": {"cpi": 0.8, "d1_retention": 0.30, "roas": 0.9, "installs": 150},
        })
        assert response.status_code == 200
        assert response.json()["stage"] == "live"

    def test_missing_product_id_400(self, client: TestClient):
        """缺 product_id 返回 400."""
        response = client.post("/api/p4/product/advance", json={"stage": "idea"})
        assert response.status_code == 400

    def test_invalid_stage_400(self, client: TestClient):
        """非法 stage 返回 400."""
        response = client.post("/api/p4/product/advance", json={
            "product_id": "p1",
            "stage": "invalid_stage",
        })
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════
# 8. Governance Arbitrate
# ═══════════════════════════════════════════════════════════════


class TestP4GovernanceArbitrate:
    """P4.4 多 Agent 仲裁."""

    def test_arbitrate_selects_within_budget(self, client: TestClient):
        """预算内选中提案."""
        response = client.post("/api/p4/governance/arbitrate", json={
            "proposals": [
                {
                    "role": "growth", "game_id": "g1", "resource": "budget",
                    "action": "increase", "priority": 0.9, "confidence": 0.9,
                    "requested_budget": 100,
                },
                {
                    "role": "ua", "game_id": "g2", "resource": "campaign",
                    "action": "create", "priority": 0.5, "confidence": 0.8,
                    "requested_budget": 50,
                },
            ],
            "budget": 200,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_arbitrate_empty_proposals(self, client: TestClient):
        """空提案返回空."""
        response = client.post("/api/p4/governance/arbitrate", json={
            "proposals": [],
            "budget": 100,
        })
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_arbitrate_invalid_role_400(self, client: TestClient):
        """非法 role 返回 400."""
        response = client.post("/api/p4/governance/arbitrate", json={
            "proposals": [{
                "role": "invalid_role", "game_id": "g1", "resource": "r",
                "action": "a", "priority": 0.5, "confidence": 0.5,
            }],
            "budget": 100,
        })
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════
# 9. Governance Takeover/Release
# ═══════════════════════════════════════════════════════════════


class TestP4GovernanceTakeover:
    """P4.4 人工接管."""

    def test_unauthorized_takeover_fails(self, client: TestClient):
        """未授权接管失败."""
        response = client.post("/api/p4/governance/takeover", json={"authorized": False})
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_authorized_takeover_succeeds(self, client: TestClient):
        """授权接管成功."""
        response = client.post("/api/p4/governance/takeover", json={"authorized": True})
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["human_takeover"] is True

    def test_takeover_then_release(self, client: TestClient):
        """接管后释放."""
        client.post("/api/p4/governance/takeover", json={"authorized": True})
        response = client.post("/api/p4/governance/release", json={"authorized": True})
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["human_takeover"] is False


# ═══════════════════════════════════════════════════════════════
# 10. Governance Permissions
# ═══════════════════════════════════════════════════════════════


class TestP4GovernancePermissions:
    """P4.4 权限矩阵查询."""

    def test_permissions_returns_10_roles(self, client: TestClient):
        """返回 10 个角色的权限."""
        response = client.get("/api/p4/governance/permissions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        assert "strategy" in data
        assert "growth" in data
        assert "ua" in data
        assert "data_analyst" in data
        assert "player_support" in data
        assert "market_intelligence" in data

    def test_strategy_permissions(self, client: TestClient):
        """STRATEGY 权限内容."""
        data = client.get("/api/p4/governance/permissions").json()
        assert data["strategy"] == ["propose_strategy", "read_all"]


# ═══════════════════════════════════════════════════════════════
# 11. SLO Evaluate
# ═══════════════════════════════════════════════════════════════


class TestP4SLOEvaluate:
    """P4.5 SLO 评估."""

    def test_all_healthy(self, client: TestClient):
        """所有指标达标."""
        response = client.get("/api/p4/slo/evaluate", params={
            "success_rate": 1.0,
            "failed_shards": 0,
            "latency_ms": 100000.0,
            "queue_depth": 100,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["violations"] == []

    def test_violations_detected(self, client: TestClient):
        """检测到违规."""
        response = client.get("/api/p4/slo/evaluate", params={
            "success_rate": 0.90,
            "failed_shards": 1,
            "latency_ms": 400000.0,
            "queue_depth": 2000,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is False
        assert len(data["violations"]) == 4


# ═══════════════════════════════════════════════════════════════
# 12. Queue Operations
# ═══════════════════════════════════════════════════════════════


class TestP4Queue:
    """P4.5 DurableQueue 操作."""

    def test_enqueue_and_pending(self, client: TestClient):
        """入队并查询 pending."""
        job_id = _unique_id("job")
        response = client.post("/api/p4/queue/enqueue", json={
            "job_id": job_id,
            "payload": {"task": "analyze"},
        })
        assert response.status_code == 200
        assert response.json()["success"] is True

        pending = client.get("/api/p4/queue/pending").json()
        assert pending["count"] >= 1
        assert any(j["job_id"] == job_id for j in pending["jobs"])

    def test_enqueue_idempotent(self, client: TestClient):
        """重复入队返回 False (幂等)."""
        job_id = _unique_id("job")
        client.post("/api/p4/queue/enqueue", json={"job_id": job_id, "payload": {}})
        response = client.post("/api/p4/queue/enqueue", json={"job_id": job_id, "payload": {}})
        assert response.json()["success"] is False

    def test_ack_job(self, client: TestClient):
        """ack job."""
        job_id = _unique_id("job")
        client.post("/api/p4/queue/enqueue", json={"job_id": job_id, "payload": {}})
        response = client.post(f"/api/p4/queue/ack/{job_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_fail_job(self, client: TestClient):
        """fail job."""
        job_id = _unique_id("job")
        client.post("/api/p4/queue/enqueue", json={"job_id": job_id, "payload": {}})
        response = client.post(f"/api/p4/queue/fail/{job_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_dead_letters(self, client: TestClient):
        """死信队列."""
        job_id = _unique_id("job-dead")
        # 入队并 fail 到死信
        client.post("/api/p4/queue/enqueue", json={
            "job_id": job_id, "payload": {}, "max_attempts": 1,
        })
        client.post(f"/api/p4/queue/fail/{job_id}")
        response = client.get("/api/p4/queue/dead-letters")
        assert response.status_code == 200
        data = response.json()
        assert any(j["job_id"] == job_id for j in data["jobs"])

    def test_enqueue_missing_job_id_400(self, client: TestClient):
        """缺 job_id 返回 400."""
        response = client.post("/api/p4/queue/enqueue", json={"payload": {}})
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════
# 13. Canary Run
# ═══════════════════════════════════════════════════════════════


class TestP4CanaryRun:
    """P4.5 Canary 灰度运行."""

    def test_canary_success(self, client: TestClient):
        """Canary 成功."""
        canary_id = _unique_id("canary")
        response = client.post("/api/p4/canary/run", json={
            "canary_id": canary_id,
            "game_id": "g1",
            "action": {"type": "budget_increase"},
            "approval_id": "appr-1",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["executed"] is True

    def test_canary_missing_approval_400(self, client: TestClient):
        """缺 approval_id 返回 400."""
        response = client.post("/api/p4/canary/run", json={
            "canary_id": _unique_id("canary"),
            "game_id": "g1",
            "action": {"type": "test"},
        })
        assert response.status_code == 400

    def test_canary_idempotent(self, client: TestClient):
        """重复 canary_id 拒绝."""
        canary_id = _unique_id("canary")
        client.post("/api/p4/canary/run", json={
            "canary_id": canary_id,
            "game_id": "g1",
            "action": {"type": "test"},
            "approval_id": "a1",
        })
        response = client.post("/api/p4/canary/run", json={
            "canary_id": canary_id,
            "game_id": "g1",
            "action": {"type": "test"},
            "approval_id": "a1",
        })
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "already used" in response.json()["reason"]
