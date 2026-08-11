"""iOS App Store 上架能力 — AppStoreRealClient.upload_build (altool) 测试

Spec: docs/ios_upload_spec.md §5.1.1, §8.1 场景 1-4

覆盖（D17 范围）：
  1. altool 上传成功
  2. xcrun 不存在（非 macOS 环境）
  3. 凭证缺失（api_key_id / api_issuer_id）
  4. altool 超时

后续 D18/D19/D21 在本文件追加 poll_build_status / select_build /
phased release 等场景。
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from operation.publishing.providers.app_store.real_client import AppStoreRealClient


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def cred():
    return {
        "api_key_id": "TEST_KEY_ID",
        "api_issuer_id": "TEST_ISSUER_ID",
        "private_key_p8": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
        "bundle_id": "com.test.game",
    }


@pytest.fixture
def client(cred):
    return AppStoreRealClient(credential=cred)


# --------------------------------------------------------------------------- #
# Spec §8.1 场景 1-4 — upload_build (altool CLI)
# --------------------------------------------------------------------------- #
class TestUploadBuildAltool:
    """Spec §8.1 场景 1-4: upload_build (altool CLI)."""

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_1_altool_upload_success(self, _mock_which, client):
        """场景 1: altool 成功 → success=True, build_id 非空."""
        def mock_run(cmd, timeout):
            return SimpleNamespace(
                returncode=0,
                stdout='{"buildId":"bld_abc123","bundleId":"com.test.game"}',
                stderr="",
            )
        client.arm_altool(mock_run)

        result = client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is True
        assert result["build_id"] == "bld_abc123"
        assert result["version"] == "1.2.0"
        assert result["build_number"] == 42

    @patch("shutil.which", return_value=None)
    def test_2_xcrun_not_found(self, _mock_which, client):
        """场景 2: xcrun 不存在 → success=False, error 含 'xcrun not found'."""
        result = client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is False
        assert "xcrun not found" in result["error"]

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_3_credentials_missing(self, _mock_which):
        """场景 3: 凭证缺失 → success=False, error 含 'missing api_key_id'."""
        client_no_cred = AppStoreRealClient(credential={})
        result = client_no_cred.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is False
        assert "missing api_key_id" in result["error"]

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_3b_partial_credentials_missing(self, _mock_which):
        """场景 3b: 只有 api_key_id，缺 api_issuer_id → 失败."""
        client_partial = AppStoreRealClient(credential={"api_key_id": "KEY"})
        result = client_partial.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is False
        assert "missing api_key_id" in result["error"]

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_4_altool_timeout(self, _mock_which, client):
        """场景 4: altool 超时 → success=False, error 含 'timed out'."""
        def mock_timeout(cmd, timeout):
            raise subprocess.TimeoutExpired(cmd, timeout)
        client.arm_altool(mock_timeout)

        result = client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is False
        assert "timed out" in result["error"]


# --------------------------------------------------------------------------- #
# altool 边界情况（场景 1-4 补充）
# --------------------------------------------------------------------------- #
class TestUploadBuildAltoolEdgeCases:
    """altool 调用的边界情况补充。"""

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_altool_nonzero_returncode(self, _mock_which, client):
        """altool 返回非零 → success=False, error 含 rc 和 stderr."""
        def mock_fail(cmd, timeout):
            return SimpleNamespace(returncode=1, stdout="", stderr="Error: invalid IPA")
        client.arm_altool(mock_fail)

        result = client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is False
        assert "rc=1" in result["error"]
        assert "invalid IPA" in result["error"]

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_altool_success_empty_stdout(self, _mock_which, client):
        """altool 成功但 stdout 为空 → success=True, build_id 为空字符串."""
        def mock_run(cmd, timeout):
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        client.arm_altool(mock_run)

        result = client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is True
        assert result["build_id"] == ""  # altool 未输出 buildId

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_altool_success_invalid_json(self, _mock_which, client):
        """altool 成功但 stdout 非 JSON → success=True, build_id 为空（容错）."""
        def mock_run(cmd, timeout):
            return SimpleNamespace(returncode=0, stdout="not json at all", stderr="")
        client.arm_altool(mock_run)

        result = client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is True
        assert result["build_id"] == ""

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_altool_raises_exception(self, _mock_which, client):
        """altool 抛通用异常 → success=False, error 含 'altool raised'."""
        def mock_raise(cmd, timeout):
            raise OSError("command not found")
        client.arm_altool(mock_raise)

        result = client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert result["success"] is False
        assert "altool raised" in result["error"]

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_altool_cmd_construction(self, _mock_which, client):
        """验证 altool 命令构造正确（apiKey/issuer/ipa 都在 cmd 里）."""
        captured_cmd: list = []
        def mock_run(cmd, timeout):
            captured_cmd.extend(cmd)
            return SimpleNamespace(returncode=0, stdout='{"buildId":"x"}', stderr="")
        client.arm_altool(mock_run)

        client.upload_build("game_A", "/path/to/app.ipa", "1.2.0", 42)

        assert "xcrun" in captured_cmd
        assert "altool" in captured_cmd
        assert "--upload-app" in captured_cmd
        assert "/path/to/app.ipa" in captured_cmd
        assert "--apiKey" in captured_cmd
        assert "TEST_KEY_ID" in captured_cmd
        assert "--apiIssuer" in captured_cmd
        assert "TEST_ISSUER_ID" in captured_cmd

    @patch("shutil.which", return_value="/usr/bin/xcrun")
    def test_legacy_credential_field_names(self, _mock_which):
        """兼容旧字段名 key_id/issuer_id（非 api_key_id/api_issuer_id）."""
        client_legacy = AppStoreRealClient(credential={
            "key_id": "LEGACY_KEY",
            "issuer_id": "LEGACY_ISSUER",
        })
        captured_cmd: list = []
        def mock_run(cmd, timeout):
            captured_cmd.extend(cmd)
            return SimpleNamespace(returncode=0, stdout='{"buildId":"x"}', stderr="")
        client_legacy.arm_altool(mock_run)

        result = client_legacy.upload_build("game_A", "/app.ipa", "1.0.0", 1)

        assert result["success"] is True
        assert "LEGACY_KEY" in captured_cmd
        assert "LEGACY_ISSUER" in captured_cmd


# --------------------------------------------------------------------------- #
# Spec §8.1 场景 5-7 — poll_build_status
# --------------------------------------------------------------------------- #
class TestPollBuildStatus:
    """Spec §8.1 场景 5-7: poll_build_status (build processing 轮询)."""

    def _arm_app(self, client, game_id="game_A"):
        """让 client._apps 有记录，使 app_id 可解析。"""
        client._apps[game_id] = {
            "app_id": f"as_{game_id}",
            "bundle_id": "com.test.game",
        }

    def test_5_poll_build_status_valid(self, client):
        """场景 5: processingState=VALID → success=True."""
        self._arm_app(client)
        def mock_api(method, path, body):
            return {
                "success": True,
                "data": {"data": [{
                    "id": "bld_123",
                    "attributes": {
                        "processingState": "VALID",
                        "iconAssetToken": {"templateUrl": "https://icon.url/tpl"},
                        "uploadedDate": "2026-08-06T10:00:00Z",
                    },
                }]},
            }
        client.arm_real_client(mock_api)

        result = client.poll_build_status("game_A", "1.2.0", 42, timeout_seconds=30)

        assert result["success"] is True
        bs = result["build_status"]
        assert bs["processing_state"] == "VALID"
        assert bs["build_id"] == "bld_123"
        assert bs["version"] == "1.2.0"
        assert bs["build_number"] == 42
        assert bs["icon_url"] == "https://icon.url/tpl"
        assert bs["uploaded_date"] == "2026-08-06T10:00:00Z"

    def test_6_poll_build_status_failed(self, client):
        """场景 6: processingState=FAILED → success=False, error_message 填充."""
        self._arm_app(client)
        def mock_api(method, path, body):
            return {
                "success": True,
                "data": {"data": [{
                    "id": "bld_456",
                    "attributes": {
                        "processingState": "FAILED",
                        "processingError": "invalid signature",
                    },
                }]},
            }
        client.arm_real_client(mock_api)

        result = client.poll_build_status("game_A", "1.2.0", 42, timeout_seconds=30)

        assert result["success"] is False
        assert "build processing failed" in result["error"]
        bs = result["build_status"]
        assert bs["processing_state"] == "FAILED"
        assert bs["error_message"] == "invalid signature"
        assert bs["build_id"] == "bld_456"

    @patch("time.sleep")
    @patch("time.time")
    def test_7_poll_build_status_timeout(self, mock_time, mock_sleep, client):
        """场景 7: 一直 PROCESSING → 超时, error 含 'poll timed out'."""
        self._arm_app(client)
        # time.time: deadline 计算(0), 循环1条件(0<5 True), 循环2条件(100>=5 False)
        mock_time.side_effect = [0, 0, 100, 100, 100]
        def mock_api(method, path, body):
            return {
                "success": True,
                "data": {"data": [{
                    "id": "bld_789",
                    "attributes": {"processingState": "PROCESSING"},
                }]},
            }
        client.arm_real_client(mock_api)

        result = client.poll_build_status("game_A", "1.2.0", 42, timeout_seconds=5)

        assert result["success"] is False
        assert "poll timed out" in result["error"]
        assert result["build_status"] is None
        # 验证 sleep 被调用（等待重试）
        assert mock_sleep.called

    @patch("time.sleep")
    @patch("time.time")
    def test_7b_poll_empty_builds_timeout(self, mock_time, mock_sleep, client):
        """场景 7b: builds 列表为空 → 持续等待 → 超时."""
        self._arm_app(client)
        mock_time.side_effect = [0, 0, 100, 100, 100]
        def mock_api(method, path, body):
            return {"success": True, "data": {"data": []}}
        client.arm_real_client(mock_api)

        result = client.poll_build_status("game_A", "1.2.0", 42, timeout_seconds=5)

        assert result["success"] is False
        assert "poll timed out" in result["error"]

    @patch("time.sleep")
    def test_poll_api_failure_then_retry_success(self, mock_sleep, client):
        """边界: API 第一次失败 → sleep 重试 → 第二次 VALID 成功."""
        self._arm_app(client)
        call_count = [0]
        def mock_api(method, path, body):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"success": False, "error": "transient 500"}
            return {
                "success": True,
                "data": {"data": [{
                    "id": "b1",
                    "attributes": {"processingState": "VALID"},
                }]},
            }
        client.arm_real_client(mock_api)

        result = client.poll_build_status("game_A", "1.2.0", 42, timeout_seconds=30)

        assert result["success"] is True
        assert result["build_status"]["processing_state"] == "VALID"
        assert call_count[0] == 2  # 第一次失败，第二次成功
        assert mock_sleep.called  # 失败后 sleep 了

    def test_poll_bundle_missing(self, client):
        """边界: bundle_id 缺失 → 立即失败."""
        client_no_bundle = AppStoreRealClient(credential={})
        result = client_no_bundle.poll_build_status("game_A", "1.2.0", 42)
        assert result["success"] is False
        assert "bundle_id missing" in result["error"]
        assert result["build_status"] is None


# --------------------------------------------------------------------------- #
# Spec §8.1 场景 8 — select_build
# --------------------------------------------------------------------------- #
class TestSelectBuild:
    """Spec §8.1 场景 8: select_build (关联 build 到 version)."""

    def test_8_select_build_success(self, client):
        """场景 8: PATCH 成功 → success=True."""
        captured = {}
        def mock_api(method, path, body):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = body
            return {"success": True, "data": {"id": "v1.2.0"}}
        client.arm_real_client(mock_api)

        result = client.select_build("v1.2.0", "bld_123")

        assert result["success"] is True
        assert captured["method"] == "PATCH"
        assert "v1.2.0" in captured["path"]
        assert "relationships/build" in captured["path"]
        assert captured["body"]["data"]["type"] == "builds"
        assert captured["body"]["data"]["id"] == "bld_123"

    def test_select_build_api_failure(self, client):
        """边界: PATCH 失败 → success=False."""
        def mock_api(method, path, body):
            return {"success": False, "error": "version not found", "status_code": 404}
        client.arm_real_client(mock_api)

        result = client.select_build("v_unknown", "bld_123")

        assert result["success"] is False
        assert "version not found" in result["error"]

    def test_select_build_path_construction(self, client):
        """验证 PATCH path 正确包含 version_id."""
        captured_paths = []
        def mock_api(method, path, body):
            captured_paths.append(path)
            return {"success": True}
        client.arm_real_client(mock_api)

        client.select_build("ver_abc", "bld_xyz")

        assert captured_paths[0] == "/appStoreVersions/ver_abc/relationships/build"


# --------------------------------------------------------------------------- #
# Spec §8.1 场景 9 — submit_review (修正版，含 version_id 关联)
# --------------------------------------------------------------------------- #
class TestSubmitReview:
    """Spec §8.1 场景 9: submit_review (POST /appStoreVersionSubmissions)."""

    def test_9_submit_review_with_explicit_version_id(self, client):
        """场景 9: 显式 version_id → POST 成功 → success=True, status=waiting_for_review."""
        captured = {}
        def mock_api(method, path, body):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = body
            return {"success": True, "data": {"id": "sub_1"}}
        client.arm_real_client(mock_api)

        result = client.submit_review("game_A", version_id="v1.2.0")

        assert result["success"] is True
        assert result["status"] == "waiting_for_review"
        assert captured["method"] == "POST"
        assert captured["path"] == "/appStoreVersionSubmissions"
        # body 含 version_id 关联
        rel = captured["body"]["data"]["relationships"]["appStoreVersion"]["data"]
        assert rel["type"] == "appStoreVersions"
        assert rel["id"] == "v1.2.0"

    def test_9b_submit_review_auto_resolve_version_id(self, client):
        """场景 9b: version_id=None → 自动查询最新 version → POST 成功."""
        call_count = [0]
        def mock_api(method, path, body):
            call_count[0] += 1
            # 第一次: GET /apps?filter[bundleId] → 返回 app
            if method == "GET" and "/apps?" in path:
                return {"success": True, "data": {"data": [{"id": "as_app_1"}]}}
            # 第二次: GET /apps/{id}/appStoreVersions → 返回 version
            if method == "GET" and "appStoreVersions" in path:
                return {"success": True, "data": {"data": [{"id": "ver_auto"}]}}
            # 第三次: POST /appStoreVersionSubmissions
            return {"success": True}
        client.arm_real_client(mock_api)

        result = client.submit_review("game_A")  # version_id=None

        assert result["success"] is True
        assert result["status"] == "waiting_for_review"
        assert call_count[0] == 3  # app query + version query + submit

    def test_submit_review_no_version_found(self, client):
        """边界: version_id=None 且查询无 version → success=False."""
        def mock_api(method, path, body):
            if method == "GET" and "/apps?" in path:
                return {"success": True, "data": {"data": [{"id": "as_app_1"}]}}
            # 无 version
            return {"success": True, "data": {"data": []}}
        client.arm_real_client(mock_api)

        result = client.submit_review("game_A")

        assert result["success"] is False
        assert "no appStoreVersion" in result["error"]

    def test_submit_review_bundle_missing(self, client):
        """边界: bundle_id 缺失 → 立即失败."""
        client_no_bundle = AppStoreRealClient(credential={})
        result = client_no_bundle.submit_review("game_A")
        assert result["success"] is False
        assert "app not found" in result["error"]

    def test_submit_review_api_failure(self, client):
        """边界: POST 失败 → success=False."""
        def mock_api(method, path, body):
            return {"success": False, "error": "metadata missing", "status_code": 422}
        client.arm_real_client(mock_api)

        result = client.submit_review("game_A", version_id="v1")

        assert result["success"] is False
        assert "metadata missing" in result["error"]


# --------------------------------------------------------------------------- #
# Spec §8.1 场景 10-12 — phased release
# --------------------------------------------------------------------------- #
class TestPhasedRelease:
    """Spec §8.1 场景 10-12: phased release (start/pause/resume/complete/check)."""

    def test_10_start_phased_release_success(self, client):
        """场景 10: start_phased_release 成功."""
        captured = {}
        def mock_api(method, path, body):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = body
            return {
                "success": True,
                "data": {"id": "pr_1", "attributes": {"state": "ACTIVE"}},
            }
        client.arm_real_client(mock_api)

        result = client.start_phased_release("v1.2.0")

        assert result["success"] is True
        assert captured["method"] == "POST"
        assert captured["path"] == "/appStoreVersionPhasedReleases"
        rel = captured["body"]["data"]["relationships"]["appStoreVersion"]["data"]
        assert rel["id"] == "v1.2.0"

    def test_11_pause_resume_phased_release(self, client):
        """场景 11: pause → resume 成功，state 正确."""
        captured_states = []
        def mock_api(method, path, body):
            state = body["data"]["attributes"]["state"]
            captured_states.append((method, path, state))
            return {"success": True}
        client.arm_real_client(mock_api)

        r1 = client.pause_phased_release("pr_1")
        r2 = client.resume_phased_release("pr_1")

        assert r1["success"] is True and r2["success"] is True
        assert captured_states[0] == ("PATCH", "/appStoreVersionPhasedReleases/pr_1", "PAUSED")
        assert captured_states[1] == ("PATCH", "/appStoreVersionPhasedReleases/pr_1", "ACTIVE")

    def test_11b_complete_phased_release(self, client):
        """场景 11b: complete → state=COMPLETE."""
        captured = {}
        def mock_api(method, path, body):
            captured["method"] = method
            captured["path"] = path
            captured["state"] = body["data"]["attributes"]["state"]
            return {"success": True}
        client.arm_real_client(mock_api)

        result = client.complete_phased_release("pr_99")

        assert result["success"] is True
        assert captured["method"] == "PATCH"
        assert captured["path"] == "/appStoreVersionPhasedReleases/pr_99"
        assert captured["state"] == "COMPLETE"

    def test_12_check_phased_release_status(self, client):
        """场景 12: check_phased_release 返回 state 字段."""
        captured = {}
        def mock_api(method, path, body):
            captured["method"] = method
            captured["path"] = path
            return {
                "success": True,
                "data": {
                    "id": "pr_1",
                    "attributes": {
                        "state": "ACTIVE",
                        "currentReleasePercentage": 0.05,
                    },
                },
            }
        client.arm_real_client(mock_api)

        result = client.check_phased_release("v1.2.0")

        assert result["success"] is True
        assert captured["method"] == "GET"
        assert captured["path"] == "/appStoreVersions/v1.2.0/appStoreVersionPhasedRelease"
        # 返回的 data 含 state 字段
        data = result.get("data", {})
        attrs = data.get("attributes", {}) if isinstance(data, dict) else {}
        assert attrs.get("state") == "ACTIVE"

    def test_start_phased_release_api_failure(self, client):
        """边界: POST 失败 → success=False."""
        def mock_api(method, path, body):
            return {"success": False, "error": "version not approved", "status_code": 409}
        client.arm_real_client(mock_api)

        result = client.start_phased_release("v1")

        assert result["success"] is False
        assert "not approved" in result["error"]

    def test_pause_phased_release_path_construction(self, client):
        """验证 pause PATCH path 正确包含 phased_release_id."""
        captured_paths = []
        def mock_api(method, path, body):
            captured_paths.append(path)
            return {"success": True}
        client.arm_real_client(mock_api)

        client.pause_phased_release("pr_xyz")

        assert captured_paths[0] == "/appStoreVersionPhasedReleases/pr_xyz"


# --------------------------------------------------------------------------- #
# Spec §5.2 — Provider apply_change 路由新操作
# --------------------------------------------------------------------------- #
from operation.publishing.app_store.provider import AppStoreProvider
from operation.publishing.providers.app_store.provider import (
    AppStoreProductionProvider,
)
from operation.publishing.providers.models import (
    OP_CHECK_PHASED_RELEASE, OP_COMPLETE_PHASED_RELEASE,
    OP_PAUSE_PHASED_RELEASE, OP_POLL_BUILD_STATUS, OP_RESUME_PHASED_RELEASE,
    OP_SELECT_BUILD, OP_START_PHASED_RELEASE, OP_UPLOAD_BUILD_ALTOOL,
    PublishingChange,
)
from monetization.providers.models import SandboxMode


class TestAppStoreProviderRouting:
    """Spec §5.2: AppStoreProvider (mock) apply_change 路由 9 个新操作."""

    @pytest.fixture
    def provider(self):
        p = AppStoreProvider(sandbox=SandboxMode.SIMULATION)
        # MockAppStoreClient.upload_build 要求 app 先注册
        p.client.create_app("game_A", "com.test.game", "Test Game")
        return p

    def _change(self, operation, payload):
        return PublishingChange(
            target=f"game_A/app_store/{operation}",
            operation=operation,
            provider="app_store",
            game_id="game_A",
            new=payload,
        )

    def test_upload_build_altool_routing(self, provider):
        change = self._change(OP_UPLOAD_BUILD_ALTOOL, {
            "ipa_path": "/app.ipa", "version": "1.2.0", "build_number": 42,
        })
        result = provider.apply_change(change)
        assert result.success is True
        assert result.operation == OP_UPLOAD_BUILD_ALTOOL

    def test_poll_build_status_routing(self, provider):
        change = self._change(OP_POLL_BUILD_STATUS, {
            "version": "1.2.0", "build_number": 42,
        })
        result = provider.apply_change(change)
        assert result.success is True
        # mock stub 返回 build_status
        assert "build_status" in result.after or result.after.get("success")

    def test_select_build_routing(self, provider):
        change = self._change(OP_SELECT_BUILD, {
            "version_id": "v1", "build_id": "b1",
        })
        result = provider.apply_change(change)
        assert result.success is True

    def test_start_phased_release_routing(self, provider):
        change = self._change(OP_START_PHASED_RELEASE, {"version_id": "v1"})
        result = provider.apply_change(change)
        assert result.success is True

    def test_pause_phased_release_routing(self, provider):
        change = self._change(OP_PAUSE_PHASED_RELEASE, {"phased_release_id": "pr1"})
        result = provider.apply_change(change)
        assert result.success is True

    def test_resume_phased_release_routing(self, provider):
        change = self._change(OP_RESUME_PHASED_RELEASE, {"phased_release_id": "pr1"})
        result = provider.apply_change(change)
        assert result.success is True

    def test_complete_phased_release_routing(self, provider):
        change = self._change(OP_COMPLETE_PHASED_RELEASE, {"phased_release_id": "pr1"})
        result = provider.apply_change(change)
        assert result.success is True

    def test_check_phased_release_routing(self, provider):
        change = self._change(OP_CHECK_PHASED_RELEASE, {"version_id": "v1"})
        result = provider.apply_change(change)
        assert result.success is True


class TestAppStoreProductionProviderRouting:
    """Spec §5.2: AppStoreProductionProvider apply_change 路由 9 个新操作.

    SIMULATION 模式下用 MockAppStoreClient（有 stub），验证路由正确。
    """

    @pytest.fixture
    def provider(self):
        p = AppStoreProductionProvider(sandbox=SandboxMode.SIMULATION)
        # mock client 需要先注册 app
        p._mock_client.create_app("game_A", "com.test.game", "Test Game")
        return p

    def _change(self, operation, payload):
        return PublishingChange(
            target=f"game_A/app_store/{operation}",
            operation=operation,
            provider="app_store",
            game_id="game_A",
            new=payload,
        )

    def test_upload_build_altool_sim_routing(self, provider):
        """SIMULATION 模式: OP_UPLOAD_BUILD_ALTOOL → mock upload_build."""
        change = self._change(OP_UPLOAD_BUILD_ALTOOL, {
            "ipa_path": "/app.ipa", "version": "1.0.0", "build_number": 1,
        })
        result = provider.apply_change(change)
        assert result.success is True

    def test_poll_build_status_sim_routing(self, provider):
        change = self._change(OP_POLL_BUILD_STATUS, {
            "version": "1.0.0", "build_number": 1,
        })
        result = provider.apply_change(change)
        assert result.success is True

    def test_select_build_sim_routing(self, provider):
        change = self._change(OP_SELECT_BUILD, {
            "version_id": "v1", "build_id": "b1",
        })
        result = provider.apply_change(change)
        assert result.success is True

    def test_phased_release_chain_sim(self, provider):
        """端到端: start → pause → resume → complete → check."""
        for op, payload in [
            (OP_START_PHASED_RELEASE, {"version_id": "v1"}),
            (OP_PAUSE_PHASED_RELEASE, {"phased_release_id": "pr1"}),
            (OP_RESUME_PHASED_RELEASE, {"phased_release_id": "pr1"}),
            (OP_COMPLETE_PHASED_RELEASE, {"phased_release_id": "pr1"}),
            (OP_CHECK_PHASED_RELEASE, {"version_id": "v1"}),
        ]:
            change = self._change(op, payload)
            result = provider.apply_change(change)
            assert result.success is True, f"{op} failed: {result.error}"


class TestProviderExistingOpsRegression:
    """回归: 现有操作（V1）在 mock provider 上不受新分支影响."""

    @pytest.fixture
    def provider(self):
        p = AppStoreProvider(sandbox=SandboxMode.SIMULATION)
        p.client.create_app("game_A", "com.test.game", "Test Game")
        return p

    def test_create_app_still_works(self, provider):
        from operation.publishing.providers.models import OP_CREATE_APP
        change = PublishingChange(
            target="game_A/app_store/create",
            operation=OP_CREATE_APP, provider="app_store",
            game_id="game_A",
            new={"bundle_id": "com.test.game", "title": "Test Game"},
        )
        result = provider.apply_change(change)
        assert result.success is True

    def test_upload_build_v1_still_works(self, provider):
        """OP_UPLOAD_BUILD (V1) 仍走原 upload_build 分支，不受 OP_UPLOAD_BUILD_ALTOOL 影响."""
        from operation.publishing.providers.models import OP_UPLOAD_BUILD
        change = PublishingChange(
            target="game_A/app_store/upload",
            operation=OP_UPLOAD_BUILD, provider="app_store",
            game_id="game_A",
            new={"file_path": "/app.ipa", "version": "1.0.0", "build_number": 1},
        )
        result = provider.apply_change(change)
        assert result.success is True

    def test_unknown_op_returns_error(self, provider):
        change = PublishingChange(
            target="game_A/app_store/unknown",
            operation="totally_unknown_op", provider="app_store",
            game_id="game_A",
        )
        result = provider.apply_change(change)
        assert result.success is False
        assert "unknown op" in result.error
