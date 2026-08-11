"""E17.13 Offline Diagnostic — offline/connected 状态诊断测试.

验证 ControlPlane 的离线模式检测和诊断报告功能:
  - 无环境变量时 offline_mode=True
  - 离线时 publish 能力为 blocked
  - diagnostic_report() 返回完整结构
  - 缺失凭据列表
  - 有凭据时 connected 模式
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from market_ops.product.control_plane import ControlPlane, SystemSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _make_control_plane(tmp_path: Path, env_vars: dict[str, str] | None = None):
    """Create a ControlPlane with a valid temp root and env patched for the full test scope."""
    src_dir = tmp_path / "src" / "market_ops"
    src_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "active").mkdir(parents=True, exist_ok=True)

    with patch.dict(os.environ, env_vars or {}, clear=True):
        yield ControlPlane(tmp_path)


# ---------------------------------------------------------------------------
# test_offline_mode_detected_without_env
# ---------------------------------------------------------------------------

def test_offline_mode_detected_without_env(tmp_path: Path) -> None:
    """无环境变量时 _offline_mode() 返回 True."""
    with patch.dict(os.environ, {}, clear=True):
        cp = ControlPlane(tmp_path)
        assert cp._offline_mode() is True


# ---------------------------------------------------------------------------
# test_offline_mode_false_with_single_credential
# ---------------------------------------------------------------------------

def test_offline_mode_false_with_single_credential(tmp_path: Path) -> None:
    """至少有一个凭据时 _offline_mode() 返回 False."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
        cp = ControlPlane(tmp_path)
        assert cp._offline_mode() is False


# ---------------------------------------------------------------------------
# test_offline_mode_blocks_publish_capability
# ---------------------------------------------------------------------------

def test_offline_mode_blocks_publish_capability(tmp_path: Path) -> None:
    """离线时 snapshot 中 publish 能力为 not_configured."""
    with _make_control_plane(tmp_path, {}) as cp:
        snapshot = cp.snapshot()
        assert snapshot.offline_mode is True
        assert snapshot.capabilities["publish"] == "not_configured"


# ---------------------------------------------------------------------------
# test_connected_mode_with_meta_token(tmp_path)
# ---------------------------------------------------------------------------

def test_connected_mode_with_meta_token(tmp_path: Path) -> None:
    """有 META_ACCESS_TOKEN 时 publish 能力为 configured."""
    with _make_control_plane(tmp_path, {"META_ACCESS_TOKEN": "test-token"}) as cp:
        snapshot = cp.snapshot()
        assert snapshot.offline_mode is False
        assert snapshot.capabilities["publish"] == "configured"


# ---------------------------------------------------------------------------
# test_diagnostic_report_structure
# ---------------------------------------------------------------------------

def test_diagnostic_report_structure(tmp_path: Path) -> None:
    """诊断报告包含 mode/offline_mode/missing_credentials/blocked_capabilities/recommendations."""
    with _make_control_plane(tmp_path, {}) as cp:
        report = cp.diagnostic_report()
        assert "mode" in report
        assert "offline_mode" in report
        assert "missing_credentials" in report
        assert "blocked_capabilities" in report
        assert "recommendations" in report
        assert isinstance(report["mode"], str)
        assert isinstance(report["offline_mode"], bool)
        assert isinstance(report["missing_credentials"], list)
        assert isinstance(report["blocked_capabilities"], list)
        assert isinstance(report["recommendations"], list)


# ---------------------------------------------------------------------------
# test_diagnostic_report_missing_credentials
# ---------------------------------------------------------------------------

def test_diagnostic_report_missing_credentials(tmp_path: Path) -> None:
    """无凭据时诊断报告列出所有缺失凭据."""
    with _make_control_plane(tmp_path, {}) as cp:
        report = cp.diagnostic_report()
        missing = report["missing_credentials"]
        expected = [
            "OPENAI_API_KEY",
            "LOVART_API_KEY",
            "META_ACCESS_TOKEN",
            "FEISHU_BOT_WEBHOOK",
            "FEISHU_MARKET_WEBHOOK",
            "GOOGLE_ADS_CLIENT_ID",
        ]
        for cred in expected:
            assert cred in missing, f"Expected {cred} in missing_credentials, got {missing}"


# ---------------------------------------------------------------------------
# test_diagnostic_report_partial_credentials
# ---------------------------------------------------------------------------

def test_diagnostic_report_partial_credentials(tmp_path: Path) -> None:
    """部分凭据存在时诊断报告只列出缺失的."""
    with _make_control_plane(tmp_path, {
        "OPENAI_API_KEY": "sk-test",
        "META_ACCESS_TOKEN": "token-test",
    }) as cp:
        report = cp.diagnostic_report()
        missing = report["missing_credentials"]
        assert "OPENAI_API_KEY" not in missing
        assert "META_ACCESS_TOKEN" not in missing
        assert "LOVART_API_KEY" in missing
        assert "FEISHU_BOT_WEBHOOK" in missing
        assert "GOOGLE_ADS_CLIENT_ID" in missing


# ---------------------------------------------------------------------------
# test_diagnostic_report_blocked_capabilities
# ---------------------------------------------------------------------------

def test_diagnostic_report_blocked_capabilities(tmp_path: Path) -> None:
    """诊断报告正确列出被阻止的能力."""
    with _make_control_plane(tmp_path, {}) as cp:
        report = cp.diagnostic_report()
        blocked = report["blocked_capabilities"]
        assert "creative generation" in blocked
        assert "ad publishing" in blocked
        assert "notifications" in blocked


# ---------------------------------------------------------------------------
# test_diagnostic_report_recommendations
# ---------------------------------------------------------------------------

def test_diagnostic_report_recommendations(tmp_path: Path) -> None:
    """诊断报告为每个缺失凭据提供建议."""
    with _make_control_plane(tmp_path, {}) as cp:
        report = cp.diagnostic_report()
        recommendations = report["recommendations"]
        assert len(recommendations) > 0
        assert any("OPENAI_API_KEY" in r for r in recommendations)
        assert any("META_ACCESS_TOKEN" in r for r in recommendations)


# ---------------------------------------------------------------------------
# test_snapshot_offline_mode_field
# ---------------------------------------------------------------------------

def test_snapshot_offline_mode_field(tmp_path: Path) -> None:
    """SystemSnapshot 包含 offline_mode 字段."""
    with _make_control_plane(tmp_path, {}) as cp:
        snapshot = cp.snapshot()
        assert hasattr(snapshot, "offline_mode")
        assert isinstance(snapshot.offline_mode, bool)

        d = snapshot.to_dict()
        assert "offline_mode" in d


# ---------------------------------------------------------------------------
# test_snapshot_mode_offline_when_no_credentials
# ---------------------------------------------------------------------------

def test_snapshot_mode_offline_when_no_credentials(tmp_path: Path) -> None:
    """无凭据时 snapshot.mode 为 'offline'."""
    with _make_control_plane(tmp_path, {}) as cp:
        snapshot = cp.snapshot()
        assert snapshot.mode == "offline"


# ---------------------------------------------------------------------------
# test_snapshot_mode_unconfigured_with_partial_credentials
# ---------------------------------------------------------------------------

def test_snapshot_mode_unconfigured_with_partial_credentials(tmp_path: Path) -> None:
    """有部分凭据但无 FEISHU_APP_ID/ADS_PERFORMANCE_CSV 时 mode 为 'unconfigured'."""
    with _make_control_plane(tmp_path, {"OPENAI_API_KEY": "sk-test"}) as cp:
        snapshot = cp.snapshot()
        assert snapshot.offline_mode is False
        assert snapshot.mode == "unconfigured"


# ---------------------------------------------------------------------------
# test_snapshot_mode_connected_with_feishu
# ---------------------------------------------------------------------------

def test_snapshot_mode_connected_with_feishu(tmp_path: Path) -> None:
    """有 FEISHU_APP_ID 但无 API 凭据时 mode 为 'offline'（_offline_mode 优先于 _mode）."""
    with _make_control_plane(tmp_path, {"FEISHU_APP_ID": "app-123"}) as cp:
        snapshot = cp.snapshot()
        # FEISHU_APP_ID 不在 _offline_mode 检查列表中，所以 offline_mode=True
        assert snapshot.offline_mode is True
        assert snapshot.mode == "offline"


# ---------------------------------------------------------------------------
# test_snapshot_mode_local_with_csv
# ---------------------------------------------------------------------------

def test_snapshot_mode_local_with_csv(tmp_path: Path) -> None:
    """有 ADS_PERFORMANCE_CSV 但无 API 凭据时 mode 为 'offline'（_offline_mode 优先于 _mode）."""
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("col1,col2\n1,2")
    with _make_control_plane(tmp_path, {"ADS_PERFORMANCE_CSV": str(csv_path)}) as cp:
        snapshot = cp.snapshot()
        # ADS_PERFORMANCE_CSV 不在 _offline_mode 检查列表中，所以 offline_mode=True
        assert snapshot.offline_mode is True
        assert snapshot.mode == "offline"


__all__ = [
    "test_offline_mode_detected_without_env",
    "test_offline_mode_false_with_single_credential",
    "test_offline_mode_blocks_publish_capability",
    "test_connected_mode_with_meta_token",
    "test_diagnostic_report_structure",
    "test_diagnostic_report_missing_credentials",
    "test_diagnostic_report_partial_credentials",
    "test_diagnostic_report_blocked_capabilities",
    "test_diagnostic_report_recommendations",
    "test_snapshot_offline_mode_field",
    "test_snapshot_mode_offline_when_no_credentials",
    "test_snapshot_mode_unconfigured_with_partial_credentials",
    "test_snapshot_mode_connected_with_feishu",
    "test_snapshot_mode_local_with_csv",
]