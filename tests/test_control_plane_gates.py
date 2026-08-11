from pathlib import Path

from market_ops.product.control_plane import ControlPlane


def test_snapshot_exposes_platform_write_gate(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src" / "market_ops").mkdir(parents=True)
    monkeypatch.setenv("META_ACCESS_TOKEN", "token")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "act_1")
    payload = ControlPlane(tmp_path).snapshot().to_dict()
    assert payload["capabilities"]["publish"] == "approval_required"
    assert payload["metrics"]["platform_write"]["ready"] is False
    assert any(check["name"] == "Meta write gate" for check in payload["checks"])
