"""凭证健康检查工具单元测试.

测试覆盖:
  1. 数据模型 (CredentialCheck, CredentialHealthReport)
  2. 占位符检测与脱敏工具函数
  3. 各检查器 (E1-E3, E7, U1, O4, O2, GA, AI, DP)
  4. 报告构建逻辑 (canary_ready, production_ready, overall_status)
  5. 单例工厂
  6. API 端点
  7. CLI 入口
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# 确保项目根在 path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.market_ops.workspace.credential_health_checker import (
    CredentialCheck,
    CredentialHealthChecker,
    CredentialHealthReport,
    _is_placeholder,
    _mask,
    get_credential_health_checker,
    reset_credential_health_checker,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """FastAPI TestClient — 重置单例避免测试间污染."""
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "mock")
    reset_credential_health_checker()
    from src.market_ops.workspace.app import app
    yield TestClient(app)
    reset_credential_health_checker()


# ── 工具函数测试 ──────────────────────────────────────────────

class TestPlaceholderDetection:
    """占位符检测."""

    def test_empty_string(self):
        assert _is_placeholder("") is True
        assert _is_placeholder("   ") is True

    def test_your_prefix(self):
        assert _is_placeholder("your_api_key") is True
        assert _is_placeholder("YOUR_TOKEN_HERE") is True

    def test_placeholder_prefix(self):
        assert _is_placeholder("placeholder_value") is True

    def test_known_placeholders(self):
        assert _is_placeholder("changeme") is True
        assert _is_placeholder("xxx") is True
        assert _is_placeholder("your_api_key") is True

    def test_real_values(self):
        assert _is_placeholder("EAAB1234abcd") is False
        assert _is_placeholder("sk-proj-abc123") is False
        assert _is_placeholder("/path/to/service-account.json") is False


class TestMask:
    """脱敏函数."""

    def test_empty(self):
        assert _mask("") == ""

    def test_short_value(self):
        assert _mask("short") == "***"
        assert _mask("12345678") == "***"

    def test_long_value(self):
        result = _mask("EAAB1234567890xyz")
        assert result.startswith("EAA")
        assert result.endswith("xyz")
        assert "***" in result

    def test_no_full_exposure(self):
        result = _mask("secret-key-123456789")
        assert "secret-key-123456789" not in result
        assert "***" in result


# ── 数据模型测试 ──────────────────────────────────────────────

class TestCredentialCheck:
    """CredentialCheck 数据模型."""

    def test_to_dict_has_all_fields(self):
        check = CredentialCheck(
            check_id="E1",
            name="Test",
            category="P0",
            status="pass",
        )
        d = check.to_dict()
        assert d["check_id"] == "E1"
        assert d["status"] == "pass"
        assert d["category"] == "P0"
        assert "is_canary_blocker" in d

    def test_is_canary_blocker_true(self):
        check = CredentialCheck(
            check_id="E1", name="Test", category="P0", status="fail"
        )
        assert check.is_canary_blocker is True

    def test_is_canary_blocker_false_pass(self):
        check = CredentialCheck(
            check_id="E1", name="Test", category="P0", status="pass"
        )
        assert check.is_canary_blocker is False

    def test_is_canary_blocker_false_non_canary(self):
        check = CredentialCheck(
            check_id="O4", name="Test", category="P1", status="fail"
        )
        assert check.is_canary_blocker is False


class TestCredentialHealthReport:
    """CredentialHealthReport 数据模型."""

    def test_to_dict(self):
        report = CredentialHealthReport(
            overall_status="blocked",
            canary_ready=False,
            production_ready=False,
            timestamp="2026-01-01T00:00:00Z",
        )
        d = report.to_dict()
        assert d["overall_status"] == "blocked"
        assert d["canary_ready"] is False
        assert "checks" in d
        assert "summary" in d

    def test_to_json(self):
        report = CredentialHealthReport(
            overall_status="ready",
            canary_ready=True,
            production_ready=True,
            timestamp="2026-01-01",
        )
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["overall_status"] == "ready"


# ── 检查器测试 ────────────────────────────────────────────────

class TestMetaCredentialsCheck:
    """E1: Meta/Facebook 凭证检查."""

    def test_missing_all_credentials(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_meta_credentials()
        assert check.check_id == "E1"
        assert check.status == "fail"
        assert "MAX_REPORT_KEY" in check.missing_vars
        assert "META_ACCESS_TOKEN" in check.missing_vars

    def test_placeholder_values(self, tmp_path):
        env = {
            "MAX_REPORT_KEY": "your_max_key",
            "META_ACCESS_TOKEN": "changeme",
            "META_AD_ACCOUNT_ID": "act_123",
            "META_APP_ID": "123456",
            "META_APP_SECRET": "secret",
        }
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_meta_credentials()
        assert check.status == "fail"
        assert "MAX_REPORT_KEY" in check.placeholder_vars
        assert "META_ACCESS_TOKEN" in check.placeholder_vars

    def test_all_configured_no_real_time(self, tmp_path):
        env = {
            "MAX_REPORT_KEY": "real_max_key_12345",
            "META_ACCESS_TOKEN": "EAABrealtoken12345",
            "META_AD_ACCOUNT_ID": "act_123456789",
            "META_APP_ID": "987654321",
            "META_APP_SECRET": "realsecret12345",
        }
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_meta_credentials(include_real_time=False)
        assert check.status == "pass"
        assert check.real_time_ok is None
        # 验证脱敏
        assert "real_max_key_12345" not in check.masked_values.get("MAX_REPORT_KEY", "")
        assert "***" in check.masked_values.get("MAX_REPORT_KEY", "")

    def test_real_time_check_skipped_when_missing(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_meta_credentials(include_real_time=True)
        assert check.status == "fail"
        assert check.real_time_ok is None


class TestGooglePlayCheck:
    """E2: Google Play 服务账号检查."""

    def test_missing(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_google_play()
        assert check.check_id == "E2"
        assert check.status == "fail"
        assert "PLAY_SERVICE_ACCOUNT_JSON" in check.missing_vars

    def test_placeholder(self, tmp_path):
        env = {"PLAY_SERVICE_ACCOUNT_JSON": "your_service_account"}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_google_play()
        assert check.status == "fail"

    def test_file_not_found(self, tmp_path):
        env = {"PLAY_SERVICE_ACCOUNT_JSON": str(tmp_path / "nonexistent.json")}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_google_play()
        assert check.status == "fail"
        assert any("文件不存在" in m for m in check.missing_vars)

    def test_file_exists(self, tmp_path):
        sa_file = tmp_path / "service-account.json"
        sa_file.write_text('{"type": "service_account"}', encoding="utf-8")
        env = {"PLAY_SERVICE_ACCOUNT_JSON": str(sa_file)}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_google_play()
        assert check.status == "pass"
        assert check.file_checks[str(sa_file)] is True


class TestApproverCheck:
    """E3: 人工审批人检查."""

    def test_file_not_exists(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_approver()
        assert check.check_id == "E3"
        assert check.status == "fail"
        assert "approver.json 不存在" in check.message

    def test_file_missing_fields(self, tmp_path):
        approver_file = tmp_path / "credentials" / "approver.json"
        approver_file.parent.mkdir(parents=True, exist_ok=True)
        approver_file.write_text(
            json.dumps({"approver_name": "Alice"}), encoding="utf-8"
        )
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_approver()
        assert check.status == "fail"
        assert "approver_contact" in check.missing_vars

    def test_file_complete(self, tmp_path):
        approver_file = tmp_path / "credentials" / "approver.json"
        approver_file.parent.mkdir(parents=True, exist_ok=True)
        approver_file.write_text(
            json.dumps({
                "approver_name": "Alice Zhang",
                "approver_contact": "alice@example.com",
            }),
            encoding="utf-8",
        )
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_approver()
        assert check.status == "pass"
        assert "审批人已指定" in check.message

    def test_file_invalid_json(self, tmp_path):
        approver_file = tmp_path / "credentials" / "approver.json"
        approver_file.parent.mkdir(parents=True, exist_ok=True)
        approver_file.write_text("NOT JSON", encoding="utf-8")
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_approver()
        assert check.status == "fail"
        assert "解析失败" in check.message


class TestCredentialRotationCheck:
    """E7: 凭证轮转责任人检查."""

    def test_file_not_exists(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_credential_rotation()
        assert check.check_id == "E7"
        assert check.status == "fail"

    def test_complete(self, tmp_path):
        rot_file = tmp_path / "credentials" / "rotation_owner.json"
        rot_file.parent.mkdir(parents=True, exist_ok=True)
        rot_file.write_text(
            json.dumps({
                "rotation_owner": "Bob Li",
                "oncall_contact": "bob@example.com",
            }),
            encoding="utf-8",
        )
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_credential_rotation()
        assert check.status == "pass"


class TestClosedLoopCheck:
    """O4: 闭环投放配置检查."""

    def test_missing(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_closed_loop()
        assert check.check_id == "O4"
        assert check.status == "warning"

    def test_configured(self, tmp_path):
        env = {
            "CLOSED_LOOP_ADSET_ID": "12020789",
            "CLOSED_LOOP_PAGE_ID": "123456789",
        }
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_closed_loop()
        assert check.status == "pass"


class TestGoogleAdsCheck:
    """Google Ads 凭证组检查."""

    def test_all_missing(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_google_ads()
        assert check.status == "skip"

    def test_all_configured(self, tmp_path):
        env = {v: f"real_{v}_value" for v in [
            "GOOGLE_ADS_DEVELOPER_TOKEN",
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_CUSTOMER_ID",
        ]}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_google_ads()
        assert check.status == "pass"

    def test_partial_configured(self, tmp_path):
        env = {"GOOGLE_ADS_DEVELOPER_TOKEN": "real_token"}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_google_ads()
        assert check.status == "warning"


class TestAIProviderCheck:
    """AI Provider 凭证检查."""

    def test_mock_mode(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_ai_provider()
        assert check.status == "skip"
        assert "mock" in check.message

    def test_openai_configured(self, tmp_path):
        env = {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "sk-real-key-12345"}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_ai_provider()
        assert check.status == "pass"

    def test_openai_missing_key(self, tmp_path):
        env = {"AI_PROVIDER": "openai"}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_ai_provider()
        assert check.status == "warning"


class TestDataPlatformsCheck:
    """数据平台凭证检查."""

    def test_none_configured(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        check = checker._check_data_platforms()
        assert check.status == "skip"

    def test_thinkingdata_configured(self, tmp_path):
        env = {
            "THINKINGDATA_BASE_URL": "https://api.thinkingdata.com",
            "THINKINGDATA_TOKEN": "real_token_12345",
        }
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_data_platforms()
        assert check.status == "pass"
        assert "ThinkingData" in check.message

    def test_partial(self, tmp_path):
        env = {"THINKINGDATA_BASE_URL": "https://api.thinkingdata.com"}
        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        check = checker._check_data_platforms()
        assert check.status == "warning"


# ── 报告构建测试 ──────────────────────────────────────────────

class TestReportBuilding:
    """报告构建逻辑."""

    def test_blocked_when_p0_fail(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        report = checker.check_all()
        assert report.overall_status == "blocked"
        assert report.canary_ready is False
        assert "E1" in report.canary_blockers
        assert "E2" in report.canary_blockers
        assert "E3" in report.canary_blockers

    def test_canary_ready_when_e1_e2_e3_pass(self, tmp_path):
        # 准备 E1
        env = {
            "MAX_REPORT_KEY": "real_max_key",
            "META_ACCESS_TOKEN": "EAABrealtoken",
            "META_AD_ACCOUNT_ID": "act_123",
        }
        # 准备 E2
        sa_file = tmp_path / "sa.json"
        sa_file.write_text('{"type": "service_account"}', encoding="utf-8")
        env["PLAY_SERVICE_ACCOUNT_JSON"] = str(sa_file)
        # 准备 E3
        approver_file = tmp_path / "credentials" / "approver.json"
        approver_file.parent.mkdir(parents=True, exist_ok=True)
        approver_file.write_text(
            json.dumps({"approver_name": "Alice", "approver_contact": "alice@example.com"}),
            encoding="utf-8",
        )
        # 准备 E7
        rot_file = tmp_path / "credentials" / "rotation_owner.json"
        rot_file.write_text(
            json.dumps({"rotation_owner": "Bob", "oncall_contact": "bob@example.com"}),
            encoding="utf-8",
        )

        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        report = checker.check_all()
        assert report.canary_ready is True
        assert report.canary_blockers == []
        assert "E1" not in report.canary_blockers
        assert "E2" not in report.canary_blockers
        assert "E3" not in report.canary_blockers

    def test_production_ready_when_all_p0_pass(self, tmp_path):
        env = {
            "MAX_REPORT_KEY": "real_max_key",
            "META_ACCESS_TOKEN": "EAABrealtoken",
            "META_AD_ACCOUNT_ID": "act_123",
        }
        sa_file = tmp_path / "sa.json"
        sa_file.write_text('{"type": "service_account"}', encoding="utf-8")
        env["PLAY_SERVICE_ACCOUNT_JSON"] = str(sa_file)

        approver_file = tmp_path / "credentials" / "approver.json"
        approver_file.parent.mkdir(parents=True, exist_ok=True)
        approver_file.write_text(
            json.dumps({"approver_name": "Alice", "approver_contact": "alice@example.com"}),
            encoding="utf-8",
        )
        rot_file = tmp_path / "credentials" / "rotation_owner.json"
        rot_file.write_text(
            json.dumps({"rotation_owner": "Bob", "oncall_contact": "bob@example.com"}),
            encoding="utf-8",
        )

        checker = CredentialHealthChecker(project_root=tmp_path, environ=env)
        report = checker.check_all()
        assert report.production_ready is True
        assert report.overall_status in ("ready", "degraded")  # P1 可能有 warning

    def test_summary_counts(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        report = checker.check_all()
        total = sum(report.summary.values())
        assert total == len(report.checks)
        assert report.summary["fail"] >= 3  # E1, E2, E3 at minimum

    def test_recommendations_present_when_fail(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        report = checker.check_all()
        assert len(report.recommendations) > 0

    def test_canary_prerequisites_method(self, tmp_path):
        checker = CredentialHealthChecker(project_root=tmp_path, environ={})
        report = checker.check_canary_prerequisites()
        assert len(report.checks) == 3  # E1, E2, E3
        assert all(c.check_id in {"E1", "E2", "E3"} for c in report.checks)


# ── 单例测试 ──────────────────────────────────────────────────

class TestSingleton:
    """单例工厂测试."""

    def test_get_singleton(self):
        reset_credential_health_checker()
        c1 = get_credential_health_checker()
        c2 = get_credential_health_checker()
        assert c1 is c2

    def test_reset(self):
        reset_credential_health_checker()
        c1 = get_credential_health_checker()
        reset_credential_health_checker()
        c2 = get_credential_health_checker()
        assert c1 is not c2

    def test_custom_environ_creates_new(self):
        reset_credential_health_checker()
        c1 = get_credential_health_checker()
        c2 = get_credential_health_checker(environ={"CUSTOM": "env"})
        assert c1 is not c2


# ── API 端点测试 ──────────────────────────────────────────────

class TestAPIEndpoints:
    """API 端点测试."""

    def test_health_summary_endpoint(self, client):
        resp = client.get("/api/credentials/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "canary_ready" in data
        assert "checks" in data
        assert "summary" in data

    def test_health_detail_endpoint(self, client):
        resp = client.get("/api/credentials/health/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        assert len(data["checks"]) > 0

    def test_canary_check_endpoint(self, client):
        resp = client.get("/api/credentials/canary-check")
        assert resp.status_code == 200
        data = resp.json()
        assert "canary_ready" in data
        assert "canary_blockers" in data
        check_ids = [c["check_id"] for c in data["checks"]]
        assert "E1" in check_ids
        assert "E2" in check_ids
        assert "E3" in check_ids

    def test_real_time_check_endpoint(self, client):
        resp = client.post("/api/credentials/real-time-check")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "checks" in data


# ── CLI 入口测试 ──────────────────────────────────────────────

class TestCLI:
    """CLI 入口测试."""

    def test_cli_json_output(self, tmp_path, monkeypatch):
        """测试 CLI JSON 输出模式."""
        monkeypatch.setenv("MAX_REPORT_KEY", "")
        monkeypatch.setenv("META_ACCESS_TOKEN", "")
        monkeypatch.setenv("PLAY_SERVICE_ACCOUNT_JSON", "")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["check_credentials.py", "--json"])

        from scripts.check_credentials import main
        exit_code = main()
        # 环境变量未配置, 应返回 2 (blocked)
        assert exit_code == 2

    def test_cli_no_crash(self, monkeypatch, tmp_path):
        """CLI 不应崩溃."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["check_credentials.py", "--json"])
        from scripts.check_credentials import main
        # 只要不抛异常就行
        try:
            main()
        except SystemExit as e:
            assert e.code in (0, 1, 2)
