"""GooglePlayReleaseOrchestrator 单元测试 — 7 步发布编排器.

测试覆盖 (对称于 iOS orchestrator 测试):
  1. 全链路 7 步 (mock client): upload→create→submit→[rollout]
  2. 断点续跑: 从中间步骤恢复
  3. 失败重试: 单步失败后重试成功
  4. 状态持久化: JSON 文件读写
  5. SIMULATION/PRODUCTION 模式自动切换
  6. 审核被拒场景 (终态, 非编排器失败)
  7. Rollout 控制: halt / advance
  8. API 端点: start/status/resume/list/credentials/halt/advance
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Mock GooglePlayClient ─────────────────────────────────────


class MockGooglePlayClientForOrchestrator:
    """编排器测试专用 mock, 记录调用历史."""

    def __init__(self, fail_steps: list | None = None,
                 review_status: str = "approved"):
        self.fail_steps = fail_steps or []
        self.call_history: list = []
        self._created = False
        self._review_status = review_status  # approved / rejected / in_review
        self._rollout_status = "inProgress"

    def create_app(self, game_id, package_name, title):
        self._created = True
        return {"success": True, "app_id": f"gp_{game_id}"}

    def upload_bundle(self, game_id, build_path, version, build_number):
        self.call_history.append(("upload_bundle", game_id, version, build_number))
        if "upload_bundle" in self.fail_steps:
            return {"success": False, "error": "mock upload failed"}
        return {"success": True, "version_code": build_number}

    def create_release(self, game_id, track="internal"):
        self.call_history.append(("create_release", game_id, track))
        if "create_release" in self.fail_steps:
            return {"success": False, "error": "mock create failed"}
        return {"success": True, "release_id": f"rel_{game_id}_{track}", "track": track}

    def submit_review(self, game_id):
        self.call_history.append(("submit_review", game_id))
        if "submit_review" in self.fail_steps:
            return {"success": False, "error": "submit failed"}
        return {"success": True, "status": "in_review"}

    def check_status(self, game_id):
        self.call_history.append(("check_status", game_id))
        if "check_status" in self.fail_steps:
            return {"success": False, "error": "check failed"}
        # 返回预设的审核状态
        return {
            "success": True,
            "game_id": game_id,
            "status": self._review_status,
            "rejection": ({"code": "POLICY_VIOLATION", "reason": "mock"}
                          if self._review_status == "rejected" else None),
        }

    def release_to_production(self, game_id):
        self.call_history.append(("release_to_production", game_id))
        if "release_to_production" in self.fail_steps:
            return {"success": False, "error": "release failed"}
        return {"success": True, "status": "published"}

    def rollback(self, game_id):
        self.call_history.append(("rollback", game_id))
        return {"success": True, "status": "draft"}


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    return MockGooglePlayClientForOrchestrator()


@pytest.fixture
def failing_client():
    return MockGooglePlayClientForOrchestrator(fail_steps=["upload_bundle"])


@pytest.fixture
def rejected_client():
    return MockGooglePlayClientForOrchestrator(review_status="rejected")


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> str:
    d = tmp_path / "google_play_release"
    d.mkdir()
    return str(d)


@pytest.fixture
def orchestrator(mock_client, tmp_data_dir):
    from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
    return GooglePlayReleaseOrchestrator(
        game_id="game_test",
        package_name="com.test.game",
        aab_path="/fake/path/app.aab",
        version="1.2.0",
        build_number=42,
        client=mock_client,
        data_dir=tmp_data_dir,
        poll_timeout=2,  # 短超时方便测试
        poll_interval=0.01,
    )


# ── 1. 全链路测试 ─────────────────────────────────────────────


class TestFullFlow:
    """7 步全链路测试."""

    def test_run_to_submit_review(self, orchestrator, mock_client):
        """执行到 submit_review (默认)."""
        result = orchestrator.run()

        assert result["success"] is True
        assert result["status"] == "submitted"
        assert "upload_bundle" in result["completed_steps"]
        assert "create_release" in result["completed_steps"]
        assert "submit_review" in result["completed_steps"]
        # start_rollout / check_rollout 不应执行
        assert "start_rollout" not in result["completed_steps"]
        assert "check_rollout" not in result["completed_steps"]
        assert result["version_code"] == "42"

    def test_run_full_release_with_rollout(self, orchestrator):
        """执行完整流程 (含 rollout)."""
        result = orchestrator.run_full_release()

        assert result["success"] is True
        assert "start_rollout" in result["completed_steps"]
        assert "check_rollout" in result["completed_steps"]

    def test_all_steps_called_in_order(self, orchestrator, mock_client):
        """步骤按顺序执行 (到 submit_review)."""
        orchestrator.run()
        steps = [call[0] for call in mock_client.call_history]
        assert steps == ["upload_bundle", "create_release", "submit_review"]

    def test_version_code_propagated(self, orchestrator):
        """upload_bundle 的 version_code 传播到状态."""
        result = orchestrator.run()
        assert result["version_code"] == "42"

    def test_release_id_play_propagated(self, orchestrator):
        """create_release 的 release_id_play 传播到状态."""
        result = orchestrator.run()
        assert result["release_id_play"] == "rel_game_test_internal"


# ── 2. 断点续跑 ───────────────────────────────────────────────


class TestResume:
    """断点续跑测试."""

    def test_resume_from_middle_step(self, mock_client, tmp_data_dir):
        """从中间步骤恢复执行."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator

        # 第一次执行: 只到 upload_bundle
        orch1 = GooglePlayReleaseOrchestrator(
            game_id="game_test", package_name="com.test.game",
            aab_path="/fake/app.aab", version="1.2.0", build_number=42,
            client=mock_client, data_dir=tmp_data_dir,
            release_id="test_release_001",
        )
        orch1.run(stop_step="upload_bundle")
        release_id = orch1.release_id

        # 第二次: 从 create_release 继续
        orch2 = GooglePlayReleaseOrchestrator.load_release(release_id, data_dir=tmp_data_dir)
        orch2._client = mock_client
        result = orch2.run(start_step="create_release")

        assert result["success"] is True
        assert "upload_bundle" in result["completed_steps"]
        assert "create_release" in result["completed_steps"]
        assert "submit_review" in result["completed_steps"]

    def test_state_persisted_between_runs(self, mock_client, tmp_data_dir):
        """状态在 JSON 文件中持久化."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator

        orch = GooglePlayReleaseOrchestrator(
            game_id="game_persist", package_name="com.persist.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=mock_client, data_dir=tmp_data_dir,
            release_id="persist_test",
        )
        orch.run(stop_step="upload_bundle")

        state_file = Path(tmp_data_dir) / "persist_test.json"
        assert state_file.exists()

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state["release_id"] == "persist_test"
        assert state["game_id"] == "game_persist"
        assert state["package_name"] == "com.persist.game"
        assert "upload_bundle" in state["completed_steps"]
        assert state["version_code"] == "1"


# ── 3. 失败重试 ───────────────────────────────────────────────


class TestFailureRetry:
    """失败重试测试."""

    def test_step_failure_blocks_subsequent(self, failing_client, tmp_data_dir):
        """单步失败阻塞后续步骤."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_fail", package_name="com.fail.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=failing_client, data_dir=tmp_data_dir,
            release_id="fail_test",
        )
        result = orch.run()

        assert result["success"] is False
        assert result["failed_step"] == "upload_bundle"
        assert "upload_bundle" not in result["completed_steps"]
        assert result["status"] == "failed"

    def test_retry_after_failure(self, tmp_data_dir):
        """失败后重试成功."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator

        # 第一次: 失败
        fail_client = MockGooglePlayClientForOrchestrator(fail_steps=["upload_bundle"])
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_retry", package_name="com.retry.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=fail_client, data_dir=tmp_data_dir,
            release_id="retry_test",
        )
        result1 = orch.run(stop_step="upload_bundle")
        assert result1["success"] is False

        # 第二次: 成功 (换成功 client)
        success_client = MockGooglePlayClientForOrchestrator()
        orch2 = GooglePlayReleaseOrchestrator.load_release("retry_test", data_dir=tmp_data_dir)
        orch2._client = success_client
        result2 = orch2.run(start_step="upload_bundle")

        assert result2["success"] is True
        assert "upload_bundle" in result2["completed_steps"]

    def test_create_release_failure(self, tmp_data_dir):
        """create_release 失败."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        client = MockGooglePlayClientForOrchestrator(fail_steps=["create_release"])
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_cr", package_name="com.cr.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=client, data_dir=tmp_data_dir,
            release_id="cr_fail",
        )
        result = orch.run()
        assert result["success"] is False
        assert result["failed_step"] == "create_release"
        assert "upload_bundle" in result["completed_steps"]


# ── 4. 状态管理 ───────────────────────────────────────────────


class TestStateManagement:
    """状态管理测试."""

    def test_get_status(self, orchestrator):
        """get_status 返回当前状态."""
        status = orchestrator.get_status()
        assert status["release_id"] == orchestrator.release_id
        assert status["game_id"] == "game_test"
        assert status["package_name"] == "com.test.game"
        assert status["version"] == "1.2.0"
        assert status["status"] == "pending"

    def test_load_release_not_found(self, tmp_data_dir):
        """加载不存在的 release 抛 FileNotFoundError."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        with pytest.raises(FileNotFoundError):
            GooglePlayReleaseOrchestrator.load_release("nonexistent", data_dir=tmp_data_dir)

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

    def test_unknown_stop_step_returns_error(self, orchestrator):
        """未知 stop_step 触发 ValueError."""
        with pytest.raises(ValueError):
            orchestrator.run(stop_step="unknown_step")


# ── 5. 模式自动切换 ───────────────────────────────────────────


class TestModeSwitch:
    """SIMULATION/PRODUCTION 模式切换测试."""

    def test_simulation_mode_when_no_credentials(self, tmp_data_dir):
        """无凭证时自动使用 MockGooglePlayClient."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        with patch("operation.providers.live.store_keys.get_googleplay", return_value=None):
            orch = GooglePlayReleaseOrchestrator(
                game_id="game_sim", package_name="com.sim.game",
                aab_path="/fake/app.aab", version="1.0.0", build_number=1,
                data_dir=tmp_data_dir,
                release_id="sim_test",
            )
            client = orch._get_client()
            # MockGooglePlayClient 有 create_app 方法
            assert hasattr(client, "create_app")
            assert hasattr(client, "upload_bundle")

    def test_production_mode_when_credentials_exist(self, tmp_data_dir):
        """有凭证时使用 GooglePlayRealClient."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        fake_cred = {
            "service_account_json": {
                "type": "service_account",
                "project_id": "test-project",
                "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
                "client_email": "test@test-project.iam.gserviceaccount.com",
                "client_id": "12345",
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            "package_name": "com.prod.game",
        }
        with patch("operation.providers.live.store_keys.get_googleplay", return_value=fake_cred):
            orch = GooglePlayReleaseOrchestrator(
                game_id="game_prod", package_name="com.prod.game",
                aab_path="/fake/app.aab", version="1.0.0", build_number=1,
                data_dir=tmp_data_dir,
                release_id="prod_test",
            )
            client = orch._get_client()
            # GooglePlayRealClient 有 _call_api / set_rollout 方法
            assert hasattr(client, "_call_api")
            assert hasattr(client, "set_rollout")
            assert hasattr(client, "halt_rollout")


# ── 6. 审核被拒场景 ───────────────────────────────────────────


class TestRejectionScenario:
    """审核被拒场景测试."""

    def test_rejection_is_terminal_not_orchestrator_failure(self, rejected_client, tmp_data_dir):
        """审核被拒是终态, 不算编排器失败."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_rej", package_name="com.rej.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=rejected_client, data_dir=tmp_data_dir,
            release_id="rej_test",
            poll_timeout=2, poll_interval=0.01,
        )
        result = orch.run(stop_step="check_status")

        # 审核被拒不是编排器失败 (是外部决策)
        assert result["success"] is True
        assert result["review_status"] == "rejected"
        assert result["status"] == "rejected"
        assert "check_status" in result["completed_steps"]
        # rejection 信息应记录
        state = result["state"]
        assert state["rejection"] is not None
        assert state["rejection"]["code"] == "POLICY_VIOLATION"

    def test_rollout_blocked_after_rejection(self, rejected_client, tmp_data_dir):
        """审核被拒后 start_rollout 应失败."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_blk", package_name="com.blk.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=rejected_client, data_dir=tmp_data_dir,
            release_id="blk_test",
            poll_timeout=2, poll_interval=0.01,
        )
        # 先到 check_status (被拒)
        orch.run(stop_step="check_status")
        # 然后尝试 start_rollout
        result = orch.run(start_step="start_rollout", stop_step="start_rollout")

        assert result["success"] is False
        assert result["failed_step"] == "start_rollout"
        assert "review_status" in result["error"]


# ── 7. Rollout 控制 ───────────────────────────────────────────


class TestRolloutControl:
    """Rollout 控制测试."""

    def test_halt_rollout_with_mock(self, mock_client, tmp_data_dir):
        """halt_rollout 在 mock client 下走 rollback."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_halt", package_name="com.halt.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=mock_client, data_dir=tmp_data_dir,
            release_id="halt_test",
        )
        result = orch.halt_rollout()
        assert result["success"] is True
        assert result["status"] == "halted"

    def test_advance_rollout_not_supported_with_mock(self, mock_client, tmp_data_dir):
        """advance_rollout 在 mock client (无 set_rollout) 下应失败."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_adv", package_name="com.adv.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=mock_client, data_dir=tmp_data_dir,
            release_id="adv_test",
        )
        result = orch.advance_rollout(0.10)
        assert result["success"] is False
        assert "set_rollout" in result["error"]

    def test_advance_rollout_with_real_client(self, tmp_data_dir):
        """advance_rollout 在 RealClient (有 set_rollout) 下成功."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator

        # 构造一个支持 set_rollout 的 mock
        class ClientWithRollout(MockGooglePlayClientForOrchestrator):
            def set_rollout(self, package_name, track="production",
                            user_fraction=0.05, version_code=None,
                            release_notes=None, in_app_update_priority=0):
                self.call_history.append(("set_rollout", package_name, track, user_fraction))
                return {"success": True, "user_fraction": user_fraction, "track": track}

            def halt_rollout(self, package_name, track="production"):
                self.call_history.append(("halt_rollout", package_name, track))
                return {"success": True, "track": track}

            def get_track_status(self, package_name, track="production"):
                self.call_history.append(("get_track_status", package_name, track))
                return {
                    "success": True,
                    "track": track,
                    "status": "inProgress",
                    "user_fraction": 0.10,
                    "version_code": 1,
                    "releases": [],
                }

        client = ClientWithRollout()
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_real", package_name="com.real.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=1,
            client=client, data_dir=tmp_data_dir,
            release_id="real_test",
            rollout_fraction=0.05,
        )
        result = orch.advance_rollout(0.10)
        assert result["success"] is True
        assert result["rollout_fraction"] == 0.10

        # halt 也要工作
        halt_result = orch.halt_rollout()
        assert halt_result["success"] is True

    def test_full_release_with_staged_rollout_client(self, tmp_data_dir):
        """完整发布流程使用支持 staged rollout 的 client."""
        from operation.publishing.google_play.orchestrator import GooglePlayReleaseOrchestrator

        class ClientWithRollout(MockGooglePlayClientForOrchestrator):
            def set_rollout(self, package_name, track="production",
                            user_fraction=0.05, version_code=None,
                            release_notes=None, in_app_update_priority=0):
                self.call_history.append(("set_rollout", package_name, track, user_fraction))
                return {"success": True, "user_fraction": user_fraction, "track": track}

            def get_track_status(self, package_name, track="production"):
                self.call_history.append(("get_track_status", package_name, track))
                return {
                    "success": True,
                    "track": track,
                    "status": "completed",
                    "user_fraction": 1.0,
                    "version_code": 42,
                    "releases": [],
                }

        client = ClientWithRollout()
        orch = GooglePlayReleaseOrchestrator(
            game_id="game_full", package_name="com.full.game",
            aab_path="/fake/app.aab", version="1.0.0", build_number=42,
            client=client, data_dir=tmp_data_dir,
            release_id="full_test",
            rollout_fraction=0.05,
            poll_timeout=2, poll_interval=0.01,
        )
        result = orch.run_full_release()

        assert result["success"] is True
        assert "check_rollout" in result["completed_steps"]
        assert result["rollout_status"] == "completed"
        assert result["status"] == "released"


# ── 8. API 端点 ───────────────────────────────────────────────


class TestGooglePlayReleaseAPI:
    """Google Play 上架 API 端点测试."""

    @pytest.fixture
    def client(self):
        from market_ops.workspace.app import app
        return TestClient(app)

    def test_credentials_status_endpoint(self, client):
        """凭证状态端点返回配置信息."""
        response = client.get("/api/googleplay/credentials/status")
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "mode" in data
        assert "has_service_account" in data

    def test_release_start_endpoint(self, client):
        """启动发布端点 (SIMULATION 模式)."""
        response = client.post(
            "/api/googleplay/release/start",
            params={
                "game_id": "game_api_test",
                "package_name": "com.api.test",
                "aab_path": "/fake/app.aab",
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
            "/api/googleplay/release/start",
            params={
                "game_id": "game_status_test",
                "package_name": "com.status.test",
                "aab_path": "/fake/app.aab",
                "version": "1.0.0",
                "build_number": 1,
            },
        )
        release_id = start_resp.json().get("release_id", "")
        assert release_id

        # 查询状态
        response = client.get(f"/api/googleplay/release/{release_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["release_id"] == release_id

    def test_releases_list_endpoint(self, client):
        """发布列表端点."""
        response = client.get("/api/googleplay/releases")
        assert response.status_code == 200
        data = response.json()
        assert "releases" in data
        assert isinstance(data["releases"], list)

    def test_resume_nonexistent_release(self, client):
        """恢复不存在的 release 返回错误."""
        response = client.post("/api/googleplay/release/nonexistent_id/resume")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_status_nonexistent_release(self, client):
        """查询不存在的 release 返回错误."""
        response = client.get("/api/googleplay/release/nonexistent_id/status")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_halt_nonexistent_release(self, client):
        """halt 不存在的 release 返回错误."""
        response = client.post("/api/googleplay/release/nonexistent_id/halt")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_advance_nonexistent_release(self, client):
        """advance 不存在的 release 返回错误."""
        response = client.post(
            "/api/googleplay/release/nonexistent_id/advance",
            params={"next_fraction": 0.10},
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
