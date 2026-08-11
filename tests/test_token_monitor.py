"""TokenMonitor 单元测试 — Token 过期监控.

测试覆盖:
  1. Meta token 实时检查 (mock requests): 有效/无效/过期/永不过期
  2. 手动注册 token: register/unregister
  3. 状态持久化: JSON 文件读写
  4. 告警生成: critical/warning/info/expired/invalid
  5. 从环境变量自动检查 Meta token
  6. get_status 摘要
  7. API 端点
  8. 单例模式
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> str:
    d = tmp_path / "token_monitor"
    d.mkdir()
    return str(d)


@pytest.fixture
def monitor(tmp_data_dir):
    """每个测试独立的 TokenMonitor (避免单例污染)."""
    from market_ops.workspace.token_monitor import TokenMonitor
    return TokenMonitor(data_dir=tmp_data_dir)


@pytest.fixture
def mock_response_valid():
    """模拟 Graph API debug_token 返回有效 token."""
    resp = MagicMock()
    resp.json.return_value = {
        "data": {
            "app_id": "123456789",
            "type": "USER",
            "expires_at": int(time.time()) + 86400 * 30,  # 30 天后过期
            "is_valid": True,
            "scopes": ["ads_management", "ads_read"],
        }
    }
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def mock_response_expired():
    """模拟 Graph API debug_token 返回已过期 token."""
    resp = MagicMock()
    resp.json.return_value = {
        "data": {
            "app_id": "123456789",
            "type": "USER",
            "expires_at": int(time.time()) - 3600,  # 1 小时前过期
            "is_valid": False,
            "scopes": [],
            "error": {"message": "Token has expired"},
        }
    }
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def mock_response_never_expiring():
    """模拟 Graph API debug_token 返回永不过期的 app token."""
    resp = MagicMock()
    resp.json.return_value = {
        "data": {
            "app_id": "123456789",
            "type": "APP",
            "expires_at": 0,
            "is_valid": True,
            "scopes": [],
        }
    }
    resp.raise_for_status.return_value = None
    return resp


# ── 1. Meta token 实时检查 ────────────────────────────────────


class TestMetaTokenCheck:
    """Meta token 实时检查测试."""

    def test_check_valid_token(self, monitor, mock_response_valid):
        """检查有效的 Meta token."""
        with patch("requests.get", return_value=mock_response_valid):
            status = monitor.check_meta_token(
                access_token="EAAG_test_token_12345",
                app_id="123456789",
                app_secret="secret",
            )
        assert status.is_valid is True
        assert status.token_type == "meta_access_token"
        assert status.expires_at > time.time()
        assert status.source == "graph_api_debug_token"
        assert "ads_management" in status.scopes
        assert status.app_id == "123456789"
        # token 预览不暴露完整 token
        assert status.token_preview == "EAAG_tes..."
        assert "12345" not in status.token_preview or len(status.token_preview) < 15

    def test_check_expired_token(self, monitor, mock_response_expired):
        """检查已过期的 Meta token."""
        with patch("requests.get", return_value=mock_response_expired):
            status = monitor.check_meta_token(
                access_token="EAAG_expired_token",
            )
        assert status.is_valid is False
        assert status.is_expired is True
        assert status.severity == "critical"
        assert "expired" in status.error.lower()

    def test_check_never_expiring_token(self, monitor, mock_response_never_expiring):
        """检查永不过期的 app token."""
        with patch("requests.get", return_value=mock_response_never_expiring):
            status = monitor.check_meta_token(
                access_token="123456789|abc-def",
            )
        assert status.is_valid is True
        assert status.is_never_expiring is True
        assert status.severity == "info"  # 永不过期的有效 token 不告警

    def test_check_empty_token(self, monitor):
        """空 token 应返回无效状态."""
        status = monitor.check_meta_token(access_token="")
        assert status.is_valid is False
        assert "empty" in status.error.lower()

    def test_check_token_request_failure(self, monitor):
        """网络请求失败应返回无效状态, 不抛异常."""
        with patch("requests.get", side_effect=Exception("network error")):
            status = monitor.check_meta_token(access_token="EAAG_test")
        assert status.is_valid is False
        assert "check failed" in status.error.lower()

    def test_check_token_uses_app_access_token_when_provided(self, monitor, mock_response_valid):
        """提供 app_id + app_secret 时用 app access token 自查."""
        with patch("requests.get", return_value=mock_response_valid) as mock_get:
            monitor.check_meta_token(
                access_token="EAAG_user_token",
                app_id="123456789",
                app_secret="secret",
            )
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["access_token"] == "123456789|secret"
        assert params["input_token"] == "EAAG_user_token"

    def test_check_token_self_check_without_app_credentials(self, monitor, mock_response_valid):
        """无 app_id/app_secret 时用 token 自查."""
        with patch("requests.get", return_value=mock_response_valid) as mock_get:
            monitor.check_meta_token(access_token="EAAG_user_token")
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["access_token"] == "EAAG_user_token"


# ── 2. 手动注册 token ─────────────────────────────────────────


class TestRegisterToken:
    """手动注册 token 测试."""

    def test_register_custom_token(self, monitor):
        """注册自定义 token."""
        expires_at = time.time() + 86400 * 5  # 5 天后过期
        status = monitor.register_token(
            token_id="my_oauth_token",
            expires_at=expires_at,
            token_type="custom",
            token_preview="ya29.abc...",
        )
        assert status.token_id == "my_oauth_token"
        assert status.is_valid is True
        assert status.expires_at == expires_at
        assert status.severity == "warning"  # 5 天 → warning

    def test_register_never_expiring_token(self, monitor):
        """注册永不过期的 token."""
        status = monitor.register_token(
            token_id="app_token",
            expires_at=0,
            token_type="custom",
        )
        assert status.is_never_expiring is True
        assert status.severity == "info"

    def test_unregister_token(self, monitor):
        """移除已注册的 token."""
        monitor.register_token("temp_token", expires_at=time.time() + 3600)
        assert monitor.get_token_status("temp_token") is not None
        result = monitor.unregister_token("temp_token")
        assert result is True
        assert monitor.get_token_status("temp_token") is None

    def test_unregister_nonexistent_token(self, monitor):
        """移除不存在的 token 返回 False."""
        result = monitor.unregister_token("nonexistent")
        assert result is False

    def test_register_google_play_token(self, monitor):
        """注册 Google Play OAuth token."""
        expires_at = time.time() + 3500  # Google Play OAuth ~1 小时
        status = monitor.register_token(
            token_id="google_play_oauth",
            expires_at=expires_at,
            token_type="google_play_oauth",
        )
        assert status.token_type == "google_play_oauth"
        # 3500 秒 < 1 天 → critical
        assert status.severity == "critical"


# ── 3. 状态持久化 ─────────────────────────────────────────────


class TestPersistence:
    """状态持久化测试."""

    def test_status_persisted_to_json(self, monitor, tmp_data_dir):
        """注册 token 后状态持久化到 JSON."""
        monitor.register_token(
            "persist_token",
            expires_at=time.time() + 86400 * 10,
        )
        status_file = Path(tmp_data_dir) / "status.json"
        assert status_file.exists()

        data = json.loads(status_file.read_text(encoding="utf-8"))
        assert "persist_token" in data
        assert data["persist_token"]["token_id"] == "persist_token"

    def test_status_loaded_from_json(self, tmp_data_dir):
        """新实例从 JSON 加载历史状态."""
        from market_ops.workspace.token_monitor import TokenMonitor

        # 第一个实例注册 token
        monitor1 = TokenMonitor(data_dir=tmp_data_dir)
        monitor1.register_token(
            "loaded_token",
            expires_at=time.time() + 86400 * 3,
        )

        # 第二个实例应能加载
        monitor2 = TokenMonitor(data_dir=tmp_data_dir)
        status = monitor2.get_token_status("loaded_token")
        assert status is not None
        assert status.token_id == "loaded_token"

    def test_persistence_handles_malformed_file(self, tmp_data_dir):
        """损坏的状态文件不应导致崩溃."""
        from market_ops.workspace.token_monitor import TokenMonitor
        status_file = Path(tmp_data_dir) / "status.json"
        status_file.write_text("not valid json", encoding="utf-8")

        # 不应抛异常
        monitor = TokenMonitor(data_dir=tmp_data_dir)
        assert monitor.get_all_tokens() == []


# ── 4. 告警生成 ───────────────────────────────────────────────


class TestAlerts:
    """告警生成测试."""

    def test_critical_alert_for_expiring_token(self, monitor):
        """距过期 < 1 天的 token 生成 critical 告警."""
        monitor.register_token(
            "critical_token",
            expires_at=time.time() + 3600,  # 1 小时后过期
        )
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"
        assert "critical_token" in alerts[0]["message"]
        assert alerts[0]["category"] == "token_expiry"
        assert alerts[0]["alert_id"] == "token_expiry_critical_token"

    def test_warning_alert_for_soon_expiring_token(self, monitor):
        """距过期 < 7 天的 token 生成 warning 告警."""
        monitor.register_token(
            "warning_token",
            expires_at=time.time() + 86400 * 3,  # 3 天后过期
        )
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"

    def test_no_alert_for_healthy_token(self, monitor):
        """距过期 > 30 天的 token 不生成告警."""
        monitor.register_token(
            "healthy_token",
            expires_at=time.time() + 86400 * 60,  # 60 天后过期
        )
        alerts = monitor.get_alerts()
        assert len(alerts) == 0

    def test_no_alert_for_never_expiring_valid_token(self, monitor):
        """永不过期的有效 token 不生成告警."""
        monitor.register_token(
            "app_token",
            expires_at=0,
            is_valid=True,
        )
        alerts = monitor.get_alerts()
        assert len(alerts) == 0

    def test_critical_alert_for_expired_token(self, monitor):
        """已过期的 token 生成 critical 告警."""
        monitor.register_token(
            "expired_token",
            expires_at=time.time() - 3600,  # 1 小时前过期
        )
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"
        assert "已过期" in alerts[0]["message"]

    def test_critical_alert_for_invalid_token(self, monitor):
        """无效 token 生成 critical 告警."""
        monitor.register_token(
            "invalid_token",
            expires_at=time.time() + 86400 * 30,  # 远未过期
            is_valid=False,
            error="revoked",
        )
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"
        assert "无效" in alerts[0]["message"]

    def test_multiple_alerts(self, monitor):
        """多个 token 生成多个告警."""
        monitor.register_token("t1", expires_at=time.time() + 3600)  # critical
        monitor.register_token("t2", expires_at=time.time() + 86400 * 3)  # warning
        monitor.register_token("t3", expires_at=time.time() + 86400 * 60)  # 健康
        alerts = monitor.get_alerts()
        assert len(alerts) == 2
        severities = {a["severity"] for a in alerts}
        assert severities == {"critical", "warning"}

    def test_alert_format_compatible_with_alert_notifier(self, monitor):
        """告警格式兼容 AlertNotifier (含 alert_id, severity, message)."""
        monitor.register_token("fmt_token", expires_at=time.time() + 3600)
        alerts = monitor.get_alerts()
        a = alerts[0]
        # AlertNotifier.notify_alerts 需要的字段
        assert "alert_id" in a
        assert "severity" in a
        assert "message" in a
        assert a["severity"] in ("critical", "warning", "info")


# ── 5. 从环境变量自动检查 ─────────────────────────────────────


class TestEnvAutoCheck:
    """从环境变量自动检查 Meta token."""

    def test_check_meta_token_from_env_with_token(self, monitor, mock_response_valid):
        """环境变量有 META_ACCESS_TOKEN 时自动检查."""
        with patch.dict("os.environ", {"META_ACCESS_TOKEN": "EAAG_env_token"}):
            with patch("requests.get", return_value=mock_response_valid):
                status = monitor.check_meta_token_from_env()
        assert status is not None
        assert status.is_valid is True

    def test_check_meta_token_from_env_without_token(self, monitor):
        """环境变量无 META_ACCESS_TOKEN 时返回 None."""
        with patch.dict("os.environ", {}, clear=True):
            status = monitor.check_meta_token_from_env()
        assert status is None

    def test_check_meta_token_from_env_with_app_credentials(self, monitor, mock_response_valid):
        """环境变量有 app_id + app_secret 时用 app access token."""
        env = {
            "META_ACCESS_TOKEN": "EAAG_env_token",
            "META_APP_ID": "123456",
            "META_APP_SECRET": "secret123",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch("requests.get", return_value=mock_response_valid) as mock_get:
                monitor.check_meta_token_from_env()
        params = mock_get.call_args.kwargs.get("params") or mock_get.call_args[1].get("params")
        assert params["access_token"] == "123456|secret123"


# ── 6. get_status 摘要 ────────────────────────────────────────


class TestGetStatus:
    """get_status 摘要测试."""

    def test_empty_status(self, monitor):
        """无 token 时状态为 healthy."""
        status = monitor.get_status()
        assert status["status"] == "healthy"
        assert status["total_tokens"] == 0
        assert status["expired_count"] == 0
        assert status["critical_count"] == 0
        assert status["warning_count"] == 0

    def test_critical_status_with_expired_token(self, monitor):
        """有过期 token 时状态为 critical."""
        monitor.register_token("expired", expires_at=time.time() - 3600)
        status = monitor.get_status()
        assert status["status"] == "critical"
        assert status["expired_count"] == 1
        assert status["critical_count"] == 1

    def test_degraded_status_with_warning_token(self, monitor):
        """有 warning token 时状态为 degraded."""
        monitor.register_token("warn", expires_at=time.time() + 86400 * 3)
        status = monitor.get_status()
        assert status["status"] == "degraded"
        assert status["warning_count"] == 1
        assert status["critical_count"] == 0

    def test_status_includes_thresholds(self, monitor):
        """status 包含阈值配置."""
        status = monitor.get_status()
        assert "thresholds" in status
        assert status["thresholds"]["critical_seconds"] == 86400
        assert status["thresholds"]["warning_seconds"] == 604800

    def test_status_includes_tokens_list(self, monitor):
        """status 包含所有 token 的详细列表."""
        monitor.register_token("t1", expires_at=time.time() + 3600)
        monitor.register_token("t2", expires_at=0)
        status = monitor.get_status()
        assert len(status["tokens"]) == 2
        token_ids = {t["token_id"] for t in status["tokens"]}
        assert token_ids == {"t1", "t2"}


# ── 7. API 端点 ───────────────────────────────────────────────


class TestTokenMonitorAPI:
    """Token 监控 API 端点测试."""

    @pytest.fixture
    def client(self):
        from market_ops.workspace.app import app
        return TestClient(app)

    def test_token_status_endpoint(self, client):
        """token 状态查询端点."""
        response = client.get("/api/token-monitor/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "total_tokens" in data
        assert "thresholds" in data

    def test_token_alerts_endpoint(self, client):
        """token 告警查询端点."""
        response = client.get("/api/token-monitor/alerts")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    def test_token_register_endpoint(self, client):
        """手动注册 token 端点."""
        response = client.post(
            "/api/token-monitor/register",
            json={
                "token_id": "api_test_token",
                "expires_at": time.time() + 86400 * 5,
                "token_type": "custom",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["token_id"] == "api_test_token"
        assert data["is_valid"] is True

    def test_token_unregister_endpoint(self, client):
        """移除 token 端点."""
        # 先注册
        client.post(
            "/api/token-monitor/register",
            json={
                "token_id": "to_remove",
                "expires_at": time.time() + 3600,
            },
        )
        # 移除
        response = client.delete("/api/token-monitor/tokens/to_remove")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_token_check_meta_endpoint(self, client):
        """触发 Meta token 检查端点 (无 token 时返回 skip)."""
        response = client.post("/api/token-monitor/check/meta")
        assert response.status_code == 200
        data = response.json()
        # 无 META_ACCESS_TOKEN 时应返回 skipped=True
        assert "skipped" in data or "status" in data


# ── 8. 单例模式 ───────────────────────────────────────────────


class TestSingleton:
    """单例模式测试."""

    def test_get_token_monitor_returns_singleton(self):
        """get_token_monitor 返回单例."""
        from market_ops.workspace.token_monitor import (
            get_token_monitor,
            reset_token_monitor,
        )
        reset_token_monitor()
        m1 = get_token_monitor(data_dir="/tmp/test_tm_singleton")
        m2 = get_token_monitor()  # 不传 data_dir 应返回同一实例
        assert m1 is m2
        reset_token_monitor()

    def test_reset_token_monitor(self):
        """reset 后应创建新实例."""
        from market_ops.workspace.token_monitor import (
            get_token_monitor,
            reset_token_monitor,
        )
        reset_token_monitor()
        m1 = get_token_monitor(data_dir="/tmp/test_tm_reset1")
        reset_token_monitor()
        m2 = get_token_monitor(data_dir="/tmp/test_tm_reset2")
        assert m1 is not m2
        reset_token_monitor()
