from market_ops.execution_runtime.adapters.facebook.facebook_config import FacebookConfig


def test_meta_environment_aliases_support_execution_config(monkeypatch):
    monkeypatch.delenv("FACEBOOK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("FACEBOOK_AD_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-token")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "act_123")
    monkeypatch.setenv("META_API_VERSION", "v22.0")
    config = FacebookConfig.from_env()
    assert config.access_token == "meta-token"
    assert config.ad_account_id == "act_123"
    assert config.api_version == "v22.0"
