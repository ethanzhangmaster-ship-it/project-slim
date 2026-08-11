"""E10.2 Facebook Adapter Configuration.

Manages Facebook Graph API credentials and runtime settings.
All secrets come from environment variables — never hardcoded.

Usage:
    config = FacebookConfig.from_env()
    client = FacebookClient(config)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class FacebookConfig:
    """Facebook Ads adapter configuration.

    All sensitive fields (app_secret, access_token) are loaded
    from environment variables. Never store secrets in code.

    Args:
        app_id: Facebook App ID.
        app_secret: Facebook App Secret (from env).
        access_token: User or System User access token (from env).
        ad_account_id: Facebook Ad Account ID (e.g., 'act_123456').
        api_version: Graph API version. Default: 'v22.0'.
        timeout: HTTP request timeout in seconds.
        sandbox: If True, FacebookClient returns mock responses
                 without making real API calls. Default: True.
        max_retries: Max retry attempts for transient failures.
        retry_delay: Base delay between retries in seconds.
    """

    app_id: str = ""
    app_secret: str = ""
    access_token: str = ""
    ad_account_id: str = ""
    api_version: str = "v22.0"
    timeout: int = 30
    sandbox: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0

    # ── env var keys ────────────────────────────────────
    _ENV_APP_ID: str = field(default="FACEBOOK_APP_ID", repr=False)
    _ENV_APP_SECRET: str = field(default="FACEBOOK_APP_SECRET", repr=False)
    _ENV_ACCESS_TOKEN: str = field(default="FACEBOOK_ACCESS_TOKEN", repr=False)
    _ENV_AD_ACCOUNT_ID: str = field(default="FACEBOOK_AD_ACCOUNT_ID", repr=False)
    _ENV_API_VERSION: str = field(default="FACEBOOK_API_VERSION", repr=False)
    _ENV_SANDBOX: str = field(default="FACEBOOK_SANDBOX", repr=False)

    @classmethod
    def from_env(cls) -> FacebookConfig:
        """Create config from FACEBOOK_* environment variables.

        Reads:
          FACEBOOK_APP_ID
          FACEBOOK_APP_SECRET
          FACEBOOK_ACCESS_TOKEN
          FACEBOOK_AD_ACCOUNT_ID
          FACEBOOK_API_VERSION (optional, default v22.0)
          FACEBOOK_SANDBOX (optional, default 'true')

        Returns:
            FacebookConfig populated from environment.
        """
        return cls(
            app_id=os.getenv("FACEBOOK_APP_ID") or os.getenv("META_APP_ID", ""),
            app_secret=os.getenv("FACEBOOK_APP_SECRET", ""),
            access_token=os.getenv("FACEBOOK_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN", ""),
            ad_account_id=os.getenv("FACEBOOK_AD_ACCOUNT_ID") or os.getenv("META_AD_ACCOUNT_ID", ""),
            api_version=os.getenv("FACEBOOK_API_VERSION") or os.getenv("META_API_VERSION", "v22.0"),
            sandbox=os.getenv("FACEBOOK_SANDBOX", "true").lower() not in ("false", "0", "no"),
            timeout=int(os.getenv("FACEBOOK_TIMEOUT", "30")),
            max_retries=int(os.getenv("FACEBOOK_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("FACEBOOK_RETRY_DELAY", "1.0")),
        )

    @property
    def graph_url(self) -> str:
        """Base Graph API URL."""
        return f"https://graph.facebook.com/{self.api_version}"

    @property
    def is_configured(self) -> bool:
        """Check if minimum required credentials are present."""
        return bool(self.access_token and self.ad_account_id)

    def validate(self) -> list[str]:
        """Validate required configuration fields.

        Returns:
            List of missing field names (empty = valid).
        """
        missing: list[str] = []
        if not self.app_id:
            missing.append("app_id")
        if not self.access_token:
            missing.append("access_token")
        if not self.ad_account_id:
            missing.append("ad_account_id")
        return missing