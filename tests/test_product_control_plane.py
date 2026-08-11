from pathlib import Path

import pytest

from market_ops.product.control_plane import ControlPlane


def test_snapshot_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "src" / "market_ops").mkdir(parents=True)
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("ADS_PERFORMANCE_CSV", raising=False)
    payload = ControlPlane(tmp_path).snapshot().to_dict()
    assert payload["version"] == "1.0.0"
    assert payload["mode"] == "unconfigured"
    assert {"observe", "recommend", "generate", "publish", "notify"} <= payload["capabilities"].keys()


def test_snapshot_persistence(tmp_path: Path) -> None:
    (tmp_path / "src" / "market_ops").mkdir(parents=True)
    assert ControlPlane(tmp_path).write_snapshot().exists()


def test_safe_command_allowlist(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported safe command"):
        ControlPlane(tmp_path).run_safe_command("publish")
