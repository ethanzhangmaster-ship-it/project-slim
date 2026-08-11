from pathlib import Path

from market_ops.product.platform_write_readiness import facebook_write_readiness


def test_writes_are_blocked_by_default(tmp_path: Path, monkeypatch):
    for name in ("FACEBOOK_SANDBOX", "FACEBOOK_ACCESS_TOKEN", "FACEBOOK_AD_ACCOUNT_ID", "META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "MARKET_OPS_ALLOW_PLATFORM_WRITES"):
        monkeypatch.delenv(name, raising=False)
    result = facebook_write_readiness(tmp_path / "campaign_bindings.json")
    assert not result.ready
    assert "Meta access token is missing" in result.reasons


def test_meta_configuration_satisfies_credential_part_of_gate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "token")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "act_1")
    monkeypatch.setenv("FACEBOOK_SANDBOX", "true")
    result = facebook_write_readiness(tmp_path / "campaign_bindings.json")
    assert "Meta access token is missing" not in result.reasons
    assert "Meta ad account ID is missing" not in result.reasons


def test_empty_binding_file_never_satisfies_write_gate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "token")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "act_1")
    binding = tmp_path / "campaign_bindings.json"
    binding.write_text("[]", encoding="utf-8")
    result = facebook_write_readiness(binding)
    assert not result.ready
    assert any("binding file is invalid" in reason for reason in result.reasons)
