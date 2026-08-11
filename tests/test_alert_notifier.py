"""AlertNotifier 单元测试 — 验证告警通知多渠道推送.

测试覆盖:
  1. 配置加载: 环境变量 > credentials 文件 > 默认值
  2. 幂等去重: 同一 alert_id 在时间窗口内只推送一次
  3. 降级模式: 无渠道配置时降级为日志记录
  4. 渠道实现: email/wecom/feishu (mock 网络层)
  5. 消息格式构建: 邮件主题/正文/HTML/企微 markdown/飞书 card
  6. 严重级别过滤: info 不推送, warning/critical 推送
  7. API 端点: /api/maintenance/alerts/notify + /channels
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── 公共 fixtures ──────────────────────────────────────────────


@pytest.fixture
def sample_alerts() -> list[dict]:
    """样例告警列表."""
    return [
        {
            "alert_id": "approval_backlog",
            "severity": "warning",
            "category": "approval",
            "message": "待审批积压 10 条",
            "current_value": 10,
            "threshold": 5,
            "suggestion": "及时处理 pending 审批",
        },
        {
            "alert_id": "disk_full",
            "severity": "critical",
            "category": "storage",
            "message": "磁盘使用率 95%",
            "current_value": 95,
            "threshold": 90,
            "suggestion": "清理日志或扩容",
        },
    ]


@pytest.fixture
def single_warning_alert() -> dict:
    return {
        "alert_id": "test_alert_001",
        "severity": "warning",
        "message": "测试告警",
        "current_value": 80,
        "threshold": 75,
    }


@pytest.fixture
def empty_config():
    from market_ops.workspace.alert_notifier import AlertNotifierConfig
    return AlertNotifierConfig()


@pytest.fixture
def email_config():
    from market_ops.workspace.alert_notifier import AlertNotifierConfig
    return AlertNotifierConfig(
        smtp_host="smtp.test.com",
        smtp_port=465,
        smtp_user="sender@test.com",
        smtp_password="pass",
        email_from="sender@test.com",
        email_to=["recv@test.com"],
    )


@pytest.fixture
def wecom_config():
    from market_ops.workspace.alert_notifier import AlertNotifierConfig
    return AlertNotifierConfig(wecom_webhook="https://qyapi.weixin.qq.com/test")


@pytest.fixture
def feishu_config():
    from market_ops.workspace.alert_notifier import AlertNotifierConfig
    return AlertNotifierConfig(feishu_webhook="https://open.feishu.cn/test")


# ── 1. 配置加载 ────────────────────────────────────────────────


class TestConfigLoad:
    """配置加载测试."""

    def test_default_config_has_nothing(self, empty_config):
        """默认配置无任何渠道."""
        assert empty_config.has_email_config() is False
        assert empty_config.has_wecom_config() is False
        assert empty_config.has_feishu_config() is False

    def test_email_config_detected(self, email_config):
        """邮件配置被正确识别."""
        assert email_config.has_email_config() is True

    def test_wecom_config_detected(self, wecom_config):
        assert wecom_config.has_wecom_config() is True

    def test_feishu_config_detected(self, feishu_config):
        assert feishu_config.has_feishu_config() is True

    def test_load_from_credentials_file(self, tmp_path: Path):
        """从 credentials/notify.json 加载配置."""
        from market_ops.workspace.alert_notifier import load_notifier_config

        creds_dir = tmp_path / "credentials"
        creds_dir.mkdir()
        notify_file = creds_dir / "notify.json"
        notify_file.write_text(json.dumps({
            "smtp_host": "smtp.file.com",
            "smtp_user": "user@file.com",
            "smtp_password": "secret",
            "email_to": "a@x.com,b@x.com",
            "wecom_webhook": "https://wecom.file",
            "feishu_alert_webhook": "https://feishu.file",
        }), encoding="utf-8")

        cfg = load_notifier_config(project_root=str(tmp_path))

        assert cfg.smtp_host == "smtp.file.com"
        assert cfg.smtp_user == "user@file.com"
        assert cfg.email_to == ["a@x.com", "b@x.com"]
        assert cfg.wecom_webhook == "https://wecom.file"
        assert cfg.feishu_webhook == "https://feishu.file"
        assert cfg.has_email_config() is True
        assert cfg.has_wecom_config() is True
        assert cfg.has_feishu_config() is True

    def test_env_var_overrides_file(self, tmp_path: Path, monkeypatch):
        """环境变量优先于 credentials 文件."""
        from market_ops.workspace.alert_notifier import load_notifier_config

        creds_dir = tmp_path / "credentials"
        creds_dir.mkdir()
        (creds_dir / "notify.json").write_text(json.dumps({
            "smtp_host": "from-file.com",
        }), encoding="utf-8")

        monkeypatch.setenv("SMTP_HOST", "from-env.com")
        cfg = load_notifier_config(project_root=str(tmp_path))
        assert cfg.smtp_host == "from-env.com"

    def test_missing_credentials_file_uses_defaults(self, tmp_path: Path):
        """credentials 文件不存在时用默认值."""
        from market_ops.workspace.alert_notifier import load_notifier_config
        cfg = load_notifier_config(project_root=str(tmp_path))
        assert cfg.smtp_host == ""
        assert cfg.smtp_port == 465


# ── 2. 幂等去重 ────────────────────────────────────────────────


class TestDeduplication:
    """幂等去重测试."""

    def test_first_push_not_duplicated(self, empty_config, single_warning_alert):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        assert notifier._is_duplicate("alert_1") is False

    def test_second_push_within_window_deduplicated(self, empty_config):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        notifier._is_duplicate("alert_1")  # 第一次
        assert notifier._is_duplicate("alert_1") is True  # 第二次

    def test_different_alert_ids_not_deduplicated(self, empty_config):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        notifier._is_duplicate("alert_1")
        assert notifier._is_duplicate("alert_2") is False

    def test_expired_entries_cleaned_up(self, empty_config):
        """过期的去重条目被清理."""
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        # 手动写入过期条目
        notifier._dedup_cache["old_alert"] = time.time() - 1000
        # 触发一次去重检查 (会清理过期)
        notifier._is_duplicate("new_alert")
        assert "old_alert" not in notifier._dedup_cache

    def test_empty_alert_id_not_deduplicated(self, empty_config):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        assert notifier._is_duplicate("") is False


# ── 3. 降级模式 ────────────────────────────────────────────────


class TestDegradedMode:
    """无渠道配置时的降级模式."""

    def test_no_alerts_returns_empty(self, empty_config):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        results = notifier.notify_alerts([])
        assert len(results) == 1
        assert results[0].channel == "log"
        assert results[0].success is True

    def test_no_channel_configured_degrades_to_log(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        results = notifier.notify_alerts(sample_alerts)
        assert len(results) == 1
        assert results[0].channel == "log"
        assert results[0].success is True
        assert results[0].sent == 2

    def test_all_deduplicated_skips_push(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        # 第一次推送 (降级到 log)
        notifier.notify_alerts(sample_alerts)
        # 第二次推送 (全部去重)
        results = notifier.notify_alerts(sample_alerts)
        assert results[0].channel == "log"
        assert "deduplicated" in results[0].error


# ── 4. 严重级别过滤 ────────────────────────────────────────────


class TestSeverityFilter:
    """严重级别过滤测试."""

    def test_info_alerts_not_pushed(self, empty_config):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        info_alert = {"alert_id": "info_1", "severity": "info", "message": "info"}
        results = notifier.notify_alerts([info_alert])
        # info 被过滤, 无可推送 → 返回 log + no alerts
        assert results[0].sent == 0 or "no alerts" in results[0].error or "deduplicated" in results[0].error

    def test_warning_and_critical_pushed(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        results = notifier.notify_alerts(sample_alerts)
        # 降级模式, sent 应为 2 (warning + critical)
        assert results[0].sent == 2


# ── 5. 渠道实现 (mock 网络) ─────────────────────────────────────


class TestEmailChannel:
    """邮件渠道测试."""

    @patch("market_ops.workspace.alert_notifier.smtplib.SMTP_SSL")
    def test_email_sent_successfully(self, mock_smtp, email_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=email_config)
        results = notifier.notify_alerts(sample_alerts)

        email_result = [r for r in results if r.channel == "email"]
        assert len(email_result) == 1
        assert email_result[0].success is True
        assert email_result[0].sent == 2
        mock_smtp.assert_called_once()

    def test_email_not_configured_returns_error(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        # 强制走 email 渠道但无配置
        notifier = AlertNotifier(config=empty_config)
        results = notifier.notify_alerts(sample_alerts, channels=["email"])
        assert results[0].channel == "email"
        assert results[0].success is False
        assert "not configured" in results[0].error


class TestWecomChannel:
    """企业微信渠道测试."""

    @patch("market_ops.workspace.alert_notifier.urllib.request.urlopen")
    def test_wecom_sent_successfully(self, mock_urlopen, wecom_config, sample_alerts):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"errcode":0}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=wecom_config)
        results = notifier.notify_alerts(sample_alerts)

        wecom_result = [r for r in results if r.channel == "wecom"]
        assert len(wecom_result) == 1
        assert wecom_result[0].success is True
        assert wecom_result[0].sent == 2
        mock_urlopen.assert_called_once()

    @patch("market_ops.workspace.alert_notifier.urllib.request.urlopen")
    def test_wecom_network_error_handled(self, mock_urlopen, wecom_config, sample_alerts):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("network error")

        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=wecom_config)
        results = notifier.notify_alerts(sample_alerts)

        wecom_result = [r for r in results if r.channel == "wecom"]
        assert len(wecom_result) == 1
        assert wecom_result[0].success is False
        assert "network error" in wecom_result[0].error


class TestFeishuChannel:
    """飞书渠道测试."""

    @patch("market_ops.workspace.alert_notifier.urllib.request.urlopen")
    def test_feishu_sent_successfully(self, mock_urlopen, feishu_config, sample_alerts):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"code":0}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=feishu_config)
        results = notifier.notify_alerts(sample_alerts)

        feishu_result = [r for r in results if r.channel == "feishu"]
        assert len(feishu_result) == 1
        assert feishu_result[0].success is True
        assert feishu_result[0].sent == 2

    def test_feishu_not_configured_returns_error(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        results = notifier.notify_alerts(sample_alerts, channels=["feishu"])
        assert results[0].success is False
        assert "not configured" in results[0].error


class TestMultiChannel:
    """多渠道同时推送."""

    def test_multiple_channels_all_pushed(self, sample_alerts):
        from market_ops.workspace.alert_notifier import (
            AlertNotifier, AlertNotifierConfig,
        )
        cfg = AlertNotifierConfig(
            smtp_host="smtp.test.com",
            smtp_user="u@t.com",
            smtp_password="p",
            email_to=["r@t.com"],
            wecom_webhook="https://wecom.test",
            feishu_webhook="https://feishu.test",
        )
        notifier = AlertNotifier(config=cfg)

        with patch("market_ops.workspace.alert_notifier.smtplib.SMTP_SSL"), \
             patch("market_ops.workspace.alert_notifier.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{}'
            mock_url.return_value.__enter__.return_value = mock_resp

            results = notifier.notify_alerts(sample_alerts)

        channels_pushed = {r.channel for r in results if r.channel != "log"}
        assert "email" in channels_pushed
        assert "wecom" in channels_pushed
        assert "feishu" in channels_pushed


# ── 6. 消息格式构建 ────────────────────────────────────────────


class TestMessageFormat:
    """消息格式构建测试."""

    def test_email_subject_includes_severity(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        subject = notifier._build_email_subject(sample_alerts)
        assert "CRITICAL" in subject  # 有 critical 告警

    def test_email_text_body_has_content(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        body = notifier._build_email_text(sample_alerts)
        assert "approval_backlog" in body
        assert "disk_full" in body

    def test_email_html_has_table(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        html = notifier._build_email_html(sample_alerts)
        assert "<table" in html
        assert "approval_backlog" in html

    def test_wecom_markdown_has_alerts(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import AlertNotifier
        notifier = AlertNotifier(config=empty_config)
        md = notifier._build_wecom_markdown(sample_alerts)
        assert "AI Studio" in md
        assert "approval_backlog" in md

    def test_feishu_card_structure(self, empty_config, sample_alerts):
        from market_ops.workspace.alert_notifier import (
            AlertNotifier, AlertNotifierConfig,
        )
        notifier = AlertNotifier(config=empty_config)
        # _send_feishu 内部构建 card, 这里间接验证 payload 构建
        # 通过 mock urlopen 捕获 payload
        with patch("market_ops.workspace.alert_notifier.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{}'
            mock_url.return_value.__enter__.return_value = mock_resp

            feishu_cfg = AlertNotifierConfig(feishu_webhook="https://test")
            notifier2 = AlertNotifier(config=feishu_cfg)
            notifier2.notify_alerts(sample_alerts, channels=["feishu"])

            # 验证 urlopen 被调用
            assert mock_url.called
            # 检查 payload
            call_args = mock_url.call_args
            req = call_args[0][0]
            payload = json.loads(req.data.decode("utf-8"))
            assert payload["msg_type"] == "interactive"
            assert "card" in payload
            assert "elements" in payload["card"]


# ── 7. API 端点 ────────────────────────────────────────────────


class TestAlertNotifyAPI:
    """告警通知 API 端点测试."""

    @pytest.fixture
    def client(self):
        from market_ops.workspace.app import app
        return TestClient(app)

    def test_notify_endpoint_no_alerts(self, client):
        """无告警时返回成功."""
        response = client.post("/api/maintenance/alerts/notify")
        assert response.status_code == 200
        data = response.json()
        assert "alerts_total" in data
        assert "results" in data

    def test_channels_endpoint(self, client):
        """渠道状态端点返回配置信息."""
        response = client.get("/api/maintenance/alerts/channels")
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "wecom" in data
        assert "feishu" in data
        assert "active_channels" in data
        assert "dedup_window_seconds" in data

    def test_channels_endpoint_hides_credentials(self, client):
        """渠道状态不暴露凭证值."""
        response = client.get("/api/maintenance/alerts/channels")
        data = response.json()
        # 不应包含 password/webhook 实际值
        text = json.dumps(data)
        assert "password" not in text.lower()
        assert "secret" not in text.lower()


# ── 8. 单例管理 ────────────────────────────────────────────────


class TestSingleton:
    """单例管理测试."""

    def test_get_alert_notifier_returns_singleton(self):
        from market_ops.workspace.alert_notifier import (
            get_alert_notifier, reset_alert_notifier,
        )
        reset_alert_notifier()
        n1 = get_alert_notifier()
        n2 = get_alert_notifier()
        assert n1 is n2

    def test_reset_alert_notifier_creates_new(self):
        from market_ops.workspace.alert_notifier import (
            get_alert_notifier, reset_alert_notifier,
        )
        reset_alert_notifier()
        n1 = get_alert_notifier()
        reset_alert_notifier()
        n2 = get_alert_notifier()
        assert n1 is not n2
