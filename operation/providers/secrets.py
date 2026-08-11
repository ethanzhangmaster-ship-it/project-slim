"""
E15.2.3 — Credential / Secrets Manager

Env-based credential loading. Production should use AWS Secrets Manager or similar.
Never hardcode API keys in source code.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional


class SecretsManager:
    """Read credentials from environment variables.

    Keys:
        MAX_API_KEY, MAX_ACCOUNT_ID
        ADMOB_CLIENT_ID, ADMOB_CLIENT_SECRET
        ADJUST_APP_TOKEN
        APPSTORE_KEY_ID, APPSTORE_ISSUER_ID, APPSTORE_PRIVATE_KEY
        GOOGLE_PLAY_SERVICE_ACCOUNT
    """

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(key, default)

    @staticmethod
    def get_max_credentials() -> Dict[str, str]:
        return {
            "api_key": os.environ.get("MAX_API_KEY", ""),
            "account_id": os.environ.get("MAX_ACCOUNT_ID", ""),
        }

    @staticmethod
    def get_adjust_credentials() -> Dict[str, str]:
        return {"app_token": os.environ.get("ADJUST_APP_TOKEN", "")}

    @staticmethod
    def get_appstore_credentials() -> Dict[str, str]:
        return {
            "key_id": os.environ.get("APPSTORE_KEY_ID", ""),
            "issuer_id": os.environ.get("APPSTORE_ISSUER_ID", ""),
            "private_key": os.environ.get("APPSTORE_PRIVATE_KEY", ""),
        }

    @staticmethod
    def all_present(creds: Dict[str, str]) -> bool:
        """Check if all credential fields are non-empty."""
        return all(v for v in creds.values())


__all__ = ["SecretsManager"]
