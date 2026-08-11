"""iOSReleaseOrchestrator 单元测试 — 7 步发布编排器.

测试覆盖:
  1. 全链路 7 步 (mock client): upload→poll→select→submit→[phased]
  2. 断点续跑: 从中间步骤恢复
  3. 失败重试: 单步失败后重试成功
  4. 状态持久化: JSON 文件读写
  5. SIMULATION/PRODUCTION 模式自动切换
  6. API 端点: start/status/resume/list/credentials
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Mock AppStoreClient ──────────────────────────────────────


class MockAppStoreClientForOrchestrator:
    """编排器测试专用 mock, 记录调用历史."""

    def __init__(self, fail_steps: list | None = None):
        self.fail_steps = fail_steps or []
        self.call_history: list = []
        self._created = False

    def create_app(self, game_id, bundle_id, title):
        self._created = True
        return {"success": True, "app_id": f"as_{game_id}"}

    def upload_build(self, game_id, build_path, version, build_number):
        self.call_history.append(("upload_build", game_id, version, build_number))
        if "upload_build" in self.fail_steps:
            return {"success": False, "error": "mock upload failed"}
        return {"success": True, "build_id": "bld_mock_123"}

    def poll_build_status(self, game_id, version, build_number,
                          timeout_seconds=1800, poll_interval_seconds=30):
        self.call_history.append(("poll_build_status", game_id, version, build_number))
        if "poll_build_status" in self.fail_steps:
            return {"success": False, "error": "poll failed", "build_status": None}
        return {
            "success": True,
            "build_status": {
                "build_id": "bld_mock_123",
                "version": version,
                "build_number": build_number,
                "processing_state": "VALID",
            },
        }

    def select_build(self, version_id, build_id):
        self.call_history.append(("select_build", version_id, build_id))
        if "select_build" in self.fail_steps:
            return {"success": False, "error": "select failed"}
        return {"success": True}

    def submit_review(self, game_id, version_id=None):
        self.call_history.append(("submit_review", game_id, version_id))
        if "submit_review" in self.fail_steps:
            return {"success": False, "error": "submit failed"}
        return {"success": True, "status": "waiting_for_review"}

    def start_phased_release(self, version_id):
        self.call_history.append(("start_phased_release", version_id))
        if "start_phased_release" in self.fail_steps:
            return {"success": False, "error": "start phased failed"}
        return {
            "success": True,
            "data": {"data": {"id": "pr_mock_001", "type": "appStoreVersionPhasedReleases"}},
        }

    def check_phased_release(self, version_id):
        self.call_history.append(("check_phased_release", version_id))
        return {
            "success": True,
            "data": {"data": {"attributes": {"state": "ACTIVE"}}},
        }


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    return MockAppStoreClientForOrchestrator()


@pytest.fixture
def failing_client():
    return MockAppStoreClientForOrchestrator(fail_steps=["upload_build"])


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> str:
    d = tmp_path / "ios_release"
    d.mkdir()
    return str(d)


@pytest.fixture
def orchestrator(mock_client, tmp_data_dir):
    from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
    return IOSReleaseOrchestrator(
        game_id="game_test",
        bundle_id="com.test.game",
        ipa_path="/fake/path/app.ipa",
        version="1.2.0",
        build_number=42,
        client=mock_client,
        data_dir=tmp_data_dir,
    )


# ── 1. 全链路测试 ─────────────────────────────────────────────


class TestFullFlow:
    """7 步全链路测试."""

    def test_run_to_submit_review(self, orchestrator, mock_client):
        """执行到 submit_review (默认)."""
        result = orchestrator.run()

        assert result["success"] is True
        assert result["status"] == "submitted"
        assert "upload_build" in result["completed_steps"]
        assert "poll_build_status" in result["completed_steps"]
        assert "select_build" in result["completed_steps"]
        assert "submit_review" in result["completed_steps"]
        # start_phased_release 不应执行
        assert "start_phased_release" not in result["completed_steps"]
        assert result["build_id"] == "bld_mock_123"

    def test_run_full_release_with_phased(self, orchestrator):
        """执行完整流程 (含灰度)."""
        result = orchestrator.run_full_release()

        assert result["success"] is True
        assert "start_phased_release" in result["completed_steps"]
        assert "check_phased_release" in result["completed_steps"]

    def test_all_steps_called_in_order(self, orchestrator, mock_client):
        """步骤按顺序执行."""
        orchestrator.run()
        steps = [call[0] for call in mock_client.call_history]
        assert steps == ["upload_build", "poll_build_status",
                         "select_build", "submit_review"]

    def test_build_id_propagated(self, orchestrator):
        """upload_build 的 build_id 传播到后续步骤."""
        result = orchestrator.run()
        assert result["build_id"] == "bld_mock_123"


# ── 2. 断点续跑 ───────────────────────────────────────────────


class TestResume:
    """断点续跑测试."""

    def test_resume_from_middle_step(self, mock_client, tmp_data_dir):
        """从中间步骤恢复执行."""
        from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator

        # 第一次执行: 只到 upload_build
        orch1 = IOSReleaseOrchestrator(
            game_id="game_test", bundle_id="com.test.game",
            ipa_path="/fake/app.ipa", version="1.2.0", build_number=42,
            client=mock_client, data_dir=tmp_data_dir,
            release_id="test_release_001",
        )
        orch1.run(stop_step="upload_build")
        release_id = orch1.release_id

        # 第二次: 从 poll_build_status 继续
        orch2 = IOSReleaseOrchestrator.load_release(release_id, data_dir=tmp_data_dir)
        orch2._client = mock_client
        result = orch2.run(start_step="poll_build_status")

        assert result["success"] is True
        assert "upload_build" in result["completed_steps"]
        assert "poll_build_status" in result["completed_steps"]
        assert "submit_review" in result["completed_steps"]

    def test_state_persisted_between_runs(self, mock_client, tmp_data_dir):
        """状态在 JSON 文件中持久化."""
        from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator

        orch = IOSReleaseOrchestrator(
            game_id="game_persist", bundle_id="com.persist.game",
            ipa_path="/fake/app.ipa", version="1.0.0", build_number=1,
            client=mock_client, data_dir=tmp_data_dir,
            release_id="persist_test",
        )
        orch.run(stop_step="upload_build")

        state_file = Path(tmp_data_dir) / "persist_test.json"
        assert state_file.exists()

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state["release_id"] == "persist_test"
        assert state["game_id"] == "game_persist"
        assert "upload_build" in state["completed_steps"]


# ── 3. 失败重试 ───────────────────────────────────────────────


class TestFailureRetry:
    """失败重试测试."""

    def test_step_failure_blocks_subsequent(self, failing_client, tmp_data_dir):
        """单步失败阻塞后续步骤."""
        from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
        orch = IOSReleaseOrchestrator(
            game_id="game_fail", bundle_id="com.fail.game",
            ipa_path="/fake/app.ipa", version="1.0.0", build_number=1,
            client=failing_client, data_dir=tmp_data_dir,
            release_id="fail_test",
        )
        result = orch.run()

        assert result["success"] is False
        assert result["failed_step"] == "upload_build"
        assert "upload_build" not in result["completed_steps"]
        assert result["status"] == "failed"

    def test_retry_after_failure(self, tmp_data_dir):
        """失败后重试成功."""
        from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator

        # 第一次: 失败
        fail_client = MockAppStoreClientForOrchestrator(fail_steps=["upload_build"])
        orch = IOSReleaseOrchestrator(
            game_id="game_retry", bundle_id="com.retry.game",
            ipa_path="/fake/app.ipa", version="1.0.0", build_number=1,
            client=fail_client, data_dir=tmp_data_dir,
            release_id="retry_test",
        )
        result1 = orch.run(stop_step="upload_build")
        assert result1["success"] is False

        # 第二次: 成功 (换成功 client)
        success_client = MockAppStoreClientForOrchestrator()
        orch2 = IOSReleaseOrchestrator.load_release("retry_test", data_dir=tmp_data_dir)
        orch2._client = success_client
        result2 = orch2.run(start_step="upload_build")

        assert result2["success"] is True
        assert "upload_build" in result2["completed_steps"]


# ── 4. 状态管理 ───────────────────────────────────────────────


class TestStateManagement:
    """状态管理测试."""

    def test_get_status(self, orchestrator):
        """get_status 返回当前状态."""
        status = orchestrator.get_status()
        assert status["release_id"] == orchestrator.release_id
        assert status["game_id"] == "game_test"
        assert status["version"] == "1.2.0"
        assert status["status"] == "pending"

    def test_load_release_not_found(self, tmp_data_dir):
        """加载不存在的 release 抛 FileNotFoundError."""
        from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
        with pytest.raises(FileNotFoundError):
            IOSReleaseOrchestrator.load_release("nonexistent", data_dir=tmp_data_dir)

    def test_state_file_created_on_init(self, orchestrator, tmp_data_dir):
        """首次加载状态时创建状态文件 (惰性创建)."""
        orchestrator._load_state()  # 触发状态创建
        state_file = Path(tmp_data_dir) / f"{orchestrator.release_id}.json"
        assert state_file.exists()

    def test_unknown_start_step_returns_error(self, orchestrator):
        """未知 start_step 返回错误."""
        result = orchestrator.run(start_step="unknown_step")
        assert result["success"] is False
        assert "unknown" in result["error"].lower()


# ── 5. 模式自动切换 ───────────────────────────────────────────


class TestModeSwitch:
    """SIMULATION/PRODUCTION 模式切换测试."""

    def test_simulation_mode_when_no_credentials(self, tmp_data_dir):
        """无凭证时自动使用 MockAppStoreClient."""
        from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
        with patch("operation.providers.live.store_keys.get_appstore", return_value=None):
            orch = IOSReleaseOrchestrator(
                game_id="game_sim", bundle_id="com.sim.game",
                ipa_path="/fake/app.ipa", version="1.0.0", build_number=1,
                data_dir=tmp_data_dir,
                release_id="sim_test",
            )
            client = orch._get_client()
            # MockAppStoreClient 有 create_app 方法
            assert hasattr(client, "create_app")

    def test_production_mode_when_credentials_exist(self, tmp_data_dir):
        """有凭证时使用 AppStoreRealClient."""
        from operation.publishing.app_store.orchestrator import IOSReleaseOrchestrator
        fake_cred = {
            "key_id": "TEST_KEY",
            "issuer_id": "TEST_ISSUER",
            "private_key_p8": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
        }
        with patch("operation.providers.live.store_keys.get_appstore", return_value=fake_cred):
            orch = IOSReleaseOrchestrator(
                game_id="game_prod", bundle_id="com.prod.game",
                ipa_path="/fake/app.ipa", version="1.0.0", build_number=1,
                data_dir=tmp_data_dir,
                release_id="prod_test",
            )
            client = orch._get_client()
            # AppStoreRealClient 有 _auth_header 方法
            assert hasattr(client, "_auth_header")
            assert hasattr(client, "_call_api")


# ── 6. API 端点 ───────────────────────────────────────────────


class TestIOSReleaseAPI:
    """iOS 上架 API 端点测试."""

    @pytest.fixture
    def client(self):
        from market_ops.workspace.app import app
        return TestClient(app)

    def test_credentials_status_endpoint(self, client):
        """凭证状态端点返回配置信息."""
        response = client.get("/api/ios/credentials/status")
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "mode" in data
        assert "has_key_id" in data
        assert "has_issuer_id" in data
        assert "has_private_key" in data

    def test_release_start_endpoint(self, client):
        """启动发布端点 (SIMULATION 模式)."""
        response = client.post(
            "/api/ios/release/start",
            params={
                "game_id": "game_api_test",
                "bundle_id": "com.api.test",
                "ipa_path": "/fake/app.ipa",
                "version": "1.0.0",
                "build_number": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # SIMULATION 模式下应成功
        assert "success" in data
        assert "release_id" in data
        assert "status" in data

    def test_release_status_endpoint(self, client):
        """查询发布状态端点."""
        # 先启动一个 release
        start_resp = client.post(
            "/api/ios/release/start",
            params={
                "game_id": "game_status_test",
                "bundle_id": "com.status.test",
                "ipa_path": "/fake/app.ipa",
                "version": "1.0.0",
                "build_number": 1,
            },
        )
        release_id = start_resp.json().get("release_id", "")
        assert release_id

        # 查询状态
        response = client.get(f"/api/ios/release/{release_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["release_id"] == release_id

    def test_releases_list_endpoint(self, client):
        """发布列表端点."""
        response = client.get("/api/ios/releases")
        assert response.status_code == 200
        data = response.json()
        assert "releases" in data
        assert isinstance(data["releases"], list)

    def test_resume_nonexistent_release(self, client):
        """恢复不存在的 release 返回错误."""
        response = client.post("/api/ios/release/nonexistent_id/resume")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_status_nonexistent_release(self, client):
        """查询不存在的 release 返回错误."""
        response = client.get("/api/ios/release/nonexistent_id/status")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
